# -*- coding: utf-8 -*-
"""
test_min_embed.py — 最小独立 embedding 测试
完全不经过 OpenAI 兼容端点、不经过 langchain、不经过我自己写的 wrapper。
只用 dashcope SDK 直接调，调一条最简单的英文。

目的：隔离验证「dashcope SDK + 你的 key」能不能跑通。
- 通过 → 跑 build_vectorstore.py 入库
- 失败 → 是 key/账号/网络问题，不用跑 build
"""
import dashscope
from dashscope import TextEmbedding

# 从 config 读 key（你已经把新 key 写进 config.py 了）
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