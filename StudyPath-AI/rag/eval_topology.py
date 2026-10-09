# -*- coding: utf-8 -*-
"""拓扑对照评测：并行 fan-out 与串行链的耗时对比，外加检索层耗时。

同一条 query 在同一进程、同一时间窗内分别喂给并行图与串行图，用
stream_mode="updates" 记录各节点到达时刻，把端到端拆成三段：
supervisor(路由) / 三个 worker(各自检索 + 角色分析) / synthesizer(汇总)。

并行图的三个 worker 属于同一 superstep，worker 段耗时 = max(三者)；
串行图依次执行，worker 段耗时 = sum(三者)。两者之比即编排并行收益。

两条 query 一起测，是为了暴露收益的路由依赖性：命中越多，并行省得越多。
supervisor 是真实 LLM 调用（temperature>0），两次路由可能不一致；不一致说明两图
干的活不一样，该条不计加速比（route_matched=false），只留分段耗时备查。

结果写入 data/processed/rag_metrics.json：
    latency.topology_ab  —— 并行 / 串行对照（含 route、三段时间、答案字数）
    latency.retrieval    —— 检索层（embed + Chroma MMR）单次耗时

运行（ai-base / ai-langchain 环境均可）：
    python rag/eval_topology.py
"""
import json
import os
import statistics
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from langgraph.graph import StateGraph, START, END          # noqa: E402
from langgraph.checkpoint.memory import MemorySaver          # noqa: E402
from langchain_core.messages import HumanMessage             # noqa: E402

import agents                                                # noqa: E402
from agents import (State, supervisor, worker_school,        # noqa: E402
                    worker_admission, worker_essay, synthesizer)
from qa import retrieve_docs                                 # noqa: E402

PROCESSED = os.path.join(HERE, "..", "data", "processed")
METRICS = os.path.join(PROCESSED, "rag_metrics.json")

WORKER_NODES = ("worker_school", "worker_admission", "worker_essay")

# 一条会触发多路 worker 的宽问题，一条只指向单个库的窄问题
QUERIES = [
    ("多路命中",
     "我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？录取概率大吗？文书怎么准备？"),
    ("单路命中", "介绍一下 University of Waterloo 的 MMath 项目"),
]


def build_serial():
    """节点与 prompt 与 build_graph 完全一致，只把边改成串行链，作为对照组。"""
    g = StateGraph(State)
    g.add_node("supervisor", supervisor)
    g.add_node("worker_school", worker_school)
    g.add_node("worker_admission", worker_admission)
    g.add_node("worker_essay", worker_essay)
    g.add_node("synthesizer", synthesizer)
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", "worker_school")
    g.add_edge("worker_school", "worker_admission")
    g.add_edge("worker_admission", "worker_essay")
    g.add_edge("worker_essay", "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile(checkpointer=MemorySaver())


def run_once(graph, query, tag):
    """跑一次完整链路，返回 route、三段耗时、总耗时、答案字数、逐节点时刻。"""
    cfg = {"configurable": {"thread_id": f"topo-{tag}-{int(time.time() * 1000)}"}}
    init = {
        "messages": [HumanMessage(content=query)], "query": query, "route": [],
        "school_docs": [], "admission_docs": [], "essay_docs": [],
        "school_plan": "", "admission_risk": "", "essay_outline": "", "answer": "",
    }
    t0 = time.time()
    marks, route, alen = {}, [], 0
    for chunk in graph.stream(init, config=cfg, stream_mode="updates"):
        now = time.time() - t0
        for node, upd in chunk.items():
            marks.setdefault(node, now)
            if node == "supervisor":
                route = upd.get("route", [])
            if node == "synthesizer":
                alen = len(upd.get("answer", ""))
    total = time.time() - t0

    sup_done = marks.get("supervisor", 0.0)
    worker_last = max((marks[n] for n in WORKER_NODES if n in marks), default=sup_done)
    syn_done = marks.get("synthesizer", total)
    seg = {
        "supervisor": round(sup_done, 2),
        "workers": round(worker_last - sup_done, 2),
        "synthesizer": round(syn_done - worker_last, 2),
    }
    return route, seg, round(total, 2), alen, {k: round(v, 2) for k, v in marks.items()}


def measure_retrieval(n=8):
    """检索层单次耗时。先预热一次吃掉 Chroma 首次加载，再测 n 次。"""
    q = QUERIES[0][1]
    retrieve_docs(q, sheet="院校项目库")
    ts = []
    for _ in range(n):
        t0 = time.time()
        retrieve_docs(q, sheet="院校项目库")
        ts.append(time.time() - t0)
    return {
        "n": n,
        "p50": round(statistics.median(ts), 3),
        "mean": round(statistics.mean(ts), 3),
        "min": round(min(ts), 3),
        "max": round(max(ts), 3),
    }


def main():
    par, ser = agents.build_graph(), build_serial()
    ab = {}
    for label, q in QUERIES:
        entry = {}
        for name, g in (("parallel", par), ("serial", ser)):
            route, seg, total, alen, marks = run_once(g, q, name)
            entry[name] = {"route": route, "total_s": total,
                           "answer_chars": alen, "segments_s": seg}
            print(f"[{label}] {name:8s} 总 {total:6.2f}s  答案 {alen} 字  route={route}")
            print(f"            supervisor {seg['supervisor']}s | "
                  f"workers {seg['workers']}s | synthesizer {seg['synthesizer']}s")
        p, s = entry["parallel"], entry["serial"]
        # supervisor 每次都是真实 LLM 调用，temperature>0 时两次路由可能不一致。
        # 路由不同就意味着两图干的活不一样，worker 段耗时不可直接相比，加速比记 null。
        matched = sorted(p["route"]) == sorted(s["route"])
        entry["route_matched"] = matched
        gain = (round(s["segments_s"]["workers"] / p["segments_s"]["workers"], 2)
                if matched and p["segments_s"]["workers"] else None)
        entry["worker_speedup"] = gain
        if matched:
            print(f"            -> worker 段 {s['segments_s']['workers']}s => "
                  f"{p['segments_s']['workers']}s，加速 {gain}x")
        else:
            print(f"            -> ⚠️ 两图路由不一致（parallel={p['route']} / "
                  f"serial={s['route']}），worker 段不可直接相比，加速比记 null")
        ab[label] = entry

    retr = measure_retrieval()
    print(f"\n检索层（embed + Chroma MMR，n={retr['n']}）：P50 {retr['p50']}s  "
          f"mean {retr['mean']}s")

    metrics = json.load(open(METRICS, encoding="utf-8"))
    lat = metrics.setdefault("latency", {})
    # 旧的串行基线（3.119s）与自身「5 次 LLM」的结构矛盾、当前不可复现，移除。
    lat.pop("multi_agent_serial_baseline", None)
    lat["topology_ab"] = ab
    lat["retrieval"] = retr
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"\n已写回 {os.path.relpath(METRICS, os.path.join(HERE, '..'))}")


if __name__ == "__main__":
    main()
