# -*- coding: utf-8 -*-
"""
把内容逐页导出为 .pptx（17 页正文 + 5 页附录 · 亮色科技学术风）。

版式：16:9，三档底色 —— 正文页白底、架构与附录页浅蓝底、代码页深底。
主色 #243B7A（深蓝）／强调 #5267D8（蓝紫）／卡片 #F5F7FC + 边框 #DDE3F0。
字体 Microsoft YaHei，代码块 Consolas。

页面按三种节奏组织，避免连续多页同一种版式：
  A 类 逻辑说明页 —— 大标题 + 少量核心结论 + 流程/对照，回答「为什么这么做」
  B 类 系统演示页 —— 真实截图占主要空间 + 2-3 个编号标注，回答「它真的在跑」
  C 类 实验结果页 —— 实验条件 + 对照 / 数字 + 结论，只留与结论相关的数字
图片取自 ppt素材/ 下的真实运行截图、分布图与架构图；证据类截图旁配
「这张图证明了什么」标注条，写图能支撑的结论，而不是复述界面有什么。
"""
import sys
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
# 第二个参数可指定输出路径：PPT 被打开时原文件写不进去，先出到临时文件核对。
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"F:\13.答辩材料\毕设PPT.pptx")

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
    label = idx if isinstance(idx, str) else "%02d" % idx
    add_text(slide, SLIDE_W - M - Inches(1.4), Inches(7.08), Inches(1.4), Inches(0.28),
             label, font_size=9, color=c, align=PP_ALIGN.RIGHT)


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


def add_evidence_v(slide, left, top, width, items, item_h=Inches(1.42), gap=Inches(0.16)):
    """竖排证据卡：适合窄列（如右侧 4.4in 宽）放 3 条结论。"""
    marks = "①②③④⑤"
    y = top
    for i, (head, body) in enumerate(items):
        add_rect(slide, left, y, width, item_h, fill=EVID_BG, line_rgb=EVID_LINE)
        add_text(slide, left + Inches(0.18), y + Inches(0.1), width - Inches(0.36), Inches(0.28),
                 "%s %s" % (marks[i], head), font_size=11, bold=True, color=TEAL)
        add_text(slide, left + Inches(0.18), y + Inches(0.43), width - Inches(0.36),
                 item_h - Inches(0.55), body, font_size=9.5, color=T_BODY, line_spacing=1.25)
        y = y + item_h + gap


def add_metric(slide, left, top, width, height, label, value, note, value_color=NAVY,
               tag=None, tag_color=ACCENT):
    add_rect(slide, left, top, width, height, fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(slide, left + Inches(0.16), top + Inches(0.06), width - Inches(0.32), Inches(0.24),
             label, font_size=9.5, bold=True, color=T_MUTED)
    if tag:
        add_pill(slide, left + width - Inches(0.88), top + Inches(0.05), tag,
                 fill=tag_color, fg=T_WHITE, size=8, width=Inches(0.74), height=Inches(0.22))
    add_text(slide, left + Inches(0.16), top + Inches(0.27), width - Inches(0.32), Inches(0.34),
             value, font_size=16, bold=True, color=value_color)
    add_text(slide, left + Inches(0.16), top + Inches(0.6), width - Inches(0.32), Inches(0.22),
             note, font_size=8, color=T_MUTED)


def add_metric_s(slide, left, top, width, height, label, value, note=None,
                 value_color=NAVY, value_size=15, label_size=8.5, note_size=7.5):
    """组内小指标卡：标签 / 数值 / 可选注脚，用于一页放多个分组的场景。"""
    add_rect(slide, left, top, width, height, fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(slide, left + Inches(0.14), top + Inches(0.05), width - Inches(0.28), Inches(0.2),
             label, font_size=label_size, bold=True, color=T_MUTED)
    add_text(slide, left + Inches(0.14), top + Inches(0.23), width - Inches(0.28), Inches(0.3),
             value, font_size=value_size, bold=True, color=value_color)
    if note:
        add_text(slide, left + Inches(0.14), top + height - Inches(0.22), width - Inches(0.28),
                 Inches(0.19), note, font_size=note_size, color=T_MUTED)


def add_flow(slide, left, top, width, steps, *, box_h=Inches(1.08), gap=Inches(0.3),
             head_size=10, body_size=8.2, accent=ACCENT, fill=CARD_BG, line=CARD_LINE):
    """横向流程链：等宽方块 + 中间的走向箭头。steps = [(编号, 小标题, 说明), ...]"""
    n = len(steps)
    bw = int((width - gap * (n - 1)) / n)
    x = left
    for i, (no, head, body) in enumerate(steps):
        add_rect(slide, x, top, bw, box_h, fill=fill, line_rgb=line)
        add_text(slide, x + Inches(0.13), top + Inches(0.06), bw - Inches(0.26), Inches(0.19),
                 no, font_size=8.5, bold=True, color=accent)
        add_text(slide, x + Inches(0.13), top + Inches(0.25), bw - Inches(0.26), Inches(0.22),
                 head, font_size=head_size, bold=True, color=NAVY)
        add_text(slide, x + Inches(0.13), top + Inches(0.51), bw - Inches(0.26),
                 box_h - Inches(0.57), body, font_size=body_size, color=T_BODY,
                 line_spacing=1.12)
        if i < n - 1:
            add_text(slide, x + bw, top + box_h // 2 - Inches(0.17), gap, Inches(0.34),
                     "▶", font_size=9.5, color=T_MUTED, align=PP_ALIGN.CENTER)
        x = x + bw + gap


def add_compare(slide, left, top, width, height, left_spec, right_spec, gap=Inches(0.19),
                head_size=12.5, item_size=9.5, row_h=Inches(0.32)):
    """左右对照卡。每侧 = (标题, 标题色, 底色, 边线, [条目], 结语, 结语色)。

    结语紧跟在条目之后排布，不贴卡片底边 —— 条目行数变化时不会压到结语上。
    """
    w = int((width - gap) / 2)
    for spec, x in ((left_spec, left), (right_spec, left + w + gap)):
        head, hc, fill, line, items, foot, fc = spec
        add_rect(slide, x, top, w, height, fill=fill, line_rgb=line)
        add_text(slide, x + Inches(0.22), top + Inches(0.1), w - Inches(0.44), Inches(0.28),
                 head, font_size=head_size, bold=True, color=hc)
        iy = top + Inches(0.48)
        for it in items:
            add_text(slide, x + Inches(0.24), iy, w - Inches(0.48), row_h,
                     "· " + it, font_size=item_size, color=T_BODY, line_spacing=1.16)
            iy = iy + row_h
        if foot:
            add_text(slide, x + Inches(0.24), iy + Inches(0.03), w - Inches(0.48),
                     Inches(0.3), foot, font_size=item_size, bold=True, color=fc)


def add_panel(slide, left, top, width, height, tag, tag_color, *, fill=PAGE_NORMAL,
              line=CARD_LINE, tag_h=Inches(0.3)):
    """带角标的区块容器：把「一条独立运行路径」框成一个整体。

    角标占 top+0.12 ~ top+0.42，区块内的小标题从 top+0.48 起排，避免压字。
    """
    add_rect(slide, left, top, width, height, fill=fill, line_rgb=line)
    add_pill(slide, left + Inches(0.17), top + Inches(0.12), tag,
             fill=tag_color, fg=T_WHITE, size=9, height=tag_h)


def add_node(slide, left, top, width, height, text, *, fill=CARD_BG, line=CARD_LINE,
             color=NAVY, size=10, bold=True):
    """流程节点：单行居中方块。"""
    add_rect(slide, left, top, width, height, fill=fill, line_rgb=line)
    add_text(slide, left + Inches(0.1), top, width - Inches(0.2), height, text,
             font_size=size, bold=bold, color=color, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)


def add_arrow(slide, left, top, width, height, glyph="↓", size=12, color=T_MUTED):
    add_text(slide, left, top, width, height, glyph, font_size=size, color=color,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def add_summary(slide, left, top, width, text, *, height=Inches(0.82), fill=CARD_BG2,
                line=ACCENT, color=NAVY, size=11, bold=True):
    """页底结论条：统一「这页要记住什么」的表达，不每页都用。"""
    add_rect(slide, left, top, width, height, fill=fill, line_rgb=line)
    add_text(slide, left + Inches(0.24), top + Inches(0.1), width - Inches(0.48),
             height - Inches(0.2), text, font_size=size, bold=bold, color=color,
             line_spacing=1.25)


# ==================== 页面 ====================
prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank = prs.slide_layouts[6]


# ----- 01 封面 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_COVER)
add_bar(s, M, Inches(0.84), Inches(0.46), Inches(0.07), ACCENT)
add_text(s, M, Inches(0.96), Inches(6), Inches(0.32),
         "2026 毕业设计答辩", font_size=12.5, bold=True, color=ACCENT)
add_text(s, M, Inches(1.58), Inches(11), Inches(1.12),
         "StudyPath", font_size=52, bold=True, color=T_TITLE)
add_text(s, M, Inches(2.66), Inches(11), Inches(0.56),
         "基于大模型的留学申请规划助手", font_size=21, color=NAVY)
add_text(s, M, Inches(3.22), Inches(11.6), Inches(0.36),
         "从申请者画像，到选校建议、申请规划与可追溯的信息支持",
         font_size=13.5, color=T_MUTED)

# 封面只留四项业务能力，技术名下沉到底部，避免与项目定位争夺视觉层级。
caps = ["可信知识检索", "多角色协作", "领域适配实验", "工作流自动化"]
x = M
for t in caps:
    _, w = add_pill(s, x, Inches(3.84), t, size=11.5)
    x = x + w + Inches(0.18)

add_rect(s, M, Inches(4.48), CW, Inches(1.18), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.26), Inches(4.6), CW - Inches(0.52), Inches(0.28),
         "项目定位", font_size=11.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.26), Inches(4.92), CW - Inches(0.52), Inches(0.66),
         "面向留学申请场景的规划助手：以 180 条真实可溯源数据为底座，用检索增强保证事实可信，"
         "再由三个领域角色分域推理后汇总成一份可执行的申请规划；每条事实都可点开原始来源核对。",
         font_size=12, color=T_BODY)

add_rect(s, M, Inches(5.84), CW, Inches(0.6), fill=CARD_BG2, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.26), Inches(5.96), CW - Inches(0.52), Inches(0.36),
         "技术栈：LangChain · LangGraph · Chroma · LoRA（低秩适配） · Dify · N8N",
         font_size=10.5, color=T_MUTED)


# ----- 02 背景与痛点（工作流对比）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "背景与痛点", "留学申请的信息准备，本身就是一道需要反复人工核对的工作流")
add_footer(s, 2)

add_text(s, M, Inches(1.66), Inches(8), Inches(0.26),
         "现在的做法：信息准备全靠人工串联", font_size=11.5, bold=True, color=T_TITLE)
add_flow(s, M, Inches(1.96), CW, [
    ("现状 01", "搜索官网", "逐个院校站、论坛与中介页面翻找要求"),
    ("现状 02", "整理字段", "手工摘录 GPA、语言、DDL 到自己的表格"),
    ("现状 03", "比较院校", "按主观印象排梯度，缺少同背景案例参照"),
    ("现状 04", "核对来源", "回头确认每条数字出自哪一页、是否最新"),
], box_h=Inches(1.0), body_size=8)

add_rect(s, M, Inches(3.06), CW, Inches(0.52), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.24), Inches(3.15), CW - Inches(0.48), Inches(0.36),
         "障碍：信息分散且口径不一 · 来源核对成本高 · 时效性易过期",
         font_size=11, bold=True, color=AMBER)

add_text(s, M, Inches(3.74), Inches(9), Inches(0.26),
         "本项目：把可复用的结构化数据与规划能力接进同一条链", font_size=11.5, bold=True,
         color=T_TITLE)
add_flow(s, M, Inches(4.04), CW, [
    ("StudyPath 01", "输入画像", "一句话描述背景，转成结构化画像字段"),
    ("StudyPath 02", "检索匹配", "从 180 条真实记录里召回相关院校与案例"),
    ("StudyPath 03", "生成规划", "三个角色分域推理后汇总成一份申请规划"),
    ("StudyPath 04", "查看出处", "每条事实可点开原始来源逐条核对"),
], box_h=Inches(1.0), body_size=8, accent=TEAL)

add_rect(s, M, Inches(5.12), CW, Inches(0.52), fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + Inches(0.24), Inches(5.21), CW - Inches(0.48), Inches(0.36),
         "目标：把「分散、难核对、易过期」三个障碍，收敛成一条可复用、可更新的信息链路",
         font_size=11, bold=True, color=TEAL)

add_summary(s, M, Inches(5.78), CW, [
    "三个障碍指向同一个技术选择：把事实从模型参数里拿出来，放进可检索、可更新、可追溯的知识库 —— "
    "分散的信息要归一，核对要有低成本出处，过期的信息要能低成本更新。",
    "下排为本项目已实现的能力；知识库规模与覆盖范围在第 3 页如实列出，未实现的环节不在此列出。",
], height=Inches(0.92), size=10.5)


# ----- 03 项目目标与范围 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "项目目标与范围", "一套可运行的产品能力 · 一组独立的技术实验 · 一条说清楚的边界")
add_footer(s, 3)

add_rect(s, M, Inches(1.66), CW, Inches(0.98), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.26), Inches(1.78), CW - Inches(0.52), Inches(0.76),
         "做一个端到端完成留学申请规划的助手：把自然语言画像结构化，用真实数据检索出选校依据，"
         "再由多个领域角色分域推理，汇总成一份可执行的申请规划；每条事实均可点开原始来源核对。",
         font_size=12, color=NAVY, bold=True, line_spacing=1.3)

caps3 = [
    ("产品能力 · 用户可感知", ACCENT, CARD_BG, CARD_LINE, [
        "Profile 抽取：自然语言 → 结构化画像",
        "知识检索：180 条真实数据，附来源",
        "申请规划：五阶段可执行规划",
        "多轮对话：会话内指代消解",
        "来源展示：可点开原始页面",
        "工作流推送：表单 → AI → 飞书",
    ]),
    ("技术实验 · 研究性验证", TEAL, EVID_BG, EVID_LINE, [
        "LoRA 领域适配：表达范式迁移",
        "检索指标测试：HitRate / MRR",
        "并行性能对比：worker 段 A/B",
        "能力边界核查：事实层 vs 表达层",
        "A/B 受控对照：唯一变量切 adapter",
    ]),
    ("当前边界 · 如实收窄", AMBER, WARNBG, WARNLINE, [
        "知识库 180 条离线快照，非全量院校库",
        "未实现实时增量采集",
        "微调模型不独立承担事实回答",
        "跨会话长期记忆有意不启用",
    ]),
]
cw3 = Inches(3.83)
cx = M
for head, hc, fc, lc, items in caps3:
    add_rect(s, cx, Inches(2.78), cw3, Inches(3.44), fill=fc, line_rgb=lc)
    add_text(s, cx + Inches(0.22), Inches(2.9), cw3 - Inches(0.44), Inches(0.28),
             head, font_size=12, bold=True, color=hc)
    iy = Inches(3.32)
    for it in items:
        add_text(s, cx + Inches(0.22), iy, cw3 - Inches(0.44), Inches(0.46),
                 "· " + it, font_size=9.5, color=T_BODY, line_spacing=1.2)
        iy = iy + Inches(0.55)
    cx = cx + cw3 + Inches(0.2)

add_summary(s, M, Inches(6.34), CW,
            "产品能力与技术实验分开陈列：主链路的回答由检索层与 qwen-plus 生成，"
            "LoRA 是离线实验模块，不参与线上推理 —— 两者的验收标准互不冒充。",
            height=Inches(0.52), size=10.5)


# ----- 04 系统总体架构（两条运行路径 + 一个离线实验）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "系统总体架构", "两条独立运行路径 + 一个离线实验模块 —— 不是被箭头硬串起来的一个大系统")
add_footer(s, 4)

main_w = Inches(6.95)
rx = M + main_w + Inches(0.26)
rw = CW - main_w - Inches(0.26)

# 左：主链路
add_panel(s, M, Inches(1.62), main_w, Inches(2.62), "主研究链路", ACCENT)
add_text(s, M + Inches(0.22), Inches(2.1), main_w - Inches(0.44), Inches(0.26),
         "本地留学规划助手（Gradio · localhost:7860）", font_size=10.5, bold=True, color=NAVY)
nl = main_w - Inches(1.4)
nx = M + Inches(0.7)
for i, t in enumerate(["用户问题 / 画像", "Chroma + MMR 检索真实数据",
                       "LangGraph 三角色协作与汇总", "Gradio 展示回答与来源"]):
    add_node(s, nx, Inches(2.4) + Inches(0.47) * i, nl, Inches(0.38), t,
             fill=CARD_BG2 if i in (0, 3) else CARD_BG, size=9.5)
    if i < 3:
        add_arrow(s, nx, Inches(2.78) + Inches(0.47) * i, nl, Inches(0.09), "↓", 9)

# 左：自动化链路
add_panel(s, M, Inches(4.36), main_w, Inches(1.96), "自动化应用链路", TEAL)
add_text(s, M + Inches(0.22), Inches(4.84), main_w - Inches(0.44), Inches(0.26),
         "Dify + N8N 工作流（与主链路各自独立运行）", font_size=10.5, bold=True, color=NAVY)
nx2 = M + Inches(0.7)
nl2 = main_w - Inches(1.4)
for i, t in enumerate(["表单输入", "Dify 三路知识库检索与生成", "N8N 推送至飞书"]):
    add_node(s, nx2, Inches(5.12) + Inches(0.40) * i, nl2, Inches(0.34), t,
             fill=EVID_BG if i == 2 else CARD_BG, size=9.5,
             color=TEAL if i == 2 else NAVY)
    if i < 2:
        add_arrow(s, nx2, Inches(5.46) + Inches(0.40) * i, nl2, Inches(0.06), "↓", 9)

# 右：离线实验
add_panel(s, rx, Inches(1.62), rw, Inches(4.70), "独立模型适配实验", AMBER, fill=PAGE_NORMAL)
add_text(s, rx + Inches(0.22), Inches(2.1), rw - Inches(0.44), Inches(0.3),
         "Qwen2.5-7B-Instruct + LoRA", font_size=11, bold=True, color=NAVY)
add_text(s, rx + Inches(0.22), Inches(2.42), rw - Inches(0.44), Inches(0.44),
         "离线开展，不参与主链路的线上推理", font_size=9.5, color=T_MUTED,
         line_spacing=1.2)
for i, (h, b) in enumerate([
    ("训练", "LoRA 领域适配，产出的 adapter 独立落盘"),
    ("A/B 受控对照", "同一 prompt 只切换 adapter，观察输出行为变化"),
    ("能力边界核查", "URL 逐字溯源 / 排名一致性 / 表达层迁移"),
]):
    y = Inches(2.88) + Inches(0.98) * i
    add_rect(s, rx + Inches(0.22), y, rw - Inches(0.44), Inches(0.86),
             fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, rx + Inches(0.38), y + Inches(0.09), rw - Inches(0.76), Inches(0.24),
             h, font_size=10, bold=True, color=AMBER)
    add_text(s, rx + Inches(0.38), y + Inches(0.36), rw - Inches(0.76), Inches(0.44),
             b, font_size=8.5, color=T_BODY, line_spacing=1.18)

add_summary(s, M, Inches(6.42), CW,
            "图为逻辑示意：主链路与自动化链路各自独立跑通，LoRA 为离线实验模块 —— "
            "上图三条路径之间没有隐藏的调用关系，不靠一条装饰性箭头假装贯通。",
            height=Inches(0.5), size=10, fill=CARD_BG, line=CARD_LINE, color=T_BODY, bold=False)


# ----- 05 用户输入理解：Profile 抽取 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "用户输入理解：Profile 抽取", "用户只写一句话，系统把它转成结构化画像 —— 无表单可填、无信息不硬编、估算值单独标记")
add_footer(s, 5)

add_image_fit(s, ASSETS / "profile_snapshot.png", M, Inches(1.52), CW, Inches(3.45))

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


# ----- 06 可追溯数据底座（含标注体系）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "可追溯数据底座", "180 条真实记录 · 每条带 source_url · 5 个标注维度把自由文本变成可用资产")
add_footer(s, 6)

bars = [("院校项目库  100 条", 100, NAVY), ("录取案例库  50 条", 50, ACCENT),
        ("文书范例库  30 条", 30, TEAL)]
bx = M
for label, cnt, col in bars:
    w = int(CW * cnt / 180)
    add_bar(s, bx, Inches(1.68), w, Inches(0.56), col)
    add_text(s, bx, Inches(1.81), w, Inches(0.3), label, font_size=11.5, bold=True,
             color=T_WHITE, align=PP_ALIGN.CENTER)
    bx = bx + w

libs = [
    ("院校项目库 · 100 条",
     "排名、项目时长、学费、语言要求、截止日期、先修课要求。选校类问题的事实依据全部来自这里。"),
    ("录取案例库 · 50 条",
     "真实录取与拒录案例：申请人背景、申请结果、去向院校。用于校准「这个背景够不够」，而不是凭模型印象给结论。"),
    ("文书范例库 · 30 条",
     "SOP / PS / CV / 推荐信范例：结构拆解与写作要点。未命中时会明确标注「未检索到同方向范文」。"),
]
lw3 = Inches(3.83)
lx = M
for head, body in libs:
    add_card(s, lx, Inches(2.36), lw3, Inches(1.28), head=head, body=body,
             head_size=11, body_size=9)
    lx = lx + lw3 + Inches(0.2)

half = Inches(5.85)
add_rect(s, M, Inches(3.76), half, Inches(1.32), fill=CARD_BG2, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(3.86), half - Inches(0.48), Inches(0.26),
         "每条记录的字段结构（annotated_dataset.jsonl）", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(4.16), half - Inches(0.48), Inches(0.84),
         '{ "id": "case_001",  "source_lib": "录取案例库",  "text": "<正文>",\n'
         '  "label_dimension": "申请结果",  "label": "Admit",\n'
         '  "source_url": "https://<原始页面地址>"     # 可点击外跳，逐条反查 }',
         font_size=9.5, color=NAVY, font=MONO, line_spacing=1.28)

add_rect(s, M + half + Inches(0.19), Inches(3.76), half, Inches(1.32),
         fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + half + Inches(0.43), Inches(3.86), half - Inches(0.48), Inches(0.26),
         "5 个标注维度（由真实字段解析，不做推断）", font_size=10.5, bold=True, color=TEAL)
add_text(s, M + half + Inches(0.43), Inches(4.16), half - Inches(0.48), Inches(0.86),
         "申请结果 → Admit / Reject　·　排名档 → 冲 / 稳 / 保　·　文书类型 → SOP / PS / CV / LOR\n"
         "文书质量 → 优 / 良 / 中　·　院校国家 → 10 个国家 / 地区\n"
         "解析不出的一律标 Unknown：排名档因此有 25 条未评级，而不是猜一个档位。",
         font_size=9, color=T_BODY, line_spacing=1.22)

add_rect(s, M, Inches(5.18), CW, Inches(0.82), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(5.3), CW - Inches(0.48), Inches(0.6),
         "数据铁律：180 条全部来自院校官网、QS / USNews、公开案例页与论坛的真实内容，每条带 source_url，"
         "不混入样本数据、不虚构字段。source_url 不是装饰字段 —— 来源卡片直接由它渲染，点开即可回到原始页面复核。",
         font_size=10, color=NAVY, line_spacing=1.24)

add_text(s, M, Inches(6.14), CW, Inches(0.44),
         "口径说明：50 条录取案例中 Admit 49 / Reject 1，是原始采集样本的实际分布，不代表整体录取概率，"
         "也不作为标签区分度的依据。",
         font_size=9, color=T_MUTED)


# ----- 07 为什么用 RAG：从原理到链路 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "为什么用检索增强（RAG）", "通用大模型能生成通顺的答案，但生成不了可核对的答案 —— 事实必须来自可检索、可更新的外部数据")
add_footer(s, 7)

add_compare(s, M, Inches(1.66), CW, Inches(2.14),
            ("✗ 纯 LLM 直答", RED, CARD_BG, CARD_LINE, [
                "输出流畅，但没有任何来源标注",
                "分不清哪句是事实、哪句是模型补全",
                "院校要求变更，模型参数不会跟着变",
                "同一问题多问几次，给出的数字可能不一致",
            ], "→ 可用于闲聊，不能用于高风险决策", RED),
            ("✓ 检索增强（RAG）", TEAL, EVID_BG, EVID_LINE, [
                "回答中的事实来自检索到的原始记录",
                "每条资料带 source_url，可点开原始页面复核",
                "更新知识库即可同步最新要求，不必重训模型",
                "召回结果与答案并排展示，依据可当场验证",
            ], "→ 结论可验证、可追溯、可更新", TEAL))

add_text(s, M, Inches(3.9), Inches(8), Inches(0.26),
         "实现链路：从官方数据到带来源的答案", font_size=11.5, bold=True, color=T_TITLE)
add_flow(s, M, Inches(4.18), CW, [
    ("01", "官方数据采集", "院校官网 / QS / USNews / 公开案例页与论坛"),
    ("02", "清洗与标签归一化", "多源原始页 → 统一字段表（按库定义 schema）"),
    ("03", "拼装为文档", "字段拼成自然语言正文 + 关键字段存 metadata"),
    ("04", "向量化入库", "text-embedding-v3（1024 维）→ Chroma 本地库 180 条"),
    ("05", "MMR 检索", "最大边际相关性检索，k=8 / fetch_k=20"),
    ("06", "生成附来源", "qwen-plus 基于召回资料作答，标注 [资料N]"),
], box_h=Inches(1.2), gap=Inches(0.26), body_size=7.6)

add_summary(s, M, Inches(5.54), CW,
            "本项目的路线是：让模型只负责把检索到的事实组织成可读的规划，事实本身一律由检索层提供并附上出处 —— "
            "模型不承担它本来就不可靠的记忆职责。",
            height=Inches(0.74), size=11)

add_text(s, M, Inches(6.4), CW, Inches(0.44),
         "一条记录 = 一个 Document = 一条向量；数据为离线采集快照，更新时重跑采集与向量化即可，不必重训模型。"
         "切分器配置与查询侧归一化的细节见附录 A4。",
         font_size=9, color=T_MUTED, line_spacing=1.2)


# ----- 08 RAG 效果证据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "RAG 效果证据", "真实运行记录：左侧为答案，右侧为本次召回的 Top-8 原始资料 —— 答案与依据并排，可当场验证")
add_footer(s, 8)

add_image_fit(s, ASSETS / "rag_demo.png", M, Inches(1.68), Inches(5.3), Inches(4.7))

evx = M + Inches(5.52)
evw = CW - Inches(5.52)
add_evidence_v(s, evx, Inches(1.68), evw, [
    ("答案与资料并排", "回答与本次召回的原始资料左右对照展示，"
     "「答案来自资料」这句话可以当场验证，而不是口头声明。"),
    ("Top-8 每条带库标签", "每条命中都标注来源库（院校 / 案例 / 文书），"
     "证明三个库是分别检索的，不是把整个向量库混在一起查。"),
    ("source_url 可外跳", "底部来源卡片由真实 source_url 渲染，点开回到原始页面 —— "
     "可溯源最终落在可点击的链接上。"),
])

add_summary(s, M, Inches(6.52), CW,
            "截图来源：rag_demo_capture.json（真实运行记录）→ rag/build_demo_panel.py 渲染，非手工绘制。",
            height=Inches(0.52), size=10)


# ----- 09 多智能体协作设计 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "多智能体协作设计", "三个库的关注点不同、三个角色的分析框架不同 —— 所以拆成三个 worker 并行检索后再统一汇总")
add_footer(s, 9)

lw = Inches(6.95)
rx = M + lw + Inches(0.26)
rw = CW - lw - Inches(0.26)

# 左：拓扑
add_node(s, M + Inches(1.6), Inches(1.66), Inches(3.6), Inches(0.38),
         "用户问题（已做入口查询改写）", fill=CARD_BG2, size=10)
add_arrow(s, M + Inches(1.6), Inches(2.04), Inches(3.6), Inches(0.16), "↓", 10)
add_node(s, M + Inches(1.6), Inches(2.2), Inches(3.6), Inches(0.46),
         "supervisor · 判断本轮该查哪几个库", fill=CARD_BG2, size=10)

# 分叉
add_text(s, M + Inches(1.6), Inches(2.66), Inches(3.6), Inches(0.18),
         "三路分派（同一 superstep 并发执行）", font_size=8, color=T_MUTED,
         align=PP_ALIGN.CENTER)
add_node(s, M + Inches(0.05), Inches(2.88), Inches(2.3), Inches(0.62),
         "worker_school\n院校项目库", fill=CARD_BG, size=9)
add_node(s, M + Inches(2.45), Inches(2.88), Inches(2.3), Inches(0.62),
         "worker_admission\n录取案例库", fill=CARD_BG, size=9)
add_node(s, M + Inches(4.85), Inches(2.88), Inches(2.05), Inches(0.62),
         "worker_essay\n文书范例库", fill=CARD_BG, size=9)

add_arrow(s, M + Inches(1.6), Inches(3.5), Inches(3.6), Inches(0.16), "↓", 10)
add_node(s, M + Inches(1.6), Inches(3.66), Inches(3.6), Inches(0.46),
         "synthesizer · 合并去重 + 统一 [资料N] 编号", fill=EVID_BG, size=10, color=TEAL)
add_arrow(s, M + Inches(1.6), Inches(4.12), Inches(3.6), Inches(0.16), "↓", 10)
add_node(s, M + Inches(1.6), Inches(4.28), Inches(3.6), Inches(0.4),
         "带来源的结构化申请规划", fill=CARD_BG2, size=10)

add_rect(s, M, Inches(4.86), lw, Inches(1.62), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(4.96), lw - Inches(0.44), Inches(0.26),
         "并行是真的，不是画出来的", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.22), Inches(5.26), lw - Inches(0.44), Inches(1.1),
         "三个 worker 挂在 supervisor 的同一条出边上，按 Pregel 语义属于同一个 superstep，"
         "并发执行、全部结束后才汇合到 synthesizer；全图 7 个节点 / 8 条边，全部用 add_edge 直连，"
         "没有 conditional_edges。\n"
         "同条件 A/B（并行图 / 串行图跑同一条 query）只比较三个 worker 段的执行耗时："
         "139.88 秒 → 46.99 秒，约 2.98 倍。端到端耗时由生成长度支配，不作为工程指标。",
         font_size=8.6, color=T_BODY, line_spacing=1.24)

# 右：worker 明细
add_text(s, rx, Inches(1.66), rw, Inches(0.26),
         "每个 worker 的数据源与输出", font_size=11, bold=True, color=T_TITLE)
wk = [
    ("worker_school", "院校项目库 · 100 条", "选校策略：冲 / 稳 / 保 梯度组合", NAVY),
    ("worker_admission", "录取案例库 · 50 条", "录取风险评估：定位与短板", ACCENT),
    ("worker_essay", "文书范例库 · 30 条", "文书结构与写作大纲", TEAL),
]
for i, (name, src, out, col) in enumerate(wk):
    y = Inches(2.0) + Inches(1.06) * i
    add_rect(s, rx, y, rw, Inches(0.94), fill=CARD_BG, line_rgb=CARD_LINE)
    add_bar(s, rx, y, Inches(0.05), Inches(0.94), col)
    add_text(s, rx + Inches(0.2), y + Inches(0.08), rw - Inches(0.4), Inches(0.24),
             name, font_size=10.5, bold=True, color=col)
    add_text(s, rx + Inches(0.2), y + Inches(0.36), rw - Inches(0.4), Inches(0.24),
             "数据源：" + src, font_size=8.8, color=T_BODY)
    add_text(s, rx + Inches(0.2), y + Inches(0.6), rw - Inches(0.4), Inches(0.24),
             "输出：" + out, font_size=8.8, color=T_BODY)

add_rect(s, rx, Inches(5.2), rw, Inches(1.28), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, rx + Inches(0.2), Inches(5.3), rw - Inches(0.4), Inches(0.26),
         "为什么不用单 Agent", font_size=10.5, bold=True, color=AMBER)
add_text(s, rx + Inches(0.2), Inches(5.58), rw - Inches(0.4), Inches(0.84),
         "① 三个库要分别检索，混检会稀释相关性；\n"
         "② 三个角色的分析框架不同，一个 prompt 只能取交集；\n"
         "③ 三路召回必须统一编号，才能与 [资料N] 对上。",
         font_size=8.6, color=T_BODY, line_spacing=1.22)


# ----- 10 多智能体运行效果证据 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "多智能体运行效果证据", "真实运行截图：三个角色分别检索与推理后，汇总成一份可执行的申请规划")
add_footer(s, 10)

add_image_fit(s, ASSETS / "Gradio本地Demo.png", M, Inches(1.72), Inches(7.3), Inches(4.02))

add_evidence_v(s, M + Inches(7.5), Inches(1.72), Inches(4.39), [
    ("引用编号全局一致", "答案里的 [资料N] 与底部来源卡片一一对应 —— "
     "证明三个 worker 的召回做了合并去重后统一编号，不是各写各的。"),
    ("五阶段结构化输出", "选校定稿 → 材料准备 → 文书写作 → 网申提交 → 面试准备，"
     "说明 synthesizer 确实在整合三份角色结论，而不是一次生成。"),
    ("本地可复现", "顶栏为 localhost:7860 本地实例，评委现场即可复跑同一问题验证。"),
], item_h=Inches(1.5), gap=Inches(0.16))

add_summary(s, M, Inches(5.84), CW,
            "图中第二轮的连续追问（「那第一个的截止日期和学费呢」）正确落到了上一轮推荐的院校 —— "
            "这依赖 LangGraph checkpointer 保存的跨轮 state 与入口处的查询改写，而不是靠模型猜上下文。",
            height=Inches(0.86), size=10.5)


# ----- 11 自动化闭环：Dify + N8N -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "自动化闭环：Dify + N8N", "回答不能只停在聊天窗口 —— 从表单输入到飞书推送，端到端无人值守")
add_footer(s, 11)

iw = [Inches(4.02), Inches(3.72), Inches(3.42)]
ix = M
shots = [
    ("N8N工作流全景.png", "N8N 工作流：表单触发 → 调 Dify API → 提取字段 → 推送"),
    ("Dify-Chatflow编排.png", "Dify Chatflow：三路知识库并联检索后生成"),
    ("飞书群推送消息.png", "飞书群实时收到完整回答"),
]
for i, (fn, cap) in enumerate(shots):
    add_image_fit(s, ASSETS / fn, ix, Inches(1.68), iw[i], Inches(3.2),
                  caption=cap, cap_size=8.5)
    if i < 2:
        add_arrow(s, ix + iw[i], Inches(2.9), Inches(0.35), Inches(0.4), "▶", 11)
    ix = ix + iw[i] + Inches(0.35)

add_evidence(s, M, Inches(5.12), CW, [
    ("输入如何触发流程", "Form Trigger 收集问题，HTTP Request 以 POST 调用 Dify API —— "
     "整条链的起点是一次表单提交，不需要人守在页面前。"),
    ("Dify 如何处理并返回", "Dify 侧是三个知识库并联检索后再由 qwen-plus 生成，"
     "检索环节真实存在于这条自动化链路里，不是把问题直接丢给大模型。"),
    ("N8N 如何推送结果", "提取 answer 字段后推送至飞书群 —— 群里收到的是完整回答正文，"
     "而不是一条链接或「有新消息」的提示。"),
], height=Inches(1.12))

add_summary(s, M, Inches(6.4), CW,
            "这条链路与本地主链路各自独立运行：线上 Dify 承担推理，本地只负责编排与推送，"
            "换台机器改 webhook 即可复用。工程异常处理细节见附录 A5。",
            height=Inches(0.5), size=10)


# ----- 12 领域适配：为什么做与怎么做 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "领域适配：让输出像顾问，而不是像通用模型", "LoRA（低秩适配）只调整表达范式 —— 不承担事实记忆")
add_footer(s, 12)

add_image_fit(s, ASSETS / "training_loss.png", M, Inches(1.68), Inches(5.4), Inches(3.3))

cfx = M + Inches(5.62)
cfw = CW - Inches(5.62)
cards = [
    ("通用基座的缺口", WARNBG, WARNLINE, AMBER,
     "语体偏通用说明文，不像顾问给学生的建议；结构松散，缺少可执行的分阶段组织；不主动标注来源。"),
    ("适配目标", EVID_BG, EVID_LINE, TEAL,
     "习得「结构化输出 + 主动附来源」的表达范式，让输出形态贴近顾问的工作文档。"),
    ("为什么选 LoRA 而非全参微调", CARD_BG, CARD_LINE, NAVY,
     "本机显存不足以承载 7B 全参训练；目标只是表达范式而非事实注入。可训练参数 504.6 万，占基座 0.066%，基座权重冻结。"),
    ("训练配置", CARD_BG, CARD_LINE, NAVY,
     "Qwen2.5-7B-Instruct · rank 8 / alpha 16 / dropout 0.05，注入 q/k/v/o · lr 2e-4 · 3 epoch · batch1×accum8 · bf16 · AutoDL 单卡 RTX 3090。"),
]
for i, (h, fc, lc, hc, b) in enumerate(cards):
    y = Inches(1.68) + Inches(0.86) * i
    add_rect(s, cfx, y, cfw, Inches(0.79), fill=fc, line_rgb=lc)
    add_text(s, cfx + Inches(0.18), y + Inches(0.06), cfw - Inches(0.36), Inches(0.22),
             h, font_size=9.5, bold=True, color=hc)
    add_text(s, cfx + Inches(0.18), y + Inches(0.28), cfw - Inches(0.36), Inches(0.46),
             b, font_size=8.2, color=T_BODY, line_spacing=1.14)

add_rect(s, M, Inches(5.14), CW, Inches(1.0), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.24), CW - Inches(0.48), Inches(0.26),
         "数据流向（三组数字的关系）", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(5.52), CW - Inches(0.48), Inches(0.56),
         "180 条采集数据 → 8:2 划分（固定随机种子）→ 144 条训练 / 36 条留出 → 训练侧在 144 条内按 val_size=0.1 再切出 "
         "15 条作验证监控、129 条参与训练。36 条留出集全程不参与训练与调参，生成质量与事实核查的 20 条样本取自这一部分；"
         "A/B 对照用的是另拟的 3 组业务 prompt，与数据划分无关。",
         font_size=9, color=T_BODY, line_spacing=1.24)

add_text(s, M, Inches(6.28), CW, Inches(0.48),
         "曲线只说明训练正常跑通（train_loss 与 eval_loss 同步下降、未见回弹，51 步内完成 3 个 epoch）—— "
         "学得像不等于事实正确，结论由后两页的实验给出。",
         font_size=9, color=T_MUTED, line_spacing=1.2)


# ----- 13 实验①：LoRA 是否改变了输出行为 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "实验①：LoRA 是否改变了输出行为", "同一 prompt、同一解码策略，唯一变量是「是否挂载 LoRA adapter」")
add_footer(s, 13)

add_rect(s, M, Inches(1.66), CW, Inches(0.84), fill=CARD_BG2, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(1.74), CW - Inches(0.48), Inches(0.26),
         "实验条件（受控变量）", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(0.24), Inches(2.0), CW - Inches(0.48), Inches(0.44),
         "Prompt：你是一名留学文书顾问，请为申请纽约大学 MS Data Science 的学生写一段 SOP 开头，不超过 150 字。\n"
         "解码 greedy（do_sample=False）｜唯一变量 = 是否挂载 LoRA adapter（19.3 MB）｜A 组通过 disable_adapter() 切回纯净基座",
         font_size=9, color=T_BODY, line_spacing=1.25)

A_CARD = RGBColor(0xF7, 0xF7, 0xFA)
B_CARD = RGBColor(0xEC, 0xF7, 0xF1)
add_rect(s, M, Inches(2.6), Inches(5.85), Inches(2.44), fill=A_CARD, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(2.7), Inches(5.41), Inches(0.28),
         "A · 纯基座（未微调）", font_size=12, bold=True, color=T_MUTED)
add_text(s, M + Inches(0.22), Inches(3.02), Inches(5.41), Inches(1.5),
         "在数字化浪潮席卷全球的今天，数据科学作为连接现实世界与数字世界的桥梁，正以前所未有的速度"
         "改变着我们的生活方式、工作模式乃至思维方式。作为一名热衷于探索数据背后故事的学子，我深知"
         "数据科学不仅是一门学科，更是一种工具……因此，当我在众多顶尖学府中选择纽约大学时，"
         "被其在数据科学领域的卓越成就和深厚底蕴深深吸引。",
         font_size=9.5, color=RGBColor(0x6E, 0x76, 0x8C), line_spacing=1.22)
add_text(s, M + Inches(0.22), Inches(4.56), Inches(5.41), Inches(0.4),
         "✗ 通用陈述式长句：通篇宏观议论，没有任何个人背景事实，语气与「通用 AI 作文」无异。",
         font_size=9, bold=True, color=RED)

add_rect(s, M + Inches(6.04), Inches(2.6), Inches(5.85), Inches(2.44),
         fill=B_CARD, line_rgb=OKLINE)
add_text(s, M + Inches(6.26), Inches(2.7), Inches(5.41), Inches(0.28),
         "B · 基座 + LoRA（微调后）", font_size=12, bold=True, color=TEAL)
add_text(s, M + Inches(6.26), Inches(3.02), Inches(5.41), Inches(1.5),
         "我自小就对数据科学充满兴趣，高中时便开始自学 Python 和 R 语言。本科期间，我主修数学与统计学，"
         "并辅修计算机科学。这段经历不仅让我掌握了扎实的理论基础，还培养了我解决实际问题的能力。"
         "如今，我渴望在纽约大学继续深造，成为数据科学领域的顶尖人才。",
         font_size=10, color=RGBColor(0x2A, 0x4A, 0x3E), line_spacing=1.24)
add_text(s, M + Inches(6.26), Inches(4.56), Inches(5.41), Inches(0.4),
         "✓ 第一人称文书语体：由宏观议论转为分点陈述，语体与结构发生权重层迁移。"
         "⚠ 其中个人背景是模型自行补全的，prompt 并未给出 —— 见下页核查。",
         font_size=9, bold=True, color=TEAL)

add_rect(s, M, Inches(5.14), CW, Inches(0.86), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(5.24), CW - Inches(0.48), Inches(0.68),
         "结论：在相同提示词与解码设置下，挂载 LoRA 后的输出表现出更明显的第一人称文书语体和结构变化。"
         "但在缺少用户背景信息时，模型仍可能补全未经提供的个人经历 —— 表达风格改善不等于事实可靠性改善。",
         font_size=10, bold=True, color=TEAL, line_spacing=1.24)

for i, (label, val, note) in enumerate([
    ("损失下降", "1.2952 → 0.7597", "train → eval"),
    ("训练步数", "51 steps", "3 epoch"),
    ("纯训练耗时", "106.8 秒", "单卡 3090"),
    ("Adapter 体积", "19.3 MB", "基座冻结"),
]):
    add_metric_s(s, M + (Inches(2.845) + Inches(0.17)) * i, Inches(6.12), Inches(2.845),
                 Inches(0.66), label, val, note, value_size=11, label_size=8)
cleanup_note = "以上为训练产物文件中的工程信息"


# ----- 14 实验②：能力边界核查 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "实验②：能力边界核查",
          "微调让表达更像专家，但不等于事实更可靠 —— 这条结论决定了「检索管事实、微调管表达」的分工")
add_footer(s, 14)

checks = [
    ("来源链接逐字溯源", "0 / 20", AMBER,
     "20 条生成文本都主动附了来源 URL，\n但逐字命中知识库真实 URL 的为 0 条 ——\n链接是模型生成的，不可直接采信。"),
    ("排名数字一致性", "0 / 7", AMBER,
     "含排名数字的 7 条样本，\n与知识库参考文本全部不一致 ——\n事实数值没有被参数记住。"),
    ("表达层迁移有效性", "3 / 3", TEAL,
     "三类业务任务的 A/B 输出均发生\n权重层变化：语体、结构、\n主动附来源的习惯可迁移。"),
]
cwid3 = Inches(3.83)
cx = M
for name, val, col, note in checks:
    add_rect(s, cx, Inches(1.8), cwid3, Inches(1.74), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, cx + Inches(0.22), Inches(1.9), cwid3 - Inches(0.44), Inches(0.26),
             name, font_size=10.5, bold=True, color=NAVY)
    add_text(s, cx + Inches(0.22), Inches(2.18), cwid3 - Inches(0.44), Inches(0.52),
             val, font_size=24, bold=True, color=col)
    add_text(s, cx + Inches(0.22), Inches(2.66), cwid3 - Inches(0.44), Inches(0.82),
             note, font_size=8.4, color=T_BODY, line_spacing=1.2)
    cx = cx + cwid3 + Inches(0.2)

add_compare(s, M, Inches(3.66), CW, Inches(1.9),
            ("LoRA 负责", TEAL, EVID_BG, EVID_LINE, [
                "领域表达风格：像顾问而不是像通用模型",
                "输出结构与组织方式：分阶段、可执行",
                "特定任务的表达习惯：主动附来源",
            ], "→ 表达层：风格与结构可迁移", TEAL),
            ("RAG 负责", NAVY, CARD_BG2, CARD_LINE, [
                "检索实际数据：事实来自知识库原文",
                "提供真实来源链接：可点击外跳复核",
                "支持事实核对与更新：改库不必重训",
            ], "→ 事实层：数值与链接必须来自检索", NAVY),
            row_h=Inches(0.34), head_size=11.5, item_size=9)

add_rect(s, M, Inches(5.68), CW, Inches(1.32), fill=OKBG, line_rgb=OKLINE)
add_text(s, M + Inches(0.24), Inches(5.78), CW - Inches(0.48), Inches(0.44),
         "设计原则：实验表明，微调后的模型仍可能生成无法追溯的链接与不一致的数字。"
         "因此本项目不把模型参数作为事实依据，而由检索层提供事实证据，并要求最终回答与检索资料保持一致。",
         font_size=10, bold=True, color=TEAL, line_spacing=1.22)
add_text(s, M + Inches(0.24), Inches(6.26), CW - Inches(0.48), Inches(0.26),
         "边界声明：当前系统的字段一致性核查为抽样核验（3 条），尚未实现逐项自动事实校验。",
         font_size=8.6, color=T_MUTED)
add_text(s, M + Inches(0.24), Inches(6.54), CW - Inches(0.48), Inches(0.4),
         "工程落地：实验①得到的表达范式已蒸馏为 prompt 规则，固化进主链三段（单链检索 / 3 个 worker / 整合器）；"
         "同条件 A/B 实测 —— 客服式敬语「您」单链 22 → 0、录取 worker 38 → 0，宏观铺垫式开场同步清零。",
         font_size=8.6, color=TEAL, line_spacing=1.2)


# ----- 15 系统测试与结果（按指标性质分三组）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "系统测试与结果", "按指标性质分三组 —— 检索质量 · 生成与事实核验 · 工程性能与调度")
add_footer(s, 15)

groups = [
    ("01 · 检索质量", TEAL, EVID_BG, EVID_LINE, [
        ("对抗集 HitRate@8", "100%", "n=15 · CI 下界 79.6%"),
        ("对抗集 MRR", "0.933", "n=15 · 命中结果排序质量"),
        ("常规集 HitRate@1", "100%", "n=50 · CI 下界 92.9%"),
    ], "结论：在当前自建测试集上，检索能较好地找到目标记录。"),
    ("02 · 生成与事实核验", NAVY, CARD_BG2, CARD_LINE, [
        ("引用命中", "10 / 10", "n=10 · CI 下界 72.2%"),
        ("关键字段抽样核验", "3 / 3", "n=3，仅定性核验"),
    ], "结论：当前样本内引用与字段核验结果良好，但样本很小，不能推断所有问题都能准确回答。"),
    ("03 · 工程性能与调度", AMBER, WARNBG, WARNLINE, [
        ("并行收益", "2.98x", "当前测试条件下 worker 段耗时比"),
        ("路由精确率", "63.3%", "n=30 · 需结合覆盖率解释"),
        ("检索层延迟 P50", "0.154s", "仅检索段，与生成长度无关"),
    ], "结论：并行执行有性能收益，但路由存在一定冗余，应结合覆盖率一起解释。"),
]
gw3 = Inches(3.83)
cx = M
for name, gc, fc, lc, mets, concl in groups:
    add_rect(s, cx, Inches(1.72), gw3, Inches(3.2), fill=fc, line_rgb=lc)
    add_bar(s, cx, Inches(1.72), gw3, Inches(0.06), gc)
    add_text(s, cx + Inches(0.2), Inches(1.88), gw3 - Inches(0.4), Inches(0.26),
             name, font_size=11.5, bold=True, color=gc)
    my = Inches(2.22)
    for label, val, note in mets:
        add_metric_s(s, cx + Inches(0.18), my, gw3 - Inches(0.36), Inches(0.64),
                     label, val, note, value_color=gc, value_size=13)
        my = my + Inches(0.7)
    add_text(s, cx + Inches(0.2), Inches(4.36), gw3 - Inches(0.4), Inches(0.5),
             concl, font_size=8, color=T_BODY, line_spacing=1.18)
    cx = cx + gw3 + Inches(0.2)

add_rect(s, M, Inches(5.06), Inches(5.85), Inches(1.32), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(5.16), Inches(5.45), Inches(0.26),
         "路由 = 多标签分类：P 63.3% · R 100% · F1 77.6%", font_size=10.5, bold=True,
         color=NAVY)
add_text(s, M + Inches(0.22), Inches(5.46), Inches(5.45), Inches(0.84),
         "supervisor 决定这一轮要调哪几个 worker（30 题）。覆盖率 R=100% 保证不漏库；"
         "精确率 P=63.3% 偏低是 prompt 明确要求的结果：问题笼统时允许全选三个 worker —— "
         "漏掉一个该查的库（该查没查）的代价，远大于多查一个库带来的少量冗余。",
         font_size=8.4, color=T_BODY, line_spacing=1.2)

add_rect(s, M + Inches(6.04), Inches(5.06), Inches(5.85), Inches(1.32),
         fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(6.26), Inches(5.16), Inches(5.45), Inches(0.26),
         "指标怎么测的", font_size=10.5, bold=True, color=NAVY)
add_text(s, M + Inches(6.26), Inches(5.46), Inches(5.45), Inches(0.84),
         "检索侧：规范集 50 题 + 自建对抗集，把问题与两段内容相近但来源不同的文档配对，检验能否命中正确那一条。\n"
         "生成侧：真实性核验集 10 条逐条比对答案里的 URL 是否命中知识库真实地址，字段一致性另抽 3 条核对。\n"
         "编排侧：同进程内并行图 / 串行图跑同一条 query 对照，取三个 worker 段的耗时之比；检索段延迟单独计时。",
         font_size=8.4, color=T_BODY, line_spacing=1.2)

add_text(s, M, Inches(6.46), CW, Inches(0.4),
         "口径：小样本指标另附 Wilson 95% 置信下界，避免把「全中」读成「系统上限」。",
         font_size=9, color=T_MUTED)


# ----- 16 迭代过程与失败案例 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "迭代过程与失败案例", "现在这个版本是三轮迭代的结果，中间排查过的坑比顺利的部分更有用")
add_footer(s, 16)

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
        "引用命中 10/10",
        "→ 事实可溯源，更新不必重训模型",
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
    add_rect(s, sx, Inches(1.78), sw3, Inches(2.46), fill=fc, line_rgb=lc)
    add_pill(s, sx + Inches(0.22), Inches(1.92), tag, fill=tc, fg=T_WHITE, size=10,
             width=Inches(0.62))
    add_text(s, sx + Inches(0.96), Inches(1.94), sw3 - Inches(1.2), Inches(0.28),
             name, font_size=11.5, bold=True, color=tc)
    iy = Inches(2.42)
    for it in items:
        add_text(s, sx + Inches(0.22), iy, sw3 - Inches(0.44), Inches(0.5),
                 "· " + it, font_size=8.6, color=T_BODY, line_spacing=1.18)
        iy = iy + Inches(0.46)
    sx = sx + sw3 + Inches(0.35)

add_rect(s, M, Inches(4.42), CW, Inches(2.36), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.24), Inches(4.54), CW - Inches(0.48), Inches(0.26),
         "排查过的三个坑（也是这轮最实在的收获）", font_size=11.5, bold=True, color=AMBER)
pit = [
    "① 别名闭环：入库侧给院校加了别名，查询侧却忘了归一化，裸简称直接匹配不上、掉出召回 —— "
    "补 query_norm.py 做查询侧归一化后，对抗集 15 条全部命中正确文档（HitRate@8 = 100%）。",
    "② 实验被自己骗：PEFT 的 adapter 是原地注入，却在循环里反复套 PeftModel，导致第 2、3 轮的「对照组」也带着微调权重 —— "
    "改成只套一次、A 组用 disable_adapter() 取，A/B 输出差异从 1/3 恢复到 3/3。",
    "③ 并发踩真实报错：三个 worker 并发打开同一个 Chroma 会报租户错误（tenant）—— "
    "改成模块级单例 + 线程锁（双重检查，锁只护首次构造），之后查询是只读，三 worker 起始时间差 0.00s。",
]
py2 = Inches(4.88)
for p in pit:
    add_text(s, M + Inches(0.24), py2, CW - Inches(0.48), Inches(0.6),
             p, font_size=8.6, color=T_BODY, line_spacing=1.2)
    py2 = py2 + Inches(0.62)


# ----- 17 总结 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_NORMAL)
add_title(s, "总结", "这个项目验证了什么 —— 而不是用了多少个框架")
add_footer(s, 17)

colw = Inches(3.83)
cols = [
    ("01 · 数据与可信检索", NAVY, CARD_BG, CARD_LINE, [
        "建立 180 条结构化留学信息记录，关联来源链接，通过 RAG 检索为回答提供可核验的参考依据。",
        "全部记录带 source_url，检索结果的来源卡片直接由它渲染。",
        "引用命中 10/10；更新知识库即可同步最新要求，不必重训模型。",
    ]),
    ("02 · 多角色协作与自动化", TEAL, EVID_BG, EVID_LINE, [
        "实现三角色协作的申请规划流程，并搭建独立的 Dify / N8N 自动化链路，将回答推送到飞书。",
        "三个 worker 并行检索后统一编号汇总，全图 7 节点 / 8 边。",
        "并行收益 2.98x（worker 段 A/B），路由覆盖率 100%。",
    ]),
    ("03 · 实验验证与能力边界", AMBER, WARNBG, WARNLINE, [
        "通过检索测试、微调 A/B 对照和事实核查，分析系统的有效性及局限，明确检索层与生成模型的职责。",
        "A/B 证明 LoRA 改变的是表达行为：语体与结构可迁移。",
        "URL 逐字溯源 0/20、排名一致 0/7 —— 事实仍由检索层负责。",
    ]),
]
cx = M
for head, hc, fc, lc, items in cols:
    add_rect(s, cx, Inches(1.72), colw, Inches(3.34), fill=fc, line_rgb=lc)
    add_text(s, cx + Inches(0.22), Inches(1.86), colw - Inches(0.44), Inches(0.3),
             head, font_size=12.5, bold=True, color=hc)
    iy = Inches(2.44)
    for j, it in enumerate(items):
        add_text(s, cx + Inches(0.22), iy, colw - Inches(0.44), Inches(1.0),
                 ("· " if j else "") + it, font_size=j and 9 or 9.8,
                 color=T_BODY if j else NAVY, bold=(j == 0), line_spacing=1.26)
        iy = iy + Inches(0.92)
    cx = cx + colw + Inches(0.2)

add_rect(s, M, Inches(5.24), CW, Inches(0.76), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.34), CW - Inches(0.48), Inches(0.56),
         "项目边界：知识库规模有限，尚未实现实时增量采集；微调主要改善表达行为，不保证事实正确性。"
         "这两条不是待修复的缺陷，而是当前设计范围内如实收窄的说明。",
         font_size=10, bold=True, color=NAVY, line_spacing=1.22)

add_rect(s, M, Inches(6.12), CW, Inches(0.74), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.24), Inches(6.24), CW - Inches(0.48), Inches(0.5),
         "一句话收尾：这个项目的价值不在于用了多少个框架，而在于每一处技术选择都能说出它对应哪个具体问题 —— "
         "以及哪些结论有证据、哪些没有。",
         font_size=10, bold=True, color=NAVY, line_spacing=1.22)


# ==================== 附录 ====================
# ----- A1 StateGraph 状态定义与图组装（深色代码页）-----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_CODE)
add_title(s, "附录 A1 · StateGraph 的状态定义与图组装", "rag/agents.py —— 状态字段、节点注册与边表（正文第 9 页的代码级依据）",
          dark=True)
add_footer(s, "A1", dark=True)

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

add_text(s, M + Inches(0.02), Inches(4.82), Inches(6.4), Inches(0.28),
         "# 路由不靠条件边：worker 自己判断是否在 route 里，不在则返回 {}",
         font_size=9, color=D_CMT, font=MONO)

rx = M + Inches(6.5)
add_text(s, rx, Inches(1.66), Inches(5.4), Inches(0.3),
         "# 组装与编译：5 个业务节点 + 8 条直连边（并行 fan-out）", font_size=10,
         color=D_CMT, font=MONO)
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
          {"text": "① 并行无竞态：三个 worker 只写各自专属字段（school_* / admission_* / essay_*），无同 key 更新，故无需 reducer。",
           "color": D_BODY, "size": 9},
          {"text": "② 路由裁剪：未被 supervisor 选中的 worker 返回 {}，并行与裁剪同时成立；8 条边全是 add_edge 直连，无 conditional_edges。",
           "color": D_BODY, "size": 9}],
         font_size=9, color=D_BODY, line_spacing=1.3)


# ----- A2 训练超参与产物明细 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "附录 A2 · 训练超参与产物明细",
          "LLaMA Factory + qwen_lora_sft.yaml · AutoDL 单卡 RTX 3090 24GB（正文第 12-13 页的完整配置）")
add_footer(s, "A2")

cfg = [
    ("基座模型", "Qwen2.5-7B-Instruct"),
    ("微调方式", "LoRA —— rank 8 / alpha 16 / dropout 0.05"),
    ("注入位置", "q_proj · k_proj · v_proj · o_proj"),
    ("训练数据", "180 条 SFT → 144 训练 / 36 留出；训练侧按 val_size=0.1 再切 129 训练 + 15 验证"),
    ("超参", "lr 2e-4 · epochs 3 · batch 1 × grad_accum 8 · bf16 · cutoff 2048"),
    ("工具链", "LLaMA Factory（llamafactory-cli train）"),
]
cfx = M
cfw = Inches(5.85)
cy = Inches(1.76)
for k, v in cfg:
    add_rect(s, cfx, cy, cfw, Inches(0.62), fill=CARD_BG, line_rgb=CARD_LINE)
    add_text(s, cfx + Inches(0.18), cy + Inches(0.05), cfw - Inches(0.36), Inches(0.22),
             k, font_size=9.5, bold=True, color=NAVY)
    add_text(s, cfx + Inches(0.18), cy + Inches(0.28), cfw - Inches(0.36), Inches(0.3),
             v, font_size=8.8, color=T_BODY)
    cy = cy + Inches(0.68)

add_rect(s, M + Inches(6.04), Inches(1.76), Inches(5.85), Inches(1.9),
         fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + Inches(6.26), Inches(1.88), Inches(5.45), Inches(0.26),
         "这些数字怎么来的", font_size=11, bold=True, color=TEAL)
add_text(s, M + Inches(6.26), Inches(2.18), Inches(5.45), Inches(1.36),
         "训练由 LLaMA Factory 一条命令跑完，结束自动写出 train_results.json / trainer_state.json / "
         "trainer_log.jsonl / loss 曲线。\n"
         "四个数字分别对应：train_results.json 的 loss 与 runtime、trainer_state.json 的 global_step、"
         "adapter_model.safetensors 的实际文件体积 —— 随手可查，不是记忆值。",
         font_size=9, color=T_BODY, line_spacing=1.26)

add_rect(s, M + Inches(6.04), Inches(3.78), Inches(5.85), Inches(1.9),
         fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(6.26), Inches(3.9), Inches(5.45), Inches(0.26),
         "为什么不把 loss 当成果指标", font_size=11, bold=True, color=AMBER)
add_text(s, M + Inches(6.26), Inches(4.2), Inches(5.45), Inches(1.36),
         "129 条训练样本、3 个 epoch 的 loss 曲线本身不构成任何结论 —— 它只能证明训练跑通了。\n"
         "真正需要回答的是：微调之后输出行为到底变了什么、能不能稳定复现、有没有超出它该承担的范围。"
         "这三问由正文的 A/B 对照与能力边界核查回答。",
         font_size=9, color=T_BODY, line_spacing=1.26)

add_rect(s, M, Inches(1.76), Inches(5.85), Inches(1.9), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(1.88), Inches(5.45), Inches(0.26),
         "切分与隔离关系", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.22), Inches(2.18), Inches(5.45), Inches(1.36),
         "144 / 36 是 build_sft_data.py 的 8:2 划分（固定随机种子，可复现）。\n"
         "129 / 15 是训练框架在 144 条内部按 val_size=0.1 再切，用于训练期监控。\n"
         "36 条留出集独立成文件，全程不参与训练与调参；生成质量与事实核查的 20 条样本取自该部分。\n"
         "A/B 对照使用另拟的 3 组业务 prompt，与数据划分无关。",
         font_size=8.8, color=T_BODY, line_spacing=1.24)


# ----- A3 标注体系与标签分布 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "附录 A3 · 标注体系与标签分布",
          "把自由文本归一化成 5 个可量化维度，作为后续数据构造的依据（正文第 6 页的分布明细）")
add_footer(s, "A3")

top_charts = [("dist_申请结果.png", "申请结果 · Admit 49 / Reject 1"),
              ("dist_排名档.png", "排名档 · 冲 / 稳 / 保（另 25 条未评级）"),
              ("dist_文书类型.png", "文书类型 · SOP / PS / CV / LOR"),
              ("dist_文书质量.png", "文书质量 · 优 / 良 / 中")]
cw4 = Inches(2.82)
cx = M
for fn, cap in top_charts:
    add_image_fit(s, ASSETS / fn, cx, Inches(1.68), cw4, Inches(1.9),
                  caption=cap, cap_size=9)
    cx = cx + cw4 + Inches(0.2)

add_image_fit(s, ASSETS / "dist_院校国家.png", M, Inches(3.86), cw4, Inches(1.9),
              caption="院校国家 · 美英加澳港新等 10 国", cap_size=9)

add_rect(s, M + cw4 + Inches(0.2), Inches(3.86), CW - cw4 - Inches(0.2), Inches(1.9),
         fill=EVID_BG, line_rgb=EVID_LINE)
add_text(s, M + cw4 + Inches(0.44), Inches(3.98), CW - cw4 - Inches(0.68), Inches(0.3),
         "这张图证明了什么", font_size=11.5, bold=True, color=TEAL)
ev = [
    "① 每个维度都有实际分布、类别之间有区分度 —— 标签体系能支撑按维度筛选数据。",
    "② 文书质量与文书类型的分档，直接对应 SFT 数据构造时的类别标签，标注结果可被训练流程消费。",
    "③ 院校国家以美国为主（54 条），英 16 / 加 13 次之 —— 覆盖范围与知识库实际分布一致。",
    "④ Admit 49 / Reject 1 是原始采集样本的实际分布，不代表整体录取概率。",
]
ey = Inches(4.34)
for e in ev:
    add_text(s, M + cw4 + Inches(0.44), ey, CW - cw4 - Inches(0.68), Inches(0.36),
             e, font_size=9, color=T_BODY, line_spacing=1.18)
    ey = ey + Inches(0.36)

add_summary(s, M, Inches(5.94), CW,
            "标注把不可比的自由文本变成可筛选、可统计、可构造训练集的结构化数据，"
            "是数据底座从「一堆文档」变成「可用资产」的关键一步。",
            height=Inches(0.78), size=11)


# ----- A4 RAG 链路的两个工程旁注 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "附录 A4 · RAG 链路的两个工程旁注",
          "切分器为何未生效、查询侧归一化做了什么（正文第 7 页的补充说明）")
add_footer(s, "A4")

add_rect(s, M, Inches(1.8), Inches(5.85), Inches(2.6), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.24), Inches(1.92), Inches(5.45), Inches(0.28),
         "旁注一：切分器的实际情况（未进主链，仅预留兜底）", font_size=11.5, bold=True,
         color=AMBER)
add_text(s, M + Inches(0.24), Inches(2.26), Inches(5.45), Inches(2.0),
         "build_vectorstore 里配置了 800 / 80 的切分器，但实测 180 条记录中最长文本为 530 字符、"
         "超 800 字符的为 0 条 —— 一条记录 = 一个 Document = 一条向量，切分器是预留兜底，未实际生效。\n\n"
         "为什么保留：记录本身就是语义完整单元（一所院校的一个项目、一个申请案例、一份文书范例），"
         "强行切分反而会把「截止日期」与「所属项目」拆到两个向量里，破坏召回质量。",
         font_size=9.5, color=T_BODY, line_spacing=1.28)

add_rect(s, M + Inches(6.04), Inches(1.8), Inches(5.85), Inches(2.6),
         fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(6.26), Inches(1.92), Inches(5.45), Inches(0.28),
         "旁注二：查询侧归一化（query_norm）", font_size=11.5, bold=True, color=NAVY)
add_text(s, M + Inches(6.26), Inches(2.26), Inches(5.45), Inches(2.0),
         "把 38 所院校的别名统一映射到标准名（如「CMU / 卡内基梅隆」→ 同一实体），"
         "并先剥离 (UCI) 一类括号后缀，再匹配。目的是提升召回率，而不是改写用户的问题。\n\n"
         "这是一个纯规则词典，不调用大模型：入库时把别名拼进了文档，查询侧就必须做同样的处理，"
         "否则两侧表示不一致，口语化提问会直接掉出召回。",
         font_size=9.5, color=T_BODY, line_spacing=1.28)

add_summary(s, M, Inches(4.68), CW, [
    "两条旁注都指向同一件事：链路的每一处配置，要么在真实数据上被验证过是否生效，要么就如实说明它是预留兜底。",
    "180 条数据的长度分布、切分器阈值、别名表覆盖的院校数，都可以在本地重跑脚本核对。",
], height=Inches(1.3), size=10.5)

add_rect(s, M, Inches(6.14), CW, Inches(0.72), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(6.24), CW - Inches(0.48), Inches(0.52),
         "对应的数据铁律：事实不进模型参数 —— 更新知识库只需重跑采集与向量化，代价是分钟级，"
         "不必重新训练模型。",
         font_size=10, bold=True, color=NAVY, line_spacing=1.22)


# ----- A5 工程异常处理与运行细节 -----
s = prs.slides.add_slide(blank)
set_bg(s, PAGE_ARCH)
add_title(s, "附录 A5 · 工程异常处理与运行细节",
          "自动化链路的转义处理、多智能体的状态与并发（正文第 9、11、16 页的补充）")
add_footer(s, "A5")

add_rect(s, M, Inches(1.8), Inches(5.85), Inches(1.7), fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(0.22), Inches(1.92), Inches(5.45), Inches(0.26),
         "推送飞书时的 JSON 转义", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(0.22), Inches(2.22), Inches(5.45), Inches(1.2),
         "推送飞书时用 JSON.stringify() 包裹模板变量，自动转义换行与特殊字符，"
         "避免长文本里的换行把 JSON 结构冲掉。\n"
         "这个问题只在回答较长时才暴露 —— 短回答不带换行，看起来一切正常。",
         font_size=9.5, color=T_BODY, line_spacing=1.26)

add_rect(s, M + Inches(6.04), Inches(1.8), Inches(5.85), Inches(1.7),
         fill=CARD_BG, line_rgb=CARD_LINE)
add_text(s, M + Inches(6.26), Inches(1.92), Inches(5.45), Inches(0.26),
         "并发的状态写入", font_size=11, bold=True, color=NAVY)
add_text(s, M + Inches(6.26), Inches(2.22), Inches(5.45), Inches(1.2),
         "三个 worker 只写各自专属字段（school_plan / admission_risk / essay_outline），"
         "彼此不重叠，因此不存在同一 key 上的并发写冲突，也就不需要额外写 reducer。\n"
         "召回文档字段同样按 worker 分列，互不覆盖。",
         font_size=9.5, color=T_BODY, line_spacing=1.26)

add_rect(s, M, Inches(3.62), CW, Inches(2.06), fill=WARNBG, line_rgb=WARNLINE)
add_text(s, M + Inches(0.24), Inches(3.74), CW - Inches(0.48), Inches(0.26),
         "并发报错的定位过程（正文第 16 页坑③的展开）", font_size=11, bold=True, color=AMBER)
add_text(s, M + Inches(0.24), Inches(4.06), CW - Inches(0.48), Inches(1.5),
         "现象：串行时一切正常，改并行后三个 worker 同时开跑就报「Could not connect to tenant default_tenant」。\n"
         "定位：报错信息指向租户，第一反应是 Chroma 服务没起来；实际上三个 worker 各自 new 了一个 Chroma 客户端，"
         "在同一线程里同时打开同一个本地库，撞在初始化竞态上。\n"
         "修复：改成模块级单例 + 线程锁，用双重检查保证只构造一次，锁只护首次构造，之后查询是只读、不加锁 —— "
         "既消除了竞态，也没有把并行退化成串行。",
         font_size=9.5, color=T_BODY, line_spacing=1.3)

add_rect(s, M, Inches(5.82), CW, Inches(0.5), fill=CARD_BG2, line_rgb=ACCENT)
add_text(s, M + Inches(0.24), Inches(5.91), CW - Inches(0.48), Inches(0.34),
         "修复后实测：三个 worker 的起始时间差为 0.00s，并行收益完整保留（2.98x）。",
         font_size=9.5, bold=True, color=NAVY)


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
