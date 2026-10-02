# -*- coding: utf-8 -*-
"""模型加载与 LoRA 注入
对应老师例子里「把预训练模型加载进来、再追加 LoRA 适配层」这一环节。
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType

from .config import (
    PRETRAINED_DIR, LORA_RANK, LORA_ALPHA, LORA_DROPOUT, TARGET_MODULES,
)


def load_base_model():
    """加载基座 Qwen + 分词器（bf16 + device_map=auto）"""
    tokenizer = AutoTokenizer.from_pretrained(
        str(PRETRAINED_DIR), trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(PRETRAINED_DIR),
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    return model, tokenizer


def setup_lora(model):
    """注入 LoRA（只训练 adapter，原参数冻结）"""
    cfg = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    return model


def save_lora(model, out_dir):
    """保存 LoRA adapter 权重"""
    model.save_pretrained(str(out_dir))
    print(f"[model] LoRA 权重已保存到 {out_dir}")


if __name__ == "__main__":
    m, t = load_base_model()
    m = setup_lora(m)
    print("[model] 加载 + LoRA 注入完成")
