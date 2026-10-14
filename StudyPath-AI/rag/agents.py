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


def _remap_citations(text: str, docs: List[Document], url2gidx: dict) -> str:
    """把 worker 结论里的本库编号 [资料i] 重映射为全局编号。

    worker 看到的是自己那一路文档（编号从 1 起），整合器看到的是三库合并去重后的
    编号，两套编号本来对不上——不改的话，答案里的 [资料N] 和底部来源卡片是两张皮。
    重映射后同一份资料在全文只有一个编号，来源卡片才点得准。
    """
    def repl(m):
        i = int(m.group(1))
        if not (1 <= i <= len(docs)):
            return ""                                  # 越界编号直接丢掉
        url = docs[i - 1].metadata.get("source_url") or ""
        g = url2gidx.get(url)
        return "[资料%d]" % g if g else ""
    return re.sub(r"\[资料(\d+)\]", repl, text)


# worker 也要吃同一条语体约束：它们输出的是给整合器消费的「专家结论」，
# 若这一层就写成通用说明文，整合器拿到的原料已经是那个腔调，最终答复很难掰回来。
WORKER_STYLE_RULE = (
    "表达上用顾问口吻面向申请者，直接给结论；称呼申请者一律用「你」，不要用「您」；"
    "不要写「在数字化浪潮席卷全球的今天」这类宏观铺垫式开场，不要泛泛而谈或写成通用说明文。"
)

# worker 层的院校口径：只认本库确实检索到的院校。
# 起因是实跑里出现过「拿清单外的知名院校当论据、还给它编了语言分要求」，
# 检索没错，是专家在结论里顺手补了资料里没有的常识。
WORKER_FACT_RULE = (
    "只允许引用【检索资料】中实际出现的院校；不得为资料之外的院校"
    "(包括你熟知的知名院校)给出语言成绩、截止日期、学费等要求数值。"
    "用户提到的院校若资料中没有，明确写「知识库未收录该校」，不要用常识补齐。"
)

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
        + WORKER_STYLE_RULE
        + WORKER_FACT_RULE
    ),
    "admission": (
        "你是录取风险评估师。基于【检索资料】中的真实录取/拒信案例，评估用户的申请竞争力。\n"
        "要求：\n"
        "1. 找出与用户背景(专业、GPA、语言成绩)最相似的案例；\n"
        "2. 对比相似案例的录取/被拒结果，给出用户在该档位的定位(冲刺型/稳妥型/保底型)；\n"
        "3. 指出用户的背景短板与风险点；\n"
        "4. 给出补齐建议(如补科研、刷分、换项目)，且建议必须基于资料中出现过的案例/院校。\n"
        "只使用【检索资料】中明确出现的案例与字段，严禁引入资料外的案例、学校或阈值。中文、条理清晰。"
        + WORKER_STYLE_RULE
        + WORKER_FACT_RULE
    ),
    "essay": (
        "你是文书规划师。基于【检索资料】中的真实文书范例，为用户规划申请文书。\n"
        "要求：\n"
        "1. 找出与目标专业/方向最相关的范文；\n"
        "2. 拆解这个范文的写作结构(开头→学术经历→科研/实习→职业规划→结尾)；\n"
        "3. 输出可填充的文书大纲(各段落要点)；\n"
        "4. 列出用户需要准备的素材清单。\n"
        "只使用【检索资料】中明确出现的范文与字段，严禁引入资料外的范文或写法。"
        "范文所属院校的校名、教授姓名、课程编号写进结论会把整合器带偏：这些一律不要出现在你的结论里，"
        "只描述写作结构与可迁移的写法。中文、条理清晰。"
        + WORKER_STYLE_RULE
        + WORKER_FACT_RULE
    ),
}

# key -> 该 worker 的结论在 State 中存放的字段名
CONCL_FIELD = {
    "school": "school_plan",
    "admission": "admission_risk",
    "essay": "essay_outline",
}

# ---- 语体约束：LoRA 实验的蒸馏结论 ----
# 实验①证明「面向具体人说话、不写宏观铺垫」这种表达范式可以跨模型迁移。
# 这里把它固化成 prompt 规则，替代挂 adapter 的权重方案（零成本、可随时改）。
# 抽成常量是为了可测：对照实验构造「旧版」= 拼好的 prompt 里删掉这一段。
SYNTH_STYLE_RULE = (
    "【语体要求】以顾问口吻面向具体申请者，直接给出可执行的建议；"
    "称呼申请者一律用「你」，不要用「您」；"
    "不要写「在数字化浪潮席卷全球的今天」这类宏观铺垫式开场，不要泛泛而谈或写成通用说明文。"
)

FOLLOWUP_RULE = (
    "\n\n【多轮追问模式】检测到这是对话追问(上一轮已有答案)。用户当前问题"
    "只关心某个具体信息点(如截止日期 / 学费 / 材料 / 排名等)。请直接针对该信息点"
    "给出答案，并明确引用上一轮提到的具体实体(学校名、项目名)；"
    "不要重复输出完整的阶段1-5规划模板，也不要重新推荐学校。"
    "若专家结论未覆盖用户问的字段，明确写『知识库未检索到该字段』，不要编造。"
)

# ---- 一致性自检：专治「同一份输出里前后不一致」 ----
# 实跑里抓到的三类自相矛盾（都在同一份规划内）：阶段1 说某校语言达标、阶段2 又说
# 该校要求更高分；阶段1 列 5 所、阶段5 写「当前 3 所」；同一院校的 [资料N] 前后对不上。
# 检索层没错，是整合器落笔前没把三路结论对齐。
CONSISTENCY_RULE = (
    "\n\n【一致性自检·仅内部】以下内容只供你自查，任何一句都不许出现在答案里：\n"
    "动笔前核对三项，冲突时以选校那一份结论为准，核对结果直接体现在正文，不要复述过程：\n"
    "1. 院校清单：全文各阶段只允许出现选校清单内的院校；专家结论里若出现清单外的院校"
    "(常见于范文所属院校、案例所属院校)，一律改写为不点名的通用表述或直接删去，不得保留校名。"
    "尤其是阶段3：范文出自哪所学校，只写「范文」或「目标项目」，绝不写出该校校名、教授姓名、"
    "课程编号、课程名、实验室名、研究中心名或任何项目代号——这些知识库都没有收录，写出即为编造；"
    "需要指代时只写「该项目的相关课程与实验室资源」；"
    "也不要建议申请者去写出具体课程名/module 名/实验室名/研究组名（同样会在正文里留下无处可查的名字）。"
    "同一所院校的语言成绩、截止日期、学费在全文只允许有一组数字。\n"
    "2. 数量口径：凡提到院校所数，必须等于清单里实际列出的院校条数。\n"
    "3. 引用形式：全文只用 [资料N] 表示引用，N 必须是单个数字(如 [资料3])。"
    "不得写成区间 [资料1-7]、不得并列多个编号，更不得写成 [资料中录取评估部分] 这类文字引用；"
    "一句话引用多条资料，就连续写多个 [资料N]。\n"
    "4. 事实边界：不得编造资料里没写过的流程性规定——如「不接受邮件补交」"
    "「需额外上传预算说明」「必须在网申系统勾选某课程」这类细则，资料没写就不许写；"
    "同样不得编造面试形式与时长、录取委员会电话核实材料真伪、成绩认证机构、"
    "申请费凭证要求等资料里没有的流程细节；"
    "也不得描述任何教授的研究方向、论文题目或研究成果（知识库没有教授名录，写出即为编造）；"
    "用「某实验室近2年某某论文」「某教授的某某工具课程」这类泛指写法照样算编造，同样不得出现，"
    "需要指代时只写「该项目的相关课程与实验室资源」；"
    "说「该校不要求 X」之前先确认资料里确实没有这项要求，没有依据的否定句同样算编造。\n"
    "【面向申请者直接作答】只给结论，不要叙述你是怎么得出结论的：\n"
    "不得写「依据…结论」「按…范围执行」「经核对」「已比对」「已确认编号」这类过程说明；\n"
    "不得出现任何内部环节、模块或数据结构的名称，凡属系统内部叫法的词一律换成面向申请者的说法"
    "(如把「可引用的院校范围」说成「可申请的院校」，把「条件未达标」直接说成你的条件差在哪)；\n"
    "方括号内只允许是单个 [资料N] 引用，不得出现任何板块名或标签名。"
)


def time_rule(today=None) -> str:
    """时间口径：把「今天」注入 prompt，让模型知道哪些资料是往季的。

    抽成函数（而不是内联字符串）是为了让日期可被参数覆盖，方便测试与对照实验。

    规则只允许「原样引用 + 加标注」，并给了反例——实测模型会把 2025 的截止日
    顺手改成 2026 让它看起来更新，等同于篡改原文，必须用具体例子堵死。
    """
    from datetime import date
    d = today or date.today()
    return (
        "\n\n【数据时效】当前日期为 %s。"
        "判断「最新」「当前申请季」一律以该日期为锚，不得以资料中出现的最大年份为锚；"
        "截止日期已早于该日期的记录属于往季，不得称作「最新」。"
        "若用户在问题中说明了目标入学时间或申请季（如「2027 Fall 入学」），以用户所说的为准；"
        "用户未说明时，以当前日期为锚判断最近一个可申请季节，并说明知识库是否覆盖该季节。"
        "资料里的日期与年份一律原样引用："
        "资料写 2025-12-15 就必须写 2025-12-15，不得改成 2026-12-15；"
        "资料没写年份就不许自己补年份。特别注意：资料里的截止日常写成「Dec 15 (Fall)」"
        "「Feb 1 (Fall)」这类不带年份的形式，这是正常的(Fall 截止日每年相同)。"
        "遇到这类值必须原样照抄，一个字都不许加年份，也不许据此推算「X月X日前完成」这类前置日期；"
        "只有资料本身写了年份时(如「Jan 6, 2026」)，才可以带上那个年份。"
        "若某日期早于当前日期，只能原样写出并在其后标注"
        "「（往季参考，以官网为准）」，倒排表中可以保留该日期，但必须带上这个标注。"
        "若资料中带年份的截止日期均早于当前日期（即知识库未覆盖当前申请季），说明知识库整体是往季数据："
        "阶段4 可以照常列出各校截止日与提交节点，但每一条末尾都必须标注「（往季参考，以官网为准）」，"
        "并在该阶段开头声明一句「知识库收录的截止日为 20XX 申请季，最新信息以官网为准」，"
        "同时给出「各校截止日前 2–3 周完成提交」这类相对节奏。"
        "【写法一致】阶段4 引用的截止日，日期本身的写法必须与阶段1 逐字一致："
        "阶段1 写成不带年份的（如「Dec 15 (Fall)」），阶段4 也必须不带年份，严禁补一个年份；"
        "阶段1 带年份的（如「Jan 6, 2026」）才带。「（往季参考，以官网为准）」是附加说明，不算写法不一致。"
        "同一所院校的截止日在全文只允许一种写法。全文不要同时出现两个不同的申请季年份。" % d.isoformat()
    )


def synth_system_prompt(is_followup: bool, today=None, facts: str = "") -> str:
    """整合器的 system prompt 全文。

    抽成函数而非内联字符串，是为了让对照实验能精确地「只摘掉语体那一段」，
    其余逐字不变——否则两段 prompt 各自维护，差异就不再是唯一变量。

    facts：确定性事实块（门槛核对 + 截止日期原文清单），由调用方算好后传入，
    插在角色说明之后、行为规则之前。语体规则固定在**最末尾**——实测规则全堆在
    后面时，夹在中间的语体要求会被稀释，人称会退回客服腔的「您」。
    """
    followup_rule = FOLLOWUP_RULE if is_followup else ""
    return (
        "你是 StudyPath 留学规划整合器。你已收到三位专家的结构化结论：\n"
        "选校策略(冲刺/稳妥/保底)、录取风险评估(定位/风险点)、文书规划(结构/大纲)。\n"
        "请将其整合为一份【可执行的留学申请规划】，严格按时间轴组织：\n"
        "阶段1 选校定稿 → 阶段2 材料准备 → 阶段3 文书写作 → "
        "阶段4 网申提交(含截止日期checklist) → 阶段5 面试准备。\n"
        "每个阶段给出关键任务与优先级。严格基于专家结论，不要补充专家结论之外的信息；\n"
        "若【文书规划结论】为空(essay worker 未命中)，阶段3 文书写作需明确标注『未检索到同方向范文，以下为通用写作框架』，不得伪装成来自知识库。\n"
        "引用资料时用 [资料N] 标注。中文，用「### 阶段N + 列表」组织。\n"
        + (facts + "\n" if facts else "")
        + "【格式铁律】不要使用 markdown 表格(单元格内换行会显示错乱)，"
        "一律用「### 小标题 + 无序列表(- 要点)」组织；"
        "不要使用 <br>/<br/> 标签，需换行直接用真实换行符；"
        "只引用资料中明确写出的字段名，不要自行发明字段名；"
        "引用资料时用 [资料N] 标注，N 来自资料块开头的编号。"
        + CONSISTENCY_RULE
        + time_rule(today)
        + followup_rule
        + SYNTH_STYLE_RULE
    )


# ---------------------------------------------------------------- 门槛核对
# 整合器最容易犯的错不是措辞，而是「为了给出建议而自己造论据」：
# 实测它会写出「资料明确指出 Cambridge 不设授课型 CS 硕士」这类资料里根本没有的结论，
# 也会把用户雅思 7.0 不达标的学校直接放进冲刺档。这类问题 prompt 措辞只能压低概率，
# 不能消除——所以这里改用确定性代码，先把「用户条件 vs 清单内每校门槛」算一遍，
# 结果作为只读事实块喂给整合器，同时给出院校白名单。
#
# 设计原则：能算出可比数值才下结论；算不出来（英式 2:1、双口径混写）一律标
# 「需人工核对」，绝不猜——宁可让答案说"这里要你自己确认"，也不能给错的门槛。

def _first_num(text):
    """取文本里第一个数字，取不到返回 None。'7.0 (6.5)' -> 7.0"""
    m = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    return float(m.group(0)) if m else None


def _parse_gpa_min(text):
    """把院校 gpa_min 的自由文本解析成 (量纲, 阈值)。

    量纲取 'scale4' / 'scale100'；返回 (None, None) 表示该字段无法自动核对。
    英式学位等级（2:1 / First class）与「4 分制、百分制混写」都归入不可核对，
    因为它们和用户自报的 GPA 之间没有可靠的换算关系。
    """
    s = str(text or "").strip()
    if not s:
        return (None, None)
    if re.search(r"(2:1|first\s*class|second\s*class|high\s*2)", s, re.I) and "/" not in s:
        return (None, None)
    if re.search(r"211|985|双一流|双非", s):
        return (None, None)              # 分档门槛（211/985 一套、双非一套），与用户单一 GPA 不可比
    if len(re.findall(r"\d{2,3}", s)) > 1:
        return (None, None)              # 多个候选取值（区间或多口径），无法唯一确定，宁可标需人工核对
    m100 = re.search(r"(\d{2,3})\s*(?:%|/100)", s)
    m4 = (re.search(r"(\d\.\d+)\s*/\s*4(?:\.0)?", s)
          or re.search(r"(?<![\d.])(\d\.\d+)(?![\d])", s))
    if m100 and m4:
        return (None, None)              # 同时给了两种口径，无法唯一确定
    if m100:
        return ("scale100", float(m100.group(1)))
    if m4:
        return ("scale4", float(m4.group(1)))
    mn = re.search(r"(\d{2,3})", s)
    if mn:
        return ("scale100", float(mn.group(1)))
    return (None, None)


def _profile_scale(gpa_num, raw):
    """判断用户自报 GPA 是 4 分制还是百分制。"""
    s = str(raw or "")
    if "%" in s or "/100" in s:
        return "scale100"
    if "/4" in s:
        return "scale4"
    return "scale4" if gpa_num <= 4.0 else "scale100"


def _extract_profile(query: str) -> dict:
    """从用户问题里抽硬性条件（GPA / 雅思 / 托福）。

    只做一次轻量 JSON 抽取，抽不到就返回 {}，调用方据此跳过核对——
    没有条件时必须什么都不说，而不是补一个默认值去比。
    """
    try:
        sys = SystemMessage(content=(
            "从用户问题中抽取留学申请的硬性条件，只返回 JSON，不要任何解释。"
            '格式：{"gpa": "...", "gpa_scale": "4或100", "ielts": "...", "toefl": "..."}。'
            "gpa 填用户原话里的数值（如 3.6 或 85），gpa_scale 填 4 或 100；"
            "ielts/toefl 填总分。用户没提到的字段填 null，不要猜测、不要给默认值。"
        ))
        resp = llm.invoke([sys, HumanMessage(content=query)])
        d = json.loads(_extract_json(resp.content))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _gate_check(profile: dict, school_docs: List[Document]):
    """逐校比对用户自报条件与资料原文门槛，返回 (事实块文本, 未达标校名列表)。"""
    if not profile or not school_docs:
        return ("", [])
    g_raw = profile.get("gpa")
    ielts_u = _first_num(profile.get("ielts"))
    toefl_u = _first_num(profile.get("toefl"))
    g_u = _first_num(g_raw)
    u_scale = _profile_scale(g_u, g_raw) if g_u is not None else None

    lines, fails = [], set()
    for d in school_docs:
        name = d.metadata.get("school_name") or ""
        m = re.search(r"最低申请要求：GPA (.*?)，托福 (.*?)，雅思 (.*?)，GRE",
                      d.page_content or "")
        if not m:
            continue
        g_min_txt, t_min_txt, i_min_txt = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        verdicts = []

        i_min = _first_num(i_min_txt)
        if ielts_u is not None:
            if not i_min_txt:
                verdicts.append("资料未给雅思门槛")
            elif i_min is None:
                verdicts.append("雅思门槛「%s」需人工核对" % i_min_txt)
            elif ielts_u < i_min:
                verdicts.append("雅思未达标（要求 %s，用户 %s）" % (i_min_txt, profile.get("ielts")))
                fails.add(name)
            else:
                verdicts.append("雅思达标（要求 %s）" % i_min_txt)

        t_min = _first_num(t_min_txt)
        if toefl_u is not None:
            if not t_min_txt:
                verdicts.append("资料未给托福门槛")
            elif t_min is None:
                verdicts.append("托福门槛「%s」需人工核对" % t_min_txt)
            elif toefl_u < t_min:
                verdicts.append("托福未达标（要求 %s，用户 %s）" % (t_min_txt, profile.get("toefl")))
                fails.add(name)
            else:
                verdicts.append("托福达标（要求 %s）" % t_min_txt)

        scale, thr = _parse_gpa_min(g_min_txt)
        if not g_min_txt:
            verdicts.append("资料未给 GPA 门槛")
        elif u_scale and scale and thr is not None:
            if u_scale != scale:
                verdicts.append("GPA 门槛「%s」与用户口径不同，需人工核对" % g_min_txt)
            elif g_u < thr:
                verdicts.append("GPA 未达标（要求 %s，用户 %s）" % (g_min_txt, g_raw))
                fails.add(name)
            else:
                verdicts.append("GPA 达标（要求 %s）" % g_min_txt)
        else:
            verdicts.append("GPA 门槛「%s」需人工核对" % g_min_txt)

        lines.append("- %s（%s）：%s" % (name, d.metadata.get("program_name") or "", "；".join(verdicts)))

    if not lines:
        return ("", [])
    head = "用户自报条件：" + "，".join([x for x in [
        ("GPA %s" % g_raw) if g_raw else "",
        ("雅思 %s" % profile.get("ielts")) if profile.get("ielts") else "",
        ("托福 %s" % profile.get("toefl")) if profile.get("toefl") else "",
    ] if x])
    return (head + "\n" + "\n".join(lines), sorted(fails))


def _gate_block(profile: dict, school_docs: List[Document]) -> str:
    """门槛核对 + 院校白名单，合成一段只读事实块，拼到整合器 system prompt 末尾。"""
    facts, fails = _gate_check(profile, school_docs)
    names = []
    for d in school_docs:
        n = d.metadata.get("school_name") or ""
        if n and n not in names:
            names.append(n)
    if not facts and not names:
        return ""

    parts = ["\n\n【以下是已核实的事实，不得改写、不得推翻；本段只供你判断，措辞不得出现在答案里】"]
    if facts:
        parts.append("用户条件与各校要求的匹配情况:\n" + facts
                     + "\n以上每所院校的门槛值只能引用该校资料里自己写出的内容——"
                       "不得把其他院校的门槛、录取平均值或备注挪到该校名下"
                       "（实测出现过把 NYU 的「录取平均3.6」写进 USC 的门槛理由）。")
        if fails:
            parts.append("条件未达标的院校：" + "、".join(fails)
                         + "。这些院校不得列入冲刺或稳妥档；若仍需保留，"
                           "必须在该校后面显式写出「条件未达标，需先补齐」并给出补齐路径。")
    if names:
        parts.append("可以引用的院校范围（全文只允许出现以下院校名，范文与案例所属院校也不例外；"
                     "范围之外的院校名一律改写为不点名表述，"
                     "连同它们的教授姓名、课程编号、实验室名一并不得出现）:\n- " + "\n- ".join(names))
    return "\n".join(parts)


def _deadline_block(school_docs: List[Document]) -> str:
    """把院校资料里的 deadline 原文抽成只读清单，注入整合器。

    deadline 在这条链上被改写两次（worker 先简化成一句话，整合器再"生成"一个
    整齐的日期），实测 8 条里 7 条与原文对不上：Imperial 的 Oct 15 原文里不存在，
    Rolling 是从另一所学校串过来的，SNU 的日期挂到了 UW 的值上。
    做法与门槛核对一致——不给模型生成空间，只给复制素材。
    """
    rows, seen = [], set()
    for d in school_docs:
        name = d.metadata.get("school_name") or ""
        m = re.search(r"申请截止：(.*?)。", d.page_content or "")
        val = m.group(1).strip() if m else ""
        if not name or not val:
            continue
        key = (name, val)
        if key in seen:
            continue
        seen.add(key)
        rows.append((name, d.metadata.get("program_name") or "", val))
    if not rows:
        return ""
    lines = ["- %s（%s）：%s" % (n, p, v) for n, p, v in rows]
    return ("\n\n【截止日期原文清单，以下为硬事实，不得改写】\n"
            "凡是提到下列院校的申请截止日期，必须逐字复制对应值：不许自己生成日期，"
            "不许把某校的日期挪给另一校，也不许改用清单外的日期。"
            "清单里没写年份的，输出里同样不写年份；日期已早于今天的，"
            "在给出日期后补「（往季参考，以官网为准）」即可，不必因此删掉日期。\n"
            + "\n".join(lines))


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
    return _clean_answer(resp.content, max_n=len(docs))   # 编号上限=本库资料数


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
    # 来源(与 ask_multi 同样去重逻辑，保证 [资料N] 编号对齐)
    all_docs: List[Document] = []
    for key in ("school", "admission", "essay"):
        all_docs.extend(state.get(f"{key}_docs", []))
    deduped = _dedup_docs(all_docs)
    sources_text = "\n".join(
        f"[{i+1}] {d.metadata.get('source_url', '')}" for i, d in enumerate(deduped)
    )
    # url -> 全局编号：worker 结论里的本库编号靠它换算成整合器的全局编号
    url2gidx = {}
    for i, d in enumerate(deduped, 1):
        u = d.metadata.get("source_url") or ""
        if u and u not in url2gidx:
            url2gidx[u] = i

    sections = []
    for key, field, title in (("school", "school_plan", "选校策略结论"),
                              ("admission", "admission_risk", "录取风险评估结论"),
                              ("essay", "essay_outline", "文书规划结论")):
        txt = state.get(field, "")
        if txt:
            sections.append(f"【{title}】\n"
                            + _remap_citations(txt, state.get(f"{key}_docs", []), url2gidx))
    expert_text = "\n\n".join(sections)

    # 多轮追问检测：messages 里已有上一轮的助手答案，即说明本轮是对话追问。
    # add_messages reducer 保证历史跨 invoke 累积，故可直接从 state 判断。
    is_followup = any(getattr(m, "type", "") == "ai" for m in state.get("messages", []))

    # 门槛核对只在有院校召回时才有意义；没有院校召回就不额外花一次 LLM 调用去抽条件
    profile = _extract_profile(state["query"]) if state.get("school_docs") else {}
    facts = (_gate_block(profile, state.get("school_docs", []))
             + _deadline_block(state.get("school_docs", [])))

    sys = SystemMessage(content=synth_system_prompt(is_followup, facts=facts))
    user = HumanMessage(content=(
        f"{expert_text}\n\n【可引用来源】\n{sources_text}\n\n"
        f"【用户问题】\n{state['query']}\n\n【整合后的申请规划】"
    ))
    resp = llm.invoke([sys, user])
    answer = _clean_answer(resp.content, max_n=len(deduped))
    # 自造日期收敛：白名单 = 本次召回院校资料的原文
    answer = _strip_unbacked_dates(
        answer, [d.page_content or "" for d in state.get("school_docs", [])])
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


def _normalize_citations(text: str, max_n=None) -> str:
    """把模型偷懒写的区间/并列引用还原成逐个 [资料N]，并丢掉不存在的编号。

    模型经常把 [资料1] [资料2] ... [资料7] 压成 [资料1-7] 或 [资料1-5,7]，
    甚至写成 [资料中录取评估部分] 这类文字引用；更麻烦的是它会把知识库里的
    case_024 / case_025 当成引用号，编出 [资料24] [资料25] 这种根本没来源的编号。
    前者让"编号可逐条核对"失效，后者是伪引用。这里做确定性归一，不依赖模型自觉。
    max_n 传当前可引用资料条数时，超出范围的编号会被删掉。
    """
    def repl(m):
        body = m.group(1)
        nums = []
        for part in re.split(r"[,，、]", body):
            part = part.strip()
            rng = re.match(r"^(\d+)\s*[-–—~]\s*(\d+)$", part)
            if rng:
                a, b = int(rng.group(1)), int(rng.group(2))
                if a <= b and b - a <= 30:      # 防御异常区间
                    nums.extend(range(a, b + 1))
            elif part.isdigit():
                nums.append(int(part))
        if max_n:
            nums = [n for n in nums if 1 <= n <= max_n]
        if not nums:
            return m.group(0) if max_n is None else ""   # 编号不存在 → 删掉
        seen, out = set(), []
        for n in nums:
            if n not in seen:
                seen.add(n)
                out.append("[资料%d]" % n)
        return " ".join(out)
    # 文字伪引用（如 [资料中…]）直接删除，它不是可核对的编号。
    # 长度不设上限——模型会把整段内部说明塞进方括号（实测出现过一整句
    # 「[资料中文书规划未命中…故不引用 essay_021 等编号…]」）。
    text = re.sub(r"\[资料中[^\]]*\]", "", text)
    return re.sub(r"\[资料([0-9,，、\-–—~\s]+)\]", repl, text)


_COURSE_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?!(?:GRE|GPA|TOEFL|IELTS|SAT|ACT|AP|QS|US|UK|STEM)\b)"
    r"[A-Z]{2,4}[ \-]?\d{3}(?!\d)"
)
_LAB_NAME_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9@&._\-]*(?:\s+[A-Za-z&][A-Za-z0-9@&._\-]*){0,4}\s*"
    r"(?:实验室|研究中心|Labs?\b|Seminar\b)"
)
_LAB_FOR_RE = re.compile(r"Labs?\s+for\s+(?:[A-Za-z][A-Za-z0-9@&._\-]*\s*){1,3}")
# 学历认证机构名：知识库没有这一字段，实测模型会顺手写「如 USC 要求 WES 认证」。
# 认证本身是常识，但"某校要求某认证"是无出处的断言，统一降级为不点名的说法。
_CERT_RE = re.compile(r"(?:WES|ECE|CDGDC|CHESICC|学信网)\s*(?:认证)?")


def _neutralize_refs(text: str) -> str:
    """把知识库没有收录的课程编号、实验室/研究中心名换成通用指代。

    知识库只有院校/项目/门槛/截止日/案例/范文这几类字段，既没有课程表也没有实验室名录。
    实测模型会凭常识补出「CS 599」「GamePipe 实验室」这类听起来很具体、实际无处可查的名字，
    对「每条都能溯源」是硬伤；措辞规则两次都没压住，这里做确定性替换兜底。

    只替换明显属于"专有资源名"的形式，中文泛指（如「建议联系实验室导师」）不受影响。
    """
    text = _LAB_FOR_RE.sub("相关实验室", text)
    text = _LAB_NAME_RE.sub("相关实验室", text)
    text = _COURSE_CODE_RE.sub("相关课程", text)
    text = _CERT_RE.sub("官方成绩认证", text)
    # 原文可能写成「WES/官方成绩认证」，替换后重复 → 去重
    text = re.sub(r"(官方成绩认证)(?:\s*[/、,，]\s*官方成绩认证)+", r"\1", text)
    # ETS 送分代码：知识库没有这个字段（school 表只有 17 个字段，无 code 列）。
    # 实测整合器会凭记忆逐校补出「（Code: 2724）」——既属越界引入，又无法核验对错。
    # 一律抹掉代码本身，只留「送分」这个动作。
    text = re.sub(r"[（(]\s*(?:ETS\s*)?[Cc]ode\s*[:：]?\s*\d{3,4}\s*[）)]", "", text)
    text = re.sub(r"(?:ETS\s*)?送分代码\s*[:：]?\s*\d{3,4}", "送分代码以官网为准", text)
    text = re.sub(r"(?:ETS\s*)?[Cc]ode\s*[:：]\s*\d{3,4}", "", text)
    return text


def _strip_internal(text: str) -> str:
    """把答案里残留的内部叫法换成面向申请者的说法。

    事实块（门槛/截止日）里带着"范围""匹配情况"这类内部措辞，模型偶尔会照抄，
    实测出现「严格依据门槛核对结果与选校策略结论，完成院校三档定稿」这种过程叙述。
    措辞规则压不干净，这里做确定性替换兜底。
    """
    for a, b in (
        ("院校白名单", "可申请的院校"),
        ("白名单", "可申请的院校"),
        ("门槛核对结果", "你与要求的差距"),
        ("门槛核对", "条件匹配"),
        ("硬性门槛", "申请要求"),
        ("资料验证结果", "条件匹配"),
        ("资料验证", "条件匹配"),
        ("系统预计算", ""),
        ("选校策略结论", "选校结论"),
        ("录取风险评估结论", "录取评估结论"),
        ("录取评估结论", "录取评估"),
        ("风险评估结论", "风险评估"),
        ("文书规划结论", "文书规划"),
        ("可引用的院校范围", "可申请的院校"),
        ("可引用来源", "来源"),
        ("已验证的", ""),
        # 纯过程套话（实测原文）；只精确删这两串，不做模式匹配——
        # 「严格依据风险与条件」「严格依据官网流程准备」都是有内容的句子，按模式删会啃掉正文。
        ("严格依据硬性条件匹配与分档结论", ""),
        ("严格依据硬性条件匹配", ""),
        ("严格基于专家结论与资料匹配", ""),
        ("基于专家结论与资料匹配", ""),
        ("专家结论", "分析结论"),
    ):
        text = text.replace(a, b)
    # 开头的过程叙述套头（「依据…，」）整句去掉——结论不需要交代依据。
    # 注意：「严格依据」不能按模式删——实测「严格依据风险与条件」「严格依据官网流程准备」
    # 都是有内容的话，按模式删会把正文啃掉。只对确认为纯过程套话的那几种固定串做替换。
    text = re.sub(r"^\s*(?:[-*·]\s*)?依据[^，。；\n]{0,40}[，,]\s*", "", text, flags=re.M)
    text = re.sub(r"[，,]\s*(?=[：:])", "", text)          # 摘句后残留的「，：」清掉
    # 书名号包起来的内部板块名（如【选校结论】【可引用来源】）——不是给用户看的
    text = re.sub(r"【[^】]{0,14}(?:结论|来源|范围|清单|自检|核对|预计算)[^】]{0,6}】", "", text)
    text = re.sub(r"[，,]\s*([，、])", r"\1", text)      # 替换后可能出现的连续标点
    text = re.sub(r"[（(]\s*[）)]", "", text)            # 摘句后留下的空括号
    text = re.sub(r"【\s*】", "", text)                  # 摘名后留下的空书名号
    return text


def _clean_answer(text, max_n=None):
    """后处理兜底：清理标签、重复标题符号、markdown 表格、引用格式、多余空行。

    max_n = 当前答案可引用的资料条数；传了就顺带校验 [资料N] 是否越界。
    """
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<BR>", "\n")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")   # 模型偶发输出 HTML 实体
    text = re.sub(r"#{2,}\s*#{2,}\s*", "### ", text)   # 修复 "### ### 阶段" 重复符号
    text = _strip_internal(text)                         # 内部叫法 → 面向申请者的说法
    text = re.sub(r"\s*case[_\-]?\d+\s*", "某录取案例", text)   # 内部案例编号不外露
    text = re.sub(r"\s*essay[_\-]?\d+\s*", "某文书范例", text)  # 内部文书编号不外露
    # 「所有/全部已录案例…」是拿召回到的几条去概括整个案例库，表述下得太满；
    # 改成「本次检索到的」后，说法与事实（只基于召回样本）才一致。
    text = re.sub(r"(?:所有|全部)(?:的)?(?:已录|录取|被录)案例", "本次检索到的录取案例", text)
    text = _neutralize_refs(text)                        # 未收录的课程号/实验室名 → 通用指代
    text = _normalize_citations(text, max_n)             # 区间/并列/伪引用/越界编号归一
    text = re.sub(r"\]\[", "] [", text)                 # 修复 [资料1][资料2] 挤在一起 → [资料1] [资料2]
    text = _tables_to_lists(text)                        # 表格转列表，防渲染错乱
    text = re.sub(r"\s+([，。；、])", r"\1", text)        # 清掉标点前多余空格
    text = re.sub(r"(?<=\S) {2,}", " ", text)            # 行内连续空格压成一个（不动缩进）
    text = re.sub(r"[ \t]+\n", "\n", text)     # 清掉行尾空白
    text = re.sub(r"\n{3,}", "\n\n", text)     # 合并 >2 个连续空行为 1 个
    return text.strip()


# ---------------------------------------------------------------- 自造日期收敛
# 实测整合器会造两类知识库里没有的日期（都违反 time_rule）：
#   ① 给无年份的截止日补年份——原文 `Feb 1 (Fall)` 被写成 `Feb 1, 2025`；
#   ② 由截止日倒推出的具体提交日——原文 `Jan 15` 推出「最晚 2026-01-08 提交」。
# prompt 措辞两次都没压住，做法与门槛核对同构：拿召回的 KB 原文当白名单，
# 命不中的年份一律剥掉——不给模型生成空间，只做减法。
_MON_DD_YEAR_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\s*,\s*(20\d\d)")
_CN_DATE_RE = re.compile(r"(20\d\d)\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?")
_DERIVED_SUBMIT_RE = re.compile(
    r"(?:最晚|不迟于|不晚于|目标|建议)\s*(?:20\d\d\s*[-/年.]\s*)?\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?\s*(?:前)?\s*(?=提交)")
# 「某」字打头的泛指指代同样在编：实测会写出「某实验室近2年Raft优化论文」
# 「某教授eBPF观测工具课程」——知识库没有实验室/教授名录，泛指也是虚构。
_VAGUE_REF_RE = re.compile(
    r"[（(][^）)]{0,80}(?:某实验室|某教授|某研究组|某研究中心|某课题组)[^）)]{0,80}[）)]")


def _strip_unbacked_dates(text: str, raw_deadlines=None) -> str:
    """剥掉答案里没有 KB 出处的年份与倒推日期。

    raw_deadlines：本次召回资料的原文（列表）。只从这些原文里认合法日期。
    """
    allow = set()
    for d in (raw_deadlines or []):
        for m in _MON_DD_YEAR_RE.finditer(str(d)):
            allow.add((m.group(1).lower()[:3], int(m.group(2)), m.group(3)))

    def repl_mon(m):
        key = (m.group(1).lower()[:3], int(m.group(2)), m.group(3))
        return m.group(0) if key in allow else "%s %s" % (m.group(1), m.group(2))

    def repl_cn(m):
        # 有「日」就留「M月D日」，只有「Y年M月」就留「M月」——年份一律剥掉
        return ("%s月%s日" % (m.group(2), m.group(3))) if m.group(3) else ("%s月" % m.group(2))

    text = _MON_DD_YEAR_RE.sub(repl_mon, text)
    # KB 的 deadline 字段里没有任何「年月日」中文格式 → 出现的都是自造，去掉年份
    text = _CN_DATE_RE.sub(repl_cn, text)
    # 无年份的倒推提交日（「最晚 12月1日前提交」）同样不许留，换成相对说法
    text = _DERIVED_SUBMIT_RE.sub("截止日前 2–3 周", text)
    # 「某实验室…论文」这类泛指指代整段括注删掉
    text = _VAGUE_REF_RE.sub("", text)
    return text


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
