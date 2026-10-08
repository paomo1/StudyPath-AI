# -*- coding: utf-8 -*-
"""
A/B 对照：同一条 prompt 分别用「纯基座」和「基座 + LoRA」生成，对比输出差异。

PEFT 的 LoRA 注入是原地修改的：若在循环里反复调用 PeftModel.from_pretrained，
后续轮次的基座也会带上 adapter，A/B 对比必然相同。所以这里只套一次 PeftModel，
A 组用 disable_adapter() 上下文取得，保证唯一变量是 adapter 是否启用。

云端先下基座再跑本脚本：
    python -m finetune.download
    python -m finetune.ab_compare
产物 data/processed/ab_compare.json。
"""
import json
import sys
import time
from pathlib import Path

# torch 只在真正要跑 GPU 推理的机器上才装（如 AutoDL 3090）
# 这里模块级导入做兜底：本机没 torch 也能被 import，不会一 import 就炸。
try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

from .config import PRETRAINED_DIR, MODEL_OUT, DATA_PROCESSED

# 三条 prompt 分别覆盖选校策略师 / 录取风险评估师 / 文书规划师三个业务场景。
# 基座只加载一次，多跑 6 次生成，增量耗时约 2-3 分钟。
SYS = "你是一名留学申请规划顾问。"

PROMPTS = [
    {
        "name": "文书规划-SOP开头",
        "prompt": (
            "你是一名留学文书顾问，请为申请纽约大学 MS Data Science 的学生"
            "写一段 SOP 开头，不超过150字。"
        ),
    },
    {
        "name": "选校策略-选校梯度",
        "prompt": (
            "学生本科 GPA 3.6，雅思 6.5，专业背景一般，无发表论文。"
            "请给出申请英国硕士的选校梯度建议，分冲刺/主申/保底三档。"
        ),
    },
    {
        "name": "风险评估-录取概率",
        "prompt": (
            "学生想冲纽约大学 MS Data Science，本科双非，GPA 3.2，"
            "两段实习。请客观评估这个申请的录取风险，并给出两项最该补强的点。"
        ),
    },
]
TEMPLATE = (
    "<|im_start|>system\n{sys}<|im_end|>\n"
    "<|im_start|>user\n{prompt}<|im_end|>\n"
    "<|im_start|>assistant\n"
)


def is_lora_ready() -> bool:
    """基座与 LoRA 权重都齐全，才算具备本地微调推理条件"""
    adapter = MODEL_OUT / "lora" / "adapter_model.safetensors"
    return PRETRAINED_DIR.exists() and adapter.exists()


def build_inputs(tok, prompt: str, device=None):
    """按 Qwen 的 ChatML 拼 prompt（与训练时格式保持一致）"""
    text = TEMPLATE.format(sys=SYS, prompt=prompt)
    ids = tok(text, return_tensors="pt")
    return ids.to(device) if device is not None else ids


def generate(model, tok, prompt: str, max_new_tokens: int = 256):
    ids = build_inputs(tok, prompt, device=model.device)
    with torch.no_grad():
        t0 = time.time()
        out = model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
        dt = time.time() - t0
    text = tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
    return text.strip(), round(dt, 2)


def main():
    if not is_lora_ready():
        print("[ab_compare] 基座或 LoRA 权重缺失，先跑：python -m finetune.download")
        sys.exit(1)

    if torch is None:
        print("[ab_compare] 本机未安装 torch，请在 AutoDL 环境执行：pip install torch")
        sys.exit(1)

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    adapter = str(MODEL_OUT / "lora")

    print(f"[ab_compare] 基座: {PRETRAINED_DIR}")
    print(f"[ab_compare] LoRA: {adapter}")
    tok = AutoTokenizer.from_pretrained(str(PRETRAINED_DIR), trust_remote_code=True)

    # 基座只加载一次（14GB，冷启动 1-3 分钟），三组 A/B 共用
    base = AutoModelForCausalLM.from_pretrained(
        str(PRETRAINED_DIR), torch_dtype=torch.bfloat16, device_map="cuda"
    )

    # 只套一次 PeftModel（原地注入，重复套会污染 base，见文件顶部说明）
    tuned = PeftModel.from_pretrained(base, adapter)
    tuned.eval()

    has_disable = hasattr(tuned, "disable_adapter")
    mode = "disable_adapter 上下文" if has_disable else "两阶段（先全 A 后全 B）"
    print(f"[ab_compare] A/B 切分方式: {mode}")

    items = []
    if has_disable:
        # 推荐路径：同一个模型对象，仅切换 adapter，变量最干净
        for p in PROMPTS:
            print(f"\n===== [{p['name']}] =====\nA 组（adapter 关闭）生成中...")
            with tuned.disable_adapter():
                a_text, a_time = generate(tuned, tok, p["prompt"])
            print("B 组（adapter 启用）生成中...")
            b_text, b_time = generate(tuned, tok, p["prompt"])
            items.append(
                {
                    "name": p["name"],
                    "prompt": p["prompt"],
                    "A_base_model": {"text": a_text, "latency_s": a_time},
                    "B_base_plus_lora": {"text": b_text, "latency_s": b_time},
                    "identical": a_text == b_text,
                }
            )
            print(f"[ab_compare] {p['name']} | A/B 是否相同: {items[-1]['identical']}")
    else:
        # 兜底路径：先把三组 A 全跑完（此时还没注入 LoRA），再一次性注入跑 B
        print("\n===== 阶段 A：纯基座（尚未注入 LoRA）=====")
        a_buf = []
        for p in PROMPTS:
            print(f"  [{p['name']}] 生成中...")
            a_buf.append(generate(base, tok, p["prompt"]))
        base.eval()
        tuned = PeftModel.from_pretrained(base, adapter)
        tuned.eval()
        print("===== 阶段 B：基座 + LoRA =====")
        for p, (a_text, a_time) in zip(PROMPTS, a_buf):
            print(f"  [{p['name']}] 生成中...")
            b_text, b_time = generate(tuned, tok, p["prompt"])
            items.append(
                {
                    "name": p["name"],
                    "prompt": p["prompt"],
                    "A_base_model": {"text": a_text, "latency_s": a_time},
                    "B_base_plus_lora": {"text": b_text, "latency_s": b_time},
                    "identical": a_text == b_text,
                }
            )
            print(f"[ab_compare] {p['name']} | A/B 是否相同: {items[-1]['identical']}")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "ab_compare.json"
    changed = [it["name"] for it in items if not it["identical"]]
    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_model": str(PRETRAINED_DIR),
        "lora_adapter": adapter,
        "method": {
            "decoding": "greedy (do_sample=False)",
            "control": mode,
            "description": (
                "同一个模型对象、同一份基座权重，A 组关闭 LoRA adapter、"
                "B 组启用 LoRA adapter，唯一变量为 adapter 是否生效"
            ),
        },
        "summary": {
            "n_prompts": len(items),
            "changed_count": len(changed),
            "all_changed": len(changed) == len(items),
            "changed_names": changed,
            "conclusion": (
                f"{len(changed)}/{len(items)} 组 prompt 在开启 LoRA 后输出发生变化"
                " => 微调权重真实生效"
                if changed
                else "⚠️ 三组输出全部相同，需检查 LoRA 是否挂载成功"
            ),
        },
        "items": items,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 56)
    for it in items:
        print(f"\n===== {it['name']} =====")
        print("----- A 基座（未微调）-----")
        print(it["A_base_model"]["text"])
        print(f"[耗时 {it['A_base_model']['latency_s']}s]")
        print("----- B 基座 + LoRA（微调后）-----")
        print(it["B_base_plus_lora"]["text"])
        print(f"[耗时 {it['B_base_plus_lora']['latency_s']}s]")
    print("\n" + "=" * 56)
    print(f"[ab_compare] {len(changed)}/{len(items)} 组输出发生变化: {changed}")
    print(f"[ab_compare] 已写入 -> {out_path}")


if __name__ == "__main__":
    main()
