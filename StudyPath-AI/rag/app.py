# -*- coding: utf-8 -*-
"""
app.py — 命令行交互式问答 demo。

运行:  python app.py
退出:  输入 exit / quit / q 或 Ctrl+C

首次使用前请先跑 build_vectorstore.py 建好向量库。
"""
from qa import build_qa


def main():
    print("=" * 56)
    print("  StudyPath AI · RAG 问答 Demo")
    print("  数据底座: 院校项目库(100) + 录取案例库(50) + 文书范例库(30)")
    print("  输入 exit 退出")
    print("=" * 56)

    try:
        chain = build_qa()
    except Exception as e:
        print("加载向量库失败:", e)
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
            ans = chain.invoke(q)
            print("\n答>", ans)
        except Exception as e:
            print("出错了:", e)


if __name__ == "__main__":
    main()
