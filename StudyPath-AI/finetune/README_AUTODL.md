# StudyPath AI · LoRA 微调 · AutoDL 云端训练指南

> 本地机器（GTX 1650 4GB）跑不了 Qwen2.5-7B 的 LoRA，必须在云端 GPU 执行。
> 本文档记录一套完整、可复现的流程：租卡 → 上传 → 一键训练 → 导出权重 → A/B 取证。

## 一、为什么必须上云

- Qwen2.5-7B-Instruct 基座约 **15GB**（4 个分片 × 3.9GB），LoRA 微调（rank=8）在 24GB 显存下可全程 bf16，无需量化。
- 本机 1650 仅 4GB，连基座都加载不了。
- 云端用 **RTX 3090（24GB，约 ¥1.56/小时）**；单次完整流程（下基座 + 训练 + 评估 + A/B）约 40 分钟，成本 1–2 元。

## 二、准备云端环境

1. 注册 AutoDL（https://www.autodl.com）并充值。
2. 新建实例：
   - **实测可用镜像**：`PyTorch 2.8.0 / Python 3.12 (ubuntu22.04) / CUDA 12.8`（基础镜像，自带 torch，不训练的话无需 LLaMA Factory 全家桶）
   - **GPU 必须选 24GB 档**（RTX 3090 / 4090）；12GB 档装不下 bf16 的 7B，只能量化，慢且质量有损。
   - 数据盘建议 **50GB**（放 15GB 基座 + 环境足够）。
3. 开机后用 SSH 或 JupyterLab Terminal 进入（`nvidia-smi` 确认卡型）。

> 地区就近选即可，本流程是"跑脚本 + 落文件"，不需要低延迟交互。

## 三、上传项目

方式 A（scp，推荐 —— 私有仓库走 git 需要 PAT，反而麻烦）：

```powershell
# 本地 PowerShell；-P 是大写，端口以控制台 SSH 命令为准
$H = "root@connect.<区>.seetacloud.com"
scp -o StrictHostKeyChecking=no -P <端口> -r "本地路径\finetune" "本地路径\data" "本地路径\rag" "本地路径\annotations" "${H}:/root/StudyPath-AI/"
scp -o StrictHostKeyChecking=no -P <端口> "本地路径\model\lora\adapter_model.safetensors" "本地路径\model\lora\adapter_config.json" "${H}:/root/StudyPath-AI/model/lora/"
```

方式 B（git）：

```bash
git clone https://<PAT>@github.com/<用户名>/StudyPath-AI.git && cd StudyPath-AI
```

## 四、一键训练

```bash
cd /root/StudyPath-AI
bash finetune/autodl_train.sh
```

脚本依次执行：装依赖 → 下载基座（15GB，5–15 分钟）→ 启动 LoRA 训练 → 跑评估。
训练会画 loss 曲线（`model/lora/training_loss.png` / `training_eval_loss.png`）。

> ⚠️ **下基座前务必注释掉 `finetune/download.py` 里那两行 `HTTP_PROXY` / `HTTPS_PROXY`**：
> 云端没有本地代理，不注释会让 15GB 下载直接卡死。脚本已带 `unset`，手动跑时注意。

## 五、训练配置速查（`finetune/qwen_lora_sft.yaml`）

| 项 | 值 | 说明 |
|----|----|----|
| finetuning_type | lora | 只训 adapter，基座参数冻结 |
| lora_rank / alpha | 8 / 16 | 低秩维度 / 缩放 |
| lora_target | q,k,v,o_proj | 注意力投影层 |
| learning_rate | 2e-4 | LoRA 典型学习率 |
| num_train_epochs | 3 | 180 条小数据集，3 轮足够 |
| per_device_train_batch_size | 1 | 24GB 显存下保守值 |
| gradient_accumulation_steps | 8 | 等效 batch = 8 |
| bf16 / flash_attn | true / fa2 | 需 Ampere 及以上架构 |
| val_size | 0.1 | 从 `train.jsonl`(144) 切 15 条做验证监控 |

## 六、训练结果（实测）

| 指标 | 值 |
|---|---|
| train_loss | **1.2952** |
| eval_loss | **0.7597**（低于 train_loss，收敛未过拟合） |
| global_step | **51**（3 epoch × 17 步；129 训练样本 ÷ (bs1×ga8) = 17 步/epoch） |
| train_runtime | **106.83 秒**（纯训练，不含环境准备） |
| 训练集 / 验证集 | 129 / 15（由 144 条 `train.jsonl` 按 val_size=0.1 切分） |
| 权重体积 | `adapter_model.safetensors` 约 **20MB** |

## 七、A/B 对照取证（微调是否真生效的证据）

```bash
# 前置：基座在 pretrained/、adapter 在 model/lora/
python -m finetune.ab_compare    # 同 prompt：A 纯基座 vs B 基座+LoRA，产出 ab_compare.json
python -m finetune.evaluate      # 20 条自动评估：指令遵循率 / 平均 ROUGE-L
python -m finetune.fact_audit    # 事实层核查：来源 URL 可溯源率 / 排名一致率
```

**实测结论**：

| 层面 | 结果 |
|---|---|
| 表达层 | ✅ 生效 —— 3/3 组业务任务输出发生行为改变（泛化陈述句 → 第一人称文书语体 + 结构化输出） |
| 客观指标 | ✅ 指令遵循率 **100.0%**、平均 ROUGE-L **0.5731** |
| 事实层 | ⚠️ 不承担 —— 生成文本的来源 URL 对知识库真实 URL 白名单溯源命中率 **0/20**，排名数字一致率 **0/7** |

**因此本项目采用「RAG 检索层负责事实与 source_url 溯源 + 微调层负责语体与结构生成」的双轨架构**，而非纯微调方案。

> 实现细节：`ab_compare.py` 中 A/B 两组共用同一个模型对象，A 组用 `with tuned.disable_adapter():` 关闭 adapter。
> 不能在循环里反复 `PeftModel.from_pretrained(base, ...)` —— 该调用会**原地注入** LoRA 层，导致后续轮次的"A 组"其实也带着 adapter。

## 八、产物与落地

- 权重：`model/lora/`（LoRA adapter 约 20MB + `adapter_config.json` + tokenizer + 两张 loss 曲线）。
- 应用层调用入口：`finetune/inference.py` 的 `generate_essay(prompt)`（需基座在位；检测不到 `bitsandbytes` 时自动退化为 bf16 加载）。
- 把 `model/lora/` 下载回本地即可留存全部训练成果；**云端基座（15GB）释放后不必保留**。
- ⚠️ 本地 4GB 显存环境无法加载 7B 基座，因此应用主链路走云端 API，微调以「离线权重 + A/B 对照 + 双轨评估」方式独立验收。

## 九、常见坑

| 现象 | 原因 / 解决 |
|---|---|
| 基座下载卡死不动 | `finetune/download.py` 里的 `HTTP_PROXY` / `HTTPS_PROXY` 没注释，云端无本地代理 |
| `import torch` 报 NameError | `import` 写在函数内就只在函数内有效；应在模块顶部导入一次 |
| `4-bit quantization requires bitsandbytes` | 24GB 卡不需要量化；`inference.py` 已加探测，缺 bitsandbytes 时自动走 bf16 |
| `flash_attn` 报错 | 把 yaml 里 `flash_attn: fa2` 改为 `false` |
| OOM | 调小 `per_device_train_batch_size`，或把 `cutoff_len` 从 2048 降到 1024 |
| 数据量担忧 | 180 条足以讲清完整微调链路；LoRA 本身是低数据量的领域适配方案 |
