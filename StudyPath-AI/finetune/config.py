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
# 实际训练以 finetune/qwen_lora_sft.yaml 为准（LLaMA Factory CLI 路径）；
# 下面这几个常量供 train.py 里备用的 transformers.Trainer 分支使用，
# 数值与 yaml 保持一致，避免两套配置各说各话。
LEARNING_RATE    = 2e-4
NUM_EPOCHS       = 3
BATCH_SIZE       = 1
GRAD_ACCUM       = 8
WARMUP_RATIO     = 0.03
LOGGING_STEPS    = 10
# 实物：144 条 train.jsonl 按 val_size=0.1 切出 129 训练 / 15 验证，
# ceil(129/8)×3 epoch = 51 步。51 < SAVE_STEPS，所以训练中途不落 checkpoint，
# 只在训练结束时保存最终权重（即 model/lora）。保持 200 以如实反映当时的训练配置。
SAVE_STEPS       = 200

# ===== 数据 =====
TRAIN_RATIO      = 0.8
# 注意：实际 SFT 指令文案由 annotations/build_sft_data.py 写死在每条样本的
# instruction 字段里（三类任务各一套），本常量只服务于上面那个 Trainer 备用分支。
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
