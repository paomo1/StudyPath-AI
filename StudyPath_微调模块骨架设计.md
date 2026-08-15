# StudyPath AI · 微调模块骨架设计（对齐老师架构）

> 老师给的"评论正/负向 Bert 微调"是企业级垂直领域微调的标准骨架。
> 本文档把 StudyPath AI 留学项目**微调阶段**完全对齐这套架构，照搬即可。

---

## 一、老师架构一句话总结

**业务**：评论正/负向分类 → Bert 微调（轻量、企业级、可扩展）
**骨架**：`cache/ + data/{raw,processed}/ + model/ + pretrained/ + src/ + download.py`
**开发思路 5 步**：
1. 准备初始数据 + 预训练模型
2. 数据预处理，让模型能接收
3. 模型配置追加微调（垂直领域开发）
4. 喂入语料训练
5. 测试评估

整套思路**完全适用于大模型微调**，只是基座从 Bert 换成 Qwen，分类换成文书生成。

---

## 二、整体对照（老师 ↔ StudyPath AI）

| 老师例子（Bert 评论分类） | StudyPath AI（Qwen 文书微调） | 用途 |
|--------------------------|------------------------------|------|
| `cache/` | `cache/` | 临时下载缓存（HuggingFace） |
| `data/raw/` | `data/raw/` | 原始文书语料（PS/SOP/CV 全文） |
| `data/processed/` | `data/processed/` | 预处理后的指令格式（Alpaca） |
| `model/` | `model/` | 训练好的 LoRA 权重 |
| `pretrained/bert-base-chinese` | `pretrained/Qwen2.5-7B-Instruct` | 预训练基座 |
| `src/config.py` | `src/config.py` | 路径 + 超参 |
| `src/model.py` | `src/model.py` | 模型加载 + LoRA 注入 |
| `src/processed.py` | `src/processed.py` | 数据清洗格式化 |
| （新增） | `src/train.py` | 训练入口 |
| （新增） | `src/evaluate.py` | 模型评估 |
| （新增） | `src/inference.py` | 推理（供应用层 Agent 调用） |
| `download.py` | `download.py` | 下载 Qwen 基座 + 分词器 |
| `项目笔记.txt` | `项目笔记.txt` | 学习笔记 |
| （新增） | `configs/qwen_lora_sft.yaml` | LLaMA Factory 训练配置 |

---

## 三、StudyPath AI 微调模块完整目录树

```
StudyPath-AI/
├── README.md
├── 项目笔记.txt
├── requirements.txt
├── download.py
│
├── cache/                       # 临时下载缓存（HF_HOME）
│   └── README.md
│
├── data/
│   ├── raw/                     # 原始文书（30+ PS/SOP/CV）
│   │   └── README.md
│   └── processed/               # 格式化后 train.jsonl / eval.jsonl
│       └── README.md
│
├── model/                       # 微调输出（LoRA 权重）
│   └── README.md
│
├── pretrained/
│   └── Qwen2.5-7B-Instruct/     # 基座（download.py 下载到这里）
│       └── README.md
│
├── configs/
│   └── qwen_lora_sft.yaml       # LLaMA Factory 训练配置
│
└── src/                         # 【核心代码】
    ├── __init__.py
    ├── config.py                # 路径、超参、LoRA 配置
    ├── model.py                 # 加载基座 + 注入 LoRA
    ├── processed.py             # 原始文书 → Alpaca 格式 → 划分
    ├── train.py                 # 训练入口
    ├── evaluate.py              # 自动+人工双轨评估
    └── inference.py             # 推理（供文书 Agent 调用）
```

---

## 四、src/ 各文件最小实现要点

### `config.py` — 配置中心
- 路径：`PROJECT_ROOT`、`PRETRAINED_DIR`、`DATA_RAW`、`DATA_PROCESSED`、`MODEL_OUT`、`CACHE_DIR`
- 基座：`BASE_MODEL_NAME = "Qwen2.5-7B-Instruct"`，`MAX_SEQ_LEN = 2048`
- LoRA：`RANK=8, ALPHA=16, DROPOUT=0.05`，`TARGET_MODULES=q,k,v,o_proj`
- 训练：`LR=2e-4, EPOCHS=3, BS=1, GRAD_ACCUM=8`
- 数据：`TRAIN_RATIO=0.8`
- 设 `HF_HOME=CACHE_DIR` 走本地缓存

### `model.py` — 模型加载与 LoRA 注入
- `load_base_model()`：用 `transformers` 加载 Qwen，bf16，`device_map="auto"`
- `setup_lora(model)`：用 `peft.LoraConfig` + `get_peft_model` 注入 LoRA
- `save_lora(model, out_dir)`：保存 adapter 权重

### `processed.py` — 数据预处理
- `read_raw_essays()`：扫 `data/raw/` 下 json/jsonl/txt
- `format_alpaca(essays)`：统一为 `[{"instruction","input","output"}, ...]`
- `split_train_eval(data, ratio=0.8)`：随机划分，写 `train.jsonl` / `eval.jsonl`

### `train.py` — 训练入口（两种方式）
- **方式 1（推荐）**：直接调 LLaMA Factory CLI
  ```
  llamafactory-cli train configs/qwen_lora_sft.yaml
  ```
- **方式 2**：用 `transformers.Trainer` 自己写（骨架里给示例）

### `evaluate.py` — 双轨评估
- 自动：ROUGE-L / 困惑度 / 指令遵循率
- 人工：抽样 20 条评审打分（逻辑/针对性/语言）

### `inference.py` — 推理
- `load_tuned_model()`：加载基座 + LoRA 权重
- `generate_essay(prompt, max_new_tokens=1024)`：生成文书
- 应用层 `文书生成 Agent` 直接 `from src.inference import generate_essay`

---

## 五、训练数据准备流程（执行步骤）

1. 按 `文书范例库` sheet 把 30+ 真实文书写入 `data/raw/`
2. 跑 `python -m src.processed` → 生成 `data/processed/{train,eval}.jsonl`
3. 检查数据质量（指令清晰、输出合规）
4. 跑 `python download.py` 下载 Qwen 基座到 `pretrained/`
5. 配 `configs/qwen_lora_sft.yaml`（超参跟 `config.py` 对齐）
6. AutoDL 租 A100，复制项目，跑 `llamafactory-cli train ...`
7. 训练完评估 → 导出 `model/lora/`

---

## 六、与毕设加分项对齐

| 毕设要求 | 在这里怎么实现 |
|---------|--------------|
| 全流程项目 +10 | 这就是阶段二"模型微调"的核心物理实现 |
| 模型微调 +5 | 完整的 LoRA 训练流水线（数据→训练→评估→保存） |
| 技术深度 25% | 体现你能独立搭企业级微调框架 |
| 答辩 PPT | 直接展示这套目录树 + 训练曲线 + 评估结果 |

---

## 七、与老师例子的开发思路逐句对照

| 老师原文 | StudyPath AI 对应 |
|---------|------------------|
| 1. 需要有初始化的训练数据、预训练模型 | 30+ 文书 + Qwen2.5-7B-Instruct |
| 2. 先把训练的数据处理好，让预训练模型可以接收 | `processed.py` → Alpaca 格式 |
| 3. 再把预训练模型进行配置和处理，让它符合当前的需求 | `model.py` LoRA 注入 |
| 4. 接着可以正式开始喂入语料，训练模型 | `train.py` 或 LLaMA Factory CLI |
| 5. 最后可以进行模型测试、评估 | `evaluate.py` 双轨评估 |

完完全全一一对应。**老师架构就是企业级微调的标准范式**，直接复用即可。

---

## 八、即学即用 Checklist

- [ ] `cache/` 能写（HF 缓存）
- [ ] `pretrained/Qwen2.5-7B-Instruct/` 已下载（`download.py`）
- [ ] `data/raw/` 至少 30 篇真实文书（用 `文书范例库` sheet 攒）
- [ ] `data/processed/` 已生成 train/eval jsonl
- [ ] `src/config.py` 路径全对
- [ ] AutoDL 开通 + LLaMA Factory 装好
- [ ] `configs/qwen_lora_sft.yaml` 写好
- [ ] 跑通一次训练 demo（哪怕 0.1 epoch 验证流程）
- [ ] `evaluate.py` 输出指标
- [ ] `inference.py` 能被应用层 Agent 调用

---

## 九、立刻能做的 3 件事

1. **把 `study_path_微调模块骨架` 整个目录复制到你的毕设项目根**
2. **跑 `python download.py`**（建议先设 `HF_ENDPOINT=https://hf-mirror.com` 加速）
3. **每天攒 2 篇文书到 `data/raw/`**，到毕设就有 50+ 篇
