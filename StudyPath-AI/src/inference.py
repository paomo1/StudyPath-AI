# -*- coding: utf-8 -*-
"""LoRA 推理：加载基座 + LoRA 权重，生成留学建议
供应用层「文书生成 / 规划 Agent」直接调用：from src.inference import generate_essay
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from .config import PRETRAINED_DIR, MODEL_OUT


def load_tuned_model():
    """加载 基座(4-bit量化) + LoRA adapter 权重

    本地 16GB RAM + GTX 1650 4GB 用 4-bit 量化（nf4）避免 OOM：
    - 7B 基座 bf16 约 14GB → 4-bit 后约 4GB，显存/内存都吃得下
    - compute_dtype=float16（1650/Turing 不支持 bfloat16）
    - device_map="auto" 自动在 GPU/CPU 间分配
    """
    tok = AutoTokenizer.from_pretrained(str(PRETRAINED_DIR), trust_remote_code=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    base = AutoModelForCausalLM.from_pretrained(
        str(PRETRAINED_DIR),
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base, str(MODEL_OUT / "lora"))
    return model, tok


def generate(model, tok, instruction, input_text="", max_new=1024):
    """单条生成（Qwen Chat 模板）"""
    prompt = (
        "<|im_start|>system\n你是一名留学申请规划顾问。<|im_end|>\n"
        f"<|im_start|>user\n{instruction}\n{input_text}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    ids = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(**ids, max_new_tokens=max_new, do_sample=False, temperature=1.0)
    return tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)


def generate_essay(prompt, max_new_tokens=1024):
    """应用层 Agent 调用入口"""
    model, tok = load_tuned_model()
    return generate(model, tok, prompt, max_new=max_new_tokens)
