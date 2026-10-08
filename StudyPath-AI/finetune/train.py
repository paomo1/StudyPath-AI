# -*- coding: utf-8 -*-
"""
微调训练入口。

主路径用 LLaMA Factory CLI（配置见 qwen_lora_sft.yaml）；下方的 transformers.Trainer
骨架是备选实现，默认不启用。

跑之前先生成 SFT 数据集：python -m annotations.build_sft_data
"""
from .config import ensure_dirs


# 方式 1（主路径）：LLaMA Factory CLI
# 在项目根目录运行：
#   pip install -r finetune/requirements.txt
#   llamafactory-cli train finetune/qwen_lora_sft.yaml
#
# 详见 finetune/qwen_lora_sft.yaml
# 云端一键流程见 finetune/autodl_train.sh


# 方式 2：transformers Trainer 骨架（默认不启用）
def train_with_trainer():
    from datasets import load_dataset
    from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
    from .model import load_base_model, setup_lora
    from .config import (
        DATA_PROCESSED, MODEL_OUT, LEARNING_RATE, NUM_EPOCHS,
        BATCH_SIZE, GRAD_ACCUM, WARMUP_RATIO, LOGGING_STEPS, SAVE_STEPS,
        MAX_SEQ_LEN, INSTRUCTION_TMPL,
    )

    ensure_dirs()
    # 1) 数据：SFT 数据集由 annotations/build_sft_data.py 从 xlsx 生成，
    #    这里只做「存在性校验 + 读取」，不重复解析原始数据（避免两套逻辑打架）。
    train_path = DATA_PROCESSED / "train.jsonl"
    eval_path = DATA_PROCESSED / "eval.jsonl"
    if not train_path.exists() or not eval_path.exists():
        raise FileNotFoundError(
            f"缺少 SFT 数据集：{train_path}\n"
            "请先运行：python -m annotations.build_sft_data"
        )
    ds_train = load_dataset("json", data_files=str(train_path))["train"]
    ds_eval = load_dataset("json", data_files=str(eval_path))["train"]

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
        eval_strategy="steps",   # 新版 transformers 已由 evaluation_strategy 更名而来
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
    # 默认走方式 1（CLI，实际训练时用的就是这条）。要试方式 2，取消下面注释：
    # train_with_trainer()
    ensure_dirs()
    print("[train] 推荐：llamafactory-cli train finetune/qwen_lora_sft.yaml")
    print("[train] 云端一键流程：bash finetune/autodl_train.sh（见 finetune/README_AUTODL.md）")


if __name__ == "__main__":
    main()