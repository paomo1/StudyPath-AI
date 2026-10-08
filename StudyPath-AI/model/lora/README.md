---
library_name: peft
license: other
base_model: Qwen/Qwen2.5-7B-Instruct
tags:
- peft
- lora
- llama-factory
- transformers
- text-generation
pipeline_tag: text-generation
---

# StudyPath · Qwen2.5-7B-Instruct LoRA Adapter

留学申请规划领域的 **LoRA 领域适配权重**。基于 Qwen2.5-7B-Instruct 在真实留学语料上做参数高效微调，
目的是让基座学会「留学顾问的表达范式」——文书语体、结构化输出、主动标注数据来源的习惯。

> ⚠️ 本目录只有 **adapter（约 20MB）**，不含基座。推理需另配 Qwen2.5-7B-Instruct 基座。

## 目录内容说明

| 文件 | 是否入库 | 说明 |
|---|---|---|
| `adapter_model.safetensors` | ✅ | LoRA 权重本体（20MB），本目录唯一不可再生的产物 |
| `adapter_config.json` | ✅ | rank=8 / alpha=16 / target_modules，加载适配器必需 |
| `trainer_state.json` | ✅ | 真实 `global_step=51` 与 loss 序列，训练过程记录 |
| `train_results.json` / `eval_results.json` / `all_results.json` | ✅ | 训练与评估指标 |
| `trainer_log.jsonl` | ✅ | 逐条训练日志 |
| `training_loss.png` / `training_eval_loss.png` | ✅ | loss 曲线图，PPT 可直接用 |
| `tokenizer_config.json` / `chat_template.jinja` | ✅ | 体积极小，留作 SFT 阶段 prompt 格式的存档 |
| `tokenizer.json` | ❌ **未入库** | 11MB 词表，由基座提供。**本项目推理链不读这一份**：`finetune/inference.py:47` 与 `finetune/ab_compare.py:108` 都是 `AutoTokenizer.from_pretrained(PRETRAINED_DIR)`，即从基座目录取 tokenizer |

从仓库加载：备好基座（见 `finetune/README_AUTODL.md`）后
`PeftModel.from_pretrained(base, "model/lora")`，tokenizer 始终取自基座。

## Model description

| 项 | 值 |
|---|---|
| 方法 | LoRA（`finetuning_type: lora`，LLaMA Factory） |
| 秩 / 缩放 | `lora_rank: 8` / `lora_alpha: 16`，`lora_dropout: 0.05` |
| 目标模块 | `q_proj, k_proj, v_proj, o_proj` |
| 模板 | `qwen`（ChatML）· `cutoff_len: 2048` |
| 训练框架 | LLaMA Factory（`finetune/qwen_lora_sft.yaml`） |
| PEFT / Transformers | 0.18.1 / 5.6.0 |

## Training and evaluation data

SFT 数据集由 `annotations/build_sft_data.py` 从《院校数据采集.xlsx》直接构造，
**全部字段与 source_url 来自真实采集，零虚构**：

| 库 | 条数 | 构造出的任务 |
|---|---|---|
| 录取案例库 | 50 | 选校规划问答（背景 → 结果 + 梯度建议 + 来源） |
| 院校项目库 | 100 | 项目关键信息介绍（要求 / 排名 / 学制 / 来源） |
| 文书范例库 | 30 | 文书写作要点说明（类型 / 匹配度 / 质量标注） |
| **合计** | **180** | 按 8:2 划分 → `train.jsonl` 144 / `eval.jsonl` 36 |

训练时 LLaMA Factory 按 `val_size: 0.1` 从 `train.jsonl` 再切分：
**129 条参与训练，15 条作验证监控**（可由 `eval_runtime × eval_samples_per_second ≈ 15` 与
`ceil(129/8) × 3 = 51` 步双向核对）。

## Training results

| 指标 | 值 |
|---|---|
| train_loss | **1.2952** |
| eval_loss | **0.7597**（低于 train_loss，收敛且未过拟合） |
| global_step | 51（3 epoch × 17 步） |
| train_runtime | **106.83 秒**（纯训练） |
| 硬件 | AutoDL 单卡 RTX 3090 24GB，bf16 + FlashAttention2 |

## 能力边界（实测，重要）

同一 prompt、同基座、greedy 解码，唯一变量是是否挂载本 adapter：

| 层面 | 实测结论 |
|---|---|
| **表达层** | ✅ **生效**。3/3 组业务任务输出发生行为改变：泛化陈述句 → 第一人称文书语体 + 结构化输出 |
| **事实层** | ⚠️ **不承担**。生成文本附带的来源 URL 对知识库真实 URL 白名单溯源命中率 **0/20**；排名数字与知识库一致率 **0/7** |

**结论：参数高效微调习得的是【表达范式】（语体 / 结构 / 附来源的形式），不是【事实记忆】。**
因此本项目采用「RAG 检索层负责事实与 source_url 溯源 + 微调层负责语体与结构生成」的双轨架构，
而非纯微调方案。核查脚本见 `finetune/fact_audit.py`（本地可复现，无需 GPU）。

## Intended uses & limitations

**适用**：作为生成侧的语体/结构适配层，与 RAG 检索结果配合使用；离线评估与对照实验。

**不适用 / 局限**：

- ❌ 不能单独加载推理（缺基座）；
- ❌ 不可作为事实来源 —— 本 adapter 会产生看似合理但不存在的来源链接与排名数字；
- ❌ 本地 GTX 1650 4GB 显存无法承载 7B 基座（基座约 14GB），故应用主链路走云端 API，
  本 adapter 以「离线权重 + A/B 对照 + 双轨评估」方式独立验收；
- ⚠️ 训练集仅 180 条，语料规模有限，泛化边界以实测为准。

## 如何复现推理

```bash
# 前置：基座就位 + 装依赖
python -m finetune.download                 # 下 Qwen2.5-7B-Instruct 到 pretrained/
pip install -r finetune/requirements.txt

# A/B 对照取证（基座 vs 基座+LoRA），产出 data/processed/ab_compare.json
python -m finetune.ab_compare

# 20 条自动评估（指令遵循率 / 平均 ROUGE-L）
python -m finetune.evaluate

# 事实层核查（URL 可溯源率 / 排名一致率）
python -m finetune.fact_audit
```

应用侧本地推理入口：`finetune/inference.py::generate_essay()`（需基座在位；
检测不到 bitsandbytes 时自动退化为 bf16 加载）。

## Framework versions

- PEFT 0.18.1
- Transformers 5.6.0
- PyTorch 2.13.0+cu130
- Datasets 4.0.0
- Tokenizers 0.22.2
