# -*- coding: utf-8 -*-
"""
把 data_loader 读出的文档向量化并持久化到 Chroma。

embedding 走 dashscope 原生 SDK（见 dashscope_embeddings.py），绕开兼容端点的中文
批量调用问题。单条文本强制转 str 并截断 2000 字符；分批入库且失败隔离，单批出错不影响
已入库的部分。已存在的 chroma_db 会先清空重建。
"""
import os
import shutil

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CHROMA_DIR,
    MAX_CONTENT_CHARS,
    EMBED_BATCH,
)
from dashscope_embeddings import DashScopeEmbeddings
from data_loader import load_all


def get_embeddings():
    return DashScopeEmbeddings(batch_size=EMBED_BATCH)


def _safe_doc(d: Document) -> Document:
    """强制 page_content 是 str，且不超过 MAX_CONTENT_CHARS"""
    content = d.page_content
    if not isinstance(content, str):
        content = str(content)
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "..."
    return Document(page_content=content, metadata=d.metadata)


def build():
    docs = load_all()
    print(f"[1/3] 加载文档 {len(docs)} 条")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80)
    split_docs = splitter.split_documents(docs)
    split_docs = [_safe_doc(d) for d in split_docs]

    max_len = max(len(d.page_content) for d in split_docs) if split_docs else 0
    print(f"[2/3] 切片后 {len(split_docs)} 段，最长 {max_len} 字符（限 {MAX_CONTENT_CHARS}）")

    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    embeddings = get_embeddings()
    vectordb = None
    success = 0
    fail_log = []

    print(f"[3/3] 分批向量化中（每批 {EMBED_BATCH} 条，dashscope 原生 SDK）...")
    for i in range(0, len(split_docs), EMBED_BATCH):
        batch = split_docs[i : i + EMBED_BATCH]
        texts = [d.page_content for d in batch]
        metas = [d.metadata for d in batch]
        try:
            if vectordb is None:
                vectordb = Chroma.from_texts(
                    texts=texts,
                    embedding=embeddings,
                    metadatas=metas,
                    persist_directory=CHROMA_DIR,
                )
            else:
                # 后续批：用 self.embedding_function，无需再传
                vectordb.add_texts(texts=texts, metadatas=metas)
            success += len(batch)
            print(f"      [{success:>3}/{len(split_docs)}] OK")
        except Exception as e:
            fail_log.append({
                "start": i,
                "end": i + len(batch) - 1,
                "sample": texts[0][:60] if texts else "",
                "err": str(e)[:200],
            })
            print(f"      [{i:>3}-{i+len(batch)-1}] FAIL: {str(e)[:120]}")

    try:
        cnt = vectordb._collection.count() if vectordb else 0
    except Exception:
        cnt = success

    print(f"[done] 入库 {success}/{len(split_docs)} 条（Chroma 实有 {cnt} 条）")
    if fail_log:
        print(f"!! {len(fail_log)} 批失败，样本前 3 条：")
        for r in fail_log[:3]:
            print(f"   idx={r['start']:>3} {r['sample']!r} | {r['err']}")


if __name__ == "__main__":
    build()