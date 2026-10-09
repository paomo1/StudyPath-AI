# StudyPath · 手机复习速览（2026-10-06 v2 二次核对）

> ⚠️ 已弃用 PostgreSQL+pgvector，现全面用本地 **Chroma**。

## 1. 技术栈
- 向量库：**Chroma（本地，落盘 `rag/chroma_db/`）** —— 不再是 pgvector
- 嵌入：DashScope `text-embedding-v3`（自实现类，不经 langchain）
- LLM：DashScope `qwen-plus`（`.env` 配 `DASHSCOPE_API_KEY`）
- 框架：LangChain LCEL 检索链 + LangGraph 多智能体
- UI：Gradio 驾驶舱（7860）+ Dify 知识库 + N8N 飞书推送

## 2. RAG 架构（并行编排）
`START → supervisor → 3 个 worker（并行 fan-out）→ synthesizer`（worker 未命中返回 {} 跳过；三 worker 同一 superstep 并发，各写专属字段无需 reducer）
- 检索：MMR `k=8` / `fetch_k=20`
- 建库：`rag/build_vectorstore.py` → 写 `rag/chroma_db/`（跑一次即可重建）
- 配置：`rag/config.py`（`CHROMA_DIR` / `TOP_K` / `fetch_k`）

## 3. 数据（真实可溯源，零虚构）
- 源数据：`data/raw/院校数据采集.xlsx` 三 sheet 共 **180 条**，每条带 `source_url`：
  - 院校项目库 100 ｜ 录取案例库 50 ｜ 文书范例库 30
- 产物：`data/processed/`（train.jsonl / eval.jsonl / rag_evalset.jsonl / rag_metrics.json / eval_results.json / ab_compare.json）

## 4. 微调（LoRA）
- 基座：`Qwen2.5-7B-Instruct`（AutoDL 训练，本地 4GB 带不动）
- 配置：rank8 / alpha16 / target `q,k,v,o_proj` / lr 2e-4 / 3 epoch
- adapter 位置：**`model/lora/`**（非 model/ 根）
- 结果：指令遵循率 100%、ROUGE-L 0.5731（2026-10-02 重跑复核，与 8 月一致）；事实层 URL 命中 0/20（能力边界）
- ⚠️ 同步风险：本地 `model/lora/` 为 8-20，若 AutoDL 10-02~10-04 重训需 scp 拉回

## 5. 关键文件速查
- `rag/agents.py` —— 多智能体 StateGraph（supervisor + 3 worker 并行 + synthesizer）
- `rag/qa.py` —— 单 agent LCEL 检索链
- `rag/build_vectorstore.py` —— 建 Chroma 库
- `rag/config.py` —— `CHROMA_DIR` + `data/raw` xlsx 路径 + 模型名
- `rag/dashscope_embeddings.py` —— 嵌入类
- `finetune/` —— LoRA 训练 / 评估 / 取证（ab_compare.py / evaluate.py / fact_audit.py）
- `model/lora/` —— LoRA 适配器权重
- `dify_kb/` —— Dify 知识库 Markdown
- `docs/全流程架构图.svg` —— 已校正为 Chroma

## 6. 一句话答辩口径
StudyPath 是 AI 留学申请规划助手：用 **Chroma 本地向量库 + DashScope 嵌入**做真实可溯源 RAG，LangGraph 多智能体并行编排（三 worker 同 superstep 并发 fan-out/fan-in），外层接 Dify / N8N / Gradio；LoRA 微调做风格适配，但事实准确性仍依赖 RAG 检索而非生成。
