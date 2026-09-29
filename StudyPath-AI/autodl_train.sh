#!/bin/bash
# StudyPath AI · AutoDL 一键训练脚本
# 用法：把整个 StudyPath-AI 项目上传或 git clone 到 AutoDL 实例后，运行：
#   bash autodl_train.sh
set -e
# 清掉本机代理配置（云端无 127.0.0.1:7897，否则 ModelScope 下载卡死）
unset HTTP_PROXY HTTPS_PROXY
echo "== 1. 安装依赖 =="
pip install -r requirements.txt
echo "== 1.5 确保训练数据（data/processed 为空则重建）=="
if [ ! -s data/processed/train.jsonl ]; then
  echo "  data/processed 为空，从 xlsx 重建 SFT 数据 ..."
  python annotations/build_sft_data.py
else
  echo "  data/processed 已存在，跳过重建"
fi
echo "== 2. 下载基座 Qwen2.5-7B-Instruct (约15GB，ModelScope 镜像) =="
python download.py
echo "== 3. 启动 LoRA 训练 =="
llamafactory-cli train configs/qwen_lora_sft.yaml
echo "== 训练完成，权重在 model/lora =="
echo "== 4. 评估（可选）=="
python -m src.evaluate
