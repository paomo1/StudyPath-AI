# -*- coding: utf-8 -*-
"""
检索 + 生成的问答链，用 LangChain LCEL 组装。

    question
      ├─> retriever -> format_docs  => context
      └─> RunnablePassthrough      => question
    (context, question) -> PROMPT -> ChatOpenAI(qwen-plus) -> StrOutputParser

只基于检索到的资料回答，附来源，不编造。
"""
from urllib.parse import urlparse

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, CHAT_MODEL, CHROMA_DIR, TOP_K
)
from dashscope_embeddings import DashScopeEmbeddings
from query_norm import normalize_query  # 查询侧学校别名归一化（修 "Imperial" 类裸别名召回失败）

PROMPT = ChatPromptTemplate.from_template(
    """你是 StudyPath，一个留学申请规划助手。请严格基于下面的【检索到的资料】回答用户问题。

规则：
1. 只能使用资料中的事实，绝对不要编造院校、排名、分数或案例。
2. 如果资料不足以回答，明确说"资料中暂无相关信息"，并建议用户补充哪类数据。
3. 用中文回答，条理清晰，必要时分点。
4. 回答末尾附上引用来源（资料里的 source_url 或来源说明），方便用户核实。

【检索到的资料】
{context}

【用户问题】
{question}

【回答】
"""
)


def format_docs(docs):
    """把检索到的 Document 列表拼成带编号和来源的上下文文本"""
    out = []
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("source_url") or d.metadata.get("source") or d.metadata.get("source_sheet", "")
        sheet = d.metadata.get("source_sheet", "")
        out.append(f"[资料{i}] ({sheet})\n{d.page_content}\n来源: {src}")
    return "\n\n".join(out)


def get_embeddings():
    return DashScopeEmbeddings()


def build_llm():
    """构建对话 LLM（qwen-plus，走 DashScope 的 OpenAI 兼容端点）。

    单独抽出，供需要自定义上下文的调用方复用——典型场景是 demo 取证：
    用「已经检索好的 docs」生成回答，避免重复检索导致
    「落盘展示的召回结果」与「真正喂给模型的上下文」不同源。
    """
    return ChatOpenAI(
        model=CHAT_MODEL,
        openai_api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        temperature=0.3,
        max_tokens=1024,
    )


def build_qa():
    embeddings = get_embeddings()
    vectordb = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    retriever = vectordb.as_retriever(
        search_type="mmr",  # 最大边际相关性：相关 + 多样，避免 4 条都是相似内容
        search_kwargs={"k": TOP_K, "fetch_k": 20},  # 先取 20 候选再用 MMR 精选出 8 条最相关且多样的
    )
    llm = build_llm()
    chain = (
        {
            # 检索前先做别名归一化；question 仍传原文，保证 LLM 看到的就是用户原话
            "context": RunnableLambda(normalize_query) | retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | PROMPT
        | llm
        | StrOutputParser()
    )
    return chain


def answer_from_docs(question: str, docs) -> str:
    """基于【已检索好的 docs】生成回答，不再重复检索。

    demo 取证场景专用：让落盘的召回结果与喂给 LLM 的上下文严格同源，
    避免"展示的是 A 次检索、生成用的是 B 次检索"这种对不上号的情况。
    """
    chain = PROMPT | build_llm() | StrOutputParser()
    return chain.invoke({"context": format_docs(docs), "question": question})


def ask(question: str) -> str:
    """单次问答（给测试/脚本调用）"""
    chain = build_qa()
    return chain.invoke(question)


def get_retriever(sheet=None):
    """可指定 sheet 过滤的检索器，供多智能体 worker 复用。"""
    embeddings = get_embeddings()
    vectordb = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    kwargs = {"k": TOP_K, "fetch_k": 20}
    if sheet:
        kwargs["filter"] = {"source_sheet": sheet}
    return vectordb.as_retriever(search_type="mmr", search_kwargs=kwargs)


def _source_item(d) -> dict | None:
    """从 Document metadata 提取来源卡片所需字段（URL / 学校 / 项目 / 库 / 域名）。"""
    url = d.metadata.get("source_url") or ""
    if not url:
        return None
    domain = urlparse(url).netloc or ""
    if domain.startswith("www."):
        domain = domain[4:]
    return {
        "url": url,
        "school": d.metadata.get("school_name") or "",
        "program": d.metadata.get("program_name") or "",
        "sheet": d.metadata.get("source_sheet") or "",
        "domain": domain,
    }


def retrieve_docs(query: str, sheet=None):
    """只检索不生成，返回 (召回 Document 列表, 来源卡片列表)。

    返回原始 Document 列表是为了让多智能体上层做「全局统一编号」，
    避免每个 worker 各自编号导致 [资料1] 重复、答案引用与底部来源卡片对不上。
    """
    retriever = get_retriever(sheet)
    docs = retriever.invoke(normalize_query(query))  # 多智能体链路同样做别名归一化
    items = [_source_item(d) for d in docs]
    items = [x for x in items if x]
    return docs, items


def retrieve_only(query: str, sheet=None):
    """只检索不生成，返回 (格式化上下文文本, 来源卡片列表)。

    兼容旧接口（如 demo_capture.py），内部复用 retrieve_docs。
    """
    docs, items = retrieve_docs(query, sheet)
    return format_docs(docs), items


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "CMU 的计算机硕士项目要求和截止日期是什么？"
    print(ask(q))
