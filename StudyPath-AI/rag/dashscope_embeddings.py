# -*- coding: utf-8 -*-
"""
dashscope 原生 SDK 的 LangChain Embeddings 适配层。

兼容端点对中文批量 embedding 会返回 400 InvalidParameter，故改走原生
dashscope.TextEmbedding.call。

    from dashscope_embeddings import DashScopeEmbeddings
    emb = DashScopeEmbeddings(batch_size=10)
    vectors = emb.embed_documents(["text1", "text2"])
"""
import dashscope
from dashscope import TextEmbedding
from langchain_core.embeddings import Embeddings

from config import DASHSCOPE_API_KEY, EMBED_MODEL

# 设置全局 api_key（dashscope SDK 必走此路径）
dashscope.api_key = DASHSCOPE_API_KEY


class DashScopeEmbeddings(Embeddings):
    """LangChain Embeddings 接口的 dashscope 原生 SDK 实现"""

    def __init__(self, model: str = EMBED_MODEL, batch_size: int = 10):
        self.model = model
        self.batch_size = batch_size

    def _call(self, texts: list[str], batch_label: str = "") -> list[list[float]]:
        """内部批量调 dashscope 原生 SDK（手动分批避免上限）"""
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = [str(t) for t in texts[i : i + self.batch_size]]
            resp = TextEmbedding.call(model=self.model, input=batch)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"dashscope err: code={resp.code} msg={resp.message}"
                    f" | {batch_label} idx={i}-{i+len(batch)-1}"
                    f" | sample={batch[0][:60]!r}"
                )
            vectors = [item["embedding"] for item in resp.output["embeddings"]]
            all_vectors.extend(vectors)
        return all_vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量 embedding（Document 入库用）"""
        return self._call(texts, batch_label="embed_documents")

    def embed_query(self, text: str) -> list[float]:
        """单条 embedding（query 检索用）"""
        resp = TextEmbedding.call(model=self.model, input=str(text))
        if resp.status_code != 200:
            raise RuntimeError(
                f"dashscope err: code={resp.code} msg={resp.message}"
                f" | embed_query text={text[:80]!r}"
            )
        return resp.output["embeddings"][0]["embedding"]