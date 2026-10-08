# -*- coding: utf-8 -*-
"""
早期的基础版界面：白底、左输入右回答、智能体路由 + Markdown 答复。
样式比 app_gradio.py 简单，作为可运行的精简备选保留。

运行：python rag/app_gradio_v1_basic.py，浏览器打开 http://127.0.0.1:7860
"""
import re
import gradio as gr
from agents import ask_multi


# 标题区 HTML（白底干净版）
HEADER_HTML = r"""
<div style="padding:18px 8px 8px">
  <div style="font-size:22px;font-weight:700;color:#1a2233;letter-spacing:-.3px">
    📚 StudyPath · 留学规划助手
  </div>
  <div style="margin-top:8px;font-size:13.5px;color:#5b6678;line-height:1.7">
    多智能体架构 <b>(RAG + LangGraph)</b> ：Supervisor 调度
    <b>院校项目库 / 录取案例库 / 文书范例库</b>
    三个专家协同检索，再由 Synthesiser 汇总成带引用的答复。
  </div>
</div>
"""

# 路由区标题 + 答复区标题
PANEL_CSS = r"""
.panel-title{font-size:14px;font-weight:700;color:#3b5bdb;margin:0 0 10px}
.route-box{background:#f7f9fd;border:1px solid #e3e8f1;border-radius:8px;padding:12px 16px;min-height:80px}
.route-item{font-size:13.5px;color:#1a2233;padding:3px 0;line-height:1.6}
.route-item:before{content:"●";color:#3b5bdb;margin-right:8px;font-size:11px}
.ans-box{background:#fff;border:1px solid #e3e8f1;border-radius:8px;padding:18px 22px;min-height:200px;
  font-size:14px;line-height:1.75;color:#1a2233}
.ans-box a{color:#3b5bdb;text-decoration:underline}
.src-box{margin-top:12px;font-size:12.5px;color:#5b6678;line-height:1.7}
.src-box a{color:#3b5bdb;text-decoration:underline;margin-right:14px}
"""


def extract_sources(answer: str):
    """从回答里提取真实 source_url（可溯源）。"""
    urls = re.findall(r'https?://[^\s)\[\]】]+', answer or "")
    seen, out = set(), []
    for u in urls:
        u = u.rstrip('。，、')
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def render_route(route):
    """把 route 列表渲染成 Supervisor 决策清单 HTML。"""
    if not route:
        return '<div class="route-item" style="color:#94a3b8">（暂无路由）</div>'
    return "".join(f'<div class="route-item">{r}</div>' for r in route)


def render_sources(urls):
    if not urls:
        return ""
    links = "".join(f'<a href="{u}" target="_blank" rel="noopener">{u}</a>' for u in urls)
    return f'<div class="src-box">来源：{links}</div>'


def consult(query):
    """界面入口：调用多智能体，返回 (路由 HTML, 答复 HTML)。"""
    q = (query or "").strip()
    if not q:
        return '<div class="route-item" style="color:#94a3b8">（等待提问）</div>', \
               '<div class="ans-box" style="color:#94a3b8">请在左侧输入你的问题…</div>'
    try:
        out = ask_multi(q)
        route = out.get("route", [])
        answer = out.get("answer", "") or "_（未检索到相关资料）_"
        sources = extract_sources(answer)
        # 把 Markdown 答案原样渲染（Gradio Markdown 组件自身处理换行/标题/列表）
        # 这里直接 return 字符串，外层用 gr.Markdown 渲染
        route_html = render_route(route)
        sources_html = render_sources(sources)
        # 答复 + 来源拼一起（Markdown）
        full_answer = answer + ("\n\n" + sources_html if sources_html else "")
        return route_html, full_answer
    except Exception as e:
        return '<div class="route-item" style="color:#e8590c">（调用出错）</div>', \
               f"⚠️ 调用出错：{e}\n\n请检查网络 / DashScope key 后重试。"


with gr.Blocks(title="StudyPath · 留学规划助手", css=PANEL_CSS) as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("**你的问题**")
            query_box = gr.Textbox(
                label="",
                placeholder="例：GPA3.5 托福100 申 CMU MSCS",
                lines=6,
            )
            submit_btn = gr.Button("🚀 开始咨询", variant="primary")

        with gr.Column(scale=1):
            gr.Markdown('<div class="panel-title">🧭 智能体路由 (Supervisor 决策清单)</div>')
            route_box = gr.HTML(value=render_route([]))
            gr.Markdown("**答复**")
            answer_box = gr.Markdown(
                value="等待提问，下方将显示 StudyPath 的带引用答复…",
                elem_classes=["ans-box"],
            )

    submit_btn.click(consult, inputs=query_box, outputs=[route_box, answer_box])
    query_box.submit(consult, inputs=query_box, outputs=[route_box, answer_box])

    gr.Examples(
        examples=[
            "我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？需要准备什么文书？",
            "CMU 的 MSCS 项目申请要求和截止日期是什么？",
            "GPA 3.2 托福 95 能申到哪些英国 CS 硕士？",
        ],
        inputs=query_box,
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, inbrowser=True)
