# -*- coding: utf-8 -*-
"""
多智能体命令行交互 demo。

先跑 build_vectorstore.py 建好向量库，再 python app_multi.py；输入 exit / quit / q 退出。
"""
from agents import build_graph
from langchain_core.messages import HumanMessage


def main():
    print("=" * 56)
    print("  StudyPath · 多智能体 (LangGraph)")
    print("  Supervisor 调度 -> School/Admission/Essay -> 汇总")
    print("  输入 exit 退出")
    print("=" * 56)

    try:
        graph = build_graph()
    except Exception as e:
        print("加载失败:", e)
        print("请先运行: python build_vectorstore.py")
        return

    while True:
        try:
            q = input("\n你问> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见 👋")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "q"):
            print("再见 👋")
            break
        try:
            result = graph.invoke({
                "messages": [HumanMessage(content=q)],
                "query": q,
                "route": [],
                "school_ctx": "",
                "admission_ctx": "",
                "essay_ctx": "",
                "answer": "",
            })
            print("\n[路由]", result.get("route"))
            print("\n答>", result.get("answer"))
        except Exception as e:
            print("出错了:", e)


if __name__ == "__main__":
    main()
