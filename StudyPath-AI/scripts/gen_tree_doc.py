# -*- coding: utf-8 -*-
"""
扫描磁盘生成完整目录树文档（HTML + Markdown）。

真的去 walk 磁盘而不是照抄手写清单：每个文件必须有标注，缺一个即 assert 失败；
渲染完成后还要与实际文件集合做差集校验，漏渲染同样报错。每条记录标注大小、行数、
git 状态与职责说明。
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]                  # scripts/ → StudyPath-AI/ → 仓库根
OUT_DIR = HERE.parents[1] / "docs"      # → StudyPath-AI/docs/

# ── 每个文件的标注（key = 相对 ROOT 的 posix 路径）─────────────────────────
A = {
    # ===== 根目录 =====
    ".gitignore": "仓库根忽略规则：个人材料 / 开发期归档 / Excel 锁文件。注意注释必须独占一行",
    "README.md": "GitHub 仓库首页。项目背景/技术架构/核心功能/技术栈/快速开始/实测结果/能力边界",

    # ===== StudyPath-AI 顶层 =====
    "StudyPath-AI/.env": "环境变量：DASHSCOPE_API_KEY（+可选覆盖 CHAT_MODEL/EMBED_MODEL/BASE_URL）。已被忽略，不进 git",
    "StudyPath-AI/.gitignore": "子目录忽略规则：pretrained/ cache/ **/chroma_db/（model/* 但放行 model/lora/）",
    "StudyPath-AI/README.md": "子项目主 README。核心能力表/技术栈表/真实目录结构/实测结果/能力边界（RAG 100% vs 微调 0/20）",
    "StudyPath-AI/__pycache__/build_pptx.cpython-312.pyc": "编译缓存残留（build_pptx.py 移入 scripts/ 之前的）。可删，已忽略",

    # ===== 标注层 annotations/ =====
    "StudyPath-AI/annotations/build_annotations.py": "数据标注归一化（B 方案）：把 xlsx 原始字段 → 干净标签（申请结果/文书类型/质量/国家/排名档），产出 jsonl + 分布图",
    "StudyPath-AI/annotations/build_sft_data.py": "SFT 训练集构造：读 xlsx 三 sheet → Alpaca 格式，180 条切 train 144 / eval 36。零虚构",
    "StudyPath-AI/annotations/figures/dist_申请结果.svg": "标注分布图：Admit 49 / Reject 1",
    "StudyPath-AI/annotations/figures/dist_文书类型.svg": "标注分布图：SOP 13 / PS 11 / CV 5 / LOR 1",
    "StudyPath-AI/annotations/figures/dist_文书质量.svg": "标注分布图：中 15 / 优 10 / 良 5",
    "StudyPath-AI/annotations/figures/dist_院校国家.svg": "标注分布图：美国 54 / 英国 16 / 加拿大 13 / 澳洲 5 / 香港 4 / 新加坡 3 / 韩国 2 / 瑞士 1 / 荷兰 1 / 日本 1",
    "StudyPath-AI/annotations/figures/dist_排名档.svg": "标注分布图：冲(顶尖) 39 / 稳(主流) 29 / 保(保底) 7 / Unknown 25",
    "StudyPath-AI/annotations/output/annotated_dataset.jsonl": "标注产物：180 条归一化记录，每条带 source_url",
    "StudyPath-AI/annotations/output/stats.json": "标注统计汇总：申请结果/文书类型/文书质量/院校国家/排名档 5 个维度的分布计数",

    # ===== 数据层 data/ =====
    "StudyPath-AI/data/raw/院校数据采集.xlsx": "★ 唯一数据源。3 sheet = 院校项目库 100 + 录取案例库 50 + 文书范例库 30 = 180 条，全部真实可溯源",
    "StudyPath-AI/data/processed/train.jsonl": "SFT 训练集 144 条（Alpaca 格式）",
    "StudyPath-AI/data/processed/eval.jsonl": "SFT 留出集 36 条（LLaMA Factory 未使用，实际训练从 train 再切 val_size=0.1）",
    "StudyPath-AI/data/processed/dataset_info.json": "LLaMA Factory 数据集注册文件：alpaca 格式 + 列名映射（instruction/input/output）",
    "StudyPath-AI/data/processed/ab_compare.json": "★ A/B 对照结果：同 prompt 基座 vs 基座+LoRA，3/3 组输出变化（identical=false 即证据）",
    "StudyPath-AI/data/processed/eval_results.json": "微调自动评估成绩单：指令遵循率 100.0%（20/20）、平均 ROUGE-L 0.5731，含生成原文留档",
    "StudyPath-AI/data/processed/rag_evalset.jsonl": "RAG 检索评测集 50 题：含规范问法 + 口语化对抗样本",
    "StudyPath-AI/data/processed/rag_metrics.json": "RAG 五层评测指标：A规范/B对抗 HitRate·MRR/C忠实度/D路由准确率(30题)/E RAG 单链延迟 P50·P95，另有并行拓扑 A/B 与检索层耗时",

    # ===== RAG 应用层 rag/ =====
    "StudyPath-AI/rag/README.md": "RAG 层说明：架构图（并行 fan-out/fan-in）/技术栈/目录结构/本机运行步骤/数据真实性说明/功能完成度/常见坑",
    "StudyPath-AI/rag/config.py": "配置中心。零依赖加载根 .env（优先 python-dotenv，否则手动解析），暴露 CHROMA_DIR/TOP_K=8/fetch_k=20 等",
    "StudyPath-AI/rag/data_loader.py": "数据装载：xlsx 三 sheet → LangChain Document 列表 + 学校别名表",
    "StudyPath-AI/rag/dashscope_embeddings.py": "自实现 Embeddings 类：直接调 DashScope 原生 SDK（text-embedding-v3）",
    "StudyPath-AI/rag/build_vectorstore.py": "建向量库：切片 → 批量向量化 → 写入 Chroma（跑一次即可，产物可重建）",
    "StudyPath-AI/rag/qa.py": "单 agent 检索链（LCEL）。含 build_llm() / retrieve_docs() / answer_from_docs()，MMR 检索 k=8 fetch_k=20",
    "StudyPath-AI/rag/query_norm.py": "查询侧校名别名归一化：从 xlsx 动态反查，按 token 长度降序只替换最长命中，避免 UW 之类误伤",
    "StudyPath-AI/rag/agents.py": "★ LangGraph 多智能体：START → supervisor → 3 worker（并行 fan-out）→ synthesizer 的 StateGraph",
    "StudyPath-AI/rag/test_parallel_topology.py": "★ 并行拓扑验证脚本：假 LLM 计时证明三 worker 同 superstep 并发（端到端 ≈ 3.0s vs 串行理论 5.0s），并打印边表供 PPT 截图",
    "StudyPath-AI/rag/eval_topology.py": "★ 拓扑对照评测：同一条 query 分别喂并行图与串行图，拆出 supervisor / worker / synthesizer 三段耗时，外加检索层耗时，写回 rag_metrics.json",
    "StudyPath-AI/rag/measure_latency.py": "多智能体端到端耗时实测（真调云端）：含网络与生成长度影响，只作记录，不当工程指标",
    "StudyPath-AI/rag/app.py": "命令行交互 demo（单 agent）",
    "StudyPath-AI/rag/app_multi.py": "命令行交互 demo（多智能体）",
    "StudyPath-AI/rag/app_gradio.py": "★ 学术驾驶舱网页版：Gradio UI + 自研 CSS/JS 背景层，演示主入口 localhost:7860",
    "StudyPath-AI/rag/app_gradio_diag.py": "诊断版：最小可运行核，用于排查 Gradio 4.x 下 Textbox/Button 的渲染与 style 命中问题",
    "StudyPath-AI/rag/app_gradio_v1_basic.py": "驾驶舱 v1 白底备份版（保留作对照）",
    "StudyPath-AI/rag/demo_capture.py": "跑一次真实检索+问答并落盘 JSON，供 PPT 生成真实截图。单次检索、同源生成、路径基于 __file__",
    "StudyPath-AI/rag/rag_demo_capture.json": "demo 抓取数据：真实召回文档 + 真实回答 + 真实耗时",
    "StudyPath-AI/rag/rag_demo_panel.html": "RAG demo 展示面板（由 build_demo_panel.py 从上面的 json 自动生成，杜绝手写不一致）",
    "StudyPath-AI/rag/build_demo_panel.py": "从 rag_demo_capture.json 生成展示面板 HTML，含极简 Markdown 渲染 + 截断时补全 ** 标记",
    "StudyPath-AI/rag/eval_retrieval.py": "★ 五层检索评测脚本：规范集/对抗集 HitRate·MRR、生成忠实度、路由准确率、RAG 单链延迟 P50/P95",
    "StudyPath-AI/rag/test_key.py": "验证脚本：绕开 langchain 用 OpenAI 兼容端点验证 key 是否有效（只打印前缀不泄露）",
    "StudyPath-AI/rag/test_min_embed.py": "验证脚本：最小独立 embedding 测试，只用 dashscope SDK 隔离验证 key + SDK 是否跑通",
    "StudyPath-AI/rag/test_dashscope_embed.py": "验证脚本：dashscope 原生 SDK 多文本对照测试",
    "StudyPath-AI/rag/requirements.txt": "RAG 依赖：langchain / langchain-openai / langchain-chroma / chromadb / langgraph / gradio / openpyxl",
    "StudyPath-AI/rag/chroma_db/chroma.sqlite3": "Chroma 向量库主库（1.7MB）。由 xlsx 重建，已取消 git 跟踪",
    "StudyPath-AI/rag/chroma_db/78faf605-3f12-4817-b754-be49c09f7df0/data_level0.bin": "Chroma 向量数据段（423KB）。可重建，已取消 git 跟踪",
    "StudyPath-AI/rag/chroma_db/78faf605-3f12-4817-b754-be49c09f7df0/header.bin": "Chroma 索引头。可重建，已取消 git 跟踪",
    "StudyPath-AI/rag/chroma_db/78faf605-3f12-4817-b754-be49c09f7df0/length.bin": "Chroma 索引长度表。可重建，已取消 git 跟踪",
    "StudyPath-AI/rag/chroma_db/78faf605-3f12-4817-b754-be49c09f7df0/link_lists.bin": "Chroma 索引链表（空）。可重建，已取消 git 跟踪",

    # ===== 微调层 finetune/ =====
    "StudyPath-AI/finetune/.gitkeep": "占位说明文件：说明 finetune/ 目录用途（原 src/ + configs/ 已合并到此）",
    "StudyPath-AI/finetune/__init__.py": "空文件，把 finetune/ 标记为 Python 包（支持 python -m finetune.xxx）",
    "StudyPath-AI/finetune/config.py": "微调配置中心：路径推导（基于 __file__）/基座与输出目录/训练超参/INSTRUCTION_TMPL",
    "StudyPath-AI/finetune/model.py": "模型加载与 LoRA 注入 + 保存 adapter 权重",
    "StudyPath-AI/finetune/processed.py": "数据预处理（通用转换器 + ★三道安全闸门：空数据/低于 MIN_SAMPLES=20/少于现有数据集时中止，防覆盖真实数据）",
    "StudyPath-AI/finetune/train.py": "训练入口（主用 LLaMA Factory CLI，备用 transformers.Trainer 分支）",
    "StudyPath-AI/finetune/download.py": "下载 Qwen2.5-7B-Instruct 基座（约 15GB）到 pretrained/，走 ModelScope 国内镜像",
    "StudyPath-AI/finetune/inference.py": "推理入口：从基座取 tokenizer，PeftModel 挂 adapter。检测不到 bitsandbytes 自动退化为 bf16",
    "StudyPath-AI/finetune/evaluate.py": "自动评估：指令遵循率 + ROUGE-L，结果落盘 eval_results.json（含生成原文留档）",
    "StudyPath-AI/finetune/ab_compare.py": "★ A/B 对照：同 prompt 跑基座 vs 基座+LoRA。用 disable_adapter() 上下文避免原地注入污染",
    "StudyPath-AI/finetune/fact_audit.py": "★ 事实层核查：从 xlsx 抽真实 URL 白名单，比对微调输出的 URL 与排名 → URL 命中 0/20、排名一致 0/7",
    "StudyPath-AI/finetune/autodl_train.sh": "AutoDL 一键训练脚本：切回项目根 → 装依赖 → 下基座 → 训练 → 评估",
    "StudyPath-AI/finetune/qwen_lora_sft.yaml": "LLaMA Factory 训练配置：LoRA rank8/alpha16/target q,k,v,o_proj/lr 2e-4/epochs 3/bs1/grad_accum8/bf16/fa2/cutoff2048",
    "StudyPath-AI/finetune/requirements.txt": "微调依赖：llamafactory / transformers / peft / datasets / accelerate / torch / sentencepiece / modelscope / openpyxl",
    "StudyPath-AI/finetune/README_AUTODL.md": "AutoDL 云端训练指南：为什么上云/环境准备/scp 上传/一键训练/训练结果/A-B 取证/常见坑",

    # ===== 模型产物 model/lora/ =====
    "StudyPath-AI/model/lora/README.md": "LoRA model card：目录内容说明/训练数据/训练结果/能力边界实测/复现推理步骤",
    "StudyPath-AI/model/lora/adapter_model.safetensors": "★ LoRA 权重本体 20MB。train_loss 1.2952 → eval_loss 0.7597（51 步 / 106.8 秒）",
    "StudyPath-AI/model/lora/adapter_config.json": "adapter 配置：r=8 / lora_alpha=16 / target_modules=q,k,v,o_proj / base=Qwen2.5-7B-Instruct",
    "StudyPath-AI/model/lora/trainer_state.json": "训练过程记录：真实 global_step=51 与 loss 序列（推导 129 训练 + 15 验证 的依据）",
    "StudyPath-AI/model/lora/train_results.json": "训练指标：train_loss / train_runtime 106.83 秒 / train_samples_per_second 等",
    "StudyPath-AI/model/lora/eval_results.json": "验证指标：eval_loss 0.7597",
    "StudyPath-AI/model/lora/all_results.json": "训练+评估指标合并汇总",
    "StudyPath-AI/model/lora/trainer_log.jsonl": "逐条训练日志",
    "StudyPath-AI/model/lora/training_loss.png": "训练 loss 曲线图（PPT 直接用）",
    "StudyPath-AI/model/lora/training_eval_loss.png": "验证 loss 曲线图（PPT 直接用）",
    "StudyPath-AI/model/lora/chat_template.jinja": "Qwen ChatML 对话模板存档（LLaMA Factory 训练时所用）",
    "StudyPath-AI/model/lora/tokenizer_config.json": "tokenizer 配置存档（体积极小）",
    "StudyPath-AI/model/lora/tokenizer.json": "11MB 词表。项目推理链不读它（inference.py:47 / ab_compare.py:108 均从基座取），已排除出 git",
    "StudyPath-AI/model/lora/training_args.bin": "TrainingArguments 序列化快照（pickle，冗余于 yaml 配置）",

    # ===== Dify 知识库 dify_kb/ =====
    "StudyPath-AI/dify_kb/院校项目库.md": "Dify 知识库：100 个院校项目，每条附 source_url",
    "StudyPath-AI/dify_kb/录取案例库.md": "Dify 知识库：50 条真实录取案例",
    "StudyPath-AI/dify_kb/文书范例库.md": "Dify 知识库：30 条文书范例链接",
    "StudyPath-AI/dify_kb/Dify部署指南.md": "Dify 云端部署指南：前置/步骤/Prompt 模板/测试题/注意事项",

    # ===== 文档 docs/ =====
    "StudyPath-AI/docs/StudyPath_项目需求与功能说明.md": "需求与功能说明：背景价值/核心功能清单（RAG·多智能体·驾驶舱·Dify·N8N·LoRA）/技术栈/数据规模/量化成果",
    "StudyPath-AI/docs/StudyPath_微调模块骨架设计.md": "微调模块骨架设计：对齐课上企业级微调范式，含完整目录树与各文件实现要点",
    "StudyPath-AI/docs/StudyPath_手机复习速览.md": "手机复习速览：答辩前碎片时间速记版，单页浓缩架构/关键口径/数字",
    "StudyPath-AI/docs/review-site/index.html": "手机复习速览的网页版（单文件 HTML，手机浏览器直接打开）",
    "StudyPath-AI/docs/全流程架构图.svg": "全流程架构图（已按代码事实校正：Chroma 而非 pgvector、并行 fan-out/fan-in、3 worker）",
    "StudyPath-AI/docs/完整目录树.html": "◀ 本文件。由脚本真实扫描磁盘生成（非手写清单），逐文件标注",
    "StudyPath-AI/docs/完整目录树.md": "◀ 本文件的 Markdown 版本，便于 grep / 终端查看",

    # ===== 脚本 scripts/ =====
    "StudyPath-AI/scripts/build_pptx.py": "★ PPT 生成器：把答辩内容逐页导出为 .pptx（三档底色 + 含图页配「这张图证明了什么」标注条）",
    "StudyPath-AI/scripts/gen_topology_png.py": "生成并行版 LangGraph 拓扑 PNG（matplotlib 手绘 fan-out/fan-in），输出到答辩 PPT 素材目录，覆盖前自动备份旧图",
    "StudyPath-AI/scripts/gen_pptx_preview.py": "◀ 版式预览器：把 .pptx 逐形状还原成 HTML（坐标/字号/颜色，图片 base64 内嵌），--only N 导出单页供 headless 截图核对。本机无 PowerPoint，这是验收版式的标准手法",
    "StudyPath-AI/scripts/启动驾驶舱.ps1": "启动脚本：清理 7860 端口 → 启动 app_gradio.py。路径全部基于脚本位置推导，可换机器",
    "StudyPath-AI/scripts/gen_tree_doc.py": "◀ 本目录树的生成器。真实扫描磁盘 + 逐文件标注字典 + 两道断言（漏标注/漏渲染即中止输出），产出 docs/完整目录树.{html,md}",
}

# 目录标注
D = {
    "StudyPath-AI": "★ 主项目根（也是 git 仓库的子目录）",
    "StudyPath-AI/annotations": "【标注层】数据标注归一化 + SFT 数据集构造 + 分布图",
    "StudyPath-AI/annotations/figures": "5 张标注分布图（SVG）",
    "StudyPath-AI/annotations/output": "标注产物（B 方案）",
    "StudyPath-AI/data": "【数据层】唯一数据源 + 全部训练/评测产物",
    "StudyPath-AI/data/raw": "原始数据",
    "StudyPath-AI/data/processed": "处理产物：训练集 + 全部评测结果",
    "StudyPath-AI/rag": "【RAG 应用层】LangChain 检索链 + LangGraph 多智能体 + Gradio 驾驶舱",
    "StudyPath-AI/rag/chroma_db": "Chroma 向量库（可重建，已取消 git 跟踪）",
    "StudyPath-AI/finetune": "【微调层】LoRA 训练/评估/推理/取证全流程",
    "StudyPath-AI/model": "模型产物",
    "StudyPath-AI/model/lora": "★ LoRA 适配器（微调环节唯一的产物，随仓库发布）",
    "StudyPath-AI/cache": "★ 注意：空目录。LLaMA Factory / HF 的缓存位置（已被忽略）",
    "StudyPath-AI/pretrained": "★ 注意：空目录。基座模型存放位置（已被忽略）",
    "StudyPath-AI/pretrained/Qwen2.5-7B-Instruct": "★ 注意：空目录 —— 本地并未保留 15GB 基座，需 finetune/download.py 重新下载后才能跑推理",
    "StudyPath-AI/rag/chroma_db/78faf605-3f12-4817-b754-be49c09f7df0": "Chroma collection 数据目录（4 个 .bin，418 KB）",
    "StudyPath-AI/dify_kb": "【Dify 知识库】低代码 MVP 用的 markdown 知识库",
    "StudyPath-AI/docs": "项目文档",
    "StudyPath-AI/docs/review-site": "手机复习速览的网页版站点（单文件 HTML）",
    "StudyPath-AI/scripts": "工具脚本",
    "归档_留学项目开发期": "【开发期归档，已忽略】早期爬取脚本/中间批次数据/工程截图/旧模板。不属项目交付物",
    "归档_留学项目开发期/工程截图": "工程截图：Dify chatflow / Gradio 成果 / N8N 工作流 / 飞书群消息",
}
for d in ["StudyPath-AI/__pycache__", "StudyPath-AI/finetune/__pycache__",
          "StudyPath-AI/rag/__pycache__", "StudyPath-AI/scripts/__pycache__"]:
    D[d] = "Python 编译缓存（可删，已忽略）"

# 归档目录逐个标注
ARCH = {
    "append_batch.py": "早期：把批次 JSON 追加写入 Excel",
    "append_cases.py": "早期：把录取案例批次写入 Excel",
    "append_essays.py": "早期：把文书范例批次写入 Excel",
    "batch_0.json": "早期：第 0 批爬取的院校数据（19 条）",
    "batch_1.json": "早期：第 1 批院校数据",
    "batch_2.json": "早期：第 2 批院校数据",
    "batch_3.json": "早期：第 3 批院校数据",
    "batch_4.json": "早期：第 4 批院校数据",
    "batch_cases.json": "早期：录取案例批次数据",
    "batch_essays.json": "早期：文书范例批次数据",
    "data_schema_template.json": "早期：数据表结构模板定义",
    "extract_pdf.py": "早期：从 PDF 提取文本（读培养方案/说明文档）",
    "gen_excel_template.py": "早期：生成 Excel 模板（17 列表头）",
    "inspect_essay.py": "早期：查看文书 sheet 的临时脚本",
    "inspect_other.py": "早期：查看其他 sheet 的临时脚本",
    "inspect_xlsx.py": "早期：查看 xlsx 结构与列名的临时脚本",
    "verify_all.py": "早期：三库条数一致性校验",
    "verify_xlsx.py": "早期：xlsx 行数核对",
    "毕设说明文档_提取.txt": "从毕设说明 PDF 提取的文本（822 行）",
    "院校数据采集.xlsx": "早期开发期那份 xlsx 拷贝（正式版在 data/raw/）",
    "院校数据采集模板.xlsx": "空白模板",
    "院校数据采集模板_50条_backup_before_100.xlsx": "从 50 条扩到 100 条之前的备份",
    "工程截图/Dify的chatflow截图.png": "工程截图：Dify chatflow 编排",
    "工程截图/gradio成果展示图.png": "工程截图：Gradio 驾驶舱成果",
    "工程截图/工作流截图.png": "工程截图：N8N 工作流",
    "工程截图/飞书群消息截图.png": "工程截图：飞书群消息推送",
}


def fmt_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f} KB"
    return f"{n/1024/1024:.1f} MB"


def count_lines(p):
    try:
        with p.open(encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return None


def rel(p):
    return p.relative_to(ROOT).as_posix()


# ── 1. 真实扫描 ────────────────────────────────────────────────────────────
all_files, all_dirs = [], []
for dirpath, dirnames, filenames in os.walk(ROOT):
    d = Path(dirpath)
    if d == ROOT and ".git" in dirnames:
        dirnames.remove(".git")
    for dn in dirnames:
        all_dirs.append(rel(d / dn))
    for fn in filenames:
        all_files.append(rel(d / fn))

all_files.sort()
all_dirs.sort()

# ── 2. 断言：一个都不能漏 ──────────────────────────────────────────────────
missing = []
for f in all_files:
    if "__pycache__" in f:          # 编译缓存：统一聚合说明，不逐个标注
        continue
    if f.startswith("归档_留学项目开发期/"):
        key = f.split("/", 1)[1]
        if key not in ARCH:
            missing.append(f)
    elif f not in A:
        missing.append(f)

if missing:
    raise SystemExit("❌ 以下文件没有标注，请补全：\n  " + "\n  ".join(missing))

no_dir_desc = [d for d in all_dirs if d not in D and "__pycache__" not in d]
if no_dir_desc:
    raise SystemExit("❌ 以下目录没有标注：\n  " + "\n  ".join(no_dir_desc))

print(f"✅ 扫描通过：{len(all_files)} 个文件 / {len(all_dirs)} 个目录，全部已标注")

# ── 3. git 状态（三分类：已跟踪 / 已忽略 / 新增未跟踪）────────────────────
import subprocess


def _git(*args):
    return set(subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    ).stdout.splitlines())


tracked = _git("ls-files")
ignored = _git("ls-files", "-o", "-i", "--exclude-standard")
newly = _git("ls-files", "-o", "--exclude-standard")

# ── 4. 生成 HTML ───────────────────────────────────────────────────────────
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


LAYERS = [
    ("根目录", ["README.md", ".gitignore"]),
    ("StudyPath-AI/ — 主项目根", [f for f in all_files if f.startswith("StudyPath-AI/")]),
]

rows_html = []
EMITTED = set()      # 记录真正渲染出来的路径，最后与磁盘清单比对


def emit(display, is_dir, path, desc, indent=""):
    EMITTED.add(path)
    if is_dir:
        meta = ""
        cls = "dir"
    else:
        p = ROOT / path
        size = fmt_size(p.stat().st_size)
        n = count_lines(p)
        meta = size + (f" · {n} 行" if n is not None else "")
        if path in ignored:
            cls, tag = "file out", "🚫 忽略"
        elif path in newly:
            cls, tag = "file new", "🆕 新增"
        else:
            cls, tag = "file in", "✅ 进库"
        meta = tag + " · " + meta
    rows_html.append(
        f'<div class="row {cls}">'
        f'<span class="nm">{esc(indent)}{"📁 " if is_dir else ""}{esc(display)}</span>'
        f'<span class="meta">{esc(meta)}</span>'
        f'<span class="desc">{esc(desc)}</span>'
        f'</div>'
    )


def tree_walk(d: Path, prefix=""):
    """递归输出已排序的目录树行（带缩进与树枝符号）"""
    entries = sorted(
        [(x, True) for x in d.iterdir() if x.is_dir() and x.name not in (".git", "__pycache__")] +
        [(x, False) for x in d.iterdir() if x.is_file()],
        key=lambda t: (not t[1], t[0].name.lower())
    )
    for i, (p, is_dir) in enumerate(entries):
        last = (i == len(entries) - 1)
        branch = "└─ " if last else "├─ "
        r = rel(p)
        desc = D.get(r, "") if is_dir else (
            A.get(r) or ARCH.get(r.split("/", 1)[1] if r.startswith("归档_") else r, ""))
        emit(p.name + ("/" if is_dir else ""), is_dir, r, desc, indent=prefix + branch)
        if is_dir:
            tree_walk(p, prefix + ("   " if last else "│  "))


# 手动按层组织：根 → StudyPath-AI 各子区 → 归档
def section(title, subtitle):
    rows_html.append(f'<div class="sec"><b>{esc(title)}</b><span>{esc(subtitle)}</span></div>')


rows_html.append('<div class="sec root"><b>F:\\留学项目\\</b><span>git 仓库根 · master · github.com/paomo1/StudyPath-AI</span></div>')
for f in [".gitignore", "README.md"]:
    emit(f, False, f, A[f])

# StudyPath-AI 顶层文件
rows_html.append('<div class="sec"><b>StudyPath-AI/</b><span>主项目根</span></div>')
for f in [".env", ".gitignore", "README.md"]:
    emit(f, False, f"StudyPath-AI/{f}", A[f"StudyPath-AI/{f}"])

# 按业务层遍历
AREAS = [
    ("annotations", "【标注层】数据标注归一化 + SFT 数据集构造"),
    ("data", "【数据层】唯一数据源 + 训练/评测全部产物"),
    ("rag", "【RAG 应用层】LangChain 检索链 + LangGraph 多智能体 + Gradio 驾驶舱"),
    ("finetune", "【微调层】LoRA 训练 / 评估 / 推理 / 取证"),
    ("model", "【模型产物】LoRA 适配器"),
    ("dify_kb", "【Dify 知识库】低代码 MVP 知识库"),
    ("docs", "【文档】需求说明 / 微调骨架 / 架构图"),
    ("scripts", "【脚本】PPT 生成器 / 启动脚本"),
]
for area, subtitle in AREAS:
    rows_html.append(f'<div class="sec"><b>StudyPath-AI/{area}/</b><span>{subtitle}</span></div>')
    tree_walk(ROOT / "StudyPath-AI" / area)

# 空目录（有信息量：pretrained 空 → 本地没有 15GB 基座）
rows_html.append('<div class="sec warn"><b>空目录（容易被忽略）</b><span>没有任何文件，下面单独列出</span></div>')
for ed in ["StudyPath-AI/cache", "StudyPath-AI/pretrained", "StudyPath-AI/pretrained/Qwen2.5-7B-Instruct"]:
    emit(Path(ed).name + "/", True, ed, D[ed], indent="└─ ")

# pycache
rows_html.append('<div class="sec warn"><b>__pycache__/ × 4 处</b><span>Python 编译缓存，共 38 个 .pyc / 417 KB，可删（已被 .gitignore 忽略）</span></div>')

# 归档
rows_html.append('<div class="sec warn"><b>归档_留学项目开发期/</b><span>开发期归档 · 已忽略 · 不属交付物 · 26 个文件 1.2 MB</span></div>')
tree_walk(ROOT / "归档_留学项目开发期")

# ── 覆盖校验：磁盘上的每个文件都必须真的渲染进 HTML（漏一个就报错）────────
expect_files = {f for f in all_files if "__pycache__" not in f}
not_rendered = sorted(expect_files - EMITTED)
if not_rendered:
    raise SystemExit("❌ 以下文件没被渲染进 HTML：\n  " + "\n  ".join(not_rendered))
print(f"✅ 覆盖校验通过：{len(expect_files)} 个文件全部渲染进文档")

n_tracked = sum(1 for f in all_files if f in tracked)
n_new = sum(1 for f in all_files if f not in tracked and f in newly)
n_ignored = len(all_files) - n_tracked - n_new
total_bytes = sum((ROOT / f).stat().st_size for f in all_files)

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>StudyPath · 完整目录树（逐文件标注）</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f4f6fa;color:#1f2937;
       padding:28px;line-height:1.65;font-size:14px}}
  .wrap{{max-width:1180px;margin:0 auto}}
  h1{{font-size:24px;margin-bottom:6px}}
  .sub{{color:#6b7280;font-size:13px;margin-bottom:18px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:18px}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px}}
  .card b{{display:block;font-size:22px;color:#2563eb}}
  .card span{{font-size:12px;color:#6b7280}}
  .legend{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 16px;margin-bottom:18px;font-size:13px}}
  .legend b{{margin-right:10px}}
  .tag{{display:inline-block;padding:1px 8px;border-radius:20px;font-size:12px;margin-right:8px}}
  .t1{{background:#dcfce7;color:#166534}} .t2{{background:#fee2e2;color:#991b1b}}
  .t3{{background:#fef3c7;color:#92400e}} .t4{{background:#e0e7ff;color:#3730a3}}
  .t5{{background:#dbeafe;color:#1e40af}}
  .panel{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}}
  .sec{{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
        background:#eff6ff;border-top:1px solid #dbeafe;border-bottom:1px solid #dbeafe;
        padding:8px 16px;font-size:13px}}
  .sec:first-child{{border-top:none}}
  .sec b{{color:#1e40af;font-family:Consolas,Monaco,monospace;font-size:13.5px}}
  .sec span{{color:#6b7280;font-size:12px;text-align:right}}
  .sec.root{{background:#1e293b}} .sec.root b{{color:#f1f5f9}} .sec.root span{{color:#94a3b8}}
  .sec.warn{{background:#fffbeb;border-color:#fde68a}} .sec.warn b{{color:#92400e}}
  .row{{display:grid;grid-template-columns:360px 130px 1fr;gap:12px;
        padding:3px 16px;border-bottom:1px solid #f3f4f6;align-items:baseline}}
  .row:hover{{background:#f8fafc}}
  .row:last-child{{border-bottom:none}}
  .nm{{font-family:Consolas,Monaco,"Courier New",monospace;font-size:12.5px;white-space:pre;overflow-wrap:anywhere}}
  .row.dir .nm{{color:#1e40af;font-weight:700}}
  .row.out .nm{{color:#9ca3af}}
  .row.new .nm{{color:#1d4ed8;background:#eff6ff}}
  .meta{{font-family:Consolas,Monaco,monospace;font-size:11.5px;color:#9ca3af;text-align:right}}
  .desc{{font-size:12.5px;color:#4b5563;overflow-wrap:anywhere}}
  .row.out .desc{{color:#9ca3af}}
  .foot{{margin-top:18px;color:#9ca3af;font-size:12px;text-align:center}}
</style>
</head>
<body><div class="wrap">
<h1>StudyPath · 完整目录树（逐文件标注）</h1>
<div class="sub">扫描对象：<code>F:\\留学项目\\</code>　·　git 仓库根 &nbsp;|&nbsp; 分支 master &nbsp;|&nbsp; remote github.com/paomo1/StudyPath-AI</div>

<div class="cards">
  <div class="card"><b>{len(all_files)}</b><span>文件（不含 .git 内部）</span></div>
  <div class="card"><b>{len(all_dirs)}</b><span>目录（含 2 个空目录）</span></div>
  <div class="card"><b>{n_tracked}</b><span>✅ 进 git 版本库</span></div>
  <div class="card"><b>{n_ignored}</b><span>🚫 被 gitignore 忽略</span></div>
  <div class="card"><b>{n_new}</b><span>🆕 新增未提交</span></div>
  <div class="card"><b>{fmt_size(total_bytes)}</b><span>工作区总大小</span></div>
</div>

<div class="legend">
  <b>图例</b>
  <span class="tag t1">✅ 进 git</span>
  <span class="tag t2">🚫 被忽略 / 可删</span>
  <span class="tag t5">🆕 新增未提交</span>
  <span class="tag t3">★ 核心产物</span>
  <span class="tag t4">📁 目录</span>
</div>

<div class="panel">
{''.join(rows_html)}
</div>

<div class="foot">本页由脚本真实扫描磁盘生成（非手写清单）—— {len(all_files)} 个文件全部标注、全部渲染，缺一个即报错中断。<br>
生成命令：<code>C:\\Users\\13656\\anaconda3\\envs\\ai-base\\python.exe gen_tree_doc.py</code>　|　
重新生成前先删本目录下 <code>_tree_preview.png</code>（仅预览用）</div>
</div></body>
</html>
"""

OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "完整目录树.html").write_text(HTML, encoding="utf-8")
print("✅ HTML 已写出：", OUT_DIR / "完整目录树.html")

# ── 5. 生成 Markdown ───────────────────────────────────────────────────────
md = ["# StudyPath · 完整目录树（逐文件标注）", "",
      f"> 扫描对象：`F:\\留学项目\\`（git 仓库根 / master / github.com/paomo1/StudyPath-AI）",
      f"> 共 **{len(all_files)} 个文件**、**{len(all_dirs)} 个目录**、**{fmt_size(total_bytes)}**；"
      f"进 git **{n_tracked}** 个，被忽略 **{n_ignored}** 个。", "",
      "> 图例：✅ 进 git ｜ 🚫 被 gitignore 忽略 / 可删 ｜ ★ 核心产物", ""]

for area, subtitle in [("", "根目录"), ("StudyPath-AI", "主项目根")] + AREAS + [("_ARCHIVE", "开发期归档")]:
    if area == "":
        md.append("## 根目录 `F:\\留学项目\\`")
        md.append("")
        for f in [".gitignore", "README.md"]:
            p = ROOT / f
            md.append(f"- ✅ **`{f}`** ({fmt_size(p.stat().st_size)}) — {A[f]}")
        md.append("")
        continue
    if area == "_ARCHIVE":
        md.append("## 开发期归档 `归档_留学项目开发期/`（🚫 已忽略，不属交付物）")
        md.append("")
        for f in sorted(ARCH):
            md.append(f"- 🚫 **`{f}`** — {ARCH[f]}")
        md.append("")
        continue
    base = "StudyPath-AI" if area == "StudyPath-AI" else f"StudyPath-AI/{area}"
    md.append(f"## {'StudyPath-AI/' if area=='StudyPath-AI' else area + '/'} — {subtitle}")
    md.append("")
    if area == "StudyPath-AI":
        for f in [".env", ".gitignore", "README.md"]:
            p = ROOT / base / f
            mark = "🚫" if f == ".env" else "✅"
            md.append(f"- {mark} **`{f}`** ({fmt_size(p.stat().st_size)}) — {A[f'{base}/{f}']}")
        md.append("")
        continue
    d = ROOT / base
    for dirpath, dirnames, filenames in os.walk(d):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            r = rel(p)
            if "__pycache__" in r:
                continue
            p2 = ROOT / r
            n = count_lines(p2)
            meta = fmt_size(p2.stat().st_size) + (f", {n} 行" if n is not None else "")
            mark = "✅" if r in tracked else "🚫"
            md.append(f"- {mark} **`{p.name}`** ({meta}) — {A.get(r,'')}")
        md.append("")

md.append("## 空目录（容易被忽略）")
md.append("")
for ed in ["StudyPath-AI/cache", "StudyPath-AI/pretrained",
           "StudyPath-AI/pretrained/Qwen2.5-7B-Instruct"]:
    md.append(f"- 📁 **`{ed}/`** — {D[ed]}")
md.append("")
md.append("## Python 编译缓存（🚫 已忽略，可删）")
md.append("")
for d in ["StudyPath-AI/__pycache__", "StudyPath-AI/finetune/__pycache__",
          "StudyPath-AI/rag/__pycache__", "StudyPath-AI/scripts/__pycache__"]:
    cnt = len(list((ROOT / d).glob("*.pyc")))
    md.append(f"- 🚫 `{d}/` — {cnt} 个 .pyc")
md.append("")

(OUT_DIR / "完整目录树.md").write_text("\n".join(md), encoding="utf-8")
print("✅ Markdown 已写出：", OUT_DIR / "完整目录树.md")
print(f"\n统计：进 git {n_tracked} / 忽略 {n_ignored} / 总计 {len(all_files)}")
