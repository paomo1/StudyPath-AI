# -*- coding: utf-8 -*-
"""
test_key.py — 绕开 langchain，直接用 OpenAI 兼容端点验证 key 是否有效。
先确保 config.py 里 DASHSCOPE_API_KEY 已写成你自己的有效 key（自己编辑，别贴给别人）。
"""
from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, EMBED_MODEL
from openai import OpenAI


def main():
    # 只打印前缀，避免泄露完整 key
    print("当前 key 前缀:", DASHSCOPE_API_KEY[:10], "...")
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    try:
        resp = client.embeddings.create(model=EMBED_MODEL, input="test sentence")
        vec = resp.data[0].embedding
        print("✅ key 有效，embedding 维度:", len(vec))
        print("   → 可以回去跑 build_vectorstore.py 了")
    except Exception as e:
        print("❌ key 无效 / 账号未开通, 错误详情:")
        print(e)


if __name__ == "__main__":
    main()
