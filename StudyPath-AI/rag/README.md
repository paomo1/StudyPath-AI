# StudyPath-AI · 留学规划多智能体助手

把已采集的三库（**院校项目库 100 / 录取案例库 50 / 文书范例库 30**）变成**可检索、可对话、可演示**的留学规划助手。
核心能力：**RAG 检索 + LangGraph 多智能体协同**，全部回答带真实来源引用、零编造。

---

## 一、项目简介与定位

垂直场景：**留学申请规划**（毕设方向 = AI 大模型应用开发）。

系统接收用户的留学咨询（如"GPA 3.5 托福 100 申美国 CS 硕士，推荐哪些学校？"），
由**多智能体**拆解为子任务、分别检索对应知识库、再汇总成带引用的结构化答复。

答辩亮点：
1. **全流程可跑**：从数据采集 → 向量化 → RAG 问答 → 多智能体编排 → 网页演示，链路完整。
2. **多智能体架构**：不是单链 RAG，而是 Supervisor + 多 Worker + Synthesizer 的经典编排，能讲清"为什么用多 agent"。
3. **数据真实严谨**：三库全部真实可溯源，prompt 强制"不编造、附来源"，答辩当场可核实。

---

## 二、系统架构

```
用户问题
   │
   ▼
┌─────────────┐
│ Supervisor  │  LLM 决策：该派哪些专家？（school / admission / essay）
└──────┬──────┘
       │ 路由结果（如 ['school','admission','essay']）
   ┌───┼───────────────┐
   ▼   ▼               ▼
┌────────┐  ┌──────────┐  ┌────────┐
│school  │  │admission │  │ essay  │  三个 Worker 各自检索自己的 RAG 库
│ Worker │  │ Worker   │  │ Worker │  （Chroma metadata 按 sheet 隔离）
└───┬────┘  └────┬─────┘  └───┬────┘
    │            │            │
    └────────────┼────────────┘
                 ▼
          ┌──────────────┐
          │ Synthesizer  │  LLM 把三份资料汇总成带 [资料N] 引用的答复
          └──────────────┘
                 │
                 ▼
             Web UI（Gradio）/ CLI（app / app_multi）
```

**为什么用多智能体？** 单链 RAG 只能"一把梭"检索全部资料，容易信息混杂、顾此失彼。
多智能体让每个专家只盯自己的库（院校库只答项目细节、案例库只做背景匹配、文书库只给范文），
Synthesizer 再交叉推理——例如基于案例库判断"当前分数下 Stanford/CMU 竞争力较弱"，
这种洞察单 agent 跑不出来。

---

## 三、技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| 编排 | **LangGraph (StateGraph)** | 手写 Supervisor-Worker，不依赖 langgraph_supervisor 包 |
| RAG | **LangChain 1.x (LCEL)** | 检索链 + `mmr` 多样性召回 |
| 向量库 | **Chroma** | 本地持久化，按 `source_sheet` metadata 隔离三库 |
| Embedding | **DashScope `text-embedding-v3`** | 经原生 SDK 调用（兼容端点对中文/批量有 bug，已绕开） |
| 生成 | **DashScope `qwen-plus`** | 走 OpenAI 兼容端点 |
| UI | **Gradio** | 网页演示版 |

> ⚠️ **API Key 归属**：本项目写死用**阿里云 DashScope** 的 key（embedding 模型只有 DashScope 有，DeepSeek 无 embedding 不能替）。
> key 只活在 `config.py` 和你的本地环境，**不进对话、不截图**。失效时去 `dashscope.console.aliyun.com/apiKey` 重生成，自己写回 `config.py`。

---

## 四、目录结构

```
StudyPath-AI/rag/
├── config.py                  # 路径 / API key / 模型名 / Chroma 目录（改这里）
├── data_loader.py             # xlsx 三库 -> langchain Document（含 38 校中英别名映射）
├── dashscope_embeddings.py    # 自实现 LangChain Embeddings 接口，调 DashScope 原生 SDK
├── build_vectorstore.py       # 切片 + 向量化 + 持久化到 Chroma
├── qa.py                      # 检索链(LCEL) + retrieve_only(query, sheet) 按库隔离检索
├── agents.py                  # 多智能体：StateGraph(Supervisor+3 Worker+Synthesizer) + _clean_answer()
├── app.py                     # 命令行交互（单 agent 问答）
├── app_multi.py               # 命令行交互（多智能体问答）
├── app_gradio.py              # 网页版 UI（Gradio）
├── test_key.py / test_min_embed.py  # 最小验证脚本（key + embedding 可用性）
├── requirements.txt
├── README.md
└── chroma_db/                 # 运行 build 后自动生成（向量库落盘）
```

---

## 五、本机运行步骤（ai-base 环境）

> ⚠️ 联网：dashscope 端点和 pip 装包都要联网。Clash 7897 **可选**——国内直连 dashscope 通常能通，先不开试试；报 `Connection` 类错误再开 Clash 重试。

```powershell
# 全程用 ai-base 的 python 绝对路径，连 conda activate 都不用（最稳，PowerShell 直跑）
cd F:\留学项目\StudyPath-AI\rag

# 1. 装依赖（国内慢可加清华镜像: -i https://pypi.tuna.tsinghua.edu.cn/simple）
C:\Users\13656\anaconda3\envs\ai-base\python.exe -m pip install -r requirements.txt

# 2. 建向量库（只需跑一次，会调用 dashscope embedding，耗少量 token）
C:\Users\13656\anaconda3\envs\ai-base\python.exe build_vectorstore.py

# 3. 选一种方式启动：
C:\Users\13656\anaconda3\envs\ai-base\python.exe app.py          # 命令行单 agent
C:\Users\13656\anaconda3\envs\ai-base\python.exe app_multi.py    # 命令行多智能体
C:\Users\13656\anaconda3\envs\ai-base\python.exe app_gradio.py   # 网页版（浏览器开 http://127.0.0.1:7860）
```

**推荐答辩演示用 `app_gradio.py`**：浏览器界面，老师当场输入问题即可看到
「路由派单 → 三库协同检索 → 带引用汇总」全过程。

示例问题：
- `我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？需要准备什么文书？`
- `CMU 的 MSCS 项目申请要求和截止日期是什么？`
- `GPA 3.2 托福 95 能申到哪些英国 CS 硕士？`

---

## 六、数据真实性说明（毕设硬要求）

- 所有回答**只基于三库检索到的资料**，prompt 强制「不编造、附来源」。
- 每条 Document 的 `metadata.source_url` 来自采集时的官方/第三方真实链接，答复末尾回显 `[资料N]`，方便答辩当场核实。
- 资料不足时助手会如实说明并建议补充哪类数据，而非瞎编——这正是评委想看的数据严谨性。

---

## 七、拿分点对照（理论满分 135）

| 模块 | 拿分 | 状态 |
|------|------|------|
| 全流程项目（采集→向量化→RAG→多智能体→UI） | +10 | ✅ |
| RAG 检索问答（三库精确命中） | +5 | ✅ 已验证 |
| 多智能体编排（LangGraph Supervisor-Worker） | +5 | ✅ 已验证（路由命中 + 交叉推理） |
| 微调（LLaMA Factory 领域 LoRA） | +5 | ⬜ 可选拓展 |
| N8N 自动化编排 | +5 | ⬜ 可选拓展 |
| Dify 可视化 MVP | +5 | ⬜ 可选拓展 |

---

## 八、常见坑

| 现象 | 原因 / 解决 |
|------|------------|
| `Connection timeout` / 连不上 dashscope | 网络不稳。先试直连；不行再开 Clash 7897 重试 |
| `ModuleNotFoundError` | 没装依赖，重跑 `pip install -r requirements.txt` |
| 加载向量库失败 | 没跑 `build_vectorstore.py`，先建库 |
| 401 invalid_api_key | 用了错误的 key。本项目必须用**阿里云 DashScope** key，不是 DeepSeek |
| embedding 报 400 InvalidParameter | DashScope OpenAI 兼容端点对中文/批量有 bug，已改用原生 SDK 绕开（`dashscope_embeddings.py`） |
| 召回不到（"CMU 计算机硕士"答不知） | 中英跨语种召回不稳，已加 38 校中英别名映射 + `mmr` + TOP_K=8 修好 |

---

## 九、下一步可扩展（冲更高分）

1. **微调**：用录取案例库做领域 LoRA，提升录取概率判断的专业度（需 GPU，1650 4G 可跑 QLoRA 7B）。
2. **N8N 编排**：把系统接到飞书/邮件，做"申请季定时推送、多平台同步"。
3. **Dify MVP**：低代码平台再包一层可视化，答辩 PDF 多一张截图。
4. **Gradio 增强**：加历史对话、导出 PDF 咨询报告、院校对比雷达图。
