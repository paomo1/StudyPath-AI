# -*- coding: utf-8 -*-
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = r"C:\Users\13656\WorkBuddy\2026-07-22-12-49-13\院校数据采集模板.xlsx"

# ---- 样式 ----
header_fill = PatternFill("solid", fgColor="1F4E79")
header_font = Font(bold=True, color="FFFFFF", size=11)
title_font  = Font(bold=True, size=14, color="1F4E79")
note_font   = Font(italic=True, size=10, color="C00000")
warn_font   = Font(bold=True, size=10, color="C00000")
wrap   = Alignment(wrap_text=True, vertical="top")
center = Alignment(horizontal="center", vertical="center")
thin   = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

wb = Workbook()

# ============================================================
# Sheet 1: 填写说明
# ============================================================
ws = wb.active
ws.title = "填写说明"
ws.sheet_view.showGridLines = False
ws["A1"] = "StudyPath AI · 院校数据采集模板"
ws["A1"].font = title_font
notes = [
    "",
    "【数据真实性要求 — 最重要】",
    "1. 所有数据必须真实、可溯源，严禁虚构。答辩时评委必问『数据从哪来』，假数据=直接不及格。",
    "2. 真实来源渠道（均公开可查）：",
    "   - 院校项目信息：学校官网 Admission 页面、项目主页",
    "   - 排名：QS World / US News / CSRankings（注明排名机构与年份）",
    "   - 录取案例：一亩三分地(1point3acres)、寄托天下、ChaseDream 等公开案例库",
    "   - 文书范例：公开授权范文、学校官方 Sample",
    "3. 采集方式（毕设文档 Q11 允许）：Python 爬虫 / Coze 插件 / 手动整理。手动整理最稳。",
    "4. 每一行都尽量填 source_url（数据来源链接），这是 RAG 检索可溯源的技术亮点支撑。",
    "5. 下方每张表的第一行示例为『格式示范』，正式提交时请替换为你真实采集的数据。",
    "6. deadline 等时间字段请标注申请季年份（如 2026 Fall），并注『以官网当年公布为准』。",
    "",
    "【采集目标（毕设最低量）】",
    "   - 院校项目：≥ 50 条（覆盖美/英/港新主流校）",
    "   - 录取案例：≥ 100 条（带背景+结果）",
    "   - 文书范例：≥ 30 篇（PS/SOP 为主）",
    "",
    "【使用方式】",
    "   1. 在『院校项目库/录取案例库/文书范例库』三个 sheet 中填写真实数据（删除示例行）",
    "   2. 导出为 CSV 或 JSON，交给 data_loader.py 做向量化入库",
    "   3. 标注任务见『数据标注计划』sheet，用 Label Studio 完成",
]
r = 3
for line in notes:
    ws.cell(row=r, column=1, value=line)
    if line.startswith("【数据真实性"):
        ws.cell(row=r, column=1).font = warn_font
    elif line.startswith("【"):
        ws.cell(row=r, column=1).font = Font(bold=True, size=11, color="1F4E79")
    r += 1
ws.column_dimensions["A"].width = 110

# ============================================================
# Sheet 2: 院校项目库
# ============================================================
ws2 = wb.create_sheet("院校项目库")
cols2 = ["school_name","country","school_rank","rank_source","program_name",
         "degree","department","deadline","gpa_min","toefl_min","ielts_min",
         "gre_required","background_pref","tuition_usd_year","duration_years","tags","source_url"]
ws2.append(cols2)
for c in range(1, len(cols2)+1):
    cell = ws2.cell(row=1, column=c)
    cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = border

# 示例行（CMU MSCS 官网公开真实信息，2025-26 申请季）
ws2.append(["Carnegie Mellon University","USA","1","CSRankings 2025 计算机专排",
            "MS in Computer Science","MS","Computer Science","2025-12-15(以官网为准)",
            "3.5","100","7.0","Required","CS/EE/Math 背景优先","58000","1.5",
            "AI;Systems;Theory","https://www.cs.cmu.edu/admissions"])
ws2.cell(row=2, column=1).comment = None

# 下拉校验
dv_country = DataValidation(type="list", formula1='"USA,UK,Canada,Australia,Singapore,HongKong,Germany,Other"', allow_blank=True, sqref="B2:B1000")
dv_degree  = DataValidation(type="list", formula1='"MS,MENG,PHD,BA,BS,MBA"', allow_blank=True, sqref="F2:F1000")
dv_gre     = DataValidation(type="list", formula1='"Required,Recommended,NotRequired"', allow_blank=True, sqref="L2:L1000")
ws2.add_data_validation(dv_country)
ws2.add_data_validation(dv_degree)
ws2.add_data_validation(dv_gre)

ws2.freeze_panes = "A2"
widths2 = [26,10,10,22,28,8,20,20,8,10,9,14,24,14,12,18,40]
for i, w in enumerate(widths2, 1):
    ws2.column_dimensions[chr(64+i)].width = w
for row in ws2.iter_rows(min_row=2, max_row=2):
    for cell in row:
        cell.border = border; cell.alignment = wrap

# ============================================================
# Sheet 3: 录取案例库
# ============================================================
ws3 = wb.create_sheet("录取案例库")
cols3 = ["case_id","school_name","program_name","applicant_tier","gpa","toefl",
         "gre","papers","internships","result","year","source_url"]
ws3.append(cols3)
for c in range(1, len(cols3)+1):
    cell = ws3.cell(row=1, column=c)
    cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = border

# 格式示例（标注：请替换为真实采集案例，勿虚构）
ws3.append(["CASE001","CMU","MS in Computer Science","985",3.8,108,328,1,2,"Admit",2024,"https://www.1point3acres.com/bbs/"])
ws3.cell(row=2, column=1).font = note_font
ws3.cell(row=2, column=1).value = "CASE001(示例-请替换为真实采集案例)"

dv_tier  = DataValidation(type="list", formula1='"985,211,双非,海本,中外合办"', allow_blank=True, sqref="D2:D1000")
dv_res   = DataValidation(type="list", formula1='"Admit,Reject,WL"', allow_blank=True, sqref="J2:J1000")
ws3.add_data_validation(dv_tier)
ws3.add_data_validation(dv_res)

ws3.freeze_panes = "A2"
widths3 = [26,16,26,12,7,8,8,8,12,10,8,38]
for i, w in enumerate(widths3, 1):
    ws3.column_dimensions[chr(64+i)].width = w
for row in ws3.iter_rows(min_row=2, max_row=2):
    for cell in row:
        cell.border = border; cell.alignment = wrap

# ============================================================
# Sheet 4: 文书范例库
# ============================================================
ws4 = wb.create_sheet("文书范例库")
cols4 = ["essay_id","type","target_program","quality_label","content_or_link","source"]
ws4.append(cols4)
for c in range(1, len(cols4)+1):
    cell = ws4.cell(row=1, column=c)
    cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = border

ws4.append(["ES001","SOP","CMU MS in CS","优","[公开授权范文正文或链接]","公开 Sample / 授权范文"])
ws4.cell(row=2, column=1).font = note_font
ws4.cell(row=2, column=1).value = "ES001(示例-请替换为真实采集范文)"

dv_type = DataValidation(type="list", formula1='"SOP,PS,CV,RL,其他"', allow_blank=True, sqref="B2:B1000")
dv_ql   = DataValidation(type="list", formula1='"优,良,中,差"', allow_blank=True, sqref="D2:D1000")
ws4.add_data_validation(dv_type)
ws4.add_data_validation(dv_ql)

ws4.freeze_panes = "A2"
widths4 = [12,10,24,12,50,26]
for i, w in enumerate(widths4, 1):
    ws4.column_dimensions[chr(64+i)].width = w
for row in ws4.iter_rows(min_row=2, max_row=2):
    for cell in row:
        cell.border = border; cell.alignment = wrap

# ============================================================
# Sheet 5: 数据标注计划 (Label Studio)
# ============================================================
ws5 = wb.create_sheet("数据标注计划")
cols5 = ["标注任务","标注对象","标注维度","标签值","所用工具","用途"]
ws5.append(cols5)
for c in range(1, len(cols5)+1):
    cell = ws5.cell(row=1, column=c)
    cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = border
plan = [
    ["文书质量标注","文书文本","逻辑性/针对性/语言流畅度","优/良/中/差","Label Studio","微调训练数据 + 质量评估"],
    ["选校匹配标注","学生画像 + 院校项目","匹配度","高/中/低","Label Studio","选校推荐模型训练"],
    ["录取结果标注","录取案例","申请结果","Admit/Reject/WL","Label Studio","录取概率模型训练"],
    ["意图识别标注(可选)","用户提问","咨询/选校/文书/规划","4类意图","Label Studio","对话意图分类"],
]
for row_data in plan:
    ws5.append(row_data)
ws5.freeze_panes = "A2"
widths5 = [16,22,28,18,16,28]
for i, w in enumerate(widths5, 1):
    ws5.column_dimensions[chr(64+i)].width = w
for row in ws5.iter_rows(min_row=2, max_row=5):
    for cell in row:
        cell.border = border; cell.alignment = wrap

wb.save(OUT)
print("已生成:", OUT)
print("Sheets:", wb.sheetnames)
