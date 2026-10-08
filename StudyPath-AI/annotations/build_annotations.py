# -*- coding: utf-8 -*-
"""
把《院校数据采集.xlsx》的自由文本字段归一化为闭集标签，导出标注语料与分布图。
录取案例库 -> 申请结果 (Admit / Reject / WL)；文书范例库 -> 文书类型 (PS/SOP/CV/LOR)
+ 文书质量 (优/良/中)；院校项目库 -> 院校国家 + 排名档 (冲/稳/保)。
标签一律从真实字段解析，解析不出的标 Unknown / 未评级，不做推断。
"""
import openpyxl, json, re, os
from collections import Counter, OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent          # annotations/
ROOT = HERE.parent                               # StudyPath-AI/
SRC  = ROOT / "data" / "raw" / "院校数据采集.xlsx"
BASE = HERE
os.makedirs(f"{BASE}/output", exist_ok=True)
os.makedirs(f"{BASE}/figures", exist_ok=True)

wb = openpyxl.load_workbook(SRC, read_only=True)

def rows_dicts(ws):
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in r):
            continue
        out.append({hdr[i]: r[i] for i in range(len(hdr))})
    return out

records = []

# ===== 1) 录取案例库 -> 申请结果 =====
def parse_result(r):
    if r is None:
        return "Unknown"
    s = str(r)
    if re.search(r"WL|Wait|候补|waitlist", s, re.I):
        return "WL"
    if re.search(r"拒|Reject|拒绝|RD\b", s, re.I):
        return "Reject"
    if re.search(r"录取|AD\b|Admit|admitted", s, re.I):
        return "Admit"
    return "Unknown"

ws = wb["录取案例库"]
for d in rows_dicts(ws):
    text = (f"{d.get('school_name','')} {d.get('program_name','')} | "
            f"GPA{d.get('gpa','')} 托福{d.get('toefl','')} GRE{d.get('gre','')} "
            f"{d.get('applicant_tier','')} 科研{d.get('papers','')} 实习{d.get('internships','')}")
    records.append({
        "id": d.get("case_id"), "source_lib": "录取案例库",
        "text": text.strip(), "label_dimension": "申请结果",
        "label": parse_result(d.get("result")),
        "source_url": d.get("source_url")
    })

# ===== 2) 文书范例库 -> 类型 + 质量 =====
def parse_quality(q):
    if q is None:
        return "未评级"
    s = str(q)
    if "优秀" in s:
        return "优"
    if "良好" in s:
        return "良"
    if any(k in s for k in ["范例", "模板", "指南", "解析"]):
        return "中"
    return "未评级"

ws = wb["文书范例库"]
for d in rows_dicts(ws):
    t = d.get("type")
    q = parse_quality(d.get("quality_label"))
    text = (f"文书类型:{t} 目标项目:{d.get('target_program','')} "
            f"质量标注:{q} 内容:{str(d.get('content_or_link',''))[:60]}")
    records.append({
        "id": d.get("essay_id"), "source_lib": "文书范例库",
        "text": text.strip(), "label_dimension": "文书类型",
        "label": t, "label2_dimension": "文书质量", "label2": q,
        "source_url": d.get("source")
    })

# ===== 3) 院校项目库 -> 国家归一化 + 排名档 =====
def norm_country(c):
    if c is None:
        return "未知"
    s = str(c)
    if "USA" in s or "US News" in s:
        return "美国"
    if "UK" in s or "United Kingdom" in s or "英国" in s:
        return "英国"
    if "Hong Kong" in s or "中国香港" in s or "香港" in s:
        return "中国香港"
    if "Singapore" in s:
        return "新加坡"
    if "Canada" in s:
        return "加拿大"
    if "Australia" in s:
        return "澳大利亚"
    if "Switzerland" in s:
        return "瑞士"
    if "Netherlands" in s:
        return "荷兰"
    if "Japan" in s:
        return "日本"
    if "South Korea" in s or "韩国" in s:
        return "韩国"
    return s

def rank_tier(s):
    if s is None:
        return "Unknown"
    m = re.search(r"#(\d+)", str(s))
    if not m:
        return "Unknown"
    n = int(m.group(1))
    if n < 50:
        return "冲(顶尖)"
    if n <= 150:
        return "稳(主流)"
    return "保(保底)"

ws = wb["院校项目库"]
for d in rows_dicts(ws):
    text = (f"{d.get('school_name','')} {d.get('program_name','')} | "
            f"国家:{norm_country(d.get('country'))} 排名:{d.get('school_rank','')} "
            f"学位:{d.get('degree','')} 学制:{d.get('duration_years','')}yr "
            f"GRE:{d.get('gre_required','')}")
    records.append({
        "id": d.get("school_name"), "source_lib": "院校项目库",
        "text": text.strip(), "label_dimension": "院校国家",
        "label": norm_country(d.get("country")),
        "label2_dimension": "排名档", "label2": rank_tier(d.get("school_rank")),
        "source_url": d.get("source_url")
    })

# ===== 写出 jsonl 语料 =====
with open(f"{BASE}/output/annotated_dataset.jsonl", "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ===== 统计各维度分布 =====
stats = OrderedDict()
for dim in ["申请结果", "文书类型", "文书质量", "院校国家", "排名档"]:
    c = Counter()
    for r in records:
        if r.get("label_dimension") == dim:
            c[r["label"]] += 1
        if r.get("label2_dimension") == dim:
            c[r["label2"]] += 1
    stats[dim] = dict(c.most_common())

with open(f"{BASE}/output/stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print("TOTAL RECORDS:", len(records))
for k, v in stats.items():
    print(f"  {k}: {v}")

# ===== 生成 SVG 水平条形分布图 =====
def hbar_svg(title, data, fname, color="#378ADD"):
    items = list(data.items())
    if not items:
        return
    n = len(items)
    w = 680
    rowh = 36
    top = 52
    h = top + n * rowh + 30
    maxv = max(data.values())
    parts = [f'<text x="20" y="30" font-family="sans-serif" font-size="16" font-weight="600" fill="#0C447C">{title}</text>']
    for i, (k, v) in enumerate(items):
        y = top + i * rowh
        bw = max(6, int(430 * (v / maxv)))
        parts.append(f'<text x="20" y="{y+19}" font-family="sans-serif" font-size="13" fill="#333">{k}</text>')
        parts.append(f'<rect x="160" y="{y+5}" width="{bw}" height="22" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{160+bw+8}" y="{y+21}" font-family="sans-serif" font-size="13" fill="#0C447C">{v}</text>')
    svg = (f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">'
           + "".join(parts) + '</svg>')
    with open(f"{BASE}/figures/{fname}", "w", encoding="utf-8") as f:
        f.write(svg)

for dim, data in stats.items():
    hbar_svg(dim, data, f"dist_{dim}.svg")

print("SVG figures ->", f"{BASE}/figures")
