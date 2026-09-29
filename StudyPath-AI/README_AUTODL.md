# StudyPath AI · LoRA 微调 · AutoDL 云端训练指南

> 本地机器（GTX 1650 4GB）跑不了 Qwen2.5-7B 的 LoRA，必须在云端 GPU 执行。
> 本文档给一套傻瓜流程：租卡 → 上传 → 一键训练 → 导出权重。

## 一、为什么必须上云
- Qwen2.5-7B-Instruct 基座 ~15GB，LoRA 微调（rank=8）也需要 ≥16GB 显存才稳。
- 本机 1650 仅 4GB，连基座都加载不了。
- 推荐 AutoDL 租 **RTX 3090 / 4090（24GB）** 或 **A10（24GB）**，按量计费约 ¥1-2/小时，跑完即销毁。

## 二、准备云端环境
1. 注册 AutoDL（https://www.autodl.com），充值。
2. 新建实例：
   - 镜像选 **PyTorch 2.3 + CUDA 12.1 + Python 3.10**（或 LLaMA Factory 官方镜像）。
   - GPU 选 24GB 档（3090/4090/A10）。
3. 开机后，用 JupyterLab 的 Terminal 或 SSH 进入。

## 三、上传项目
方式 A（git，推荐）：
```bash
git clone <你的 StudyPath-AI 仓库>
cd StudyPath-AI
```
方式 B（无 git）：在 AutoDL「数据上传」把本地 `StudyPath-AI/` 整个传上去。

## 四、一键训练
```bash
cd StudyPath-AI
bash autodl_train.sh
```
脚本会依次：装依赖 → 下载基座(15GB，约数分钟~数十分钟) → 启动 LoRA 训练 → 跑评估。
训练日志会画 loss 曲线（`model/lora/training_loss.png`）。

## 五、训练配置速查（configs/qwen_lora_sft.yaml）
| 项 | 值 | 说明 |
|----|----|----|
| finetuning_type | lora | 只训 adapter，原参数冻结 |
| lora_rank / alpha | 8 / 16 | 低秩维度 |
| lora_target | q,k,v,o_proj | 注意力投影层 |
| learning_rate | 2e-4 | LoRA 典型学习率 |
| num_train_epochs | 3 | 180 条小数据集，3 轮足够 |
| per_device_train_batch_size | 1 | 24GB 显存下保守值 |
| gradient_accumulation_steps | 8 | 等效 batch=8 |
| bf16 | true | 需 Ampere 架构(3090+/A10) |

## 六、产物与落地
- 权重：`model/lora/`（LoRA adapter，仅几十 MB）。
- 应用层调用：见 `src/inference.py` 的 `generate_essay(prompt)`。
- 把 `model/lora/` 下载回本地，应用层 Agent 即可加载微调后的模型。

## 七、常见坑
- **flash_attn 报错**：把 yaml 里 `flash_attn: fa2` 改为 `false`。
- **OOM**：调小 `per_device_train_batch_size` 或 `cutoff_len`(2048→1024)。
- **基座下载慢**：确认 `download.py` 走了 ModelScope（国内快）；云端无需代理，注释掉 HTTP(S)_PROXY 两行。
- **数据量偏少**：180 条对本科毕设够讲清流程；若想更强，按 `StudyPath_微调模块骨架设计.md` 往 `data/raw/` 攒更多真实文书。

## 八、与毕设拿分对齐
- 模型微调 +5：完整 LoRA 流水线（数据→训练→评估→保存）✅
- 全流程项目 +10：标注(B方案已完成) + 训练(本文档) = 阶段二达成 ✅

## 九、你本人只需做这 6 步（按钮清单）
> 工程我已经全打包好（代码+数据+配置，总共 < 1MB，上传无压力）。你只需要在 AutoDL 网页上点几下 + 复制两条命令。

1. **注册充值**：打开 https://www.autodl.com 注册 → 实名 → 充值 **¥20~30**（够跑好几次）。
2. **租卡**：「租用实例」→ 镜像选 **PyTorch 2.3 + CUDA 12.1 + Python 3.10** → GPU 选 **24GB 档（3090 / 4090 / A10）** → 立即创建 → 开机。
3. **上传项目**：实例开机后，进 **JupyterLab → 上传**，把本地 `F:\留学项目\StudyPath-AI\` 整个文件夹拖上去（不用配 git）。
4. **开终端跑训练**：JupyterLab 里开 Terminal，依次执行：
   ```bash
   cd StudyPath-AI
   bash autodl_train.sh          # 自动装依赖→下基座→训练→评估
   ```
   训练跑完会打印 `== 训练完成，权重在 model/lora ==`，日志里看 loss 一路下降即成功。
5. **下载权重回本地**：把云端 `StudyPath-AI/model/lora/` 整个文件夹 **下载回 F 盘** `F:\留学项目\StudyPath-AI\model\lora\`（只有几十 MB）。然后去 AutoDL 点 **「销毁实例」** 停止计费。
6. **本地验证**：回来告诉我，我帮你跑 `src/inference.py` 加载「基座+LoRA」生成一条留学建议，确认微调真生效，再把 PPT 标注页 + LoRA 页一并补上。

> 全程 AutoDL 只是「训练那几小时」的临时 GPU 车间，权重早下回你本地了，销毁云端不影响任何东西。
