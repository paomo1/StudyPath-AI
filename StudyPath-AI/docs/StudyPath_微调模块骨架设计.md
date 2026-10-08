# StudyPath · 微调模块骨架设计（对齐课上企业级微调范式）

> 课上给的"评论正/负向 Bert 微调"是企业级垂直领域微调的标准骨架。
> 本文档记录 StudyPath 留学项目**微调阶段**如何对齐这套架构，以及最终落地的实际结构。
>
> ⚠️ 注意：本项目的目录已在后期重构为 `finetune/`（原先的 `src/` 与 `configs/` 已合并进 `finetune/`）。
> 下文所有路径均以**重构后的真实结构**为准。

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

整套思路**完全适用于大模型微调**，只是基座从 Bert 换成 Qwen，任务从分类换成文书/规划类生成。

---

## 二、整体对照（老师 ↔ StudyPath）

| 老师例子（Bert 评论分类） | StudyPath（Qwen 留学领域微调） | 用途 |
|--------------------------|----------------------------------|------|
| `cache/` | `cache/` | 临时下载缓存（HuggingFace） |
| `data/raw/` | `data/raw/院校数据采集.xlsx` | 原始语料（三库真实采集数据） |
| `data/processed/` | `data/processed/` | 指令格式数据集（Alpaca：train/eval.jsonl） |
| `model/` | `model/lora/` | 训练好的 LoRA 权重 |
| `pretrained/bert-base-chinese` | `pretrained/Qwen2.5-7B-Instruct` | 预训练基座 |
| `src/config.py` | `finetune/config.py` | 路径 + 超参 |
| `src/model.py` | `finetune/model.py` | 模型加载 + LoRA 注入 |
| `src/processed.py` | `finetune/processed.py` | 数据清洗格式化（通用转换器 + 安全闸门） |
| （新增） | `finetune/train.py` | 训练入口 |
| （新增） | `finetune/evaluate.py` | 模型评估（指令遵循率 / ROUGE-L） |
| （新增） | `finetune/inference.py` | 推理（供应用层调用） |
| `download.py` | `finetune/download.py` | 下载 Qwen 基座 + 分词器 |
| （新增） | `finetune/qwen_lora_sft.yaml` | LLaMA Factory 训练配置 |
| （本项目新增） | `finetune/ab_compare.py` | A/B 对照取证（基座 vs 基座+LoRA） |
| （本项目新增） | `finetune/fact_audit.py` | 事实层核查（来源可溯源率 / 排名一致率） |
| （本项目新增） | `annotations/build_annotations.py`<br>`annotations/build_sft_data.py` | 从 xlsx 构造标注数据与 SFT 数据集 |

---

## 三、微调模块完整目录树（实际落地）

```
StudyPath-AI/
├── README.md
├── requirements.txt（各模块自带，见下）
│
├── cache/                        # 临时下载缓存（HF_HOME）
├── pretrained/                   # 基座（download.py 下载到这里，15GB，不进 git）
│   └── Qwen2.5-7B-Instruct/
├── model/                        # 微调产物（不进 git；可加白名单保留权重）
│   └── lora/
│       ├── adapter_model.safetensors     # 约 20MB，核心产物
│       ├── adapter_config.json           # r=8 / alpha=16 / target=q,k,v,o_proj
│       ├── tokenizer.json / chat_template.jinja
│       ├── training_loss.png / training_eval_loss.png
│       ├── train_results.json / trainer_state.json / all_results.json
│       └── README.md                     # model card（含能力边界实测说明）
│
├── data/
│   ├── raw/院校数据采集.xlsx      # 唯一数据源：院校项目库100 / 录取案例库50 / 文书范例库30
│   └── processed/
│       ├── train.jsonl (144) / eval.jsonl (36)
│       ├── dataset_info.json      # LLaMA Factory 数据集说明书
│       ├── rag_evalset.jsonl / rag_metrics.json      # RAG 检索评测
│       └── ab_compare.json / eval_results.json       # 微调 A/B 对照与自动评估
│
├── annotations/                  # 数据标注阶段（B 方案）
│   ├── build_annotations.py      # xlsx 字段归一化为标注维度 -> annotated_dataset.jsonl
│   ├── build_sft_data.py         # xlsx 三库 -> SFT 数据集（180 条）+ dataset_info.json
│   ├── figures/                  # 5 张手写 SVG 分布图
│   └── output/                   # annotated_dataset.jsonl + stats.json
│
└── finetune/                     # 【微调模块核心代码】
    ├── __init__.py
    ├── config.py                 # 路径、超参、LoRA 配置
    ├── model.py                  # 加载基座 + 注入 LoRA
    ├── processed.py              # 通用格式转换（json/jsonl/txt -> Alpaca）+ 数据保护
    ├── train.py                  # 训练入口（推荐 LLaMA Factory CLI）
    ├── evaluate.py               # 自动评估：指令遵循率 / 平均 ROUGE-L（含生成文本留档）
    ├── inference.py              # 推理入口：load_tuned_model / generate_essay
    ├── ab_compare.py             # A/B 对照取证（disable_adapter 方式）
    ├── fact_audit.py             # 事实层核查（本地可跑，无需 GPU）
    ├── download.py               # 基座下载（ModelScope 国内镜像）
    ├── qwen_lora_sft.yaml        # LLaMA Factory 训练配置
    ├── requirements.txt
    ├── autodl_train.sh           # 云端一键：装依赖 -> 下基座 -> 训练 -> 评估
    └── README_AUTODL.md          # 云端训练指南（含实测结果与坑）
```

---

## 四、finetune/ 各文件实现要点

### `config.py` — 配置中心

- 路径：`PROJECT_ROOT`（由 `__file__` 上溯两级）、`PRETRAINED_DIR`、`DATA_RAW`、`DATA_PROCESSED`、`MODEL_OUT`、`CACHE_DIR`
- 基座：`BASE_MODEL_NAME = "Qwen2.5-7B-Instruct"`，`MAX_SEQ_LEN = 2048`
- LoRA：`RANK=8, ALPHA=16, DROPOUT=0.05`，`TARGET_MODULES=q,k,v,o_proj`
- 训练：`LR=2e-4, EPOCHS=3, BS=1, GRAD_ACCUM=8`
- 设 `HF_HOME=CACHE_DIR` 走本地缓存
- 所有路径**基于 `__file__` 相对推导**，克隆到任意目录都能跑

### `model.py` — 模型加载与 LoRA 注入

- `load_base_model()`：用 `transformers` 加载 Qwen，bf16，`device_map="auto"`
- `setup_lora(model)`：用 `peft.LoraConfig` + `get_peft_model` 注入 LoRA
- `save_lora(model, out_dir)`：保存 adapter 权重

### `processed.py` — 数据预处理（通用转换器 + 三道安全闸门）

- `read_raw_essays()`：扫 `data/raw/` 下 json / jsonl / txt；**只发现 xlsx 时会明确提示**并指向 `annotations/build_sft_data.py`，不再静默返回空列表
- `format_alpaca(essays)`：统一为 `[{"instruction","input","output"}, ...]`
- `split_train_eval(data, ratio=0.8)`：随机划分（固定种子 42）
- `main()` 的三道闸门：① 0 条样本直接中止；② 少于 `MIN_SAMPLES` 中止；③ **少于现有数据集条数时拒绝覆盖**（需显式 `--force`）
- 📌 本项目 SFT 数据集的**真正生产入口是 `annotations/build_sft_data.py`**（读 xlsx 三库），`processed.py` 是通用兜底工具

### `train.py` — 训练入口（两种方式）

- **方式 1（实际采用）**：LLaMA Factory CLI
  ```
  llamafactory-cli train finetune/qwen_lora_sft.yaml
  ```
- **方式 2（备用骨架）**：`transformers.Trainer`，含数据集存在性校验，默认不启用

### `evaluate.py` — 自动评估（含原文留档）

- 指标：指令遵循率（输出非空且 >20 字）、平均 ROUGE-L（自实现 LCS 版，不依赖第三方 rouge 包）
- **每条生成文本 + 参考文本截断留档**写入 `eval_results.json`，避免"只存指标不存原文"把问题藏起来

### `inference.py` — 推理

- `load_tuned_model()`：加载基座 + LoRA 权重；**探测 bitsandbytes 是否可用**，不可用自动退化为 bf16（24GB 卡无需量化）
- `is_lora_ready()`：判断基座与 adapter 是否都在位
- `generate_essay(prompt, max_new_tokens=1024)`：生成文书，供应用层调用

### `ab_compare.py` — A/B 对照取证

- 同一 prompt、同基座、greedy 解码，**唯一变量 = adapter 是否生效**
- 实现方式：先套一次 `PeftModel`，A 组用 `with tuned.disable_adapter():`，B 组直接生成
- ⚠️ 反面教材：不要在循环里反复 `PeftModel.from_pretrained(base, ...)` —— 该调用会**原地注入** LoRA 层到 `base`，导致第二轮起"A 组"其实也是微调模型

### `fact_audit.py` — 事实层核查（本地可跑）

- 读 `data/raw/院校数据采集.xlsx` 建真实 URL 白名单，再核查 `eval_results.json` / `ab_compare.json` 里的生成文本
- 输出：来源 URL 可溯源率、排名数字一致率 —— 用于量化"微调不承担事实记忆"这一结论

---

## 五、训练数据准备流程（实际执行）

1. 数据采集：`data/raw/院校数据采集.xlsx`（三库共 180 条，每条带 `source_url`）
2. 标注归一化：`python -m annotations.build_annotations` → `annotated_dataset.jsonl` + 5 张分布图
3. 构造 SFT 数据集：`python -m annotations.build_sft_data` → `train.jsonl(144)` / `eval.jsonl(36)` / `dataset_info.json`
4. 下载基座：`python -m finetune.download`（ModelScope 国内镜像，15GB）
5. 配 `finetune/qwen_lora_sft.yaml`（超参跟 `config.py` 对齐）
6. 云端训练：AutoDL **RTX 3090 24GB**，`bash finetune/autodl_train.sh`
7. 评估与取证：`python -m finetune.ab_compare` / `evaluate` / `fact_audit`
8. 导出权重：`model/lora/`（约 20MB adapter）

---

## 六、设计要点

| 设计选择 | 理由 |
|---|---|
| 基座选 **7B-Instruct** 而非更大模型 | 垂直领域适配用 LoRA 即可见效，7B 是单卡 24GB 能全程 bf16 跑完的性价比档 |
| 用 **LoRA** 而非全量微调 | 只训约 0.1% 参数、可解释、可逆、单次训练 106.8 秒，硬件与时效上最优 |
| 云端训练 + **离线权重验收** | 本地 4GB 显存无法承载 7B 基座（约 14GB），训练与部署环境分离是现实约束下的合理工程取舍 |
| **RAG + 微调双轨** | 实测证明微调只承担表达范式、不承担事实记忆（来源 URL 可溯源率 0/20），事实与溯源交由 RAG 检索层 —— 这是双轨架构的实证依据，而非"两个技术都想要" |
| 数据集**完全由 xlsx 真实字段构造** | 数据可溯源是项目的硬要求，SFT 数据与 RAG 知识库共用同一底座，零虚构 |

---

## 七、与课上开发思路逐句对照

| 老师原文 | StudyPath 对应 |
|---------|------------------|
| 1. 需要有初始化的训练数据、预训练模型 | 180 条三库真实数据 + Qwen2.5-7B-Instruct |
| 2. 先把训练的数据处理好，让预训练模型可以接收 | `annotations/build_sft_data.py` → Alpaca 格式 |
| 3. 再把预训练模型进行配置和处理，让它符合当前的需求 | `finetune/model.py` LoRA 注入 |
| 4. 接着可以正式开始喂入语料，训练模型 | `finetune/qwen_lora_sft.yaml` + LLaMA Factory CLI |
| 5. 最后可以进行模型测试、评估 | `finetune/evaluate.py` + `ab_compare.py` + `fact_audit.py` |

五步一一对应，只是把"Bert 分类"换成了"Qwen 生成 + LoRA 领域适配"。

---

## 八、Checklist（已完成项）

- [x] `cache/` 能写（HF 缓存）
- [x] `pretrained/Qwen2.5-7B-Instruct/` 已下载（`python -m finetune.download`，15GB）
- [x] `data/raw/院校数据采集.xlsx` 三库共 180 条真实数据
- [x] `data/processed/` 已生成 train/eval jsonl（144 / 36）+ `dataset_info.json`
- [x] `finetune/config.py` 路径全对（基于 `__file__` 自包含）
- [x] AutoDL 开通 + 依赖装好（PyTorch 2.8 / CUDA 12.8 / Py3.12）
- [x] `finetune/qwen_lora_sft.yaml` 写好
- [x] 跑通完整训练：51 步 / 106.83 秒 / train_loss 1.2952 → eval_loss 0.7597
- [x] `evaluate.py` 输出指标（指令遵循率 100.0% / 平均 ROUGE-L 0.5731）
- [x] `ab_compare.py` 产出 A/B 对照（3/3 组行为变化）
- [x] `fact_audit.py` 产出能力边界数据（来源可溯源 0/20、排名一致 0/7）
- [x] `inference.py::generate_essay()` 已预留应用层入口

---

## 九、后续可继续打磨

1. **微调接线**：在具备 24GB 显存的环境把生成侧切到本地 LoRA（`generate_essay()` 入口已就绪）。当前主链路走云端 API，原因是本地显存约束。
2. **评测集扩量**：自动评估 20 条 → 50–60 条，并补充分错误归因。
3. **数据扩容**：继续按 xlsx 模板采集更多真实院校/案例/文书，观测 LoRA 效果随数据量的变化曲线。
4. **量化对比实验**：在 12GB 显卡上对比 4-bit 量化与 bf16 的效果差异（当前 24GB 环境下无需量化）。
