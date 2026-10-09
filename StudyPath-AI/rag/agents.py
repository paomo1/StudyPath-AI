# -*- coding: utf-8 -*-
"""
LangGraph StateGraph 实现的 supervisor-worker 多智能体。

    query -> Supervisor（LLM 决定派哪些 worker）
          -> School / Admission / Essay（并行 fan-out：各自检索对应 RAG 库，互不阻塞）
          -> Synthesizer（fan-in 汇合，把多路结论整合成最终答复）

拓扑要点：三个 worker 挂在 supervisor 的同一条出边上，LangGraph 会在同一个
superstep 内并发执行它们，全部完成后才推进到 synthesizer（Pregel 语义）。
因此端到端耗时 ≈ supervisor + max(三 worker) + synthesizer，
而不是串行版的 supervisor + worker1 + worker2 + worker3 + synthesizer。

并发安全：三个 worker 只写自己专属的 State 字段
（school_* / admission_* / essay_*），不存在同 key 竞态，故无需 reducer。
未被 supervisor 选中的 worker 直接返回 {}，零额外开销——
"路由裁剪"与"并行执行"由此同时成立。

worker 复用 qa.retrieve_docs()，不重复实现检索。
"""
import json
import re
from typing import TypedDict, Annotated, List

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
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
    school_docs: List[Document]     # 院校库召回的原始 Document（保留，供来源卡片用）
    admission_docs: List[Document]  # 录取案例库召回的原始 Document
    essay_docs: List[Document]      # 文书库召回的原始 Document
    school_plan: str          # School Worker 的"选校策略"结论（冲刺/稳妥/保底）
    admission_risk: str       # Admission Worker 的"录取风险评估"结论
    essay_outline: str        # Essay Worker 的"文书规划"结论
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


# 三个 worker 各自的"专家人设 + 业务动作"——这是相对纯 RAG 的核心亮点
WORKER_ROLE_PROMPTS = {
    "school": (
        "你是留学选校策略师。基于【检索资料】中的真实院校项目信息，为用户做选校定位。\n"
        "要求：\n"
        "1. 先按用户硬性条件(国家/地区、专业、GPA、语言成绩、预算)做初步筛选，只保留符合或接近的项目；\n"
        "2. 将候选院校按 冲刺 / 稳妥 / 保底 三档划分(每档1-2所，依据排名、申请难度、背景匹配度)；\n"
        "3. 每所院校给出匹配理由(为什么适合用户)；\n"
        "4. 标注关键信息：截止日期、学费、语言要求、核心课程(仅用资料中明确写出的字段)。\n"
        "只使用【检索资料】中明确出现的院校与字段，严禁引入资料外的学校、项目名称、阈值或建议。绝不编造。中文、条理清晰，用「### 小标题 + 列表」组织。"
    ),
    "admission": (
        "你是录取风险评估师。基于【检索资料】中的真实录取/拒信案例，评估用户的申请竞争力。\n"
        "要求：\n"
        "1. 找出与用户背景(专业、GPA、语言成绩)最相似的案例；\n"
        "2. 对比相似案例的录取/被拒结果，给出用户在该档位的定位(冲刺型/稳妥型/保底型)；\n"
        "3. 指出用户的背景短板与风险点；\n"
        "4. 给出补齐建议(如补科研、刷分、换项目)，且建议必须基于资料中出现过的案例/院校。\n"
        "只使用【检索资料】中明确出现的案例与字段，严禁引入资料外的案例、学校或阈值。中文、条理清晰。"
    ),
    "essay": (
        "你是文书规划师。基于【检索资料】中的真实文书范例，为用户规划申请文书。\n"
        "要求：\n"
        "1. 找出与目标专业/方向最相关的范文；\n"
        "2. 拆解这个范文的写作结构(开头→学术经历→科研/实习→职业规划→结尾)；\n"
        "3. 输出可填充的文书大纲(各段落要点)；\n"
        "4. 列出用户需要准备的素材清单。\n"
        "只使用【检索资料】中明确出现的范文与字段，严禁引入资料外的范文或写法。中文、条理清晰。"
    ),
}

# key -> 该 worker 的结论在 State 中存放的字段名
CONCL_FIELD = {
    "school": "school_plan",
    "admission": "admission_risk",
    "essay": "essay_outline",
}


def _analyze(state: State, key: str, docs: List[Document]) -> str:
    """worker 检索后，用角色 prompt 让 LLM 把原始文档转成结构化业务结论。"""
    if not docs:
        return ""
    from qa import format_docs
    context = format_docs(docs)          # 召回文档拼成 [资料N] 文本，与来源卡片编号一致
    role = WORKER_ROLE_PROMPTS[key]
    sys = SystemMessage(content=role)
    user = HumanMessage(content=f"【检索资料】\n{context}\n\n【用户问题】\n{state['query']}\n\n【角色结论】")
    resp = llm.invoke([sys, user])        # 这次 LLM 调用 = 该 worker 的"业务思考"
    return _clean_answer(resp.content)


def _worker(state: State, key: str):
    """通用 worker：路由命中则检索本库 + 做角色分析，回写原始文档与结构化结论。"""
    if key not in state.get("route", []):
        return {}
    docs, _ = retrieve_docs(state["query"], sheet=SHEETS[key])
    conclusion = _analyze(state, key, docs)
    return {f"{key}_docs": docs, CONCL_FIELD[key]: conclusion}


def worker_school(state: State):
    return _worker(state, "school")


def worker_admission(state: State):
    return _worker(state, "admission")


def worker_essay(state: State):
    return _worker(state, "essay")


def synthesizer(state: State):
    """把三个 worker 的结构化结论整合成一份可执行的留学申请规划。

    三个 worker 已各自完成"业务思考"(选校策略 / 录取风险评估 / 文书规划)，
    这里只负责把它们按时间轴整合，不再重复读原始文档。
    """
    plan = state.get("school_plan", "")
    risk = state.get("admission_risk", "")
    outline = state.get("essay_outline", "")

    # 来源(与 ask_multi 同样去重逻辑，保证 [资料N] 编号对齐)
    all_docs: List[Document] = []
    for key in ("school", "admission", "essay"):
        all_docs.extend(state.get(f"{key}_docs", []))
    deduped = _dedup_docs(all_docs)
    sources_text = "\n".join(
        f"[{i+1}] {d.metadata.get('source_url', '')}" for i, d in enumerate(deduped)
    )

    sections = []
    if plan:    sections.append("【选校策略结论】\n" + plan)
    if risk:    sections.append("【录取风险评估结论】\n" + risk)
    if outline: sections.append("【文书规划结论】\n" + outline)
    expert_text = "\n\n".join(sections)

    # 多轮追问检测：messages 里已有上一轮的助手答案，即说明本轮是对话追问。
    # add_messages reducer 保证历史跨 invoke 累积，故可直接从 state 判断。
    is_followup = any(getattr(m, "type", "") == "ai" for m in state.get("messages", []))

    followup_rule = (
        "\n\n【多轮追问模式】检测到这是对话追问(上一轮已有答案)。用户当前问题"
        "只关心某个具体信息点(如截止日期 / 学费 / 材料 / 排名等)。请直接针对该信息点"
        "给出答案，并明确引用上一轮提到的具体实体(学校名、项目名)；"
        "不要重复输出完整的阶段1-5规划模板，也不要重新推荐学校。"
        "若专家结论未覆盖用户问的字段，明确写『知识库未检索到该字段』，不要编造。"
    ) if is_followup else ""

    sys = SystemMessage(content=(
        "你是 StudyPath 留学规划整合器。你已收到三位专家的结构化结论：\n"
        "选校策略(冲刺/稳妥/保底)、录取风险评估(定位/风险点)、文书规划(结构/大纲)。\n"
        "请将其整合为一份【可执行的留学申请规划】，严格按时间轴组织：\n"
        "阶段1 选校定稿 → 阶段2 材料准备 → 阶段3 文书写作 → "
        "阶段4 网申提交(含截止日期checklist) → 阶段5 面试准备。\n"
        "每个阶段给出关键任务与优先级。严格基于专家结论，不要补充专家结论之外的信息；\n"
        "若【文书规划结论】为空(essay worker 未命中)，阶段3 文书写作需明确标注『未检索到同方向范文，以下为通用写作框架』，不得伪装成来自知识库。\n"
        "引用资料时用 [资料N] 标注。中文，用「### 阶段N + 列表」组织。\n"
        "【格式铁律】不要使用 markdown 表格(单元格内换行会显示错乱)，"
        "一律用「### 小标题 + 无序列表(- 要点)」组织；"
        "不要使用 <br>/<br/> 标签，需换行直接用真实换行符；"
        "只引用资料中明确写出的字段名，不要自行发明字段名；"
        "引用资料时用 [资料N] 标注，N 来自资料块开头的编号。"
        + followup_rule
    ))
    user = HumanMessage(content=(
        f"{expert_text}\n\n【可引用来源】\n{sources_text}\n\n"
        f"【用户问题】\n{state['query']}\n\n【整合后的申请规划】"
    ))
    resp = llm.invoke([sys, user])
    answer = _clean_answer(resp.content)
    return {"answer": answer, "messages": [AIMessage(content=answer)]}


def _tables_to_lists(text: str) -> str:
    """把 markdown 表格转成无序列表，避免 Gradio/预览器渲染错乱（单元格内换行会乱）。"""
    out = []
    for line in text.split("\n"):
        s = line.strip()
        is_row = s.startswith("|") and s.endswith("|") and "|" in s[1:-1]
        if not is_row:
            out.append(line)          # 非表格行原样保留
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # 跳过分隔行 |---|---|（内容全是 - : 空格）
        if all(set(c) <= set("-: ") for c in cells):
            continue
        out.append("- " + "｜".join(cells))   # 表格行 → 列表项，单元格用 ｜ 连接
    return "\n".join(out)


def _clean_answer(text):
    """后处理兜底：清理标签、重复标题符号、markdown 表格、多余空行。"""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<BR>", "\n")
    text = re.sub(r"#{2,}\s*#{2,}\s*", "### ", text)   # 修复 "### ### 阶段" 重复符号
    text = re.sub(r"\]\[", "] [", text)                 # 修复 [资料1][资料2] 挤在一起 → [资料1] [资料2]
    text = _tables_to_lists(text)                        # 表格转列表，防渲染错乱
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
    # ---- 并行 fan-out：三个 worker 同属一个 superstep，LangGraph 并发执行 ----
    # 只有 supervisor 路由命中的 worker 才真正干活，其余立即返回 {}。
    g.add_edge("supervisor", "worker_school")
    g.add_edge("supervisor", "worker_admission")
    g.add_edge("supervisor", "worker_essay")
    # ---- fan-in：三个 worker 全部结束后才进入 synthesizer ----
    g.add_edge("worker_school", "synthesizer")
    g.add_edge("worker_admission", "synthesizer")
    g.add_edge("worker_essay", "synthesizer")
    g.add_edge("synthesizer", END)
    # 挂内存级 checkpointer：让 state 跨多次 invoke 保持（thread_id 维度），
    # 配合 ask_multi 的查询改写实现多轮指代消解。
    return g.compile(checkpointer=MemorySaver())


# 模块级复用编译好的图：checkpointer 是图级别的，若每次 build_graph() 新建
# 就会顺带新建 MemorySaver，跨轮历史无法保留。故懒加载一份长期持有。
_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def _build_history_text(messages, max_turns: int = 4, drop_last: bool = False) -> str:
    """把历史消息拼成 用户/助手 交替文本，只保留最近 max_turns 轮。

    默认保留传入的全部消息；drop_last=True 用于传进来的是「含当前轮」的完整
    列表、需要把当前这一句排除掉的场景。

    助手上一轮的答复必须留在文本里：里面出现的学校名 / 项目名，正是下一轮
    "那它的截止日期呢" 这类指代要消解的对象。丢掉助手回答，改写器就无从判断
    "它"指的是谁。空则返回 ""。
    """
    msgs = list(messages or [])
    if drop_last:
        msgs = msgs[:-1]
    turns = []
    for m in msgs:
        t = getattr(m, "type", "")
        role = "用户" if t == "human" else ("助手" if t == "ai" else None)
        if role is None:
            continue
        content = getattr(m, "content", "")
        if isinstance(content, str) and content.strip():
            turns.append(f"{role}：{content.strip()}")
    turns = turns[-max_turns * 2:]
    return "\n".join(turns)


def _rewrite_query(query: str, history: str, llm) -> str:
    """多轮查询改写：结合历史把含指代的当前问题改写成语义自包含的问题。

    当前问题已自包含则原样返回。失败（模型异常）也回退到原 query，不阻塞主流程。
    """
    sys = SystemMessage(content=(
        "你是多轮对话的查询改写器。根据【历史对话】把【当前问题】改写成"
        "不依赖上下文、语义自包含的独立问题；若当前问题已经自包含则原样返回。"
        "只返回改写后的问题，不要任何解释或前缀。"
    ))
    user = HumanMessage(content=f"【历史对话】\n{history}\n\n【当前问题】\n{query}\n\n【改写后】")
    try:
        out = llm.invoke([sys, user]).content.strip()
        return out or query
    except Exception:
        return query


def ask_multi(query: str, thread_id: str = "demo") -> dict:
    """单次多智能体问答，返回 {route, answer, sources}。

    sources = 所有 worker 召回文档经全局去重后的来源卡片列表，
    顺序与 synthesizer 看到的 [资料N] 编号完全一致（B 方案）。

    thread_id 维度通过 checkpointer 保留对话历史：下一轮调用时，会基于上一轮
    的 messages 把含指代的 query 改写成自包含问题（写入 state["query"]），
    原始 query 仍进 messages 供再下一轮使用。supervisor / worker 无需改动即可
    理解"那它呢"这类多轮指代。
    """
    graph = _get_graph()
    cfg = {"configurable": {"thread_id": thread_id}}

    # 取上一轮结束后的历史消息，用于本轮查询改写
    snap = graph.get_state(cfg)
    prev_messages = snap.values.get("messages", []) if snap else []
    history = _build_history_text(prev_messages)
    effective_query = _rewrite_query(query, history, llm) if history else query

    result = graph.invoke({
        "messages": [HumanMessage(content=query)],
        "query": effective_query,          # 检索 / 路由用的是消指代后的自包含问题
        "route": [],
        "school_docs": [],
        "admission_docs": [],
        "essay_docs": [],
        "school_plan": "",
        "admission_risk": "",
        "essay_outline": "",
        "answer": "",
    }, config=cfg)
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
