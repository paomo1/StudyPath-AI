# -*- coding: utf-8 -*-
"""
build_pptx.py — 把毕设PPT骨架（HTML）逐页导出为 .pptx。

设计目标：
- 16:9 宽屏，深色主题 (#0f111a)
- 标题带蓝色左竖线 (#4f8cff)
- 卡片用圆角矩形 (#1a1e2e + #28304a 边框)
- 嵌入所有真实运行截图/分布图/架构图
- 字体 Microsoft YaHei（保证中文）
"""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

ROOT = Path(r"F:\留学项目\StudyPath-AI")
ASSETS = Path(r"F:\13.答辩材料\ppt素材")
OUT = Path(r"F:\13.答辩材料\毕设PPT.pptx")

# ---------- theme ----------
BG = RGBColor(0x0f, 0x11, 0x1a)
CARD = RGBColor(0x1a, 0x1e, 0x2e)
BORDER = RGBColor(0x28, 0x30, 0x4a)
ACCENT = RGBColor(0x4f, 0x8c, 0xff)
TITLE_FG = RGBColor(0xff, 0xff, 0xff)
SUB_FG = RGBColor(0x9a, 0xa3, 0xb2)
BODY_FG = RGBColor(0xc5, 0xcc, 0xda)
HEAD3 = RGBColor(0x4f, 0x8c, 0xff)
CAP_FG = RGBColor(0x7a, 0x82, 0x95)
PILL_BG = RGBColor(0x2a, 0x33, 0x50)
PILL_FG = RGBColor(0x7f, 0xa8, 0xff)
OK_BG = RGBColor(0x1f, 0x3d, 0x2b)
OK_FG = RGBColor(0x5f, 0xd9, 0x8a)
WHITE = RGBColor(0xff, 0xff, 0xff)

FONT = "Microsoft YaHei"
CN_FONT = "Microsoft YaHei"

# 16:9 widescreen
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# ---------- helpers ----------
def set_solid_fill(shape, rgb):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb


def set_no_line(shape):
    shape.line.fill.background()


def set_line(shape, rgb, width_pt=0.75):
    shape.line.color.rgb = rgb
    shape.line.width = Pt(width_pt)


def add_rect(slide, left, top, width, height, fill=None, line_rgb=None, line_pt=0.75):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.adjustments[0] = 0.08
    if fill is not None:
        set_solid_fill(s, fill)
    else:
        s.fill.background()
    if line_rgb is not None:
        set_line(s, line_rgb, line_pt)
    else:
        set_no_line(s)
    return s


def add_text(slide, left, top, width, height, text, *, font_size=18, bold=False,
             color=BODY_FG, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    if isinstance(text, list):
        # treat as multiple runs
        for i, piece in enumerate(text):
            if i == 0:
                r = p.add_run()
            else:
                p2 = tf.add_paragraph()
                p2.alignment = align
                r = p2.add_run()
            if isinstance(piece, dict):
                r.text = piece.get("text", "")
                f = r.font
                f.name = piece.get("font", font)
                f.size = Pt(piece.get("size", font_size))
                f.bold = piece.get("bold", bold)
                col = piece.get("color", color)
                f.color.rgb = col
            else:
                r.text = piece
                f = r.font
                f.name = font
                f.size = Pt(font_size)
                f.bold = bold
                f.color.rgb = color
    else:
        r = p.add_run()
        r.text = text
        f = r.font
        f.name = font
        f.size = Pt(font_size)
        f.bold = bold
        f.color.rgb = color
    return tb


def add_title(slide, title, sub=None):
    # blue accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(0.55), Inches(0.55),
                                 Inches(0.08), Inches(0.7))
    set_solid_fill(bar, ACCENT)
    set_no_line(bar)
    add_text(slide, Inches(0.78), Inches(0.45), Inches(12.0), Inches(0.9),
             title, font_size=30, bold=True, color=TITLE_FG, font=FONT)
    if sub:
        add_text(slide, Inches(0.8), Inches(1.25), Inches(12.0), Inches(0.5),
                 sub, font_size=15, color=SUB_FG, font=FONT)


def add_card(slide, left, top, width, height, head, body):
    add_rect(slide, left, top, width, height, fill=CARD, line_rgb=BORDER, line_pt=0.75)
    # head
    add_text(slide, left + Inches(0.18), top + Inches(0.12), width - Inches(0.36), Inches(0.4),
             head, font_size=14, bold=True, color=HEAD3, font=FONT)
    # body
    add_text(slide, left + Inches(0.18), top + Inches(0.55), width - Inches(0.36), height - Inches(0.7),
             body, font_size=12, color=BODY_FG, font=FONT)


def add_pill(slide, left, top, text, ok=True):
    w = Inches(max(0.6, 0.12 * len(text) + 0.3))
    h = Inches(0.32)
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.adjustments[0] = 0.5
    set_solid_fill(s, OK_BG if ok else PILL_BG)
    set_no_line(s)
    tf = s.text_frame
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.0)
    tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = FONT
    f.size = Pt(11)
    f.bold = True
    f.color.rgb = OK_FG if ok else PILL_FG
    return s, w


def add_image_fit(slide, img_path, left, top, max_w, max_h, *, caption=None, cap_color=CAP_FG):
    """add image, scaled to fit max_w/max_h preserving aspect, centered; optional caption below."""
    img = Image.open(img_path)
    iw, ih = img.size
    ratio = min(max_w / iw, max_h / ih)
    w = int(iw * ratio)
    h = int(ih * ratio)
    # center within box
    lx = left + (max_w - w) // 2
    ly = top + (max_h - h) // 2
    slide.shapes.add_picture(str(img_path), lx, ly, width=w, height=h)
    if caption:
        cap_h = Inches(0.4)
        add_text(slide, left, top + max_h + Inches(0.05), max_w, cap_h,
                 caption, font_size=11, color=cap_color, align=PP_ALIGN.CENTER, font=FONT)


def set_bg(slide, rgb):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = rgb


# ---------- slides ----------
prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank = prs.slide_layouts[6]


# ===== Slide 1: 封面 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
# title
add_text(s, Inches(0.8), Inches(1.4), Inches(12), Inches(1.2),
         "StudyPath AI", font_size=54, bold=True, color=WHITE, font=FONT)
add_text(s, Inches(0.8), Inches(2.4), Inches(12), Inches(0.7),
         "基于大模型的留学申请规划助手 · 毕业设计答辩",
         font_size=22, color=SUB_FG, font=FONT)
# position card
add_rect(s, Inches(0.8), Inches(3.4), Inches(11.7), Inches(1.8), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(1.0), Inches(3.5), Inches(11.3), Inches(0.4),
         "项目定位", font_size=16, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(1.0), Inches(3.9), Inches(11.3), Inches(1.3),
         "面向留学申请场景的 AI 助手，整合 RAG 检索增强、多智能体协作、低代码工作流编排与模型微调，"
         "覆盖「选校 → 背景评估 → 文书 → 自动化推送」全流程。",
         font_size=15, color=BODY_FG, font=FONT)
# pills
pills = ["RAG 检索增强", "多智能体协作", "Dify 低代码应用", "N8N 自动化编排", "LoRA 领域微调"]
x = Inches(0.8)
y = Inches(5.6)
for p_text in pills:
    sh, w = add_pill(s, x, y, p_text, ok=True)
    x = x + w + Inches(0.18)
# footer
add_text(s, Inches(0.8), Inches(6.9), Inches(12), Inches(0.4),
         "StudyPath AI · 毕设答辩 · 2026", font_size=11, color=CAP_FG, font=FONT)


# ===== Slide 2: 系统分层架构 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "系统分层架构", "四层解耦：内核智能 / 交互入口 / 自动化 / 模型适配")

# 4 arch layers as cards
layers = [
    ("① 内核层（智能核心）", "基础框架：LangChain — DocumentLoader · RecursiveCharacterTextSplitter · Embeddings 接入 · VectorStore 封装 · RetrievalQA Chain · 自定义 Prompt 模板"),
    ("　 ↳ 多智能体编排", "LangGraph supervisor-worker 模式：选校检索 / 背景评估 / 文书生成 三个 worker 节点协同，supervisor 节点做意图分发"),
    ("② 交互层（用户入口）", "本地：Gradio Demo（app_gradio.py · localhost:7860）—— 多轮对话 + 来源引用 + 数据统计\n线上：Dify Chatflow 低代码应用，已发布 udify.app/chatbot/901mFjtnF9VuaQXb"),
    ("③ 自动化层（工作流）", "N8N 本地 docker：Form Trigger → HTTP Request（POST Dify API）→ Edit Fields → 飞书 HTTP Request 推送"),
    ("④ 模型层（领域适配）", "LoRA / QLoRA 轻量化微调 —— 基于真实留学语料做领域适配（已完成）"),
]
y = Inches(1.95)
h = Inches(0.85)
for head, body in layers:
    add_rect(s, Inches(0.8), y, Inches(11.7), h, fill=CARD, line_rgb=BORDER)
    add_text(s, Inches(0.95), y + Inches(0.06), Inches(11.4), Inches(0.32),
             head, font_size=14, bold=True, color=RGBColor(0xff, 0xcb, 0x6b), font=FONT)
    add_text(s, Inches(0.95), y + Inches(0.38), Inches(11.4), Inches(0.5),
             body, font_size=12, color=BODY_FG, font=FONT)
    y = y + h + Inches(0.05)
# data iron rule
add_rect(s, Inches(0.8), Inches(6.7), Inches(11.7), Inches(0.55), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(6.74), Inches(11.4), Inches(0.5),
         "数据铁律：全部采用真实可溯源留学数据（180 条 = 100 院校 + 50 案例 + 30 文书），每条带 source_url，零编造。",
         font_size=12, color=BODY_FG, font=FONT)


# ===== Slide 3: 本地成品 留学规划驾驶舱 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "本地成品：StudyPath AI 留学规划驾驶舱",
          "LangChain RAG + LangGraph 多智能体 一体化应用（app_gradio.py · localhost:7860）")

# 大图几乎占满整页，局部可看清
add_image_fit(s, ASSETS / "Gradio本地Demo.png",
              Inches(0.5), Inches(1.55), Inches(12.3), Inches(5.75),
              caption=None)

# 底部一行关键说明
add_text(s, Inches(0.5), Inches(7.35), Inches(12.3), Inches(0.45),
         "真实运行截图：Supervisor 路由（school · admission · essay）→ 三库检索 → 结构化申请规划 → 底部 source_url 可点击外跳。",
         font_size=12, color=BODY_FG, font=FONT)


# ===== Slide 4: RAG 检索增强 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "RAG 检索增强", "真实数据驱动的检索增强生成")

# 顶部一行关键技术参数
add_text(s, Inches(0.5), Inches(1.45), Inches(12.3), Inches(0.4),
         "技术栈：Chroma 向量库 · text-embedding-v3 · MMR 检索（fetch_k=20, k=8） ｜ 数据规模：100 院校 + 50 录取案例 + 30 文书，180 条全部带 source_url",
         font_size=12, color=BODY_FG, font=FONT)

# 大图几乎占满整页
add_image_fit(s, ASSETS / "rag_demo.png",
              Inches(0.5), Inches(1.95), Inches(12.3), Inches(5.35),
              caption=None)

# 底部说明
add_text(s, Inches(0.5), Inches(7.35), Inches(12.3), Inches(0.45),
         "真实运行记录（rag_demo_capture.json → rag/build_demo_panel.py 渲染）：左侧为仅基于检索资料的生成答案，"
         "右侧为 Chroma MMR 命中的 Top-8 资料，含库标签与真实来源域名。",
         font_size=12, color=BODY_FG, font=FONT)


# ===== Slide 5: 数据标注 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "数据标注：从原始 Excel 到结构化训练数据",
          "180 条真实留学数据 → 归一化标签体系（标注 B 方案）")

# two top cards
add_rect(s, Inches(0.8), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(5.4), Inches(0.35),
         "标注维度设计", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.28), Inches(5.4), Inches(1.0),
         "将自由文本（院校/案例/文书）统一归一化为 5 个可量化标签维度：\n"
         "• 申请结果（Admit / Reject / Waitlist）\n"
         "• 排名档（Top10 / Top30 / Top50 / 其他）\n"
         "• 文书类型（PS / SOP / 推荐信）\n"
         "• 文书质量（优 / 良 / 中）\n"
         "• 院校国家（美 / 英 / 港 / 新 / 其他）",
         font_size=10.5, color=BODY_FG, font=FONT)

add_rect(s, Inches(6.85), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(1.9), Inches(5.4), Inches(0.35),
         "标注产物", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.28), Inches(5.4), Inches(1.0),
         "annotated_dataset.jsonl（180 条）+ 5 张标签分布图。\n"
         "每条数据为 {id, source_lib, text, label_dimension, label, source_url} 结构，\n"
         "全部带真实 source_url，零编造。",
         font_size=10.5, color=BODY_FG, font=FONT)

# section title
add_text(s, Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.35),
         "标签分布可视化（依据真实标注结果绘制）",
         font_size=13, bold=True, color=HEAD3, font=FONT)

# 4 distribution charts in a row
chart_w = Inches(2.85)
chart_h = Inches(1.65)
chart_y = Inches(3.9)
chart_xs = [Inches(0.8), Inches(3.85), Inches(6.9), Inches(9.95)]
charts = ["dist_申请结果.png", "dist_排名档.png", "dist_文书类型.png", "dist_文书质量.png"]
labels = ["申请结果", "排名档", "文书类型", "文书质量"]
for cx, cfile, lbl in zip(chart_xs, charts, labels):
    add_image_fit(s, ASSETS / cfile, cx, chart_y, chart_w, chart_h, caption=lbl)

# bottom: 5th chart + example
add_image_fit(s, ASSETS / "dist_院校国家.png",
              Inches(0.8), Inches(5.85), Inches(2.85), Inches(1.4),
              caption="院校国家分布")

add_rect(s, Inches(3.85), Inches(5.85), Inches(8.7), Inches(1.4), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(4.0), Inches(5.9), Inches(8.4), Inches(0.3),
         "真实数据示例", font_size=12, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(4.0), Inches(6.2), Inches(8.4), Inches(1.0),
         '{ "id": "case_001", "source_lib": "录取案例库",\n'
         '  "label_dimension": "申请结果", "label": "Admit",\n'
         '  "source_url": "qiantum.xdf.cn/blog/.../5487688" }',
         font_size=10, color=RGBColor(0x9f, 0xe6, 0xb0), font="Consolas")


# ===== Slide 6: 多智能体协作 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "多智能体协作", "LangGraph supervisor-worker 架构")

# small card
add_rect(s, Inches(0.8), Inches(1.85), Inches(11.7), Inches(0.75), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(11.4), Inches(0.35),
         "架构", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.25), Inches(11.4), Inches(0.4),
         "supervisor 节点负责意图分发，3 个 worker 节点分别处理：选校检索 / 背景评估 / 文书生成子任务，体现复杂任务分解与协作。",
         font_size=11, color=BODY_FG, font=FONT)

# evidence card
add_rect(s, Inches(0.8), Inches(2.7), Inches(11.7), Inches(0.7), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(2.75), Inches(11.4), Inches(0.35),
         "真实证据（已补）", font_size=12, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(3.08), Inches(11.4), Inches(0.35),
         "① LangGraph 架构图（supervisor-worker）  ② agents.py 真实代码（StateGraph 组装 + 路由）  ③ app_multi.py 多智能体协作 demo",
         font_size=10.5, color=BODY_FG, font=FONT)

# architecture image
add_image_fit(s, ASSETS / "langgraph_arch.png",
              Inches(0.8), Inches(3.55), Inches(11.7), Inches(3.55),
              caption="架构图：supervisor(LLM 路由) → 3 worker 各自检索专属 Chroma sheet → Synthesizer 汇总")


# ===== Slide 7: Dify =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "Dify 低代码应用", "三路知识库并联检索的 Chatflow")

add_rect(s, Inches(0.8), Inches(1.85), Inches(5.7), Inches(1.0), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(5.4), Inches(0.35),
         "编排", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.28), Inches(5.4), Inches(0.55),
         "用户输入 → 三路并联知识检索（院校/案例/文书）→ LLM(qwen-plus) → 直接回复",
         font_size=12, color=BODY_FG, font=FONT)

add_rect(s, Inches(6.85), Inches(1.85), Inches(5.7), Inches(1.0), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(1.9), Inches(5.4), Inches(0.35),
         "已发布", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.28), Inches(5.4), Inches(0.55),
         "线上应用：https://udify.app/chatbot/901mFjtnF9VuaQXb",
         font_size=12, color=BODY_FG, font=FONT)

add_image_fit(s, ASSETS / "Dify-Chatflow编排.png",
              Inches(0.8), Inches(3.05), Inches(11.7), Inches(4.15),
              caption="✅ 已有：Dify Chatflow 三路知识检索编排图")


# ===== Slide 8: N8N 自动化编排 · 工作流全景 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "N8N 自动化编排", "端到端闭环：表单提问 → 调 AI → 飞书推送")

add_rect(s, Inches(0.8), Inches(1.85), Inches(11.7), Inches(0.75), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(11.4), Inches(0.35),
         "工作流", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.25), Inches(11.4), Inches(0.4),
         "Form Trigger（收集问题）→ HTTP Request（POST Dify API）→ Edit Fields（提取 answer）→ 飞书 HTTP Request（推送群）",
         font_size=11, color=BODY_FG, font=FONT)

add_rect(s, Inches(0.8), Inches(2.7), Inches(11.7), Inches(0.7), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(2.75), Inches(11.4), Inches(0.35),
         "技术亮点", font_size=12, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(3.08), Inches(11.4), Inches(0.35),
         "长文本推送飞书时用 JSON.stringify() 包裹模板变量，自动转义换行符与特殊字符，避免 JSON 结构被破坏——webhook 推送通用最佳实践。",
         font_size=10.5, color=BODY_FG, font=FONT)

add_image_fit(s, ASSETS / "N8N工作流全景.png",
              Inches(0.8), Inches(3.55), Inches(11.7), Inches(3.55),
              caption="✅ 已有：N8N 四节点工作流全景")


# ===== Slide 9: N8N 自动化编排 · 飞书推送效果 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "N8N 自动化编排", "飞书群实时推送 Dify 回答效果")

add_rect(s, Inches(0.8), Inches(1.85), Inches(11.7), Inches(0.95), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(11.4), Inches(0.35),
         "闭环验证", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.3), Inches(11.4), Inches(0.55),
         "表单提交留学问题后，N8N 自动调用 Dify Chatflow，将完整回答推送到飞书群。"
         "实现 AI 回答与协作场景的打通，无需人工复制粘贴。",
         font_size=11, color=BODY_FG, font=FONT)

add_image_fit(s, ASSETS / "飞书群推送消息.png",
              Inches(0.8), Inches(2.95), Inches(11.7), Inches(4.15),
              caption="✅ 已有：飞书群实时推送 Dify 回答（PolyU 申请规划）")


# ===== Slide 10: LoRA =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "LoRA 领域微调（已完成）",
          "让基座学会「留学顾问口吻 + 结构化附来源表达」——基于真实留学语料的领域适配")

# config card
add_rect(s, Inches(0.8), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(5.4), Inches(0.35),
         "训练配置（LLaMA Factory）", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.3), Inches(5.4), Inches(1.1),
         "基座：Qwen2.5-7B-Instruct\n"
         "LoRA：rank8 / alpha16 / dropout0.05 / 注入 q/k/v/o_proj\n"
         "数据：180 条 SFT（144 训练集 / 36 留出集）→ 训练侧按 val_size=0.1 切分，129 训练 + 15 验证（真实字段构造，零虚构）\n"
         "超参：lr=2e-4 / epochs=3 / bs=1×grad_accum8 / bf16 / FlashAttention2",
         font_size=10.5, color=BODY_FG, font=FONT)

# result card
add_rect(s, Inches(6.85), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(1.9), Inches(5.4), Inches(0.35),
         "训练结果", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.3), Inches(5.4), Inches(1.1),
         "train_loss 1.2952 → eval_loss 0.7597（收敛未过拟合）\n"
         "51 steps · 纯训练耗时 106.8 秒（AutoDL 单卡 RTX 3090 24GB）\n"
         "LoRA 仅训练 0.1% 参数，基座冻结。\n"
         "工具链：LLaMA Factory + qwen_lora_sft.yaml",
         font_size=10.5, color=BODY_FG, font=FONT)

# loss curve
add_image_fit(s, ASSETS / "training_loss.png",
              Inches(0.8), Inches(3.5), Inches(11.7), Inches(2.0),
              caption="✅ 训练损失曲线：3 个 epoch 内稳定下降并收敛（plot_loss 自动绘制）")

# inference card
add_rect(s, Inches(0.8), Inches(5.65), Inches(11.7), Inches(1.0), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(5.7), Inches(11.4), Inches(0.35),
         "推理验证（3 条真实问答）", font_size=12, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(6.05), Inches(11.4), Inches(0.65),
         "Q1 美国研究生留学申请 → GRE/GMAT·推荐信·PS·托福清单（结构化）\n"
         "Q2 GPA 3.5 申 Top30 → 「能，竞争激烈」+ 主动附来源链接（引用格式已习得）\n"
         "Q3 文书技巧 → 7 条带序号核心技巧（了解院校/突出经历/领导力/实习/数据支撑/避免陈词/清晰简洁）",
         font_size=10, color=BODY_FG, font="Consolas")

add_rect(s, Inches(0.8), Inches(6.75), Inches(11.7), Inches(0.55), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(6.78), Inches(11.4), Inches(0.5),
         "微调价值：模型习得「结构化输出 + 主动标注数据来源」的领域表达范式（权重层证据见下页 A/B 对照）。"
         "其事实层可靠性另做量化核查：来源链接与排名数字需由 RAG 检索层注入，微调不承担事实责任。",
         font_size=10, color=BODY_FG, font=FONT)


# ===== Slide 11: 微调效果验证 · A/B 对照实验 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "微调效果验证：A/B 对照实验",
          "同一 prompt 分别喂给「纯基座」与「基座 + LoRA」，比较输出行为差异（AutoDL RTX 3090 · 2026-10-02 实测）")

# 实验条件
add_rect(s, Inches(0.8), Inches(1.8), Inches(11.7), Inches(0.78), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.85), Inches(11.4), Inches(0.3),
         "实验条件（受控变量）", font_size=12, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.16), Inches(11.4), Inches(0.38),
         "Prompt（文书规划场景）：你是一名留学文书顾问，请为申请纽约大学 MS Data Science 的学生写一段 SOP 开头，不超过150字。\n"
         "解码：greedy（do_sample=False）｜唯一变量 = 是否挂载 LoRA adapter（20MB）｜对照方式：disable_adapter() 上下文切换，确保 A 组为纯净基座",
         font_size=10, color=BODY_FG, font=FONT)

# A 卡（左）：纯基座
A_CARD = RGBColor(0x1a, 0x1e, 0x2e)
add_rect(s, Inches(0.8), Inches(2.72), Inches(5.7), Inches(2.45), fill=A_CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(2.8), Inches(5.4), Inches(0.32),
         "A · 纯基座（未微调）", font_size=13, bold=True, color=SUB_FG, font=FONT)
add_text(s, Inches(0.95), Inches(3.14), Inches(5.4), Inches(1.35),
         "在数字化浪潮席卷全球的今天，数据科学作为连接现实世界与数字世界的桥梁，正以前所未有的速度改变着我们的生活方式、工作模式乃至思维方式。"
         "作为一名热衷于探索数据背后故事的学子，我深知数据科学不仅是一门学科，更是一种工具……因此，当我在众多顶尖学府中选择纽约大学时，"
         "被其在数据科学领域的卓越成就和深厚底蕴深深吸引。在这里，我期待能够深入学习先进的数据分析方法和技术，同时，在多元文化的浸润下，"
         "培养跨学科思维和全球视野，为未来的职业生涯奠定坚实基础。",
         font_size=10.5, color=RGBColor(0x8a, 0x92, 0xa3), font=FONT)
add_text(s, Inches(0.95), Inches(4.6), Inches(5.4), Inches(0.5),
         "✗ 通用陈述式长句：通篇宏观议论，无任何个人背景事实，语气与「通用 AI 作文」无异。",
         font_size=9.5, bold=True, color=RGBColor(0xc9, 0x8a, 0x8a), font=FONT)

# B 卡（右）：基座 + LoRA
B_CARD = RGBColor(0x14, 0x24, 0x1e)
add_rect(s, Inches(6.85), Inches(2.72), Inches(5.7), Inches(2.45), fill=B_CARD, line_rgb=OK_FG)
add_text(s, Inches(7.0), Inches(2.8), Inches(5.4), Inches(0.32),
         "B · 基座 + LoRA（微调后）", font_size=13, bold=True, color=OK_FG, font=FONT)
add_text(s, Inches(7.0), Inches(3.14), Inches(5.4), Inches(1.35),
         "开头：我自小就对数据科学充满兴趣，高中时便开始自学 Python 和 R 语言。本科期间，我主修数学与统计学，并辅修计算机科学。"
         "这段经历不仅让我掌握了扎实的理论基础，还培养了我解决实际问题的能力。如今，我渴望在纽约大学继续深造，成为数据科学领域的顶尖人才。",
         font_size=11.5, color=RGBColor(0xd8, 0xf5, 0xe2), font=FONT)
add_text(s, Inches(7.0), Inches(4.6), Inches(5.4), Inches(0.5),
         "✓ 第一人称文书语体：锚定「自学 Python/R、主修数学统计」等具体背景事实，贴合 SOP 写作范式。",
         font_size=9.5, bold=True, color=OK_FG, font=FONT)

# 结论条
add_rect(s, Inches(0.8), Inches(5.28), Inches(11.7), Inches(0.62), fill=OK_BG, line_rgb=OK_FG)
add_text(s, Inches(0.95), Inches(5.33), Inches(11.4), Inches(0.55),
         "结论：identical = False —— 仅切换 LoRA 权重，输出即由「通用陈述式长句」转为「第一人称文书语体 + 个人背景事实锚定（自学 Python/R、主修数学统计）」，"
         "属权重层行为改变，而非 prompt 修饰。",
         font_size=11, bold=True, color=OK_FG, font=FONT)

# 三个指标
m_y = Inches(6.0)
m_h = Inches(0.72)
m_w = Inches(3.77)
metrics = [
    ("指令遵循率", "100.0%", "20 / 20 条输出非空且 >20 字"),
    ("平均 ROUGE-L", "0.5731", "LCS 近似，20 条测试集均值"),
    ("训练收敛", "1.2952 → 0.7597", "train_loss → eval_loss（3 epoch / 51 step）"),
]
mx = Inches(0.8)
for name, val, note in metrics:
    add_rect(s, mx, m_y, m_w, m_h, fill=CARD, line_rgb=BORDER)
    add_text(s, mx + Inches(0.15), m_y + Inches(0.04), m_w - Inches(0.3), Inches(0.25),
             name, font_size=10, bold=True, color=HEAD3, font=FONT)
    add_text(s, mx + Inches(0.15), m_y + Inches(0.23), m_w - Inches(0.3), Inches(0.3),
             val, font_size=15, bold=True, color=WHITE, font=FONT)
    add_text(s, mx + Inches(0.15), m_y + Inches(0.5), m_w - Inches(0.3), Inches(0.2),
             note, font_size=8, color=CAP_FG, font=FONT)
    mx = mx + m_w + Inches(0.2)

# 归因说明（2026-10-02 复跑修订：3 类任务 3/3 组均有变化，但变化性质分两类）
add_text(s, Inches(0.8), Inches(6.79), Inches(11.7), Inches(0.6),
         "对照覆盖 3 类业务任务：3/3 组输出均发生变化，但性质不同 —— 文书类为【语体迁移】（通用陈述 → 第一人称文书语体 + 个人背景事实，即本项目目标能力）；\n"
         "选校 / 风险类为【格式塌缩】（复述训练集「案例记录」模板），属 180 条小样本下的记忆复述。事实层量化核查详见下页。",
         font_size=9.5, color=BODY_FG, font=FONT)


# ===== Slide 12: 微调能力边界核查（事实层）=====
# 依据：data/processed/eval_results.json（20 条生成文本）+ ab_compare.json（3 组 A/B）
# 溯源基准：data/raw/院校数据采集.xlsx 中 165 条真实 URL / 118 个域名
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "微调能力边界核查：事实层 vs 表达层",
          "对微调模型输出做量化核查 —— 这正是本项目采用「RAG + 微调」双轨设计的原因（2026-10-02 AutoDL 实测）")

AMBER = RGBColor(0xe3, 0xb3, 0x6a)
checks = [
    ("来源链接可溯源性", "0 / 20", AMBER,
     "20 条生成文本均主动附了来源 URL，\n但逐字命中知识库（165 条真实 URL）\n的为 0 条 —— 链接由模型生成，\n不可直接采信"),
    ("排名数字一致性", "0 / 7", AMBER,
     "含排名数字的 7 条样本，与知识库\n参考文本（同一测试集的标注结果）\n全部不一致 —— 事实数值\n未被参数记住"),
    ("表达层迁移有效性", "3 / 3", OK_FG,
     "3 类业务任务的 A/B 输出均发生\n权重层变化：语体、结构、\n「主动附来源」的习惯可迁移\n（文书类目标能力已达成）"),
]
cx = Inches(0.8)
cw = Inches(3.77)
for name, val, col, note in checks:
    add_rect(s, cx, Inches(1.95), cw, Inches(2.5), fill=CARD, line_rgb=BORDER)
    add_text(s, cx + Inches(0.2), Inches(2.05), cw - Inches(0.4), Inches(0.3),
             name, font_size=11, bold=True, color=HEAD3, font=FONT)
    add_text(s, cx + Inches(0.2), Inches(2.4), cw - Inches(0.4), Inches(0.55),
             val, font_size=26, bold=True, color=col, font=FONT)
    add_text(s, cx + Inches(0.2), Inches(3.05), cw - Inches(0.4), Inches(1.3),
             note, font_size=9, color=BODY_FG, font=FONT)
    cx = cx + cw + Inches(0.2)

# 结论
add_rect(s, Inches(0.8), Inches(4.62), Inches(11.7), Inches(0.95), fill=OK_BG, line_rgb=OK_FG)
add_text(s, Inches(0.95), Inches(4.68), Inches(11.4), Inches(0.85),
         "结论：参数高效微调（LoRA · rank8 · 180 条样本 · 3 epoch）习得的是【表达范式】——语体、结构、主动标注来源的习惯；\n"
         "而不承担【事实记忆】。因此本项目把职责拆开：RAG 检索层负责事实与 source_url 溯源，微调层负责语体与结构生成。",
         font_size=11, bold=True, color=OK_FG, font=FONT)

# 工程落点
add_rect(s, Inches(0.8), Inches(5.75), Inches(11.7), Inches(1.05), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(5.8), Inches(11.4), Inches(0.3),
         "对应到工程落地", font_size=11, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(6.1), Inches(11.4), Inches(0.65),
         "主链路（app_gradio.py / qa.py）：DashScope qwen-plus + Chroma 检索，回答原样携带真实 source_url —— 事实层可逐条反查溯源；\n"
         "微调链路：离线权重（20MB）落盘 + A/B 对照（权重层行为改变）+ 双轨评估（指令遵循率 100% / ROUGE-L 0.573）独立验收。",
         font_size=10, color=BODY_FG, font=FONT)


# ===== Slide 13: 总结 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "答辩总结", "覆盖「数据 → 检索 → 推理 → 交互 → 自动化 → 微调」完整链路")

# table (use shapes for visual)
table_x = Inches(0.8)
table_y = Inches(1.95)
col_w = [Inches(2.7), Inches(3.8), Inches(5.2)]
row_h = Inches(0.42)
rows = [
    ("技术模块", "落地形式", "核心实现"),
    ("RAG 检索增强", "本地 Gradio Demo", "LangChain · Chroma · MMR · 真实数据 180 条"),
    ("多智能体协作", "本地 supervisor-worker", "LangGraph · 选校/背景/文书 三 worker"),
    ("Dify 低代码应用", "已发布线上 chatbot", "Chatflow · 三路知识库并联 · qwen-plus"),
    ("N8N 自动化编排", "本地 docker 工作流", "Form → Dify API → 飞书推送 端到端闭环"),
    ("LoRA 领域微调", "已训练 qwen_lora 权重 + A/B 验证", "LLaMA Factory · rank8/alpha16 · AutoDL 3090 · loss 1.2952→0.7597 · 指令遵循率 100% / ROUGE-L 0.573"),
]
# header
hx = table_x
for i, c in enumerate(rows[0]):
    add_rect(s, hx, table_y, col_w[i], row_h, fill=RGBColor(0x1f, 0x27, 0x42), line_rgb=BORDER)
    add_text(s, hx + Inches(0.12), table_y + Inches(0.04), col_w[i] - Inches(0.24), row_h,
             c, font_size=12, bold=True, color=HEAD3, font=FONT)
    hx = hx + col_w[i]
# data rows
for ri, row in enumerate(rows[1:], start=1):
    y = table_y + row_h * ri
    hx = table_x
    bg = CARD if ri % 2 == 1 else RGBColor(0x1f, 0x24, 0x38)
    for i, c in enumerate(row):
        add_rect(s, hx, y, col_w[i], row_h, fill=bg, line_rgb=BORDER)
        add_text(s, hx + Inches(0.12), y + Inches(0.04), col_w[i] - Inches(0.24), row_h,
                 c, font_size=11, color=BODY_FG, font=FONT)
        hx = hx + col_w[i]

# bottom 2 cards
y2 = Inches(5.45)
add_rect(s, Inches(0.8), y2, Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), y2 + Inches(0.1), Inches(5.4), Inches(0.35),
         "技术深度", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), y2 + Inches(0.5), Inches(5.4), Inches(0.9),
         "整合主流大模型应用框架（LangChain / LangGraph / Dify / N8N），\n"
         "从工程落地反推技术选型理由。",
         font_size=12, color=BODY_FG, font=FONT)

add_rect(s, Inches(6.85), y2, Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), y2 + Inches(0.1), Inches(5.4), Inches(0.35),
         "完整性", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), y2 + Inches(0.5), Inches(5.4), Inches(0.9),
         "真实可溯源数据 · 端到端业务闭环 · 多个可运行可演示产物\n"
         "（Gradio 本地 / Dify 线上 / N8N 工作流 / LoRA 微调权重）。",
         font_size=12, color=BODY_FG, font=FONT)


# ===== Slide 14: 技术亮点与创新点 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "技术亮点与创新点", "从「能检索」到「能规划」的三重突破")

highlights = [
    ("① 多智能体框架（LangGraph supervisor-worker）",
     "三个 Worker 不是并列检索框，而是各有业务人设的领域专家——选校策略师（冲刺/稳妥/保底三档划分）、录取风险评估师（背景定位+风险点）、文书规划师（结构拆解+大纲）。Synthesizer 消费三者结论，整合为带优先级的五阶段申请规划。"),
    ("② 真实可溯源数据铁律",
     "知识库 180 条（100 院校+50 案例+30 文书）全部来自学校官网/QS/USNews 等公开渠道，每条带 source_url，零虚构。检索对抗测试 HitRate@8=100%，回答忠实度 100%（生成内容与检索证据逐句一致）。"),
    ("③ 全流程跨工具链闭环",
     "覆盖「数据标注 → LoRA 微调 → RAG 应用 → N8N 自动化」四大环节，贯通 LLaMA Factory / LangChain / LangGraph / Dify / N8N 五套主流技术栈，展示完整大模型工程能力。"),
    ("④ RAG 工程深度",
     "Chroma 本地向量库 + MMR 检索(fetch_k=20,k=8) + 38 校别名归一化提升召回 + 多库来源卡片全局统一编号，兼顾相关性、多样性与可解释性。"),
]
y = Inches(1.9)
h = Inches(1.12)
for head, body in highlights:
    add_rect(s, Inches(0.8), y, Inches(11.7), h, fill=CARD, line_rgb=BORDER)
    add_text(s, Inches(0.95), y + Inches(0.06), Inches(11.4), Inches(0.32),
             head, font_size=14, bold=True, color=RGBColor(0xff, 0xcb, 0x6b), font=FONT)
    add_text(s, Inches(0.95), y + Inches(0.4), Inches(11.4), Inches(0.68),
             body, font_size=11, color=BODY_FG, font=FONT)
    y = y + h + Inches(0.05)


# ===== Slide 15: 个人贡献与收获 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "个人贡献与收获", "独立完成 · 全流程贯通")

# 个人贡献
add_rect(s, Inches(0.8), Inches(1.9), Inches(5.7), Inches(4.7), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.98), Inches(5.4), Inches(0.4),
         "个人独立贡献", font_size=15, bold=True, color=HEAD3, font=FONT)
contrib = [
    "设计 LangGraph supervisor-worker 多智能体架构，将三 Worker 从「检索器」重构为「领域专家」",
    "搭建 Chroma RAG 链路：切片 / 向量化 / MMR 检索 / 来源卡片全局编号",
    "完成 180 条真实数据采集与 5 维标注，构造 144+36 条 SFT 数据集",
    "用 LLaMA Factory 完成 Qwen2.5-7B LoRA 微调，产出领域适配权重",
    "发布 Dify Chatflow MVP、编排 N8N 自动化工作流、实现 Gradio 学术驾驶舱",
]
ty = Inches(2.45)
for c in contrib:
    add_text(s, Inches(1.0), ty, Inches(5.4), Inches(0.8),
             "• " + c, font_size=11, color=BODY_FG, font=FONT)
    ty = ty + Inches(0.82)

# 收获
add_rect(s, Inches(6.85), Inches(1.9), Inches(5.7), Inches(4.7), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(1.98), Inches(5.4), Inches(0.4),
         "技术收获与成长", font_size=15, bold=True, color=HEAD3, font=FONT)
gain = [
    "掌握 LangGraph 多智能体编排与状态流转的工程实现",
    "吃透 RAG 检索增强的工程化：切分 / 嵌入 / 向量库 / 检索与评估",
    "跑通「数据标注 → 微调 → 应用」完整模型训练闭环",
    "理解低代码(Dify)与自动化(N8N)在真实业务中的落地价值",
    "树立「严禁虚构、真实可溯源」的 AI 工程伦理意识",
]
gy = Inches(2.45)
for g in gain:
    add_text(s, Inches(7.05), gy, Inches(5.4), Inches(0.8),
             "• " + g, font_size=11, color=BODY_FG, font=FONT)
    gy = gy + Inches(0.82)


# save
prs.save(str(OUT))
print(f"✅ Saved: {OUT}")
print(f"   Slides: {len(prs.slides)}")
print(f"   Size:   {OUT.stat().st_size/1024:.1f} KB")
