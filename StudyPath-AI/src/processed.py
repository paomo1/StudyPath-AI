# -*- coding: utf-8 -*-
"""数据预处理：原始文书 → Alpaca 指令格式 → 划分 train/eval
对应老师例子 src/processed.py：让预训练模型能接收
"""
import json
import random
from pathlib import Path

from .config import DATA_RAW, DATA_PROCESSED, TRAIN_RATIO, INSTRUCTION_TMPL, ensure_dirs


def read_raw_essays() -> list[dict]:
    """读取 data/raw/ 下所有文书（json / jsonl / txt）。

    期望数据格式（任选其一）：
      1) JSON/JSONL: [{"instruction":..., "input":..., "output":...}, ...]
      2) TXT: 一篇文书一个 .txt，文件名作为 instruction 的来源标识
    """
    essays: list[dict] = []
    for fp in Path(DATA_RAW).rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix in {".json", ".jsonl"}:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    essays.append(json.loads(line))
        elif fp.suffix == ".txt":
            text = fp.read_text(encoding="utf-8").strip()
            if text:
                essays.append({
                    "instruction": f"请为一篇留学{Path(fp).stem}生成示例文本",
                    "input": "",
                    "output": text,
                })
    return essays


def format_alpaca(essays: list[dict]) -> list[dict]:
    """统一为 Alpaca 格式 [{instruction, input, output}, ...]，补默认值"""
    cleaned = []
    for x in essays:
        cleaned.append({
            "instruction": x.get("instruction", "").strip() or "请生成一篇留学文书",
            "input": x.get("input", "").strip(),
            "output": x.get("output", "").strip(),
        })
    # 过滤空输出
    return [x for x in cleaned if x["output"]]


def split_train_eval(data: list[dict], ratio: float = TRAIN_RATIO):
    """随机划分 train / eval（固定种子保证可复现）"""
    random.seed(42)
    random.shuffle(data)
    n = int(len(data) * ratio)
    return data[:n], data[n:]


def main():
    ensure_dirs()
    essays = read_raw_essays()
    print(f"[processed] 读取 {len(essays)} 条原始文书")
    data = format_alpaca(essays)
    print(f"[processed] 格式化后 {len(data)} 条")
    train, evald = split_train_eval(data)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(DATA_PROCESSED / "train.jsonl", "w", encoding="utf-8") as f:
        for x in train:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(DATA_PROCESSED / "eval.jsonl", "w", encoding="utf-8") as f:
        for x in evald:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"[processed] train={len(train)}, eval={len(evald)}  → {DATA_PROCESSED}")


if __name__ == "__main__":
    main()
