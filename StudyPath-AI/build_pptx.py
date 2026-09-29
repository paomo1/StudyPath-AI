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
ASSETS = ROOT / "ppt素材"
OUT = ROOT / "毕设PPT.pptx"

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


# ===== Slide 3: 本地成品 Gradio Demo =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "本地成品：Gradio Demo",
          "LangChain RAG + LangGraph 多智能体 一体化成品（app_gradio.py · localhost:7860）")

# two cards row
add_rect(s, Inches(0.8), Inches(1.95), Inches(5.7), Inches(1.45), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(2.0), Inches(5.4), Inches(0.4),
         "用户能直接看到的能力", font_size=14, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.45), Inches(5.4), Inches(0.95),
         "多轮留学咨询对话 · Supervisor 决策面板（路由标签 school · admission）· "
         "三库融合检索自动命中（院校/案例/文书）· 来源引用高亮 + source_url 真链接外跳",
         font_size=12, color=BODY_FG, font=FONT)

add_rect(s, Inches(6.85), Inches(1.95), Inches(5.7), Inches(1.45), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(2.0), Inches(5.4), Inches(0.4),
         "技术栈", font_size=14, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.45), Inches(5.4), Inches(0.95),
         "LangChain RetrievalQA Chain · LangGraph supervisor-worker 多智能体编排 · "
         "Chroma 向量库 · DashScope qwen-turbo 推理 · Gradio 组件封装 · Synthesizer 汇总引用",
         font_size=12, color=BODY_FG, font=FONT)

# image
add_image_fit(s, ASSETS / "Gradio本地Demo.png",
              Inches(0.8), Inches(3.55), Inches(11.7), Inches(2.85),
              caption="✅ Gradio Demo 运行截图：Supervisor 调度 → 三库检索 → CMU MS CS 申请规划完整回答（含 csd.cmu.edu / 1point3acres.com 两个真实来源链接）")
# bottom card
add_rect(s, Inches(0.8), Inches(6.55), Inches(11.7), Inches(0.75), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(6.62), Inches(11.4), Inches(0.65),
         "演示动作（答辩现场跑）：输入 \"GPA 3.5 托福 100 申 CMU MSCS\" → 看到右上方 Supervisor 调度面板（school · admission）→ 主区完整结构化回答 → 滚动到底两个 source_url 真链接。",
         font_size=12, color=BODY_FG, font=FONT)


# ===== Slide 4: RAG 检索增强 =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "RAG 检索增强", "真实数据驱动的检索增强生成")

# two cards
add_rect(s, Inches(0.8), Inches(1.95), Inches(5.7), Inches(0.95), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(2.0), Inches(5.4), Inches(0.35),
         "技术栈", font_size=14, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.4), Inches(5.4), Inches(0.5),
         "Chroma 向量库 · text-embedding-v3 向量化 · 混合检索 + Rerank · TopK=8 + 阈值 0.5",
         font_size=12, color=BODY_FG, font=FONT)

add_rect(s, Inches(6.85), Inches(1.95), Inches(5.7), Inches(0.95), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(2.0), Inches(5.4), Inches(0.35),
         "数据规模", font_size=14, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.4), Inches(5.4), Inches(0.5),
         "180 条真实留学数据：100 院校库 + 50 录取案例库 + 30 文书范例库，全部带 source_url",
         font_size=12, color=BODY_FG, font=FONT)

# evidence card
add_rect(s, Inches(0.8), Inches(3.0), Inches(11.7), Inches(0.7), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(3.05), Inches(11.4), Inches(0.35),
         "真实证据（已补）", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(3.38), Inches(11.4), Inches(0.35),
         "① RAG 真实运行截图（query → 检索 Top-8 → 答案）  ② 180 条原始 xlsx 三库  ③ Chroma 向量库持久化（rag/chroma_db/，1.7MB）",
         font_size=11, color=BODY_FG, font=FONT)

# demo image
add_image_fit(s, ASSETS / "rag_demo.png",
              Inches(0.8), Inches(3.85), Inches(11.7), Inches(3.05),
              caption="真实运行截图：query=GPA 3.5 / 雅思 7.0 / 美国 Top30 CS，右侧为 Chroma 命中的 Top-8 资料（带 source 域名）")


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


# ===== Slide 8: N8N =====
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
              Inches(0.8), Inches(3.5), Inches(11.7), Inches(2.0),
              caption="✅ 已有：N8N 四节点工作流全景")

add_image_fit(s, ASSETS / "飞书群推送消息.png",
              Inches(0.8), Inches(5.7), Inches(11.7), Inches(1.55),
              caption="✅ 已有：飞书群实时推送 Dify 回答（PolyU 申请规划）")


# ===== Slide 9: LoRA =====
s = prs.slides.add_slide(blank)
set_bg(s, BG)
add_title(s, "LoRA 领域微调（已完成）",
          "让基座学会「留学顾问口吻 + 真实引用」——基于真实留学语料的领域适配")

# config card
add_rect(s, Inches(0.8), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(1.9), Inches(5.4), Inches(0.35),
         "训练配置（LLaMA Factory）", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(0.95), Inches(2.3), Inches(5.4), Inches(1.1),
         "基座：Qwen2.5-7B-Instruct\n"
         "LoRA：rank8 / alpha16 / dropout0.05 / 注入 q/k/v/o_proj\n"
         "数据：144 训练 + 36 验证（真实字段构造，零虚构）\n"
         "超参：lr=2e-4 / epochs=3 / bs=1×grad_accum8 / bf16 / FlashAttention2",
         font_size=10.5, color=BODY_FG, font=FONT)

# result card
add_rect(s, Inches(6.85), Inches(1.85), Inches(5.7), Inches(1.5), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(7.0), Inches(1.9), Inches(5.4), Inches(0.35),
         "训练结果", font_size=13, bold=True, color=HEAD3, font=FONT)
add_text(s, Inches(7.0), Inches(2.3), Inches(5.4), Inches(1.1),
         "train_loss 1.2962 → eval_loss 0.7597（收敛未过拟合）\n"
         "107 steps · 全程 < 20 分钟（AutoDL 单卡 RTX 3090 24GB）\n"
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
         "Q2 GPA 3.5 申 Top30 → \"能，竞争激烈\" + 真实引用 gradcafe.com/threads/467894\n"
         "Q3 文书技巧 → 7 条带序号核心技巧（了解院校/突出经历/领导力/实习/数据支撑/避免陈词/清晰简洁）",
         font_size=10, color=BODY_FG, font="Consolas")

add_rect(s, Inches(0.8), Inches(6.75), Inches(11.7), Inches(0.55), fill=CARD, line_rgb=BORDER)
add_text(s, Inches(0.95), Inches(6.78), Inches(11.4), Inches(0.5),
         "微调价值：Q2 主动返回 gradcafe 真实论坛 URL——SFT 数据里 source_url 字段被模型学会的「引用习惯」，直接体现「领域适配让模型学会真实引用」的微调目标。",
         font_size=11, color=BODY_FG, font=FONT)


# ===== Slide 10: 总结 =====
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
    ("RAG 检索增强", "本地 Gradio Demo", "LangChain · Chroma · Rerank · 真实数据 180 条"),
    ("多智能体协作", "本地 supervisor-worker", "LangGraph · 选校/背景/文书 三 worker"),
    ("Dify 低代码应用", "已发布线上 chatbot", "Chatflow · 三路知识库并联 · qwen-plus"),
    ("N8N 自动化编排", "本地 docker 工作流", "Form → Dify API → 飞书推送 端到端闭环"),
    ("LoRA 领域微调", "已训练 qwen_lora 权重", "LLaMA Factory · rank8/alpha16 · AutoDL 3090 · loss 1.30→0.76"),
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


# save
prs.save(str(OUT))
print(f"✅ Saved: {OUT}")
print(f"   Slides: {len(prs.slides)}")
print(f"   Size:   {OUT.stat().st_size/1024:.1f} KB")
