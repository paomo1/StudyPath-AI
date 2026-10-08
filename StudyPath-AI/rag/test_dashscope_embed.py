# -*- coding: utf-8 -*-
"""
对比三种 embedding 调用方式，确定哪种可用：
    A. OpenAI 兼容端点 + 单条文本
    B. OpenAI 兼容端点 + 多条文本
    C. dashscope 原生 SDK + 多条文本
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, EMBED_MODEL

import httpx
import dashscope
from dashscope import TextEmbedding

SAMPLE_ONE = "Carnegie Mellon University 的 MS in Computer Science 项目（MS），位于美国。"
SAMPLE_MULTI = [
    "Carnegie Mellon University 的 MS in Computer Science 项目（MS），位于美国。",
    "Massachusetts Institute of Technology 的 MS in Electrical Engineering and Computer Science 项目。",
    "Stanford University 的 MS in Computer Science 项目，位于美国。",
    "Yale University 的 MS in Computer Science 项目，位于美国。",
]


def test_a_openai_compat_one():
    """A. OpenAI 兼容 + 1 条文本"""
    print("\n[A] OpenAI 兼容 + 1 条文本")
    url = DASHSCOPE_BASE_URL.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": EMBED_MODEL, "input": SAMPLE_ONE}
    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=20)
        print(f"  status={r.status_code}")
        print(f"  body[:200]={r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"  ERR: {e}")
        return False


def test_b_openai_compat_multi():
    """B. OpenAI 兼容 + 4 条文本（list）"""
    print("\n[B] OpenAI 兼容 + 4 条文本（list）")
    url = DASHSCOPE_BASE_URL.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": EMBED_MODEL, "input": SAMPLE_MULTI}
    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=20)
        print(f"  status={r.status_code}")
        print(f"  body[:200]={r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"  ERR: {e}")
        return False


def test_c_dashscope_sdk_multi():
    """C. dashscope 原生 SDK + 4 条文本"""
    print("\n[C] dashscope 原生 SDK + 4 条文本")
    dashscope.api_key = DASHSCOPE_API_KEY
    try:
        resp = TextEmbedding.call(model=EMBED_MODEL, input=SAMPLE_MULTI)
        print(f"  status_code={resp.status_code}")
        print(f"  message={getattr(resp, 'message', '')}")
        if resp.status_code == 200:
            print(f"  输出 embedding 数: {len(resp.output['embeddings'])}")
            print(f"  向量维度: {len(resp.output['embeddings'][0]['embedding'])}")
        return resp.status_code == 200
    except Exception as e:
        print(f"  ERR: {e}")
        return False


if __name__ == "__main__":
    print(f"key 前缀: {DASHSCOPE_API_KEY[:8]}...")
    print(f"base_url: {DASHSCOPE_BASE_URL}")
    print(f"model: {EMBED_MODEL}")
    a = test_a_openai_compat_one()
    b = test_b_openai_compat_multi()
    c = test_c_dashscope_sdk_multi()
    print("\n=== 结果汇总 ===")
    print(f"  A: {'PASS' if a else 'FAIL'}")
    print(f"  B: {'PASS' if b else 'FAIL'}")
    print(f"  C: {'PASS' if c else 'FAIL'}")