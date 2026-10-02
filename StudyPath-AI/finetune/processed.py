# -*- coding: utf-8 -*-
"""数据预处理工具：原始语料 -> Alpaca 指令格式 -> 划分 train/eval

===== 职责边界（重要，别搞混）=====
本脚本是【通用格式转换器】：读取 data/raw/ 下已有的 .json / .jsonl / .txt 语料，
统一成 Alpaca 格式并按固定种子划分 train/eval。

本项目 SFT 训练集的【真正生产入口】是：
    python -m annotations.build_sft_data
它直接读《院校数据采集.xlsx》的三个 sheet（院校项目库 / 录取案例库 / 文书范例库）
构造 180 条 SFT 样本（144 train + 36 eval），并同步产出 LLaMA Factory 需要的
dataset_info.json。SFT 数据的来源与标注逻辑都以那个脚本为准。

===== 安全闸门 =====
data/raw/ 下只有 .xlsx 时，本脚本读不到样本 —— 此时它会【明确提示并拒绝写盘】，
绝不会用空数据覆盖已验证的 train.jsonl / eval.jsonl。另有两道额外保护：
  1) 样本数 < MIN_SAMPLES 直接中止
  2) 样本数 < 现有数据集条数时拒绝覆盖（需显式 --force）
"""
import argparse
import json
import random
import sys
from pathlib import Path

from .config import DATA_RAW, DATA_PROCESSED, TRAIN_RATIO, INSTRUCTION_TMPL, ensure_dirs

# 样本数低于此值视为数据源异常，拒绝写盘
MIN_SAMPLES = 20


def read_raw_essays() -> list[dict]:
    """读取 data/raw/ 下所有文书（json / jsonl / txt）。

    期望数据格式（任选其一）：
      1) JSON/JSONL: [{"instruction":..., "input":..., "output":...}, ...]
      2) TXT: 一篇文书一个 .txt，文件名作为 instruction 的来源标识

    注意：.xlsx 不在这里解析 —— 见模块 docstring（走 annotations.build_sft_data）。
    仅发现 .xlsx 时会打印提示，避免"静默返回空列表"这种危险行为。
    """
    essays: list[dict] = []
    xlsx_found: list[str] = []

    for fp in sorted(Path(DATA_RAW).rglob("*")):
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
        elif fp.suffix in {".xlsx", ".xls"}:
            xlsx_found.append(fp.name)

    if not essays and xlsx_found:
        print(f"[processed][提示] data/raw/ 下只发现 Excel 数据源：{', '.join(xlsx_found)}")
        print("[processed][提示] 本脚本不解析 xlsx。SFT 数据请用：")
        print("[processed]         python -m annotations.build_sft_data")
        print("[processed]       （它读 xlsx 三个 sheet 构造 180 条 SFT + dataset_info.json）")

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


def count_existing() -> int:
    """统计现有 train/eval 数据集的总条数（用于覆盖保护）"""
    total = 0
    for name in ("train.jsonl", "eval.jsonl"):
        p = DATA_PROCESSED / name
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                total += sum(1 for line in f if line.strip())
    return total


def main(force: bool = False):
    ensure_dirs()
    essays = read_raw_essays()
    print(f"[processed] 读取 {len(essays)} 条原始文书")
    data = format_alpaca(essays)
    print(f"[processed] 格式化后 {len(data)} 条")

    # ===== 安全闸门 1：空数据绝不写盘 =====
    if not data:
        print("[processed][中止] 没有可用样本，未写入任何文件（现有数据集保持不变）。")
        print("[processed][中止] 若 data/raw/ 只有 xlsx，请运行：python -m annotations.build_sft_data")
        sys.exit(1)

    # ===== 安全闸门 2：样本数异常下限 =====
    if len(data) < MIN_SAMPLES:
        print(f"[processed][中止] 样本数 {len(data)} < 下限 {MIN_SAMPLES}，疑似数据源异常，未写入。")
        sys.exit(1)

    # ===== 安全闸门 3：不允许用更少的数据覆盖已有数据集 =====
    existing = count_existing()
    if existing and len(data) < existing and not force:
        print(f"[processed][中止] 拒绝覆盖：新数据 {len(data)} 条 < 现有数据集 {existing} 条。")
        print("[processed][中止] 确认要用更少的数据覆盖，请显式加 --force。")
        sys.exit(2)

    train, evald = split_train_eval(data)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(DATA_PROCESSED / "train.jsonl", "w", encoding="utf-8") as f:
        for x in train:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(DATA_PROCESSED / "eval.jsonl", "w", encoding="utf-8") as f:
        for x in evald:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"[processed] train={len(train)}, eval={len(evald)}  -> {DATA_PROCESSED}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="原始语料 -> Alpaca 格式 -> 划分 train/eval")
    ap.add_argument("--force", action="store_true",
                    help="允许用更少的数据覆盖现有数据集（默认禁止）")
    args = ap.parse_args()
    main(force=args.force)
