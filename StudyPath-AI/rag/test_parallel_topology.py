# -*- coding: utf-8 -*-
"""
并行拓扑验证脚本（不发起任何真实 LLM 请求）。

做法：把 agents.llm 替换成一个"睡 1 秒再返回"的假模型，记录每个节点
调用 LLM 的开始/结束时间戳，据此判断三个 worker 是否真的并发：

    串行：school 结束 → admission 开始 → essay 开始，彼此间隔 ≈ 1s
    并行：三者的时间区间互相重叠，总耗时 ≈ 3s（supervisor + max(worker) + synthesizer）
          而串行版 ≈ 5s

同时打印 StateGraph 的边表，用于答辩材料里的"实测拓扑"截图。

运行（ai-langchain 环境）：
    python rag/test_parallel_topology.py
"""
import sys
import time
import threading
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\留学项目\StudyPath-AI\rag")

from langchain_core.documents import Document

import agents  # 必须在 patch 之前导入，才能替换它内部的 llm / retrieve_docs

T0 = time.time()
LOCK = threading.Lock()
LOG = []          # [(role, start, end)]
DELAY = 1.0       # 假 LLM 的单次耗时（秒）


def _role_of(messages):
    """从 system prompt 关键字判断这次调用属于哪个节点。"""
    sys_text = getattr(messages[0], "content", "") if messages else ""
    for kw, role in [
        ("调度器", "supervisor"),
        ("选校策略师", "worker_school"),
        ("录取风险评估师", "worker_admission"),
        ("文书规划师", "worker_essay"),
        ("整合器", "synthesizer"),
    ]:
        if kw in sys_text:
            return role
    return "unknown"


class FakeLLM:
    """每次 invoke 睡 DELAY 秒，返回该角色需要的固定内容。"""

    def invoke(self, messages, **kwargs):
        role = _role_of(messages)
        start = time.time() - T0
        time.sleep(DELAY)
        end = time.time() - T0
        with LOCK:
            LOG.append((role, start, end))
        if role == "supervisor":
            content = '{"route": ["school", "admission", "essay"]}'
        else:
            content = f"[{role}] 这是用于拓扑验证的占位输出。"
        return SimpleNamespace(content=content)


def fake_retrieve_docs(query, sheet=None, **kwargs):
    """假的检索：每个库返回 1 篇带 source_url 的文档，不碰向量库。"""
    return [
        Document(
            page_content=f"占位资料（{sheet}）",
            metadata={"source_url": f"https://example.com/{sheet}"},
        )
    ], None


def main():
    agents.llm = FakeLLM()
    agents.retrieve_docs = fake_retrieve_docs

    graph = agents.build_graph()

    print("=" * 62)
    print("StateGraph 边表（拓扑）")
    print("=" * 62)
    for e in graph.get_graph().edges:
        cond = "" if getattr(e, "conditional", False) else "  (固定边)"
        print(f"  {e.source:<18} -> {e.target}{cond}")
    print(f"  节点数: {len(graph.get_graph().nodes)}    边数: {len(graph.get_graph().edges)}")

    print()
    print("=" * 62)
    print("执行时间轴（假 LLM 单次耗时 1.0s）")
    print("=" * 62)
    graph.invoke(
        {
            "messages": [],
            "query": "我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？",
            "route": [],
            "school_docs": [],
            "admission_docs": [],
            "essay_docs": [],
            "school_plan": "",
            "admission_risk": "",
            "essay_outline": "",
            "answer": "",
        },
        config={"configurable": {"thread_id": "topology-test"}},
    )

    for role, s, e in sorted(LOG, key=lambda x: x[1]):
        print(f"  {role:<20} {s:6.2f}s  ->  {e:6.2f}s   (耗时 {e - s:.2f}s)")

    workers = [(s, e) for r, s, e in LOG if r.startswith("worker")]
    total = max(e for _, _, e in LOG)

    print()
    if len(workers) == 3:
        starts = [s for s, _ in workers]
        ends = [e for _, e in workers]
        overlap = max(ends) - min(starts)          # 三者并存的窗口
        spread = max(starts) - min(starts)         # 起始时间差
        print(f"  三个 worker 起始时间差 : {spread:.2f}s")
        print(f"  三者并存窗口           : {overlap:.2f}s")
        print(f"  端到端总耗时           : {total:.2f}s")
        if spread < 0.3 and overlap < DELAY * 1.5:
            print("  判定: ✅ 并行生效（三个 worker 在同一 superstep 内并发）")
            print(f"        串行版理论耗时 ≈ {DELAY * 5:.2f}s，当前 ≈ {total:.2f}s")
        else:
            print("  判定: ❌ 仍是串行（起始时间明显错开）")
    else:
        print(f"  worker 调用次数异常: {len(workers)}，请检查路由")


if __name__ == "__main__":
    main()
