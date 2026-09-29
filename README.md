# StudyPath AI · 留学申请智能规划助手

> 基于 **LangGraph 多智能体 + RAG 检索增强 + LoRA 微调** 的 AI 留学申请规划系统
> 垂直场景：背景评估 / 选校推荐 / 文书生成 / 时间规划

## 项目简介

StudyPath AI 是一个面向留学申请者的 AI 助手，覆盖从背景评估到申请规划的全流程。系统整合：

- **RAG 检索增强**：基于真实院校数据（学校官网 + QS/USNews + 一亩三分地），回答选校 / 项目要求 / 申请时间等问题，可溯源
- **多智能体协作**：用 LangGraph 编排 4 个 Agent —— 背景评估 → 选校推荐 → 文书生成 → 时间规划
- **LoRA 微调**：基于 Qwen2.5-7B 微调留学文书场景，让生成更贴合招生官偏好
- **N8N / Dify 编排**：申请截止日提醒、文书润色工作流自动化

## 技术栈

| 模块 | 技术 |
|------|------|
| 应用层 | Python 3.12 / LangChain 1.x / LangGraph |
| 向量库 | ChromaDB |
| 基座模型 | Qwen2.5-7B-Instruct |
| 微调框架 | LLaMA Factory (LoRA) |
| 多模态 | PaddleOCR |
| 前端 | Gradio |
| 部署 | Docker / AutoDL 云端 |
| 自动化 | N8N / Dify |

## 项目结构

```
StudyPath-AI/
├── cache/                 # 临时下载缓存
├── configs/               # LLaMA Factory 训练配置
├── data/
│   ├── raw/               # 原始文书数据
│   └── processed/         # 训练数据（Alpaca 格式）
├── model/                 # LoRA 权重输出
├── pretrained/            # 基座模型存放
└── src/                   # 核心代码
    ├── config.py          # 路径 / 超参 / LoRA 配置
    ├── model.py           # Qwen 加载 + LoRA 注入
    ├── processed.py       # 数据格式化
    └── train.py           # 微调训练（LLaMA Factory CLI）
```

## 快速开始

```bash
# 1. 准备 Python 环境（推荐 conda）
conda create -n studypath python=3.12 -y
conda activate studypath

# 2. 安装依赖
pip install -r requirements.txt   # 待补

# 3. 下载基座模型到 pretrained/
python download.py                # 待补

# 4. 微调
llamafactory-cli train configs/qwen_lora_sft.yaml
```

## 数据来源

所有院校数据来自公开可查渠道：
- 学校官网 Admission 页（项目要求、截止日、学费）
- QS / USNews / CSRankings（排名）
- 一亩三分地 / 寄托天下 / ChaseDream（录取案例）

每条数据均带 `source_url`，保证**可溯源、可解释**，严禁虚构。

## 进度

- [x] 院校项目库：8 所真实数据（CMU / Oxford / Cambridge / IC / NYU / Sydney / NUS）
- [ ] 录取案例库（≥100 条）
- [ ] 文书范例库（≥30 篇）
- [ ] LangGraph 多智能体核心
- [ ] RAG 检索增强
- [ ] LoRA 微调训练

## 许可

MIT License（待补）

---

> **作者**：paomo1 · **毕业设计**：AI 大模型应用开发 · **完成时间**：2026
