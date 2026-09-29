# -*- coding: utf-8 -*-
"""
StudyPath-AI · RAG demo 配置
所有路径/密钥/模型名集中在这里，方便你改。
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent          # rag/
ROOT = HERE.parent                               # StudyPath-AI/
# ===================== 数据文件 =====================
# 三库都在同一个 xlsx 的不同 sheet 里
XLSX_PATH = ROOT / "data" / "raw" / "院校数据采集.xlsx"
SHEET_SCHOOLS = "院校项目库"   # 17 列, 100 条
SHEET_CASES = "录取案例库"     # 12 列, 50 条
SHEET_ESSAYS = "文书范例库"    # 6 列, 30 条

# ===================== DashScope (OpenAI 兼容端点) =====================
# 复用你已有的 dashscope key；也可用环境变量 DASHSCOPE_API_KEY 覆盖
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-9c5a5386e40544a49b9d961f082e5d81")
# DashScope 提供 OpenAI 兼容协议，langchain-openai 直接能连，版本无关最稳
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_MODEL = "qwen-plus"        # 也可 qwen-turbo(省钱) / qwen-max(强)
EMBED_MODEL = "text-embedding-v3"

# 每次向量化单批大小（dashscope OpenAI 兼容端点对小批更稳）
EMBED_BATCH = 10
# 单条文本字符上限（embedding 模型 ~2048 tokens ≈ 6000~7000 中文字，留安全余量）
MAX_CONTENT_CHARS = 2000

# ===================== Chroma 向量库 =====================
# 持久化到磁盘，建一次以后直接加载，不用每次重算
CHROMA_DIR = HERE / "chroma_db"

# 每次检索返回的条数（适度大一些，让 LLM 资料更全）
TOP_K = 8
