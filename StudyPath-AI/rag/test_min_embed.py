# -*- coding: utf-8 -*-
"""
最小 embedding 测试：只用 dashscope SDK 直接调一条文本，
不经 OpenAI 兼容端点、不经 langchain、不经自定义 wrapper。

跑通说明 key 与网络没问题，可以去跑 build_vectorstore.py；失败则先排查 key / 账号 / 网络。
"""
import dashscope
from dashscope import TextEmbedding

# 从 config 读 key（config.py 会从项目根 .env 加载 DASHSCOPE_API_KEY，密钥不入库）
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DASHSCOPE_API_KEY, EMBED_MODEL

print(f"key 前缀: {DASHSCOPE_API_KEY[:8]}...")
print(f"model: {EMBED_MODEL}")

dashscope.api_key = DASHSCOPE_API_KEY

print("\n--- 测试 1: 单条英文 ---")
resp = TextEmbedding.call(model=EMBED_MODEL, input=["hello world"])
print(f"status_code: {resp.status_code}")
print(f"message: {resp.message}")
if resp.status_code == 200:
    emb = resp.output["embeddings"][0]["embedding"]
    print(f"✅ 通过！向量维度: {len(emb)}, 前 5 维: {emb[:5]}")
else:
    print(f"❌ 失败！请检查 key 有效性 / 灵积服务是否开通")

print("\n--- 测试 2: 单条中文 ---")
resp = TextEmbedding.call(model=EMBED_MODEL, input=["卡内基梅隆大学计算机硕士"])
print(f"status_code: {resp.status_code}")
print(f"message: {resp.message}")
if resp.status_code == 200:
    emb = resp.output["embeddings"][0]["embedding"]
    print(f"✅ 通过！向量维度: {len(emb)}, 前 5 维: {emb[:5]}")
else:
    print(f"❌ 失败！原因: {resp.code} - {resp.message}")