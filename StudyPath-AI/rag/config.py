# -*- coding: utf-8 -*-
"""
RAG 模块配置：路径、模型名与检索参数。
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent          # rag/
ROOT = HERE.parent                               # StudyPath-AI/


def _load_local_env():
    """零依赖加载根目录 .env：
    - 优先用 python-dotenv（若环境已安装）；
    - 否则手动解析 KEY=VALUE 注入 os.environ；
    - 不抛异常，系统环境变量同样生效。
    密钥统一放在 .env（已被 .gitignore 忽略，不进版本库）。"""
    env_path = ROOT / ".env"
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_local_env()

# ===================== 数据文件 =====================
# 三库都在同一个 xlsx 的不同 sheet 里
XLSX_PATH = ROOT / "data" / "raw" / "院校数据采集.xlsx"
SHEET_SCHOOLS = "院校项目库"   # 17 列, 100 条
SHEET_CASES = "录取案例库"     # 12 列, 50 条
SHEET_ESSAYS = "文书范例库"    # 6 列, 30 条

# ===================== DashScope (OpenAI 兼容端点) =====================
# 密钥仅从 .env 的 DASHSCOPE_API_KEY 读取，绝不在代码里写死。
# 缺失时直接报错并给出配置提示，避免把"密钥为空"带进运行期。
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    raise RuntimeError(
        "未检测到 DASHSCOPE_API_KEY。\n"
        "请在本项目根目录创建 .env 文件并写入：\n"
        "    DASHSCOPE_API_KEY=sk-你的真实密钥\n"
        "（.env 已被 .gitignore 忽略，不会提交到 GitHub）"
    )
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
