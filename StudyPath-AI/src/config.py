# -*- coding: utf-8 -*-
"""StudyPath AI · 微调模块配置
对应老师例子的 src/config.py：路径、超参、模型配置
"""
from pathlib import Path
import os

# ===== 路径（相对项目根） =====
PROJECT_ROOT     = Path(__file__).resolve().parent.parent
PRETRAINED_DIR   = PROJECT_ROOT / "pretrained" / "Qwen2.5-7B-Instruct"
DATA_RAW         = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED   = PROJECT_ROOT / "data" / "processed"
MODEL_OUT        = PROJECT_ROOT / "model"
CACHE_DIR        = PROJECT_ROOT / "cache"

# HuggingFace 缓存走本地
os.environ.setdefault("HF_HOME", str(CACHE_DIR))

# ===== 基座模型 =====
BASE_MODEL_NAME = "Qwen2.5-7B-Instruct"   # 与 download.py 对应
MAX_SEQ_LEN     = 2048

# ===== LoRA 配置 =====
LORA_RANK        = 8
LORA_ALPHA       = 16
LORA_DROPOUT     = 0.05
TARGET_MODULES   = ["q_proj", "k_proj", "v_proj", "o_proj"]

# ===== 训练超参 =====
LEARNING_RATE    = 2e-4
NUM_EPOCHS       = 3
BATCH_SIZE       = 1
GRAD_ACCUM       = 8
WARMUP_RATIO     = 0.03
LOGGING_STEPS    = 10
SAVE_STEPS       = 200

# ===== 数据 =====
TRAIN_RATIO      = 0.8
INSTRUCTION_TMPL = "你是一名留学文书顾问，请根据以下信息生成文书：\n{input}"


def ensure_dirs():
    """确保所有目录存在"""
    for d in [DATA_RAW, DATA_PROCESSED, MODEL_OUT, CACHE_DIR, PRETRAINED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print("[config] 路径检查完成")
    print(f"  PRETRAINED = {PRETRAINED_DIR}")
    print(f"  DATA_RAW   = {DATA_RAW}")
    print(f"  MODEL_OUT  = {MODEL_OUT}")
