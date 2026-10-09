# -*- coding: utf-8 -*-
"""
把答辩内容逐页导出为 .pptx（23 页 · 亮色科技学术风）。

版式：16:9，三档底色 —— 普通页白底、架构与总览页浅蓝底、代码页深底。
主色 #243B7A（深蓝）／强调 #5267D8（蓝紫）／卡片 #F5F7FC + 边框 #DDE3F0。
字体 Microsoft YaHei，代码块 Consolas。
图片取自 ppt素材/ 下的真实运行截图、分布图与架构图；证据类截图旁配
「这张图证明了什么」标注条，写图能支撑的结论，而不是复述界面有什么。
"""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.lang import MSO_LANGUAGE_ID
from PIL import Image

ROOT = Path(r"F:\留学项目\StudyPath-AI")
ASSETS = Path(r"F:\13.答辩材料\ppt素材")
OUT = Path(r"F:\13.答辩材料\毕设PPT.pptx")

# ==================== 主题 ====================
PAGE_NORMAL = RGBColor(0xFF, 0xFF, 0xFF)
PAGE_ARCH = RGBColor(0xEE, 0xF2, 0xFC)
PAGE_CODE = RGBColor(0x18, 0x1E, 0x33)
PAGE_COVER = RGBColor(0xF7, 0xF9, 0xFE)

NAVY = RGBColor(0x24, 0x3B, 0x7A)
ACCENT = RGBColor(0x52, 0x67, 0xD8)
TEAL = RGBColor(0x1F, 0x8A, 0x7A)
AMBER = RGBColor(0xC4, 0x7A, 0x1E)
RED = RGBColor(0xB8, 0x46, 0x46)

T_TITLE = RGBColor(0x1A, 0x23, 0x40)
T_BODY = RGBColor(0x3D, 0x47, 0x63)
T_MUTED = RGBColor(0x7A, 0x84, 0xA0)
T_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CARD_BG = RGBColor(0xF5, 0xF7, 0xFC)
CARD_LINE = RGBColor(0xDD, 0xE3, 0xF0)
CARD_BG2 = RGBColor(0xE9, 0xEE, 0xFA)
EVID_BG = RGBColor(0xEC, 0xF7, 0xF3)
EVID_LINE = RGBColor(0xBF, 0xE3, 0xD9)
OKBG = RGBColor(0xE8, 0xF5, 0xEE)
OKLINE = RGBColor(0x9E, 0xD4, 0xB8)
WARNBG = RGBColor(0xFD, 0xF3, 0xE3)
WARNLINE = RGBColor(0xE8, 0xC9, 0x8E)

# 深色页（代码页）
D_TITLE = RGBColor(0xE8, 0xEC, 0xF8)
D_BODY = RGBColor(0xA8, 0xB4, 0xD0)
D_ACC = RGBColor(0x7F, 0xA8, 0xFF)
D_CARD = RGBColor(0x22, 0x2A, 0x42)
D_LINE = RGBColor(0x33, 0x3D, 0x5C)
D_KEY = RGBColor(0x8F, 0xB8, 0xFF)
D_STR = RGBColor(0x9F, 0xE6, 0xB0)
D_CMT = RGBColor(0x6B, 0x78, 0x99)

FONT = "Microsoft YaHei"
MONO = "Consolas"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
M = Inches(0.72)
CW = Inches(11.89)


# ==================== 基础工具 ====================
def set_solid_fill(shape, rgb):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb


def set_no_line(shape):
    shape.line.fill.background()


def set_line(shape, rgb, width_pt=0.75):
    shape.line.color.rgb = rgb
    shape.line.width = Pt(width_pt)


def set_bg(slide, rgb):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb
    # 再铺一层覆盖整页的矩形：不同播放器对 slide 级背景的支持不一致，铺底更稳。
    # 形状按添加顺序堆叠，set_bg 是每页最先调用的，所以这层始终在最底下。
    bgrect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    set_solid_fill(bgrect, rgb)
    set_no_line(bgrect)


def add_rect(slide, left, top, width, height, fill=None, line_rgb=None, line_pt=0.75, radius=0.08):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    s.adjustments[0] = radius
    if fill is not None:
        set_solid_fill(s, fill)
    else:
        s.fill.background()
    if line_rgb is not None:
        set_line(s, line_rgb, line_pt)
    else:
        set_no_line(s)
    return s


def add_bar(slide, left, top, width, height, fill):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    set_solid_fill(s, fill)
    set_no_line(s)
    return s


def add_text(slide, left, top, width, height, text, *, font_size=18, bold=False,
             color=T_BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT,
             line_spacing=None):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.01)
    tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = anchor

    def style(run, piece):
        f = run.font
        f.name = piece.get("font", font)
        f.size = Pt(piece.get("size", font_size))
        f.bold = piece.get("bold", bold)
        f.color.rgb = piece.get("color", color)

    p = tf.paragraphs[0]
    p.alignment = align
    if line_spacing:
        p.line_spacing = line_spacing
    if isinstance(text, list):
        for i, piece in enumerate(text):
            if i > 0:
                p = tf.add_paragraph()
                p.alignment = align
                if line_spacing:
                    p.line_spacing = line_spacing
            r = p.add_run()
            if isinstance(piece, dict):
                r.text = piece.get("text", "")
                style(r, piece)
            else:
                r.text = piece
                style(r, {})
    else:
        r = p.add_run()
        r.text = text
        style(r, {})
    return tb


def add_title(slide, title, sub=None, dark=False):
    add_bar(slide, M, Inches(0.5), Inches(0.075), Inches(0.68),
            ACCENT if dark else NAVY)
    add_text(slide, M + Inches(0.2), Inches(0.4), CW - Inches(0.2), Inches(0.82),
             title, font_size=27, bold=True, color=D_TITLE if dark else T_TITLE)
    if sub:
        add_text(slide, M + Inches(0.22), Inches(1.16), CW - Inches(0.22), Inches(0.45),
                 sub, font_size=12.5, color=D_BODY if dark else T_MUTED)


def add_footer(slide, idx, dark=False):
    c = D_BODY if dark else T_MUTED
    add_text(slide, M, Inches(7.08), Inches(8), Inches(0.28),
             "StudyPath · 毕业设计答辩", font_size=9, color=c)
    add_text(slide, SLIDE_W - M - Inches(1.4), Inches(7.08), Inches(1.4), Inches(0.28),
             "%02d" % idx, font_size=9, color=c, align=PP_ALIGN.RIGHT)


def add_card(slide, left, top, width, height, head=None, body=None, *,
             fill=CARD_BG, line=CARD_LINE, head_color=NAVY, body_color=T_BODY,
             head_size=13, body_size=11, pad=0.2, gap=0.36):
    add_rect(slide, left, top, width, height, fill=fill, line_rgb=line)
    y = top + Inches(pad)
    if head:
        add_text(slide, left + Inches(pad), y, width - Inches(pad * 2), Inches(0.32),
                 head, font_size=head_size, bold=True, color=head_color)
        y = y + Inches(gap)
    if body:
        add_text(slide, left + Inches(pad), y, width - Inches(pad * 2),
                 height - Inches(pad * 2 + gap), body, font_size=body_size, color=body_color)
    return y


def add_pill(slide, left, top, text, *, fill=None, fg=None, size=11,
             width=None, height=Inches(0.34)):
    fill = CARD_BG2 if fill is None else fill
    fg = NAVY if fg is None else fg
    w = width if width is not None else Inches(max(0.72, 0.128 * len(text) + 0.34))
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, height)
    s.adjustments[0] = 0.5
    set_solid_fill(s, fill)
    set_no_line(s)
    tf = s.text_frame
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = fg
    return s, w


def add_image_fit(slide, img_path, left, top, max_w, max_h, *, caption=None,
                  cap_color=T_MUTED, cap_size=9.5):
    img = Image.open(img_path)
    iw, ih = img.size
    ratio = min(max_w / iw, max_h / ih)
    w = int(iw * ratio)
    h = int(ih * ratio)
    lx = left + (max_w - w) // 2
    ly = top + (max_h - h) // 2
    slide.shapes.add_picture(str(img_path), lx, ly, width=w, height=h)
    if caption:
        add_text(slide, left, top + max_h + Inches(0.04), max_w, Inches(0.34),
                 caption, font_size=cap_size, color=cap_color, align=PP_ALIGN.CENTER)


def add_evidence(slide, left, top, width, items, height=Inches(1.02)):
    """证据标注条：横排 N 个小卡，每卡「① 结论标题 / 依据说明」。"""
    n = len(items)
    gap = Inches(0.14)
    cw = int((width - gap * (n - 1)) / n)
    marks = "①②③④⑤"
    x = left
    for i, (head, body) in enumerate(items):
        add_rect(slide, x, top, cw, height, fill=EVID_BG, line_rgb=EVID_LINE)
        add_text(slide, x + Inches(0.14), top + Inches(0.07), cw - Inches(0.28), Inches(0.26),
                 "%s %s" % (marks[i], head), font_size=10, bold=True, color=TEAL)
        add_text(slide, x + Inches(0.14), top + Inches(0.32), cw - Inches(0.28),
                 height - Inches(0.4), body, font_size=8.5, color=T_BODY)
        x = x + cw + gap


def add_metric(slide, left, top, width, height, label, value, note, value_color=NAVY):
    add_rect(slide, left, top, width, height, fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(slide, left + Inches(0.16), top + Inches(0.06), width - Inches(0.32), Inches(0.24),
             label, font_size=9.5, bold=True, color=T_MUTED)
    add_text(slide, left + Inches(0.16), top + Inches(0.27), width - Inches(0.32), Inches(0.34),
             value, font_size=16, bold=True, color=value_color)
    add_text(slide, left + Inches(0.16), top + Inches(0.6), width - Inches(0.32), Inches(0.22),
             note, font_size=8, color=T_MUTED)


# ==================== 页面 ====================
prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank = prs.slide_layouts[6]


# ----- 01 封面 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_COVER)
add_bar(s, M, Inches(0.9), Inches(0.5), Inches(0.075), ACCENT)
add_text(s, M, Inches(1.02), Inches(6), Inches(0.35),
         "2026 毕业设计答辩", font_size=12.5, bold=True, color=ACCENT)
add_text(s, M, Inches(1.75), Inches(11), Inches(1.15),
         "StudyPath", font_size=54, bold=True, color=T_TITLE)
add_text(s, M, Inches(2.82), Inches(11), Inches(0.6),
         "基于大模型的留学申请规划助手", font_size=22, color=NAVY)
add_text(s, M, Inches(3.42), Inches(11.6), Inches(0.4),
         "RAG 检索增强 · LangGraph 多智能体 · LoRA 领域微调 · Dify / N8N 自动化",
         font_size=13, color=T_MUTED)

add_rect(s, M, Inches(4.1), CW, Inches(1.28), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.26), Inches(4.24), CW - Inches(0.52), Inches(0.3),
         "项目定位", font_size=12, bold=True, color=NAVY)
add_text(s, M + Inches(0.26), Inches(4.58), CW - Inches(0.52), Inches(0.72),
         "面向留学申请场景的规划助手：以 180 条真实可溯源数据为底座，用检索增强保证事实可信，"
         "用多智能体把复杂问题拆给三个领域角色分别处理再汇总，覆盖「选校 → 背景评估 → 文书 → 自动化推送」全流程。",
         font_size=12, color=T_BODY)

pills = ["RAG 检索增强", "多智能体协作", "LoRA 领域微调", "Dify 低代码应用", "N8N 自动化编排"]
x = M
for t in pills:
    _, w = add_pill(s, x, Inches(5.72), t, size=11)
    x = x + w + Inches(0.16)

add_text(s, M, Inches(6.5), CW, Inches(0.3),
         "数据来源全部可溯源 · 每条记录带 source_url · 零编造", font_size=11, color=TEAL)


# ----- 02 背景与痛点 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "背景与痛点", "留学申请的信息环境，决定了「生成一段通顺的话」并不解决问题")
add_footer(s, 2)

pain_w = Inches(3.85)
pain_gap = Inches(0.17)
pain_y = Inches(1.78)
pain_h = Inches(4.12)
pains = [
    ("01", "信息分散", T_MUTED,
     "招生要求散落在院校官网、论坛与中介页面，格式与口径都不统一。\n\n"
     "要凑出一份可比的选校清单，需要跨几十个站点手工比对，还无法确定哪份是最新版本。",
     "后果：选校依据不牢靠，一份清单耗时以周计。"),
    ("02", "时效性强", T_MUTED,
     "截止日期、语言要求、学费与先修课逐年调整。\n\n"
     "静态文档与旧帖往往半年就失效，而过期信息会直接误导申请节奏与材料准备。",
     "后果：拿过期数据做决策，错过关键 DDL。"),
    ("03", "通用 LLM 不可溯源", RED,
     "直接问大模型确实能得到通顺回答，但无法保证来源真实。\n\n"
     "输出没有可点击的原始出处，也无法逐条复核，正确与编造在文本上看起来一样。",
     "后果：留学属高风险决策，一条错误信息代价很大。"),
]
x = M
for no, head, hc, body, cons in pains:
    add_rect(s, x, pain_y, pain_w, pain_h, fill=CARD_BG, line_rgb=CARD_LINE)
    add_bar(s, x, pain_y, pain_w, Inches(0.055), ACCENT)
    add_text(s, x + Inches(0.24), pain_y + Inches(0.28), Inches(0.7), Inches(0.4),
             no, font_size=20, bold=True, color=CARD_BG2)
    add_text(s, x + Inches(0.24), pain_y + Inches(0.72), pain_w - Inches(0.48), Inches(0.4),
             head, font_size=15, bold=True, color=T_TITLE)
    add_text(s, x + Inches(0.24), pain_y + Inches(1.22), pain_w - Inches(0.48), Inches(2.1),
             body, font_size=10.5, color=T_BODY, line_spacing=1.25)
    add_rect(s, x + Inches(0.24), pain_y + Inches(3.38), pain_w - Inches(0.48), Inches(0.5),
             fill=WARNBG, line_rgb=WARNLINE)
    add_text(s, x + Inches(0.36), pain_y + Inches(3.44), pain_w - Inches(0.72), Inches(0.4),
             cons, font_size=9.5, bold=True, color=AMBER)
    x = x + pain_w + pain_gap

add_rect(s, M, Inches(6.06), CW, Inches(0.74), fill=CARD_BG2, line_rgb=OKLINE)
add_text(s, M + Inches(0.26), Inches(6.13), CW - Inches(0.52), Inches(0.6), [
    "三个特点指向同一个技术选择：把事实从模型参数里拿出来，放进可检索、可更新、可追溯的知识库。",
    "分散的信息要归一，过期的信息要能低成本更新，每条事实要能点开出处 —— 单纯调用大模型一件都做不到。",
], font_size=11.5, bold=True, color=NAVY, line_spacing=1.15)


# ----- 03 项目目标与范围 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "项目目标与范围", "一句话定位 · 五项能力 · 三条边界")
add_footer(s, 3)

add_rect(s, M, Inches(1.72), CW, Inches(1.02), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.26), Inches(1.85), CW - Inches(0.52), Inches(0.8),
         "做一个「回答的每个事实都能点开原始来源」的留学规划助手：\n"
         "把自然语言画像结构化，用真实数据检索出依据，再由多个领域角色分别推理、汇总成一份可执行的申请规划。",
         font_size=12.5, color=NAVY, bold=True, line_spacing=1.3)

add_text(s, M, Inches(2.96), Inches(6), Inches(0.3),
         "五项核心能力", font_size=12, bold=True, color=T_TITLE)

caps = [
    ("Profile 抽取", "从自然语言里结构化提取 GPA / 标化 / 目标院校 / 科研背景"),
    ("方案匹配", "按画像给出选校清单与冲刺-稳妥-保底风险分档"),
    ("RAG 可信检索", "180 条真实数据 · MMR 检索 · 输出逐条带 source_url"),
    ("多智能体协作", "LangGraph 三角色专家分库检索，汇总为五阶段规划"),
    ("自动化闭环", "N8N 把「表单提问 → AI 回答 → 飞书推送」串成闭环"),
]
cap_w = Inches(2.28)
cap_gap = Inches(0.185)
x = M
for i, (head, body) in enumerate(caps):
    add_rect(s, x, Inches(3.32), cap_w, Inches(1.5), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, x + Inches(0.16), Inches(3.44), cap_w - Inches(0.32), Inches(0.28),
             "0%d" % (i + 1), font_size=10, bold=True, color=ACCENT)
    add_text(s, x + Inches(0.16), Inches(3.72), cap_w - Inches(0.32), Inches(0.3),
             head, font_size=11.5, bold=True, color=NAVY)
    add_text(s, x + Inches(0.16), Inches(4.06), cap_w - Inches(0.32), Inches(0.7),
             body, font_size=9, color=T_BODY, line_spacing=1.2)
    x = x + cap_w + cap_gap

add_rect(s, M, Inches(5.06), CW, Inches(1.72), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.26), Inches(5.18), CW - Inches(0.52), Inches(0.3),
         "范围与边界（先说清楚，避免超出实际能力）", font_size=11.5, bold=True, color=AMBER)
bounds = [
    "知识库覆盖 180 条真实记录（100 院校 + 50 录取案例 + 30 文书，以美 / 英 / 港 / 新为主），不是全量院校库。",
    "院校数据为离线采集快照，实时增量抓取未做；但事实不进模型参数，更新重跑采集与向量化即可，"
    "代价是分钟级，不必重训模型。",
    "多轮对话：会话内指代消解已实现（checkpointer + 入口查询改写）；跨会话长期记忆为有意不启用 —— "
    "单次规划型任务用不上，画像含 GPA、预算等敏感信息，不落库更稳妥。",
]
by = Inches(5.52)
for b in bounds:
    add_text(s, M + Inches(0.26), by, CW - Inches(0.52), Inches(0.38),
             "· " + b, font_size=9.5, color=T_BODY, line_spacing=1.15)
    by = by + Inches(0.4)


# ----- 04 系统总体架构 + 技术选型逻辑 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "系统总体架构与技术选型逻辑", "每一层技术都由一个具体问题推导出来，而不是先选工具再找场景")
add_footer(s, 4)

arch_w = Inches(6.55)
# 数据底座
add_rect(s, M, Inches(1.7), arch_w, Inches(0.72), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.2), Inches(1.78), arch_w - Inches(0.4), Inches(0.26),
         "数据底座", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.2), Inches(2.04), arch_w - Inches(0.4), Inches(0.3),
         "180 条真实留学数据（100 院校 + 50 案例 + 30 文书）· 每条带 source_url",
         font_size=9.5, color=T_BODY)

layers = [
    ("检索与推理层", "LangChain（Loader / Embeddings / VectorStore）+ Chroma 向量库 + MMR 检索；LangGraph supervisor-worker 多智能体编排"),
    ("交互层", "Gradio 本地驾驶舱（localhost:7860，多轮对话 + 来源卡片）／Dify Chatflow 线上应用"),
    ("自动化层", "N8N 工作流：表单触发 → 调 Dify API → 飞书群推送，端到端无人值守"),
    ("模型适配层", "Qwen2.5-7B-Instruct + LoRA 领域微调（rank8 / alpha16 / 3 epoch）"),
]
ly = Inches(2.56)
for i, (head, body) in enumerate(layers):
    add_rect(s, M, ly, arch_w, Inches(0.9), fill=CARD_BG, line_rgb=CARD_LINE)
    add_bar(s, M, ly, Inches(0.055), Inches(0.9), ACCENT)
    add_text(s, M + Inches(0.2), ly + Inches(0.09), arch_w - Inches(0.4), Inches(0.26),
             head, font_size=10.5, bold=True, color=NAVY)
    add_text(s, M + Inches(0.2), ly + Inches(0.37), arch_w - Inches(0.4), Inches(0.48),
             body, font_size=9, color=T_BODY, line_spacing=1.15)
    ly = ly + Inches(0.99)

# 右侧：问题 → 技术 映射
rx = M + arch_w + Inches(0.34)
rw = CW - arch_w - Inches(0.34)
add_text(s, rx, Inches(1.7), rw, Inches(0.3),
         "问题 → 技术选择", font_size=12, bold=True, color=T_TITLE)
pairs = [
    ("事实不可信、无法溯源", "RAG + Chroma + source_url", "事实由检索层注入，可逐条反查"),
    ("单次检索内容同质", "MMR（k=8 / fetch_k=20）", "兼顾相关性与多样性"),
    ("单个 Prompt 承担不了多任务", "LangGraph supervisor-worker", "三库分检索 + 三角色分 Prompt"),
    ("输出语体不像留学顾问", "LoRA 领域微调", "权重层习得结构化输出与附来源习惯"),
    ("人工搬运问答结果", "N8N 自动化工作流", "表单到推送端到端闭环"),
]
py = Inches(2.06)
for q, tech, why in pairs:
    add_rect(s, rx, py, rw, Inches(0.86), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, rx + Inches(0.18), py + Inches(0.08), rw - Inches(0.36), Inches(0.24),
             q, font_size=9.5, color=T_MUTED)
    add_text(s, rx + Inches(0.18), py + Inches(0.31), rw - Inches(0.36), Inches(0.26),
             "▶ " + tech, font_size=11, bold=True, color=ACCENT)
    add_text(s, rx + Inches(0.18), py + Inches(0.58), rw - Inches(0.36), Inches(0.24),
             why, font_size=8.5, color=T_BODY)
    py = py + Inches(0.93)


# ----- 05 用户输入理解：Profile 抽取 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "用户输入理解：Profile 抽取", "把一段自然语言描述，转成结构化、可参与推理的画像字段")
add_footer(s, 5)

# 真实运行截图：一句话输入 → Analyze → Profile Snapshot
add_image_fit(s, ASSETS / "profile_snapshot.png", M, Inches(1.52), CW, Inches(3.45))

# GPA 抽取：四层降级匹配（横排四格）
add_text(s, M, Inches(5.04), Inches(4.6), Inches(0.28),
         "GPA 抽取：四层降级匹配（extract_profile）", font_size=11.5, bold=True, color=T_TITLE)
add_pill(s, M + Inches(5.2), Inches(5.0), "规则抽取 · 非模型打分", size=9.5)

steps = [
    ("① 直接给 4.0 制", '"GPA 3.5" → gpa = 3.5'),
    ("② 百分制换算", "90+→3.7 · 85+→3.3\n80+→3.0 · 75+→2.7"),
    ("③ 本科档次估算", "C9→3.7 · 985/211→3.5\n一本→3.2 · 双非→3.0"),
    ("④ 无任何信号", "保持 None，不计 0、不猜测"),
]
gw = Inches(2.8675)
gap = Inches(0.14)
sx = M
for head, body in steps:
    add_rect(s, sx, Inches(5.32), gw, Inches(0.6), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, sx + Inches(0.14), Inches(5.37), gw - Inches(0.28), Inches(0.22),
             head, font_size=9.5, bold=True, color=ACCENT)
    add_text(s, sx + Inches(0.14), Inches(5.6), gw - Inches(0.28), Inches(0.28),
             body, font_size=8, color=T_BODY, font=MONO)
    sx = sx + gw + gap

add_evidence(s, M, Inches(6.02), CW, [
    ("自然语言直入，无表单",
     "顶部一句话直接点 Analyze，画像抽取与检索并列触发、互不依赖，画像不进检索链。用户全程没有表单可填，也没被要求先补字段。"),
    ("GPA 3.3 是换算来的，不是「读」出来的",
     "截图里 3.3 带橙色「估算」角标，与②层「均分 85+ → 3.3」逐字吻合；代码打 gpa_is_estimated 标记，把换算值与用户直接给的分数分开。"),
    ("没信息的地方不硬编",
     "TARGET 显示「美国 · CS + 软语义识别」：用户没写具体院校就走 target_hint，不假装读到学校名；4 槽位全中，Completeness 100%。"),
], height=Inches(0.92))


# ----- 06 可追溯数据底座 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "可追溯数据底座", "180 条真实记录的构成、字段结构，以及「可溯源」具体落在哪个字段上")
add_footer(s, 6)

bars = [("院校项目库  100 条", 100, NAVY), ("录取案例库  50 条", 50, ACCENT),
        ("文书范例库  30 条", 30, TEAL)]
bx = M
for label, cnt, col in bars:
    w = int(CW * cnt / 180)
    add_bar(s, bx, Inches(1.76), w, Inches(0.64), col)
    add_text(s, bx, Inches(1.93), w, Inches(0.32), label, font_size=12, bold=True,
             color=T_WHITE, align=PP_ALIGN.CENTER)
    bx = bx + w

libs = [
    ("院校项目库 · 100 条",
     "院校与项目的基本信息：排名、项目时长、学费、语言要求、截止日期、先修课要求。"
     "回答选校类问题时，事实依据全部来自这里。"),
    ("录取案例库 · 50 条",
     "真实录取与拒录案例：申请人背景、申请结果、去向院校。"
     "用于校准「这个背景够不够」这类定位判断，而不是凭模型印象给结论。"),
    ("文书范例库 · 30 条",
     "PS / SOP / 推荐信范例：结构拆解与写作要点。"
     "文书 worker 检索时命中，未命中会明确标注「未检索到同方向范文」。"),
]
lw3 = Inches(3.83)
lx = M
for head, body in libs:
    add_card(s, lx, Inches(2.6), lw3, Inches(1.42), head=head, body=body,
             head_size=11.5, body_size=9.5)
    lx = lx + lw3 + Inches(0.2)

add_rect(s, M, Inches(4.2), CW, Inches(1.34), fill=CARD_BG2, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(4.3), CW - Inches(0.48), Inches(0.28),
         "每条记录的字段结构（annotated_dataset.jsonl）", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(4.62), CW - Inches(0.48), Inches(0.85),
         '{ "id": "case_001",  "source_lib": "录取案例库",  "text": "<归一化后的正文>",\n'
         '  "label_dimension": "申请结果",  "label": "Admit",\n'
         '  "source_url": "https://<原始页面地址>"        # 可点击外跳，逐条反查 }',
         font_size=10.5, color=NAVY, font=MONO, line_spacing=1.3)

add_rect(s, M, Inches(5.72), CW, Inches(1.0), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(5.84), CW - Inches(0.48), Inches(0.76),
         "数据铁律：180 条全部来自院校官网、QS / USNews、公开案例页与留学论坛的真实内容，每条带 source_url，"
         "不混入样本数据、不虚构字段。\n"
         "source_url 不是装饰字段 —— 检索结果的来源卡片直接由它渲染，点开即可回到原始页面复核。",
         font_size=10.5, color=NAVY, line_spacing=1.3)


# ----- 07 标注体系与分布 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "标注体系与标签分布", "把自由文本归一化成 5 个可量化维度，作为后续数据构造的依据")
add_footer(s, 7)

top_charts = [("dist_申请结果.png", "申请结果 · Admit / Reject / Waitlist"),
              ("dist_排名档.png", "排名档 · Top10 / Top30 / Top50 / 其他"),
              ("dist_文书类型.png", "文书类型 · PS / SOP / 推荐信"),
              ("dist_文书质量.png", "文书质量 · 优 / 良 / 中")]
cw4 = Inches(2.82)
cx = M
for fn, cap in top_charts:
    add_image_fit(s, ASSETS / fn, cx, Inches(1.68), cw4, Inches(1.9),
                  caption=cap, cap_size=9)
    cx = cx + cw4 + Inches(0.2)

add_image_fit(s, ASSETS / "dist_院校国家.png", M, Inches(3.86), cw4, Inches(1.9),
              caption="院校国家 · 美 / 英 / 港 / 新 / 其他", cap_size=9)

add_rect(s, M + cw4 + Inches(0.2), Inches(3.86), CW - cw4 - Inches(0.2), Inches(1.9),
         fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + cw4 + Inches(0.44), Inches(3.98), CW - cw4 - Inches(0.68), Inches(0.3),
         "这张图证明了什么", font_size=11.5, bold=True, color=TEAL)
ev = [
    "① 每个维度都有实际分布、类别之间有区分度 —— 标签体系不是摆设，能支撑后续按维度筛选数据。",
    "② 文书质量与文书类型的分档，直接对应 SFT 数据构造时的类别标签，标注结果可被训练流程直接消费。",
    "③ 院校国家以美 / 英 / 港 / 新为主 —— 与知识库实际覆盖范围一致，边界对用户是透明的。",
]
ey = Inches(4.34)
for e in ev:
    add_text(s, M + cw4 + Inches(0.44), ey, CW - cw4 - Inches(0.68), Inches(0.44),
             e, font_size=9.5, color=T_BODY, line_spacing=1.2)
    ey = ey + Inches(0.46)

add_rect(s, M, Inches(5.94), CW, Inches(0.78), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(6.04), CW - Inches(0.48), Inches(0.6),
         "标注的作用不只是「统计好看」：它把不可比的自由文本变成可筛选、可统计、可构造训练集的结构化数据，"
         "是数据底座从「一堆文档」变成「可用资产」的关键一步。",
         font_size=11, bold=True, color=NAVY)


# ----- 08 为什么需要 RAG -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "为什么需要 RAG", "通用大模型能生成通顺的答案，但生成不了「可核对的答案」")
add_footer(s, 8)

chain = ["纯 LLM 直接生成", "内容读起来合理", "但没有任何来源标注", "无法核对、无法追责"]
cwid = Inches(2.71)
cx = M
for i, c in enumerate(chain):
    col = CARD_BG if i < 2 else WARNBG
    lc = CARD_LINE if i < 2 else WARNLINE
    tc = T_BODY if i < 2 else AMBER
    add_rect(s, cx, Inches(1.74), cwid, Inches(0.86), fill=col, line_rgb=lc)
    add_text(s, cx, Inches(2.0), cwid, Inches(0.36), c, font_size=11.5, bold=True,
             color=tc, align=PP_ALIGN.CENTER)
    if i < len(chain) - 1:
        add_text(s, cx + cwid, Inches(2.0), Inches(0.35), Inches(0.36), "▶",
                 font_size=11, color=T_MUTED, align=PP_ALIGN.CENTER)
    cx = cx + cwid + Inches(0.35)

half = Inches(5.85)
add_rect(s, M, Inches(2.9), half, Inches(2.7), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(3.02), half - Inches(0.48), Inches(0.3),
         "✗ 纯 LLM 直答", font_size=13, bold=True, color=RED)
left_items = [
    "输出流畅，但没有任何来源标注",
    "无法区分哪句是事实、哪句是模型补全",
    "院校要求一变，模型参数不会跟着变",
    "同一个问题多问几次，给出的数字可能不一致",
]
ly = Inches(3.46)
for it in left_items:
    add_text(s, M + Inches(0.26), ly, half - Inches(0.52), Inches(0.4),
             "· " + it, font_size=10, color=T_BODY)
    ly = ly + Inches(0.44)
add_text(s, M + Inches(0.26), Inches(5.24), half - Inches(0.52), Inches(0.3),
         "→ 可用于闲聊，不能用于高风险决策", font_size=10.5, bold=True, color=RED)

add_rect(s, M + half + Inches(0.19), Inches(2.9), half, Inches(2.7),
         fill=EVID_BG, line_rgb=OKLINE)
add_text(s, M + half + Inches(0.43), Inches(3.02), half - Inches(0.48), Inches(0.3),
         "✓ 检索增强（RAG）", font_size=13, bold=True, color=TEAL)
right_items = [
    "回答中的事实来自检索到的原始记录",
    "每条资料带 source_url，可点开原始页面复核",
    "更新知识库即可同步最新要求，不必重训模型",
    "召回结果与答案并排展示，依据可当场验证",
]
ry = Inches(3.46)
for it in right_items:
    add_text(s, M + half + Inches(0.45), ry, half - Inches(0.52), Inches(0.4),
             "· " + it, font_size=10, color=T_BODY)
    ry = ry + Inches(0.44)
add_text(s, M + half + Inches(0.45), Inches(5.24), half - Inches(0.52), Inches(0.3),
         "→ 结论可验证、可追溯、可更新", font_size=10.5, bold=True, color=TEAL)

add_rect(s, M, Inches(5.78), CW, Inches(0.94), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.9), CW - Inches(0.48), Inches(0.72),
         "所以本项目的路线是：让模型只负责「把检索到的事实组织成可读的规划」，"
         "事实本身一律由检索层提供并附上出处 —— 模型不承担它本来就不可靠的记忆职责。",
         font_size=11.5, bold=True, color=NAVY)


# ----- 09 RAG 实现链路 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "RAG 实现链路", "从官方数据到带来源的答案，每一步都在做什么")
add_footer(s, 9)

steps = [
    ("01", "官方数据采集", "院校官网 / QS / USNews / 公开案例页与论坛"),
    ("02", "清洗与标签归一化", "多源原始页 → 统一字段表（按库定义 schema）"),
    ("03", "DocumentLoader", "字段拼成自然语言文本 + 关键字段存 metadata"),
    ("04", "Splitter（预留兜底）", "RecursiveCharacterTextSplitter 800 / 80"),
    ("05", "向量化", "text-embedding-v3 · 1024 维"),
    ("06", "向量库持久化", "Chroma 本地存储 · 180 条向量"),
    ("07", "MMR 检索", "k=8 / fetch_k=20，兼顾相关性与多样性"),
    ("08", "生成", "qwen-plus 基于召回资料作答，附 [资料N]"),
]
sw = Inches(2.81)
for i, (no, head, body) in enumerate(steps):
    row, col = divmod(i, 4)
    x = M + (sw + Inches(0.22)) * col
    y = Inches(1.7) + (Inches(1.22)) * row
    add_rect(s, x, y, sw, Inches(1.06), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, x + Inches(0.16), y + Inches(0.06), Inches(0.4), Inches(0.22),
             no, font_size=9, bold=True, color=ACCENT)
    add_text(s, x + Inches(0.16), y + Inches(0.28), sw - Inches(0.32), Inches(0.28),
             head, font_size=10.5, bold=True, color=NAVY)
    add_text(s, x + Inches(0.16), y + Inches(0.58), sw - Inches(0.32), Inches(0.42),
             body, font_size=8.5, color=T_BODY, line_spacing=1.15)

params = [
    ("嵌入模型", "text-embedding-v3", "1024 维 · DashScope 原生 SDK"),
    ("向量库", "Chroma（本地）", "180 条向量 · 持久化到磁盘"),
    ("检索策略", "MMR", "k=8 / fetch_k=20"),
    ("分库过滤", "3 个库分别检索", "按 source_sheet 过滤，不混检"),
]
pw = Inches(2.845)
for i, (label, val, note) in enumerate(params):
    add_metric(s, M + (pw + Inches(0.17)) * i, Inches(4.24), pw, Inches(1.02),
               label, val, note, value_color=NAVY)

add_rect(s, M, Inches(5.44), Inches(5.85), Inches(1.28), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.2), Inches(5.54), Inches(5.45), Inches(0.26),
         "关于 Splitter 的实际情况", font_size=10.5, bold=True, color=AMBER)
add_text(s, M + Inches(0.2), Inches(5.82), Inches(5.45), Inches(0.84),
         "build_vectorstore 里配置了 800 / 80 的切分器，但实测 180 条记录中最长文本为 530 字符、"
         "超 800 字符的为 0 条 —— 一条记录 = 一个 Document = 一条向量，切分器是预留兜底，未实际生效。",
         font_size=9, color=T_BODY, line_spacing=1.25)

add_rect(s, M + Inches(6.04), Inches(5.44), Inches(5.85), Inches(1.28),
         fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(6.24), Inches(5.54), Inches(5.45), Inches(0.26),
         "查询侧归一化（query_norm）", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(6.24), Inches(5.82), Inches(5.45), Inches(0.84),
         "把 38 所院校的别名统一映射到标准名（如「CMU / 卡内基梅隆」→ 同一实体），"
         "并先剥离 (UCI) 一类括号后缀，再匹配。目的是提升召回率，而不是改写用户的问题。",
         font_size=9, color=T_BODY, line_spacing=1.25)


# ----- 10 RAG 效果证据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "RAG 效果证据", "真实运行记录：左侧为答案，右侧为本次召回的 Top-8 原始资料")
add_footer(s, 10)

add_image_fit(s, ASSETS / "rag_demo.png", M, Inches(1.68), Inches(5.3), Inches(4.7))

evx = M + Inches(5.52)
evw = CW - Inches(5.52)
def add_evidence_v(slide, left, top, width, items, item_h=Inches(1.42), gap=Inches(0.16)):
    marks = "①②③④⑤"
    y = top
    for i, (head, body) in enumerate(items):
        add_rect(slide, left, y, width, item_h, fill=EVID_BG, line_rgb=EVID_LINE)
        add_text(slide, left + Inches(0.18), y + Inches(0.1), width - Inches(0.36), Inches(0.28),
                 "%s %s" % (marks[i], head), font_size=11, bold=True, color=TEAL)
        add_text(slide, left + Inches(0.18), y + Inches(0.43), width - Inches(0.36),
                 item_h - Inches(0.55), body, font_size=9.5, color=T_BODY, line_spacing=1.25)
        y = y + item_h + gap


add_evidence_v(s, evx, Inches(1.68), evw, [
    ("答案与资料并排", "回答与本次召回的原始资料左右对照展示，"
     "「答案来自资料」这句话可以当场验证，而不是口头声明。"),
    ("Top-8 每条带库标签", "每条命中都标注来源库（院校 / 案例 / 文书），"
     "证明三个库是分别检索的，不是把整个向量库混在一起查。"),
    ("source_url 可外跳", "底部来源卡片由真实 source_url 渲染，点开回到原始页面 —— "
     "可溯源最终落在可点击的链接上。"),
])

add_rect(s, M, Inches(6.52), CW, Inches(0.52), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(6.58), CW - Inches(0.48), Inches(0.4),
         "截图来源：rag_demo_capture.json（真实运行记录）→ rag/build_demo_panel.py 渲染，非手工绘制。",
         font_size=10, bold=True, color=NAVY)


# ----- 11 为什么不用单 Agent -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "为什么不用单 Agent", "多智能体不是堆技术，是三个具体约束推出来的结构")
add_footer(s, 11)

add_image_fit(s, ASSETS / "langgraph_arch.png", M, Inches(1.68), Inches(5.0), Inches(2.3))

why_x = M + Inches(5.22)
why_w = CW - Inches(5.22)
reasons = [
    ("① 三个库要分别检索", "院校项目库、录取案例库、文书范例库的关注点完全不同，"
     "单次检索会把三类结果混在一起，既稀释相关性也说不清依据来自哪。"),
    ("② 三个角色要不同 Prompt", "选校策略、录取风险、文书规划的分析框架不一样，"
     "一个 prompt 只能取三者交集，写不出各自该有的判断维度。"),
    ("③ 汇总需要全局统一编号", "三路召回必须合并去重后统一编号，"
     "才能和答案里的 [资料N] 与底部来源卡片一一对上。"),
]
ry = Inches(1.68)
for head, body in reasons:
    add_rect(s, why_x, ry, why_w, Inches(0.72), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, why_x + Inches(0.18), ry + Inches(0.06), why_w - Inches(0.36), Inches(0.26),
             head, font_size=10.5, bold=True, color=NAVY)
    add_text(s, why_x + Inches(0.18), ry + Inches(0.32), why_w - Inches(0.36), Inches(0.36),
             body, font_size=8.5, color=T_BODY, line_spacing=1.15)
    ry = ry + Inches(0.8)

add_image_fit(s, ASSETS / "langgraph_topology.png", M, Inches(4.14), Inches(11.0), Inches(2.5),
              caption="拓扑按 build_graph() 的真实边表绘制：7 个节点 / 8 条边 / 三个 worker 并行 fan-out，同一 superstep 并发执行（边表可由 get_graph() 打印逐条核对）",
              cap_size=9.5)


# ----- 12 实现：StateGraph 组装（深色代码页）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_CODE)
add_title(s, "实现：StateGraph 的组装", "rag/agents.py —— 状态定义与图的编译", dark=True)
add_footer(s, 12, dark=True)

add_text(s, M, Inches(1.66), Inches(7), Inches(0.3),
         "# 共享状态：所有节点读写同一个 State", font_size=10, color=D_CMT, font=MONO)

left_code = [
    {"text": "class State(TypedDict):", "color": D_ACC},
    {"text": "    messages: Annotated[List, add_messages]", "color": D_BODY},
    {"text": "    query: str            # 本轮问题（改写后的自包含句）", "color": D_BODY},
    {"text": "    route: List[str]      # supervisor 选中的 worker", "color": D_BODY},
    {"text": "    school_docs: List[Document]", "color": D_BODY},
    {"text": "    admission_docs: List[Document]", "color": D_BODY},
    {"text": "    essay_docs: List[Document]", "color": D_BODY},
    {"text": "    school_plan: str      # 三个 worker 各自的结论", "color": D_BODY},
    {"text": "    admission_risk: str", "color": D_BODY},
    {"text": "    essay_outline: str", "color": D_BODY},
    {"text": "    answer: str", "color": D_BODY},
]
add_text(s, M, Inches(2.02), Inches(7), Inches(2.6), left_code,
         font_size=10, color=D_BODY, font=MONO, line_spacing=1.32)

add_text(s, M + Inches(0.02), Inches(4.22), Inches(6.4), Inches(0.28),
         "# 路由不靠条件边：worker 自己判断是否在 route 里，不在则返回 {}", font_size=9, color=D_CMT, font=MONO)

rx = M + Inches(6.5)
add_text(s, rx, Inches(1.66), Inches(5.4), Inches(0.3),
         "# 组装与编译：5 个业务节点 + 8 条直连边（并行 fan-out）", font_size=10, color=D_CMT, font=MONO)
right_code = [
    {"text": "def build_graph():", "color": D_ACC},
    {"text": "    g = StateGraph(State)", "color": D_BODY},
    {"text": "    g.add_node(\"supervisor\", supervisor)", "color": D_BODY},
    {"text": "    g.add_node(\"worker_school\", worker_school)", "color": D_BODY},
    {"text": "    g.add_node(\"worker_admission\", worker_admission)", "color": D_BODY},
    {"text": "    g.add_node(\"worker_essay\", worker_essay)", "color": D_BODY},
    {"text": "    g.add_node(\"synthesizer\", synthesizer)", "color": D_BODY},
    {"text": "", "color": D_BODY},
    {"text": "    g.add_edge(START, \"supervisor\")", "color": D_STR},
    {"text": "    # 并行 fan-out：同一 superstep 并发执行", "color": D_CMT},
    {"text": "    g.add_edge(\"supervisor\", \"worker_school\")", "color": D_STR},
    {"text": "    g.add_edge(\"supervisor\", \"worker_admission\")", "color": D_STR},
    {"text": "    g.add_edge(\"supervisor\", \"worker_essay\")", "color": D_STR},
    {"text": "    # fan-in：全部完成后才进 synthesizer", "color": D_CMT},
    {"text": "    g.add_edge(\"worker_school\", \"synthesizer\")", "color": D_STR},
    {"text": "    g.add_edge(\"worker_admission\", \"synthesizer\")", "color": D_STR},
    {"text": "    g.add_edge(\"worker_essay\", \"synthesizer\")", "color": D_STR},
    {"text": "    g.add_edge(\"synthesizer\", END)", "color": D_STR},
    {"text": "", "color": D_BODY},
    {"text": "    return g.compile(checkpointer=MemorySaver())", "color": D_KEY},
]
add_text(s, rx, Inches(2.02), Inches(5.4), Inches(3.2), right_code,
         font_size=9.5, color=D_BODY, font=MONO, line_spacing=1.22)

add_rect(s, rx + Inches(0.0), Inches(5.5), Inches(5.39), Inches(1.3),
         fill=D_CARD, line_rgb=D_LINE)
add_text(s, rx + Inches(0.18), Inches(5.6), Inches(5.05), Inches(1.1),
         [{"text": "两个容易被追问的点", "color": D_ACC, "size": 10.5, "bold": True},
          {"text": "① 并行无竞态：三个 worker 只写各自专属字段（school_* / admission_* / essay_*），无同 key 更新，故无需 reducer。", "color": D_BODY, "size": 9},
          {"text": "② 路由裁剪：未被 supervisor 选中的 worker 返回 {}，并行与裁剪同时成立；8 条边全是 add_edge 直连，无 conditional_edges。", "color": D_BODY, "size": 9}],
         font_size=9, color=D_BODY, line_spacing=1.3)


# ----- 13 运行效果证据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "多智能体运行效果证据", "真实运行截图：三个角色分别检索与推理后，汇总成一份可执行的申请规划")
add_footer(s, 13)

add_image_fit(s, ASSETS / "Gradio本地Demo.png", M, Inches(1.72), Inches(7.3), Inches(4.02))

add_evidence_v(s, M + Inches(7.5), Inches(1.72), Inches(4.39), [
    ("引用编号全局一致", "答案里的 [资料N] 与底部来源卡片一一对应 —— "
     "证明三个 worker 的召回做了合并去重后统一编号，不是各写各的。"),
    ("五阶段结构化输出", "选校定稿 → 材料准备 → 文书写作 → 网申提交 → 面试准备，"
     "说明 synthesizer 确实在整合三份角色结论，而不是一次生成。"),
    ("本地可复现", "顶栏为 localhost:7860 本地实例，评委现场即可复跑同一问题验证。"),
], item_h=Inches(1.5), gap=Inches(0.16))

add_rect(s, M, Inches(5.84), CW, Inches(0.86), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.95), CW - Inches(0.48), Inches(0.66),
         "注意：图中第二轮的连续追问（「那第一个的截止日期和学费呢」）能正确落到上一轮推荐的院校 —— "
         "这依赖 LangGraph checkpointer 保存的跨轮 state 与入口处的查询改写，而不是靠模型猜上下文。",
         font_size=10.5, color=NAVY)


# ----- 14 为什么自动化 + 真实工作流 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "为什么做自动化：真实工作流", "回答停在聊天窗口里，业务上不产生任何动作")
add_footer(s, 14)

add_image_fit(s, ASSETS / "N8N工作流全景.png", M, Inches(1.7), Inches(7.6), Inches(3.5))

ax = M + Inches(7.82)
aw = CW - Inches(7.82)
autos = [
    ("① 回答没有落到协作场景", "AI 生成的内容如果只留在页面里，团队协作时仍要人工复制粘贴，价值打折。"),
    ("② 人工搬运无法沉淀", "每次问答都靠人转发，既不可复用也不可审计，流程永远停在「演示」阶段。"),
    ("③ 需要一条无人值守的链", "把「提问 → 调 AI → 通知」固定成工作流，才谈得上业务闭环。"),
]
ay = Inches(1.7)
for head, body in autos:
    add_rect(s, ax, ay, aw, Inches(1.14), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, ax + Inches(0.18), ay + Inches(0.1), aw - Inches(0.36), Inches(0.26),
             head, font_size=10.5, bold=True, color=NAVY)
    add_text(s, ax + Inches(0.18), ay + Inches(0.4), aw - Inches(0.36), Inches(0.66),
             body, font_size=9, color=T_BODY, line_spacing=1.2)
    ay = ay + Inches(1.25)

add_rect(s, M, Inches(5.4), CW, Inches(1.3), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(5.5), CW - Inches(0.48), Inches(0.28),
         "工作流的四个节点（N8N · 本地 docker）", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(5.82), CW - Inches(0.48), Inches(0.34),
         "Form Trigger（收集问题）  ▶  HTTP Request（POST Dify API）  ▶  Edit Fields（提取 answer 字段）  ▶  飞书 HTTP Request（推送群）",
         font_size=10.5, color=ACCENT, font=MONO)
add_text(s, M + Inches(0.24), Inches(6.22), CW - Inches(0.48), Inches(0.4),
         "工程细节：推送飞书时用 JSON.stringify() 包裹模板变量，自动转义换行与特殊字符，避免长文本里的换行把 JSON 结构冲掉。",
         font_size=9.5, color=T_BODY)


# ----- 15 闭环效果证据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "自动化闭环效果证据", "左：Dify 三路知识库并联编排 · 右：飞书群收到的完整回答")
add_footer(s, 15)

add_image_fit(s, ASSETS / "Dify-Chatflow编排.png", M, Inches(1.74), Inches(7.5), Inches(3.4),
              caption="Dify Chatflow：用户输入 → 三路知识库并联检索 → qwen-plus → 直接回复",
              cap_size=9.5)
add_image_fit(s, ASSETS / "飞书群推送消息.png", M + Inches(7.72), Inches(1.74), Inches(2.9), Inches(3.4),
              caption="飞书群实时收到 Dify 回答", cap_size=9.5)

add_evidence(s, M, Inches(5.62), CW, [
    ("端到端真的通了", "飞书群里收到的是完整回答正文，而不是一条链接或「有新消息」的提示 —— "
     "证明表单 → AI → 推送这条链确实跑通。"),
    ("不是把问题直接丢给 LLM", "Dify 侧是三个知识库并联检索后再生成，"
     "检索环节真实存在于这条自动化链路里。"),
    ("闭环可脱离本地环境", "线上 Dify 应用承担推理，本地只负责编排与推送，"
     "换台机器改 webhook 即可复用。"),
], height=Inches(1.1))


# ----- 16 为什么需要领域适配 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "为什么需要领域适配", "通用模型知道「留学」这件事，但不一定会用顾问的方式讲")
add_footer(s, 16)

adapt = [
    ("通用基座已经具备的", TEAL, CARD_BG, CARD_LINE, [
        "知道留学申请的基本概念与流程",
        "能写出通顺、连贯的中文段落",
        "具备基础的世界知识与常识推理",
    ]),
    ("实际使用中的缺口", RED, WARNBG, WARNLINE, [
        "语体偏「通用说明文」，不像顾问给学生的具体建议",
        "结构松散，缺少可执行的分阶段组织",
        "不会主动标注数据来源，习惯凭印象补充细节",
    ]),
    ("领域适配的目标", NAVY, EVID_BG, EVID_LINE, [
        "习得「结构化输出 + 主动附来源」的表达范式",
        "让输出形态贴近留学顾问的工作文档",
        "不承担事实记忆 —— 事实仍由检索层提供",
    ]),
]
aw3 = Inches(3.83)
ax = M
for head, hc, fc, lc, items in adapt:
    add_rect(s, ax, Inches(1.76), aw3, Inches(3.5), fill=fc, line_rgb=lc)
    add_text(s, ax + Inches(0.22), Inches(1.92), aw3 - Inches(0.44), Inches(0.3),
             head, font_size=12.5, bold=True, color=hc)
    iy = Inches(2.42)
    for it in items:
        add_text(s, ax + Inches(0.22), iy, aw3 - Inches(0.44), Inches(0.85),
                 "· " + it, font_size=10, color=T_BODY, line_spacing=1.25)
        iy = iy + Inches(0.88)
    ax = ax + aw3 + Inches(0.2)

add_rect(s, M, Inches(5.44), CW, Inches(1.28), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.54), CW - Inches(0.48), Inches(0.28),
         "为什么选 LoRA 而不是全参数微调", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(5.86), CW - Inches(0.48), Inches(0.72),
         "本机显存不足以承载 7B 的全参训练，而领域适配的目标只是「表达范式」而非「事实注入」，"
         "用低秩适配即可达成：LoRA 只更新约 506 万个参数（不到基座的 0.1%），基座权重冻结，训练在单卡 3090 上以分钟级完成。",
         font_size=10, color=T_BODY, line_spacing=1.25)


# ----- 17 训练配置与 loss 曲线 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "训练配置与损失曲线", "LLaMA Factory + qwen_lora_sft.yaml · AutoDL 单卡 RTX 3090 24GB")
add_footer(s, 17)

add_image_fit(s, ASSETS / "training_loss.png", M, Inches(1.74), Inches(5.6), Inches(4.2))

cfgx = M + Inches(5.82)
cfgw = CW - Inches(5.82)
cfg = [
    ("基座模型", "Qwen2.5-7B-Instruct"),
    ("微调方式", "LoRA —— rank 8 / alpha 16 / dropout 0.05"),
    ("注入位置", "q_proj · k_proj · v_proj · o_proj"),
    ("训练数据", "180 条 SFT → 144 训练 / 36 留出；训练侧按 val_size=0.1 再切 129 训练 + 15 验证"),
    ("超参", "lr 2e-4 · epochs 3 · batch 1 × grad_accum 8 · bf16 · cutoff 2048"),
    ("工具链", "LLaMA Factory（llamafactory-cli train）"),
]
cy = Inches(1.74)
for k, v in cfg:
    add_rect(s, cfgx, cy, cfgw, Inches(0.66), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, cfgx + Inches(0.18), cy + Inches(0.06), cfgw - Inches(0.36), Inches(0.24),
             k, font_size=9.5, bold=True, color=NAVY)
    add_text(s, cfgx + Inches(0.18), cy + Inches(0.31), cfgw - Inches(0.36), Inches(0.3),
             v, font_size=9, color=T_BODY)
    cy = cy + Inches(0.71)

add_rect(s, M, Inches(6.1), CW, Inches(0.62), fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + Inches(0.24), Inches(6.2), CW - Inches(0.48), Inches(0.44),
         "曲线说明：train_loss 与 eval_loss 同步下降且未见回弹上翘，3 个 epoch 内稳定收敛，"
         "在 180 条小样本下没有出现明显过拟合。",
         font_size=10.5, bold=True, color=TEAL)


# ----- 18 训练结果数据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "训练结果数据", "四个可核对的数字，全部来自本地训练产物文件")
add_footer(s, 18)

mw = Inches(2.845)
mets = [
    ("损失下降", "1.2952 → 0.7597", "train_loss → eval_loss", NAVY),
    ("训练步数", "51 steps", "3 个 epoch · batch1 × accum8", NAVY),
    ("纯训练耗时", "106.8 秒", "单卡 RTX 3090 · bf16", TEAL),
    ("Adapter 体积", "20.2 MB", "基座权重冻结 · 仅存适配层", TEAL),
]
for i, (label, val, note, vc) in enumerate(mets):
    add_metric(s, M + (mw + Inches(0.17)) * i, Inches(1.78), mw, Inches(1.24),
               label, val, note, value_color=vc)

add_rect(s, M, Inches(3.24), CW, Inches(1.4), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(3.34), CW - Inches(0.48), Inches(0.28),
         "这些数字怎么来的", font_size=11.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(3.66), CW - Inches(0.48), Inches(0.9),
         "训练由 LLaMA Factory 一条命令跑完（llamafactory-cli train qwen_lora_sft.yaml），"
         "训练结束自动写出 train_results.json / trainer_state.json / trainer_log.jsonl / loss 曲线。\n"
         "上面四个数字分别对应：train_results.json 的 loss 与 runtime、trainer_state.json 的 global_step、"
         "adapter_model.safetensors 的实际文件体积 —— 均可随手打开核对，不是记忆值。",
         font_size=10, color=T_BODY, line_spacing=1.3)

add_rect(s, M, Inches(4.82), Inches(5.85), Inches(1.9), fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + Inches(0.22), Inches(4.94), Inches(5.45), Inches(0.28),
         "结果解读", font_size=11.5, bold=True, color=TEAL)
add_text(s, M + Inches(0.22), Inches(5.26), Inches(5.45), Inches(1.34),
         "train_loss 与 eval_loss 同步下降、无回弹，说明模型确实在拟合这 180 条数据的表达模式，"
         "而不是记住了随机噪声。\n"
         "但「loss 降了」只能说明它学得像训练集，学得像不等于事实正确 —— 这一点由后面两页的实验专门核查。",
         font_size=9.5, color=T_BODY, line_spacing=1.28)

add_rect(s, M + Inches(6.04), Inches(4.82), Inches(5.85), Inches(1.9),
         fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(6.26), Inches(4.94), Inches(5.45), Inches(0.28),
         "为什么不把 loss 当成果指标", font_size=11.5, bold=True, color=AMBER)
add_text(s, M + Inches(6.26), Inches(5.26), Inches(5.45), Inches(1.34),
         "180 条样本、3 个 epoch 的 loss 曲线本身不构成任何结论 —— 它只能证明训练跑通了。\n"
         "真正需要回答的问题是：微调之后，模型的输出行为到底变了什么、能不能稳定复现、"
         "有没有超出它该承担的范围。这三问由 A/B 对照与能力边界核查来回答。",
         font_size=9.5, color=T_BODY, line_spacing=1.28)


# ----- 19 实验① 微调 A/B 受控对照 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "实验①：微调 A/B 受控对照", "同一 prompt、同一解码策略，唯一变量是「是否挂载 LoRA adapter」")
add_footer(s, 19)

add_rect(s, M, Inches(1.66), CW, Inches(0.84), fill=CARD_BG2, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(1.74), CW - Inches(0.48), Inches(0.26),
         "实验条件（受控变量）", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(2.0), CW - Inches(0.48), Inches(0.44),
         "Prompt：你是一名留学文书顾问，请为申请纽约大学 MS Data Science 的学生写一段 SOP 开头，不超过 150 字。\n"
         "解码 greedy（do_sample=False）｜唯一变量 = 是否挂载 LoRA adapter（20 MB）｜A 组通过 disable_adapter() 切回纯净基座",
         font_size=9, color=T_BODY, line_spacing=1.25)

A_CARD = RGBColor(0xF7, 0xF7, 0xFA)
B_CARD = RGBColor(0xEC, 0xF7, 0xF1)
add_rect(s, M, Inches(2.62), Inches(5.85), Inches(2.5), fill=A_CARD, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(2.72), Inches(5.41), Inches(0.28),
         "A · 纯基座（未微调）", font_size=12, bold=True, color=T_MUTED)
add_text(s, M + Inches(0.22), Inches(3.04), Inches(5.41), Inches(1.5),
         "在数字化浪潮席卷全球的今天，数据科学作为连接现实世界与数字世界的桥梁，正以前所未有的速度"
         "改变着我们的生活方式、工作模式乃至思维方式。作为一名热衷于探索数据背后故事的学子，我深知"
         "数据科学不仅是一门学科，更是一种工具……因此，当我在众多顶尖学府中选择纽约大学时，"
         "被其在数据科学领域的卓越成就和深厚底蕴深深吸引。",
         font_size=9.5, color=RGBColor(0x6E, 0x76, 0x8C), line_spacing=1.22)
add_text(s, M + Inches(0.22), Inches(4.62), Inches(5.41), Inches(0.4),
         "✗ 通用陈述式长句：通篇宏观议论，没有任何个人背景事实，语气与「通用 AI 作文」无异。",
         font_size=9, bold=True, color=RED)

add_rect(s, M + Inches(6.04), Inches(2.62), Inches(5.85), Inches(2.5),
         fill=B_CARD, line_rgb=OKLINE)
add_text(s, M + Inches(6.26), Inches(2.72), Inches(5.41), Inches(0.28),
         "B · 基座 + LoRA（微调后）", font_size=12, bold=True, color=TEAL)
add_text(s, M + Inches(6.26), Inches(3.04), Inches(5.41), Inches(1.5),
         "我自小就对数据科学充满兴趣，高中时便开始自学 Python 和 R 语言。本科期间，我主修数学与统计学，"
         "并辅修计算机科学。这段经历不仅让我掌握了扎实的理论基础，还培养了我解决实际问题的能力。"
         "如今，我渴望在纽约大学继续深造，成为数据科学领域的顶尖人才。",
         font_size=10, color=RGBColor(0x2A, 0x4A, 0x3E), line_spacing=1.24)
add_text(s, M + Inches(6.26), Inches(4.62), Inches(5.41), Inches(0.4),
         "✓ 第一人称文书语体：锚定「自学 Python/R、主修数学统计」等具体背景事实，贴合 SOP 写作范式。",
         font_size=9, bold=True, color=TEAL)

add_rect(s, M, Inches(5.26), CW, Inches(0.6), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(5.34), CW - Inches(0.48), Inches(0.44),
         "结论：identical = False —— 只切换 LoRA 权重，输出即由「通用陈述式长句」转为「第一人称文书语体 + 个人背景事实」，"
         "属权重层的行为改变，而不是 prompt 修饰出来的差异。",
         font_size=10, bold=True, color=TEAL)

mets2 = [("指令遵循率", "100.0%", "20/20 条输出非空且 > 20 字"),
         ("平均 ROUGE-L", "0.5731", "20 条测试集均值"),
         ("A/B 输出差异", "3 / 3 组", "三类业务任务均发生变化")]
for i, (label, val, note) in enumerate(mets2):
    add_metric(s, M + (mw + Inches(0.17)) * i, Inches(5.98), mw, Inches(0.8),
               label, val, note, value_color=NAVY)


# ----- 20 实验② 能力边界核查 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "实验②：能力边界核查（事实层 vs 表达层）",
          "对微调输出做量化核查 —— 这张结论直接决定了「RAG + 微调」双轨设计的必要性")
add_footer(s, 20)

checks = [
    ("来源链接可溯源性", "0 / 20", AMBER,
     "20 条生成文本都主动附了来源 URL，\n但逐字命中知识库真实 URL 的为 0 条 ——\n链接是模型生成的，不可直接采信。"),
    ("排名数字一致性", "0 / 7", AMBER,
     "含排名数字的 7 条样本，\n与知识库参考文本全部不一致 ——\n事实数值没有被参数记住。"),
    ("表达层迁移有效性", "3 / 3", TEAL,
     "三类业务任务的 A/B 输出均发生\n权重层变化：语体、结构、\n主动附来源的习惯可迁移。"),
]
cwid3 = Inches(3.83)
cx = M
for name, val, col, note in checks:
    add_rect(s, cx, Inches(1.86), cwid3, Inches(2.44), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, cx + Inches(0.22), Inches(1.98), cwid3 - Inches(0.44), Inches(0.28),
             name, font_size=11, bold=True, color=NAVY)
    add_text(s, cx + Inches(0.22), Inches(2.32), cwid3 - Inches(0.44), Inches(0.6),
             val, font_size=26, bold=True, color=col)
    add_text(s, cx + Inches(0.22), Inches(3.04), cwid3 - Inches(0.44), Inches(1.1),
             note, font_size=9, color=T_BODY, line_spacing=1.25)
    cx = cx + cwid3 + Inches(0.2)

add_rect(s, M, Inches(4.48), CW, Inches(1.06), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(4.58), CW - Inches(0.48), Inches(0.86),
         "结论：参数高效微调（LoRA · rank8 · 180 条样本 · 3 epoch）习得的是【表达范式】—— 语体、结构、"
         "主动标注来源的习惯；它不承担【事实记忆】。\n"
         "所以职责必须拆开：RAG 检索层负责事实与 source_url 溯源，微调层负责语体与结构生成 —— "
         "这不是把两个技术堆在一起，而是两条链路各自有明确的验收标准。",
         font_size=10.5, bold=True, color=TEAL, line_spacing=1.3)

add_rect(s, M, Inches(5.66), CW, Inches(1.06), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(5.76), CW - Inches(0.48), Inches(0.28),
         "对应到工程落地", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(6.06), CW - Inches(0.48), Inches(0.56),
         "主链路（app_gradio.py / qa.py）：DashScope qwen-plus + Chroma 检索，回答原样携带真实 source_url，可逐条反查；"
         "微调链路：离线权重落盘 + A/B 对照（权重层行为改变）+ 独立评估，两条链路的结论互不冒充。",
         font_size=9.5, color=T_BODY, line_spacing=1.25)


# ----- 21 系统测试与结果 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "系统测试与结果", "所有指标均来自实际跑批产物，未做估算")
add_footer(s, 21)

grid = [
    ("引用命中率", "100%", "10/10 答案均含知识库真实 source_url", NAVY),
    ("关键字段一致性", "100%", "抽样字段与检索证据吻合（3/3）", NAVY),
    ("平均 ROUGE-L", "0.5731", "20 条测试集均值", NAVY),
    ("对抗集 HitRate@8", "100%", "检索命中率，全部命中", TEAL),
    ("对抗集 MRR", "0.933", "命中结果排序质量（越接近 1 越好）", TEAL),
    ("编排并行收益", "2.98x", "三 worker 段 sum → max，同条件 A/B 实测", TEAL),
]
gw = Inches(3.83)
gh = Inches(1.32)
for i, (label, val, note, vc) in enumerate(grid):
    row, col = divmod(i, 3)
    add_metric(s, M + (gw + Inches(0.2)) * col, Inches(1.76) + (gh + Inches(0.18)) * row,
               gw, gh, label, val, note, value_color=vc)

add_rect(s, M, Inches(4.8), Inches(5.85), Inches(1.9), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.22), Inches(4.92), Inches(5.45), Inches(0.28),
         "一个刻意没做高的指标：路由精确率 63.3%", font_size=11, bold=True, color=AMBER)
add_text(s, M + Inches(0.22), Inches(5.24), Inches(5.45), Inches(1.34),
         "supervisor 决定这一轮要调哪几个 worker，覆盖率 100%、精确率 63.3%。\n"
         "精确率低是 prompt 明确要求的结果：问题笼统时允许全选三个 worker —— "
         "因为漏掉一个库（该查没查）的代价，远大于多查一个库带来的少量冗余。",
         font_size=9, color=T_BODY, line_spacing=1.25)

add_rect(s, M + Inches(6.04), Inches(4.8), Inches(5.85), Inches(1.9),
         fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(6.26), Inches(4.92), Inches(5.45), Inches(0.28),
         "指标怎么测的", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(6.26), Inches(5.24), Inches(5.45), Inches(1.34),
         "检索侧：自建对抗集，把问题与两段内容相近但来源不同的文档配对，检验能否命中正确那一条。\n"
         "生成侧：ROUGE-L 基于 20 条测试集；引用命中率以输出里出现知识库真实 URL 为准。\n"
         "编排侧：同进程内并行图 / 串行图跑同一条 query 对照，取三个 worker 段的耗时之比。",
         font_size=9, color=T_BODY, line_spacing=1.25)


# ----- 22 迭代过程与失败案例 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "迭代过程与失败案例", "现在这个版本是三轮迭代的结果，中间踩过的坑比顺利的部分更有用")
add_footer(s, 22)

stages = [
    ("V1", "纯 LLM 直答", T_MUTED, CARD_BG, CARD_LINE, [
        "直接调大模型回答问题",
        "输出流畅，但无法核对来源",
        "院校信息随时效失效",
        "→ 结论：不可用于高风险场景",
    ]),
    ("V2", "引入 RAG 检索", ACCENT, CARD_BG2, ACCENT, [
        "180 条真实数据 + Chroma 向量库",
        "MMR 检索，答案附 source_url",
        "引用命中率提升到 100%",
        "→ 事实可溯源，且更新不必重训模型",
    ]),
    ("V3", "多智能体 + 领域适配", TEAL, EVID_BG, EVID_LINE, [
        "LangGraph 三角色分工检索推理",
        "LoRA 微调统一输出语体与结构",
        "N8N 把结果推送到协作场景",
        "→ 从「能检索」到「能规划」",
    ]),
]
sw3 = Inches(3.6)
sx = M
for tag, name, tc, fc, lc, items in stages:
    add_rect(s, sx, Inches(1.84), sw3, Inches(2.9), fill=fc, line_rgb=lc)
    add_pill(s, sx + Inches(0.22), Inches(2.0), tag, fill=tc, fg=T_WHITE, size=10,
             width=Inches(0.62))
    add_text(s, sx + Inches(0.96), Inches(2.02), sw3 - Inches(1.2), Inches(0.3),
             name, font_size=12, bold=True, color=tc)
    iy = Inches(2.58)
    for it in items:
        add_text(s, sx + Inches(0.22), iy, sw3 - Inches(0.44), Inches(0.6),
                 "· " + it, font_size=9, color=T_BODY, line_spacing=1.2)
        iy = iy + Inches(0.58)
    sx = sx + sw3 + Inches(0.35)

add_rect(s, M, Inches(4.94), CW, Inches(1.78), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.24), Inches(5.06), CW - Inches(0.48), Inches(0.28),
         "踩过的三个坑（也是这轮最实在的收获）", font_size=11.5, bold=True, color=AMBER)
pit = [
    "① PEFT 的原地注入：PeftModel.from_pretrained() 会直接改写传入的基座对象，循环里反复调用会污染「纯基座」对照组 —— "
    "正解是只套一次 PeftModel，A 组用 with model.disable_adapter(): 隔离。",
    "② 兼容端点不是万能的：OpenAI 兼容接口在中文批量 embedding 上返回 400，最终把嵌入改走 DashScope 原生 SDK，主链路仍保留兼容端点。",
    "③ 忽略规则对已跟踪文件无效：.gitignore 改完必须 git rm --cached 才真正生效，且不能在改完规则后再跑 git reset。",
]
py2 = Inches(5.4)
for p in pit:
    add_text(s, M + Inches(0.24), py2, CW - Inches(0.48), Inches(0.44),
             p, font_size=9, color=T_BODY, line_spacing=1.2)
    py2 = py2 + Inches(0.45)


# ----- 23 总结 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "总结", "数据可信 · 推理分角色 · 自动化落地 · 边界说得清")
add_footer(s, 23)

colw = Inches(3.83)
cols = [
    ("项目亮点", NAVY, CARD_BG, CARD_LINE, [
        "事实层与表达层职责分离：RAG 管事实溯源，微调管语体结构",
        "双轨验证：引用命中 100% vs 微调 URL 逐字溯源 0/20",
        "180 条数据全部带 source_url，零虚构",
        "五套技术栈贯通：LangChain / LangGraph / LoRA / Dify / N8N",
    ]),
    ("个人独立完成", ACCENT, CARD_BG2, ACCENT, [
        "数据采集与 5 维标注，构造 144 + 36 条 SFT 数据集",
        "Chroma RAG 链路：归一化 / 嵌入 / MMR 检索 / 来源卡片",
        "LangGraph 多智能体编排与 checkpointer 多轮指代消解",
        "LLaMA Factory 完成 LoRA 微调并设计 A/B 与边界核查实验",
        "Gradio 驾驶舱、Dify 应用、N8N 工作流的搭建与部署",
    ]),
    ("后续工作", TEAL, EVID_BG, EVID_LINE, [
        "院校数据实时增量更新，替代当前离线快照",
        "扩充国家 / 地区覆盖，突破当前的美英港新范围",
        "多轮上下文：如扩展到多用户 / 长期陪伴场景，接入持久化 checkpointer",
        "补充人工评测，用人工打分校验自动指标的可靠性",
    ]),
]
cx = M
for head, hc, fc, lc, items in cols:
    add_rect(s, cx, Inches(1.76), colw, Inches(4.3), fill=fc, line_rgb=lc)
    add_text(s, cx + Inches(0.22), Inches(1.9), colw - Inches(0.44), Inches(0.3),
             head, font_size=13, bold=True, color=hc)
    iy = Inches(2.4)
    for it in items:
        add_text(s, cx + Inches(0.22), iy, colw - Inches(0.44), Inches(0.8),
                 "· " + it, font_size=9.5, color=T_BODY, line_spacing=1.25)
        iy = iy + Inches(0.76)
    cx = cx + colw + Inches(0.2)

add_rect(s, M, Inches(6.24), CW, Inches(0.62), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(6.34), CW - Inches(0.48), Inches(0.44),
         "一句话收尾：这个项目的价值不在于用了多少个框架，而在于每一处技术选择都能说出它对应哪个具体问题，"
         "以及什么结论有证据、什么结论没有。",
         font_size=10.5, bold=True, color=NAVY)


# __SLIDES_INSERT_POINT__

# 统一文本语言为简体中文。默认样式表里的 defRPr 写的是 en-US，而所有 run 都没有覆盖它，
# 于是编辑器拿英文词典去检查中文，整段被判为拼写错误并画上红色波浪线。
for _s in prs.slides:
    for _sh in _s.shapes:
        if not _sh.has_text_frame:
            continue
        for _p in _sh.text_frame.paragraphs:
            for _run in _p.runs:
                _run.font.language_id = MSO_LANGUAGE_ID.SIMPLIFIED_CHINESE

prs.save(str(OUT))
print("Saved: %s" % OUT)
print("Slides: %d" % len(prs.slides))
print("Size:   %.1f KB" % (OUT.stat().st_size / 1024))
