# -*- coding: utf-8 -*-
"""LoRA 双轨评估：自动指标 + 人工评审说明
对应老师架构第 5 步「模型测试、评估」
"""
import json
from pathlib import Path
from .config import DATA_PROCESSED
from .inference import load_tuned_model, generate


def load_eval(n=None):
    rows = []
    with open(DATA_PROCESSED / "eval.jsonl", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows[:n] if n else rows


def lcs_length(a, b):
    """最长公共子序列长度（ROUGE-L 近似）"""
    a, b = a or "", b or ""
    if not a or not b:
        return 0
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    return dp[len(a)][len(b)]


def auto_eval(n=20, dump: bool = True):
    """跑自动指标，并把结果落盘成 eval_results.json

    ⚠️ 旧版只 print 到终端，机器一关就没了 —— 答辩要拿的两个数必须留档。
    """
    import time

    samples = load_eval(n)
    model, tok = load_tuned_model()
    follow = rouge = 0
    per_sample = []
    for i, s in enumerate(samples, 1):
        out = generate(model, tok, s["instruction"], s["input"], max_new=256)
        ok = bool(out.strip()) and len(out) > 20
        r = lcs_length(out, s["output"]) / max(len(out), len(s["output"]), 1)
        follow += int(ok)
        rouge += r
        per_sample.append(
            {
                "idx": i,
                "follow": ok,
                "rouge_l": round(r, 4),
                # 留档：生成文本 + 参考文本（截断 300 字），避免终端一滚证据就没了
                "generated": out.strip()[:300],
                "reference": (s["output"] or "").strip()[:300],
            }
        )
        print(f"  [{i}/{len(samples)}] follow={int(ok)} rouge_l={r:.3f}")

    m = len(samples)
    follow_rate = follow / m
    mean_rouge = rouge / m
    print(f"[eval] 自动评估 {m} 条")
    print(f"  指令遵循率(输出非空且>20字): {follow_rate:.1%}")
    print(f"  平均 ROUGE-L(近似): {mean_rouge:.3f}")
    print("[eval] 人工评审：抽样 20 条，按 逻辑性/针对性/语言流畅 三项各 1-5 分自评（见 README）")

    if dump:
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_samples": m,
            "instruction_follow_rate": round(follow_rate, 4),
            "mean_rouge_l": round(mean_rouge, 4),
            "metric_definition": {
                "instruction_follow_rate": "输出非空且长度>20 视为遵循指令",
                "rouge_l": "LCS 长度 / max(输出长, 参考长)，近似值（非 HF 官方 ROUGE-L）",
            },
            "per_sample": per_sample,
        }
        out_path = DATA_PROCESSED / "eval_results.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[eval] 已写入 -> {out_path}")


if __name__ == "__main__":
    auto_eval()
