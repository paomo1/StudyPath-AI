# -*- coding: utf-8 -*-
"""微调训练入口
对应老师例子"喂入语料训练模型"步骤
推荐方式：用 LLaMA Factory CLI（省事、稳）
备选方式：用 transformers.Trainer（骨架见下方）
"""
from .config import ensure_dirs


# ============ 方式 1（强烈推荐）：LLaMA Factory CLI ============
# 在项目根目录运行：
#   pip install llamafactory
#   llamafactory-cli train configs/qwen_lora_sft.yaml
#
# 详见 configs/qwen_lora_sft.yaml


# ============ 方式 2：transformers Trainer 骨架 ============
def train_with_trainer():
    from datasets import load_dataset
    from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
    from .model import load_base_model, setup_lora
    from .processed import read_raw_essays, format_alpaca, split_train_eval
    from .config import (
        DATA_PROCESSED, MODEL_OUT, LEARNING_RATE, NUM_EPOCHS,
        BATCH_SIZE, GRAD_ACCUM, WARMUP_RATIO, LOGGING_STEPS, SAVE_STEPS,
        MAX_SEQ_LEN, INSTRUCTION_TMPL,
    )

    ensure_dirs()
    # 1) 数据
    essays = read_raw_essays()
    data = format_alpaca(essays)
    train, evald = split_train_eval(data)
    ds_train = load_dataset("json", data_files=str(DATA_PROCESSED / "train.jsonl"))["train"]
    ds_eval  = load_dataset("json", data_files=str(DATA_PROCESSED / "eval.jsonl"))["train"]

    # 2) 模型
    model, tokenizer = load_base_model()
    model = setup_lora(model)

    # 3) tokenize
    def fmt(ex):
        prompt = INSTRUCTION_TMPL.format(input=ex["input"] or "")
        text = f"<|im_start|>user\n{prompt}\n<|im_end|>\n<|im_start|>assistant\n{ex['output']}<|im_end|>"
        return tokenizer(text, truncation=True, max_length=MAX_SEQ_LEN, padding="max_length")
    ds_train = ds_train.map(fmt, remove_columns=ds_train.column_names)
    ds_eval  = ds_eval.map(fmt, remove_columns=ds_eval.column_names)

    # 4) 训练
    args = TrainingArguments(
        output_dir=str(MODEL_OUT),
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        num_train_epochs=NUM_EPOCHS,
        warmup_ratio=WARMUP_RATIO,
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        bf16=True,
        evaluation_strategy="steps",
        eval_steps=SAVE_STEPS,
        save_total_limit=2,
        report_to="none",
    )
    Trainer(
        model=model,
        args=args,
        train_dataset=ds_train,
        eval_dataset=ds_eval,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    ).train()
    print(f"[train] 完成，权重在 {MODEL_OUT}")


def main():
    # 默认走方式 1（CLI）。要试方式 2，取消下面注释：
    # train_with_trainer()
    print("[train] 见文件顶部说明，推荐：llamafactory-cli train configs/qwen_lora_sft.yaml")


if __name__ == "__main__":
    main()