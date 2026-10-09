# -*- coding: utf-8 -*-
"""多智能体链路端到端耗时实测（并行拓扑）。

取规范问法集前 5 条 query，真实调用 ask_multi（含 DashScope 往返与 Chroma 检索），
统计 P50 / mean / min / max，写回 data/processed/rag_metrics.json 的 latency.multi_agent。

注意这是端到端绝对耗时：含云端 LLM 往返，随网络与服务端负载波动，且主要由最后一跳的
生成长度决定（实测约 55 字/秒，1700 字答案约 30 秒）。所以它只作记录，不当工程指标；
要说明编排收益请用 rag/eval_topology.py 的同条件 A/B。

每条 query 用独立 thread_id：若复用同一 thread，第 2 条起会命中多轮追问分支、
额外多一次查询改写 LLM 调用，那属于对话能力的开销，不该算进单轮链路耗时。

运行（ai-base / ai-langchain 环境均可）：
    python rag/measure_latency.py
"""
import json
import os
import statistics
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from agents import ask_multi  # noqa: E402

PROCESSED = os.path.join(HERE, "..", "data", "processed")
EVALSET = os.path.join(PROCESSED, "rag_evalset.jsonl")
METRICS = os.path.join(PROCESSED, "rag_metrics.json")
N = 5


def _pct(xs, p):
    """线性插值分位数，与 eval_retrieval.py 的实现保持一致。"""
    s = sorted(xs)
    if len(s) == 1:
        return round(s[0], 3)
    k = (len(s) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 3)


def main():
    cases = [json.loads(l) for l in open(EVALSET, encoding="utf-8")][:N]

    print("=" * 66)
    print(f"多智能体链路端到端延迟实测（并行拓扑，n={len(cases)}）")
    print("=" * 66)

    ts = []
    for i, c in enumerate(cases):
        q = c["query"]
        t0 = time.time()
        try:
            out = ask_multi(q, thread_id=f"latency-parallel-{i}")
        except Exception as exc:                       # 单条失败不中断整轮测量
            print(f"[{i+1}] 失败: {type(exc).__name__}: {exc}")
            continue
        dt = time.time() - t0
        ts.append(dt)
        print(f"[{i+1}] {dt:5.2f}s  route={out['route']}  "
              f"len={len(out['answer'])}  {q[:34]}")

    if not ts:
        print("全部请求失败，未写回指标文件。")
        return

    result = {
        "n": len(ts),
        "p50": _pct(ts, 50),
        "p95": _pct(ts, 95),
        "mean": round(statistics.mean(ts), 3),
        "min": round(min(ts), 3),
        "max": round(max(ts), 3),
        "topology": "parallel",
    }

    print()
    print("实测结果:", json.dumps(result, ensure_ascii=False))

    metrics = json.load(open(METRICS, encoding="utf-8"))
    lat = metrics.setdefault("latency", {})
    lat["multi_agent"] = result
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"已写回 {os.path.relpath(METRICS, os.path.join(HERE, '..'))}")


if __name__ == "__main__":
    main()
