# StudyPath AI

基于大模型的留学申请规划助手 —— 整合 RAG 检索增强、**LangGraph 多智能体框架**、低代码工作流编排与 LoRA 微调的全流程毕设项目。

## 项目背景

### 要解决的问题
留学申请学生需要同时处理大量分散信息：院校项目官网格式不一（GPA / 语言 / GRE / 截止日 / 学费散落各处）、缺乏同背景录取案例对标、文书写作缺少可溯源范文参照、决策周期长易遗漏 deadline。

### 业务价值（真实可衡量）
- **数据真实可溯源**：知识库 180 条（100 院校 + 50 录取案例 + 30 文书范例）全部来自学校官网 / QS / USNews / 一亩三分地等公开渠道，每条带 `source_url`，零虚构。
- **检索可靠**：口语化 / 别名对抗测试 HitRate@8 = **100%**；RAG 回答的输出忠实度 **100%**（10/10 条引用了正确的 `source_url`）。
- **领域适配**：LoRA 微调纯训练 **106.8 秒**（AutoDL RTX 3090 单卡，51 steps），train_loss 1.2952 → eval_loss 0.7597，收敛未过拟合。
- **降本提效**：将原本需人工翻阅数十个官网的选校与背景评估，压缩为一次带可溯源来源的结构化五阶段申请规划。

## 技术架构

四层解耦：
1. **内核层（智能核心）**：LangChain 1.x（DocumentLoader / Splitter / Embeddings 接入 / VectorStore 封装 / LCEL 检索链 / Prompt 模板）+ **LangGraph**（`StateGraph` 手写 supervisor-worker：选校策略师 / 录取风险评估师 / 文书规划师 三 worker 串行协同 + Synthesizer）。
2. **交互层（用户入口）**：本地 Gradio 驾驶舱（localhost:7860）+ 线上 Dify Chatflow（已发布）。
3. **自动化层**：N8N 本地 docker 工作流（表单 → Dify API → 飞书推送）。
4. **模型层**：LoRA / QLoRA 领域微调（LLaMA Factory）。

> 架构图见 `docs/全流程架构图.svg`。

## 核心功能
- **RAG 问答系统**：Chroma 向量库 + text-embedding-v3 + MMR 检索（fetch_k=20, k=8）+ 38 校别名归一化 + 来源卡片全局统一编号。
- **LangGraph 多智能体规划**：Supervisor 路由 → 三个领域专家 Worker（选校策略师 / 录取风险评估师 / 文书规划师）各自做业务判断 → Synthesizer 整合为五阶段申请规划（选校定稿 → 材料准备 → 文书写作 → 网申提交 → 面试准备）。
- **学术驾驶舱（Gradio）**：画像抽取、路由可视化、参考来源卡片。
- **Dify 低代码 MVP**：同一知识库的快速落地验证。
- **N8N 自动化**：端到端闭环（提问 → 调 AI → 飞书群推送）。
- **LoRA 微调**：基于真实留学语料的领域适配权重。

## 技术栈
- LangChain 1.x
- LangGraph（多智能体框架）
- RAG（Chroma + text-embedding-v3）
- DashScope qwen-plus / text-embedding-v3（OpenAI 兼容端点）
- Gradio（前端驾驶舱）
- Dify（低代码应用）
- N8N（自动化编排）
- LLaMA Factory + LoRA（模型微调）
- openpyxl / pandas（数据处理）

## 快速开始

### 环境要求
- Python 3.9+（已验证 Conda 环境 ai-langchain）
- 依赖安装：`pip install -r finetune/requirements.txt`
- DashScope API Key（配置于项目根 `.env`，由 `rag/config.py` 加载）

### 安装步骤
```bash
pip install -r finetune/requirements.txt
```

### 运行项目（本地 Gradio 驾驶舱）
```bash
cd rag
python app_gradio.py
# 浏览器打开 http://localhost:7860
```

### 多智能体问答（命令行）
```bash
cd rag
python agents.py "我想申请美国CS硕士，GPA3.5托福100，推荐哪些学校？"
```

## 项目结构
```
StudyPath-AI/
├── rag/                  # RAG + 多智能体核心（agents.py / qa.py / config.py / build_vectorstore.py / eval_retrieval.py / app_gradio.py）
├── finetune/             # LoRA 微调模块
│   ├── config.py / model.py / processed.py / train.py / evaluate.py / inference.py   # 微调代码
│   ├── download.py        # 基座下载（AutoDL / ModelScope 国内镜像）
│   ├── qwen_lora_sft.yaml  # LLaMA Factory 训练配置
│   ├── requirements.txt    # 微调依赖
│   ├── autodl_train.sh     # 云端一键训练脚本
│   └── README_AUTODL.md    # AutoDL 训练指南
├── model/lora/           # LoRA 权重（adapter_model.safetensors，约 20MB，不进 git）
├── annotations/          # 数据标注脚本与产物（annotated_dataset.jsonl）
├── data/raw/             # 唯一数据源：院校数据采集.xlsx（180 条，进 git）
├── dify_kb/              # Dify 部署指南与知识库
├── docs/                 # 设计文档与架构图（全流程架构图.svg / 需求说明.md / 微调骨架.md）
├── scripts/              # 本地工具
│   ├── build_pptx.py      # 答辩 PPT 生成脚本（输出路径在脚本顶部配置）
│   └── 启动驾驶舱.ps1     # 一键启动 Gradio 驾驶舱
├── .env                  # 密钥（不进 git）
└── README.md
```

## 演示素材

答辩 PPT 与截图素材由 `scripts/build_pptx.py` 生成，素材来源为真实运行记录：
Gradio 驾驶舱截图、RAG 检索演示面板（`rag/build_demo_panel.py` 渲染）、
LangGraph 架构图、LoRA 训练曲线（`model/lora/training_loss.png`）等。

## 量化成果

**检索与生成（RAG 链路）**

| 指标 | 数值 |
|------|------|
| 规范集 HitRate@8 / MRR | 100% / 1.000 |
| 口语化对抗集 HitRate@8 / MRR | 100% / 0.933 |
| 生成忠实度：引用正确 `source_url` | **100%**（10 / 10） |
| 路由覆盖率 | 100% |
| 延迟 P50 / P95 | 2.67s / 9.04s（RAG）· 3.12s / 9.17s（多智能体） |

**领域微调（LoRA 链路）**

| 指标 | 数值 |
|------|------|
| 训练 loss | train_loss 1.2952 → eval_loss 0.7597（收敛未过拟合） |
| 训练步数 / 耗时 | 51 步 / **106.83 秒**（RTX 3090 单卡，bf16 + FlashAttention2） |
| 权重体积 | LoRA adapter 约 20MB |
| 指令遵循率 / 平均 ROUGE-L | **100.0%** / 0.5731 |
| A/B 对照 | 3 / 3 组业务任务输出发生行为改变（`identical = false`） |

## 能力边界（实测，重要）

同 prompt、同基座、greedy 解码，**唯一变量 = 是否挂载 LoRA adapter**：

| 层面 | 实测结论 |
|---|---|
| **表达层** | ✅ **生效** —— 3/3 组任务从泛化陈述句转为第一人称文书语体 + 结构化输出 |
| **事实层** | ⚠️ **不承担** —— 生成文本的来源 URL 对知识库真实 URL 白名单溯源命中率 **0/20**，排名数字一致率 **0/7** |

**关键对照**：同一个"来源引用"能力，**RAG 链路 `citation_url_hit` = 100%**（URL 取自检索资料的 `source_url` 字段），
而**微调链路 = 0/20**（模型自行生成的 URL）。这正是本项目采用
**「RAG 检索层负责事实与 `source_url` 溯源 + 微调层负责语体与结构生成」双轨架构**、
而非纯微调方案的实证依据。核查脚本：`finetune/fact_audit.py`（本地可跑，无需 GPU）。

## 作者

- GitHub：[@paomo1](https://github.com/paomo1)
- 项目方向：AI 大模型应用开发（毕业设计）
- 完整项目说明见仓库根目录 `README.md`
