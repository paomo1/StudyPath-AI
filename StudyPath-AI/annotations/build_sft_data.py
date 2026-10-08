# -*- coding: utf-8 -*-
"""
读《院校数据采集.xlsx》三个 sheet 的真实字段，构造 Alpaca 格式 SFT 训练集。
录取案例库 -> 选校规划问答；院校项目库 -> 项目关键信息介绍；文书范例库 -> 文书写作要点说明。

output 由真实字段拼成并引用真实 source_url，不含编造的录取结论；除客观陈述与通用
方法论建议（冲稳保梯度等）外不补充其他内容。

输出 data/processed/train.jsonl、eval.jsonl 与 dataset_info.json（供 LLaMA Factory 识别）。
"""
import openpyxl, json, random, os
from pathlib import Path

HERE = Path(__file__).resolve().parent          # annotations/
ROOT = HERE.parent                               # StudyPath-AI/
SRC  = ROOT / "data" / "raw" / "院校数据采集.xlsx"
OUT_DIR = ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def rows_dicts(ws):
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in r):
            continue
        out.append({hdr[i]: r[i] for i in range(len(hdr))})
    return out


wb = openpyxl.load_workbook(SRC, read_only=True)
data = []

# ===== 1) 录取案例库 -> 选校规划问答 SFT =====
ws = wb["录取案例库"]
for d in rows_dicts(ws):
    bg = (
        f"目标院校/专业：{d.get('school_name','')} {d.get('program_name','')}；"
        f"GPA {d.get('gpa','')}/4.0，托福 {d.get('toefl','')}，GRE {d.get('gre','')}；"
        f"申请者层级：{d.get('applicant_tier','')}；"
        f"科研 {d.get('papers','')} 篇，实习 {d.get('internships','')} 段。"
    ).strip()
    result = d.get("result", "")
    url = d.get("source_url", "")
    out_text = (
        f"该生背景：{bg} "
        f"本案例真实申请结果：{result}。"
        f"规划建议：若背景含名校实习/科研/高GPA等高竞争力要素，可冲刺顶尖项目；"
        f"无论背景强弱，均建议采用「冲刺-稳妥-保底」梯度组合以分散风险。"
        f"数据来源：{url}"
    ).strip()
    data.append({
        "instruction": "你是一名留学申请规划顾问。请根据学生的背景，给出选校与申请策略建议。",
        "input": bg,
        "output": out_text,
    })

# ===== 2) 院校项目库 -> 项目关键信息介绍 SFT =====
ws = wb["院校项目库"]
for d in rows_dicts(ws):
    inp = f"请介绍 {d.get('school_name','')} 的 {d.get('program_name','')} 项目。"
    out_text = (
        f"{d.get('school_name','')} {d.get('program_name','')}："
        f"国家/地区：{d.get('country','')}；排名：{d.get('school_rank','')}；"
        f"学位：{d.get('degree','')}；学制：{d.get('duration_years','')} 年；"
        f"GRE要求：{d.get('gre_required','')}。"
        f"数据来源：{d.get('source_url','')}"
    ).strip()
    data.append({
        "instruction": "你是一名留学顾问，请基于真实数据介绍一个留学项目的关键信息。",
        "input": inp,
        "output": out_text,
    })

# ===== 3) 文书范例库 -> 文书写作要点说明 SFT =====
ws = wb["文书范例库"]
for d in rows_dicts(ws):
    t = d.get("type", "")
    tp = d.get("target_program", "")
    q = d.get("quality_label", "")
    url = d.get("source", "")
    inp = f"请说明 {t} 文书（目标项目：{tp}）的写作要点与质量参考。"
    out_text = (
        f"{t}（目标项目：{tp}）写作要点：需突出申请者与项目的匹配度、"
        f"具体经历与量化成果、清晰的短期/长期职业目标；"
        f"本范例质量标注：{q}。参考来源：{url}"
    ).strip()
    data.append({
        "instruction": "你是一名文书顾问，请说明某类留学文书的写作要点。",
        "input": inp,
        "output": out_text,
    })

# ===== 划分 train / eval (8:2, 固定种子可复现) =====
random.seed(42)
random.shuffle(data)
n = len(data)
k = int(n * 0.8)
train, ev = data[:k], data[k:]


def write(p, rows):
    with open(p, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


write(OUT_DIR / "train.jsonl", train)
write(OUT_DIR / "eval.jsonl", ev)

# ===== LLaMA Factory dataset_info.json =====
info = {
    "studypath_sft": {
        "file_name": "train.jsonl",
        "formatting": "alpaca",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output",
        },
        "tags": {
            "role_tag": "from",
            "content_tag": "value",
            "user_tag": "human",
            "assistant_tag": "gpt",
        },
    }
}
with open(OUT_DIR / "dataset_info.json", "w", encoding="utf-8") as f:
    json.dump(info, f, ensure_ascii=False, indent=2)

# ===== 自检：确认无空 output / 全部带来源 =====
empty = sum(1 for x in data if not x["output"].strip())
no_src = sum(1 for x in data if "来源" not in x["output"] and "source" not in x["output"].lower())
print(f"[build_sft] TOTAL={n}  train={len(train)}  eval={len(ev)}")
print(f"[build_sft] 空output={empty}  缺来源标记={no_src}")
print("[build_sft] 样例(案例库):")
print("  instruction:", train[0]["instruction"])
print("  input:", train[0]["input"][:120])
print("  output:", train[0]["output"][:200])
