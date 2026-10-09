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
│ Supervisor  │  LLM 决策：本轮该激活哪些专家，落库 route=['school','admission','essay']
└──────┬──────┘
       │  并行 fan-out（同一 superstep，LangGraph 并发执行）
       ├───────────────┬───────────────┐
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ worker_school│ │worker_admiss.│ │ worker_essay │   route 命中 → 检索本库 + 角色分析
│ 院校项目库    │ │ 录取案例库    │ │ 文书范例库    │   未命中 → 返回 {}，零开销
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │  fan-in（全部完成后才推进）
       └───────────────┬───────────────┘
                       ▼
┌──────────────────┐
│   Synthesizer    │  LLM 汇总三份业务结论 → 全局统一编号 → 最终答复
└────────┬─────────┘
         ▼
   Web UI（Gradio）/ CLI（app_multi）
```

> ⚠️ **拓扑说明（对着代码说）**：三个 worker 挂在 supervisor 的**同一条出边上**，
> 属于 LangGraph 的同一个 superstep，**并发执行**（实测见
> `rag/test_parallel_topology.py`：假 LLM 计时，三 worker 起始时间差 0.00s，
> 端到端 ≈ 3.0s vs 串行版理论 5.0s）。并发安全的关键是三个 worker **各写专属
> State 字段**（`school_*` / `admission_*` / `essay_*`），不存在同 key 更新，
> 因此无需引入 reducer。Supervisor 的 `route` 决定"哪些 worker 真正干活"——
> 未命中的 worker 返回 `{}` 空转跳过、不检索不调用 LLM，"并行执行"与"按需派单"
> 同时成立。8 条边全部是 `add_edge` 直连，无 conditional_edges。

**为什么用多智能体？** 单链 RAG 只能"一把梭"检索全部资料，容易信息混杂、顾此失彼。
多智能体让每个专家只盯自己的库（院校库只答项目细节、案例库只做背景匹配、文书库只给范文），
且每个 worker 会把自己检索到的原文**转成结构化业务结论**（选校梯度 / 风险点 / 文书要点），
再交给 Synthesizer 交叉推理——例如结合案例库判断"当前分数下 Stanford/CMU 竞争力较弱"，
这种"先各自专业判断、再综合"的链路，单 agent 一把检索给不出来。

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

> ⚠️ **API Key 归属**：本项目用**阿里云 DashScope** 的 key（embedding 模型只有 DashScope 有，DeepSeek 无 embedding 不能替）。
> key 存在项目根目录的 `.env`（`DASHSCOPE_API_KEY=...`），由 `config.py` 在启动时加载注入环境变量；`.env` 已被 `.gitignore` 屏蔽，**不进版本库、不进对话、不截图**。
> 失效时去 `dashscope.console.aliyun.com/apiKey` 重新生成，自己写回 `.env` 即可。

---

## 四、目录结构

```
StudyPath-AI/rag/
├── config.py                  # 路径 / 模型名 / Chroma 目录（key 从项目根 .env 加载）
├── data_loader.py             # xlsx 三库 -> langchain Document（含 38 校中英别名映射）
├── dashscope_embeddings.py    # 自实现 LangChain Embeddings 接口，调 DashScope 原生 SDK
├── build_vectorstore.py       # 切片 + 向量化 + 持久化到 Chroma
├── query_norm.py              # 查询侧学校别名归一化（修"Imperial"类裸别名召回失败）
├── qa.py                      # 检索链(LCEL) + retrieve_docs/answer_from_docs 按库隔离检索与生成
├── agents.py                  # 多智能体：StateGraph(Supervisor+3 Worker+Synthesizer) + _clean_answer()
├── app.py                     # 命令行交互（单 agent 问答）
├── app_multi.py               # 命令行交互（多智能体问答）
├── app_gradio.py              # 网页版 UI（Gradio 驾驶舱）
├── demo_capture.py            # 跑一次真实问答并落盘 rag_demo_capture.json（取证用）
├── build_demo_panel.py        # 由上面那个 json 渲染 rag_demo_panel.html（展示面板，不手写）
├── eval_retrieval.py          # 五层检索评测 -> data/processed/rag_metrics.json
├── eval_topology.py           # 并行 / 串行拓扑对照评测（worker 段耗时 + 检索层耗时）
├── measure_latency.py         # 多智能体端到端耗时实测（参考值，受网络与生成长度影响）
├── test_parallel_topology.py  # 并行拓扑验证（假 LLM 计时，不发起真实请求）
├── test_key.py / test_min_embed.py / test_dashscope_embed.py  # 最小验证脚本（key + embedding 可用性）
├── requirements.txt
├── README.md
└── chroma_db/                 # 运行 build 后自动生成（向量库落盘，已在 .gitignore 中）
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
- 每条 Document 的 `metadata.source_url` 来自采集时的官方/第三方真实链接；回答要求附上来源说明或 `source_url`，方便答辩当场核实（`rag/build_demo_panel.py` 渲染的面板里每条命中都带真实来源域名）。
- 资料不足时助手会如实说明并建议补充哪类数据，而非瞎编——这正是评委想看的数据严谨性。

---

## 七、功能完成度

| 模块 | 状态 |
|------|------|
| 数据采集与标注（三库共 180 条，每条带 `source_url`） | ✅ 已完成 |
| 向量化与检索（Chroma + MMR，k=8 / fetch_k=20） | ✅ 已完成 |
| RAG 检索问答（三库按 `source_sheet` 隔离命中） | ✅ 已完成 |
| 多智能体编排（LangGraph Supervisor + 3 Worker + Synthesizer） | ✅ 已完成 |
| 本地演示（Gradio 驾驶舱，`app_gradio.py`） | ✅ 已完成 |
| 领域微调（LoRA · LLaMA Factory · AutoDL RTX 3090） | ✅ 已完成（见 `finetune/`） |
| N8N 自动化编排（本地 docker → Dify API → 飞书） | ✅ 已完成 |
| Dify 可视化 MVP（Chatflow 已发布） | ✅ 已完成 |

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

## 九、后续可继续打磨

1. **评测集扩量**：当前检索评测 30 道、微调自动评估 20 条，可扩到 50–60 道并补充误判归因分析。
2. **召回策略演进**：现有 MMR 已解决"多条内容雷同"的问题；若后续数据量上千条，再评估引入 Rerank 重排层。
3. **微调接线**：`finetune/inference.py::generate_essay()` 已预留应用层入口，可在具备 24GB 显存的环境把生成侧切到本地 LoRA。当前主链路走云端 API，原因是本地 GTX 1650 4GB 显存装不下 7B 基座（约 14GB）。
4. **Gradio 增强**：加历史对话、导出 PDF 咨询报告、院校对比雷达图。
