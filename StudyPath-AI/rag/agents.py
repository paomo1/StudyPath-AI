# -*- coding: utf-8 -*-
"""
agents.py — StudyPath AI 多智能体（LangGraph StateGraph 手写 supervisor-worker）。

架构:
  user query
    -> Supervisor   (LLM 决策: 这个问题该派哪些专家)
    -> School / Admission / Essay 三个 worker (各自检索自己的 RAG 库)
    -> Synthesizer  (LLM 把多份资料汇总成最终答复)

每个 worker 复用 qa.retrieve_docs()，零重复代码。
这是 LangGraph 最经典、答辩最好讲的「Supervisor + 多 Worker」模式。
"""
import json
import re
from typing import TypedDict, Annotated, List

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.documents import Document

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, CHAT_MODEL
from qa import retrieve_docs, _source_item

llm = ChatOpenAI(
    model=CHAT_MODEL,
    openai_api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    temperature=0.3,
    max_tokens=2048,  # 1024→2048: 避免三段式回复(目标校/行业建议/不建议项目)被截断
)

# worker 名 -> 对应 sheet 名
SHEETS = {
    "school": "院校项目库",
    "admission": "录取案例库",
    "essay": "文书范例库",
}


class State(TypedDict):
    messages: Annotated[List, add_messages]
    query: str
    route: List[str]          # supervisor 决定的 worker 列表
    school_docs: List[Document]     # 院校库召回的原始 Document 列表
    admission_docs: List[Document]  # 录取案例库召回的原始 Document 列表
    essay_docs: List[Document]      # 文书库召回的原始 Document 列表
    answer: str


def _extract_json(text):
    """从 LLM 输出里抠出第一个 {...} 块，避免它多嘴输出解释文字。"""
    try:
        s = text[text.index("{"): text.rindex("}") + 1]
        return s
    except Exception:
        return "{}"


def supervisor(state: State):
    """LLM 判断这个问题需要哪些专家来检索。"""
    q = state["query"]
    sys = SystemMessage(content=(
        "你是留学规划助手的调度器。用户会问留学申请相关问题。"
        "判断这个问题需要调用哪些专家来检索资料，可选专家："
        "school=院校项目信息(排名/申请要求/截止日期/学费)，"
        "admission=录取案例与背景匹配(GPA/托福/背景对应录取结果)，"
        "essay=文书范例资源(PS/SOP/CV/LOR 范文)。"
        "只返回 JSON，格式如: {\"route\":[\"school\",\"admission\"]}，"
        "最多选 3 个；问题笼统就全选。"
    ))
    resp = llm.invoke([sys, HumanMessage(content=q)])
    try:
        route = json.loads(_extract_json(resp.content)).get("route", [])
    except Exception:
        route = ["school", "admission", "essay"]
    # 只保留合法的 worker 名，空了就全选兜底
    route = [r for r in route if r in SHEETS]
    if not route:
        route = ["school", "admission", "essay"]
    return {"route": route}


def _dedup_docs(docs: List[Document]) -> List[Document]:
    """按 source_url 去重并保序。"""
    seen: set[str] = set()
    out: List[Document] = []
    for d in docs:
        url = d.metadata.get("source_url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(d)
    return out


def _worker(state: State, key: str):
    """通用 worker：若本 key 在路由里，就检索对应 sheet 的库，返回原始 Document 列表。"""
    if key not in state.get("route", []):
        return {}
    docs, _ = retrieve_docs(state["query"], sheet=SHEETS[key])
    return {f"{key}_docs": docs}


def worker_school(state: State):
    return _worker(state, "school")


def worker_admission(state: State):
    return _worker(state, "admission")


def worker_essay(state: State):
    return _worker(state, "essay")


def synthesizer(state: State):
    """把多个 worker 检索到的资料汇总成最终答复。

    关键：三个 worker 召回的 Document 先按 URL 全局去重，再用 format_docs
    统一编号成 [资料1]~[资料N]，避免每个 worker 内部独立编号导致引用混乱。
    """
    from qa import format_docs

    q = state["query"]
    all_docs: List[Document] = []
    for key in ("school", "admission", "essay"):
        all_docs.extend(state.get(f"{key}_docs", []))
    deduped = _dedup_docs(all_docs)
    context = format_docs(deduped) if deduped else "（未检索到相关资料）"

    sys = SystemMessage(content=(
        "你是 StudyPath AI 留学规划助手。请严格基于【检索到的资料】回答用户问题。"
        "规则: 1) 只用资料里的事实，绝不编造院校/排名/分数/案例; "
        "2) 资料不足就如实说明，并建议用户补充哪类数据; "
        "3) 用中文、条理清晰、必要时分点; "
        "4) 回答末尾附上引用来源(source_url)，每条来源单独一行，格式如 `[资料1] 来源：https://...`，方便用户核实；不要把所有来源堆在同一行。"
        "【格式铁律】不要使用 markdown 表格(单元格内换行会显示错乱)，一律用「### 小标题 + 无序列表(- 要点)」组织; "
        "不要使用 <br> / <br/> 标签，需要换行直接用真实换行符; "
        "只引用资料中明确写出的字段名，不要自行发明字段名(例如不要编造'GRE量化'、'满足归属'这类词); "
        "引用资料时用 [资料N] 标注，N 来自资料块开头的编号。"
    ))
    user = HumanMessage(content=f"【检索到的资料】\n{context}\n\n【用户问题】\n{q}\n\n【回答】")
    resp = llm.invoke([sys, user])
    answer = _clean_answer(resp.content)
    return {"answer": answer, "messages": [AIMessage(content=answer)]}


def _clean_answer(text):
    """后处理兜底：清理 <br> 标签、压缩多余空行，避免终端/预览器渲染错乱。"""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<BR>", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)     # 清掉行尾空白
    text = re.sub(r"\n{3,}", "\n\n", text)     # 合并 >2 个连续空行为 1 个
    return text.strip()


def build_graph():
    """组装并编译 StateGraph。"""
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
    return g.compile()


def ask_multi(query: str) -> dict:
    """单次多智能体问答，返回 {route, answer, sources}。

    sources = 所有 worker 召回文档经全局去重后的来源卡片列表，
    顺序与 synthesizer 看到的 [资料N] 编号完全一致（B 方案）。
    """
    graph = build_graph()
    result = graph.invoke({
        "messages": [HumanMessage(content=query)],
        "query": query,
        "route": [],
        "school_docs": [],
        "admission_docs": [],
        "essay_docs": [],
        "answer": "",
    })
    # 与 synthesizer 使用同一套去重逻辑，保证底部卡片 [N] == 答案里的 [资料N]
    all_docs: List[Document] = []
    for key in ("school", "admission", "essay"):
        all_docs.extend(result.get(f"{key}_docs", []))
    deduped = _dedup_docs(all_docs)
    sources = [_source_item(d) for d in deduped]
    return {"route": result.get("route", []), "answer": result.get("answer", ""), "sources": sources}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？"
    out = ask_multi(q)
    print("路由:", out["route"])
    print("答>", out["answer"])
