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


def auto_eval(n=20):
    samples = load_eval(n)
    model, tok = load_tuned_model()
    follow = rouge = 0
    for s in samples:
        out = generate(model, tok, s["instruction"], s["input"], max_new=256)
        if out.strip() and len(out) > 20:
            follow += 1
        rouge += lcs_length(out, s["output"]) / max(len(out), len(s["output"]), 1)
    m = len(samples)
    print(f"[eval] 自动评估 {m} 条")
    print(f"  指令遵循率(输出非空且>20字): {follow / m:.1%}")
    print(f"  平均 ROUGE-L(近似): {rouge / m:.3f}")
    print("[eval] 人工评审：抽样 20 条，按 逻辑性/针对性/语言流畅 三项各 1-5 分自评（见 README）")


if __name__ == "__main__":
    auto_eval()
