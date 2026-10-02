# -*- coding: utf-8 -*-
"""LoRA 推理：加载基座 + LoRA 权重，生成留学建议
供应用层「文书生成 / 规划 Agent」直接调用：from finetune.inference import generate_essay
"""
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from .config import PRETRAINED_DIR, MODEL_OUT

# bitsandbytes 必须真实可 import 才能走 4-bit；
# 注意：BitsAndBytesConfig() 构造时不会报错，直到 from_pretrained 才炸，
# 所以这里必须显式 import bitsandbytes 来判断，不能靠 try 包住构造。
try:
    import bitsandbytes  # noqa: F401

    HAS_BNB = True
except Exception:
    HAS_BNB = False


def _try_4bit_config():
    """bitsandbytes 可用才给 4-bit 配置；否则返回 None（调用方退化为 bf16）"""
    if not HAS_BNB:
        return None
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )


def load_tuned_model(use_4bit=None):
    """加载 基座 + LoRA adapter 权重

    加载策略自动兜底：
    - 默认：能用 4-bit 就用（本地 1650 4GB 显存小，需压到 ~4GB）
    - 环境无 bitsandbytes / 24GB 大显存卡：退化为 bf16（3090 直接塞得下，画质更好更快）
    - 用环境变量 USE_4BIT=0 可强制走 bf16，USE_4BIT=1 强制走 4-bit
    """
    if use_4bit is None:
        use_4bit = os.getenv("USE_4BIT", "1") == "1"

    tok = AutoTokenizer.from_pretrained(str(PRETRAINED_DIR), trust_remote_code=True)

    kwargs = {"trust_remote_code": True}
    if use_4bit:
        quant = _try_4bit_config()
        if quant is not None:
            kwargs["quantization_config"] = quant
        else:
            print("[inference] 未检测到 bitsandbytes，自动退化为 bf16 加载")
            use_4bit = False

    if not use_4bit:
        # 24GB 卡（3090/4090）走 bf16；小显卡仍建议自行装 bitsandbytes 走 4-bit
        kwargs["torch_dtype"] = torch.bfloat16
        kwargs["device_map"] = "auto"

    base = AutoModelForCausalLM.from_pretrained(str(PRETRAINED_DIR), **kwargs)
    model = PeftModel.from_pretrained(base, str(MODEL_OUT / "lora"))
    return model, tok


def generate(model, tok, instruction, input_text="", max_new=1024):
    """单条生成（Qwen Chat 模板）"""
    prompt = (
        "<|im_start|>system\n你是一名留学申请规划顾问。<|im_end|>\n"
        f"<|im_start|>user\n{instruction}\n{input_text}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    ids = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(**ids, max_new_tokens=max_new, do_sample=False, temperature=1.0)
    return tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)


def generate_essay(prompt, max_new_tokens=1024):
    """应用层 Agent 调用入口"""
    model, tok = load_tuned_model()
    return generate(model, tok, prompt, max_new=max_new_tokens)
