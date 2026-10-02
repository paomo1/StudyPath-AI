# -*- coding: utf-8 -*-
"""
demo_capture.py — 跑一次真实 RAG 检索 + 问答，把结果落盘成 JSON。
供 PPT 生成真实 demo 截图用。内容全部来自真实运行（chroma_db + qwen-plus），
不编造任何院校/排名/分数。

设计要点（v2）：
  1) 只检索【一次】，且走 query_norm 别名归一化；
  2) 用同一批 docs 生成回答 —— 保证落盘的「召回结果」与「喂给模型的上下文」严格同源；
  3) 路径基于 __file__ 推导，从任何目录调用都能跑。

用法：
    cd StudyPath-AI
    python rag/demo_capture.py                          # 跑内置的两条默认问题
    python rag/demo_capture.py "你的问题"                # 跑指定问题
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 让 qa / config 等同目录模块可被 import（不依赖当前工作目录）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa import retrieve_docs, answer_from_docs  # noqa: E402
from config import TOP_K  # noqa: E402

# 输出路径固定落在 rag/ 下，跟旧版行为一致
OUT_PATH = Path(__file__).resolve().parent / "rag_demo_capture.json"

DEFAULT_QUESTIONS = [
    "GPA 3.5、雅思 7.0，想申美国 top30 的 CS 硕士，有哪些学校比较稳？",
    "CMU 的计算机硕士项目要求和截止日期是什么？",
]


def run_one(question: str) -> dict:
    # 1) 只检索一次（内部已做别名归一化）
    t0 = time.time()
    docs, _items = retrieve_docs(question)
    t_retrieve = time.time() - t0

    # 2) 用同一批 docs 生成 —— 展示的命中与模型看到的上下文完全同源
    t1 = time.time()
    answer = answer_from_docs(question, docs)
    t_gen = time.time() - t1

    docs_out = []
    for i, d in enumerate(docs, 1):
        src = (
            d.metadata.get("source_url")
            or d.metadata.get("source")
            or d.metadata.get("source_sheet", "")
        )
        docs_out.append({
            "idx": i,
            "sheet": d.metadata.get("source_sheet", ""),
            "content": d.page_content[:400],
            "source": src,
        })

    return {
        "question": question,
        "retrieved": docs_out,
        "answer": answer,
        "top_k": TOP_K,
        "timing": {
            "retrieve_s": round(t_retrieve, 2),
            "generate_s": round(t_gen, 2),
        },
        "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def main():
    questions = sys.argv[1:] or DEFAULT_QUESTIONS
    out = []
    for q in questions:
        try:
            out.append(run_one(q))
        except Exception as e:
            out.append({"question": q, "error": str(e)[:500]})

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK 已写入 {OUT_PATH}")
    print(f"问题数: {len(out)}")
    for o in out:
        if "error" in o:
            print(f"[ERR] {o['question']}\n      {o['error']}")
        else:
            print(f"[OK] {o['question']}")
            print(f"      检索 {o['timing']['retrieve_s']}s / 生成 {o['timing']['generate_s']}s / 命中 {len(o['retrieved'])} 条")


if __name__ == "__main__":
    main()
