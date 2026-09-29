# -*- coding: utf-8 -*-
"""
demo_capture.py — 跑一次真实 RAG 检索 + 问答，把结果落盘成 JSON。
供 PPT 生成真实 demo 截图用。内容全部来自真实运行（chroma_db + qwen-plus），
不编造任何院校/排名/分数。
"""
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, ".")

from qa import build_qa, retrieve_only, format_docs
from config import CHROMA_DIR, TOP_K


def run_one(question: str) -> dict:
    t0 = time.time()
    # 1) 只检索，拿到真实命中的资料（带 source_url）
    ctx_raw = retrieve_only(question)
    docs = retrieve_only.__wrapped__ if False else None  # placeholder
    t_retrieve = time.time() - t0

    # 2) 完整链：检索 + qwen-plus 生成
    chain = build_qa()
    t1 = time.time()
    answer = chain.invoke(question)
    t_gen = time.time() - t1

    # 重新取一次结构化 docs 用于展示
    from qa import get_retriever
    retriever = get_retriever()
    raw_docs = retriever.invoke(question)

    docs_out = []
    for i, d in enumerate(raw_docs, 1):
        src = d.metadata.get("source_url") or d.metadata.get("source") or d.metadata.get("source_sheet", "")
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
    questions = [
        "GPA 3.5、雅思 7.0，想申美国 top30 的 CS 硕士，有哪些学校比较稳？",
        "CMU 的计算机硕士项目要求和截止日期是什么？",
    ]
    out = []
    for q in questions:
        try:
            out.append(run_one(q))
        except Exception as e:
            out.append({"question": q, "error": str(e)[:500]})

    with open("rag_demo_capture.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("OK 已写入 rag_demo_capture.json")
    print(f"问题数: {len(out)}")
    for o in out:
        if "error" in o:
            print(f"[ERR] {o['question']}\n      {o['error']}")
        else:
            print(f"[OK] {o['question']}")
            print(f"      检索 {o['timing']['retrieve_s']}s / 生成 {o['timing']['generate_s']}s / 命中 {len(o['retrieved'])} 条")


if __name__ == "__main__":
    main()
