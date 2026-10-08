# -*- coding: utf-8 -*-
"""
核查微调模型输出的事实层。

把训练数据源（data/raw/院校数据采集.xlsx）里的真实 URL 抽成白名单，再拿测试集上的
20 条生成文本比对：生成的 URL 能否逐字溯源、排名数字与知识库参考文本是否一致；
同时核对 A/B 取证里 B 组（基座 + LoRA）的输出。

本地可跑，不需要 GPU：python -m finetune.fact_audit
依赖 openpyxl，只打印报告不写文件。
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .config import PROJECT_ROOT, DATA_RAW, DATA_PROCESSED

URL_RE = re.compile(r"https?://[^\s,，；;）)\]】\"'。]+")
RANK_RE = re.compile(r"#\s*(\d+)")


def load_kb_whitelist(path: Path):
    """从唯一数据源 xlsx 抽出全部真实 URL 与域名（白名单）"""
    import openpyxl

    urls = set()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and "http" in cell:
                    for u in URL_RE.findall(cell):
                        urls.add(u.rstrip("/"))
    domains = {urlparse(u).netloc.lower() for u in urls}
    return urls, domains


def audit_eval(ev: dict, real_urls: set, real_domains: set) -> None:
    print("=== A. 生成文本的来源链接溯源 ===")
    with_url = same_url = only_domain = 0
    for s in ev["per_sample"]:
        gurls = [u.rstrip("/") for u in URL_RE.findall(s["generated"])]
        if not gurls:
            continue
        with_url += 1
        if any(u in real_urls for u in gurls):
            same_url += 1
        if any(urlparse(u).netloc.lower() in real_domains for u in gurls):
            only_domain += 1
        mark = (
            "✅逐字命中"
            if any(u in real_urls for u in gurls)
            else ("⚠️仅域名真" if any(urlparse(u).netloc.lower() in real_domains for u in gurls) else "❌域名亦编造")
        )
        print(f"    #{s['idx']:>2} {mark}  {gurls[0][:92]}")
    print(f"  → 带 URL 样本 {with_url}/{len(ev['per_sample'])}")
    print(f"  → 逐字命中知识库 {same_url}/{with_url}｜仅域名命中 {only_domain}/{with_url}")

    print("\n=== B. 排名数字：生成 vs 知识库参考（同一样本对照）===")
    mism = sam = 0
    for s in ev["per_sample"]:
        g = RANK_RE.findall(s["generated"])
        r = RANK_RE.findall(s["reference"])
        if g and r and g[0] != r[0]:
            mism += 1
            print(f"    #{s['idx']:>2} 生成 #{g[0]} ≠ 参考 #{r[0]}")
        elif g and r:
            sam += 1
    print(f"  → 排名不一致 {mism} 条｜一致 {sam} 条")


def audit_ab(ab: dict, real_urls: set, real_domains: set) -> None:
    print("\n=== C. A/B 取证中 B 组（基座+LoRA）输出的 URL ===")
    for it in ab["items"]:
        urls = URL_RE.findall(it["B_base_plus_lora"]["text"])
        if not urls:
            print(f"    [{it['name']}] （无 URL）")
        for u in urls:
            uu = u.rstrip("/")
            mark = (
                "✅在知识库"
                if uu in real_urls
                else ("⚠️仅域名真" if urlparse(uu).netloc.lower() in real_domains else "❌编造")
            )
            print(f"    [{it['name']}] {mark}  {u}")


def main():
    xlsx = Path(DATA_RAW) / "院校数据采集.xlsx"
    if not xlsx.exists():
        cands = sorted(Path(DATA_RAW).glob("*.xlsx"))
        if not cands:
            print(f"[fact_audit] 在 {DATA_RAW} 找不到 xlsx 数据源，无法建立白名单")
            return
        xlsx = cands[0]
    print(f"[fact_audit] 白名单源: {xlsx}")
    real_urls, real_domains = load_kb_whitelist(xlsx)
    print(f"[fact_audit] 知识库真实 URL {len(real_urls)} 条 / {len(real_domains)} 个域名\n")

    eval_p = Path(DATA_PROCESSED) / "eval_results.json"
    ab_p = Path(DATA_PROCESSED) / "ab_compare.json"
    if eval_p.exists():
        audit_eval(json.loads(eval_p.read_text(encoding="utf-8")), real_urls, real_domains)
    else:
        print(f"[fact_audit] 缺少 {eval_p}，先跑 python -m finetune.evaluate")
    if ab_p.exists():
        audit_ab(json.loads(ab_p.read_text(encoding="utf-8")), real_urls, real_domains)

    print(
        "\n[fact_audit] 结论口径：参数高效微调习得【表达范式】（语体/结构/附来源习惯），"
        "不承担【事实记忆】——事实与 source_url 由 RAG 检索层注入。"
    )


if __name__ == "__main__":
    main()
