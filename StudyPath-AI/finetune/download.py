# -*- coding: utf-8 -*-
"""
下载 Qwen2.5-7B-Instruct 基座到 pretrained/（约 15GB），默认走 ModelScope 镜像。
脚本预设了本地代理 127.0.0.1:7897；无需代理时把下面的 HTTP(S)_PROXY 两行注释掉。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 本文件位于 finetune/，向上两级回到项目根 StudyPath-AI/
DST = ROOT / "pretrained" / "Qwen2.5-7B-Instruct"
DST.mkdir(parents=True, exist_ok=True)

# ModelScope 缓存与镜像
os.environ.setdefault("MODELSCOPE_CACHE", str(DST.parent))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 本机代理（Clash Verge 默认 7897）；云端请注释下面两行
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7897")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7897")

REPO = "Qwen/Qwen2.5-7B-Instruct"


def main():
    try:
        from modelscope import snapshot_download

        path = snapshot_download(REPO, local_dir=str(DST))
        print(f"[download] ModelScope 下载完成 -> {path}")
    except ImportError:
        print("[download] 未安装 modelscope，回退到 huggingface-cli ...")
        os.system(f"hf download {REPO} --local-dir {DST}")
    print("[download] 完成。下一步：llamafactory-cli train finetune/qwen_lora_sft.yaml")


if __name__ == "__main__":
    main()
