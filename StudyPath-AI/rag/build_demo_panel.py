# -*- coding: utf-8 -*-
"""
build_demo_panel.py — 从 rag_demo_capture.json 生成 RAG demo 展示面板 HTML。

设计原则（避免"手写静态页与真实数据对不上"这类问题）：
  面板内容 **100% 由真实运行结果渲染** —— 问题、回答、Top-K 命中、
  来源域名、检索/生成耗时，全部读自 rag_demo_capture.json，不手写一个字。

用法：
    cd StudyPath-AI
    python rag/build_demo_panel.py                # 渲染第 1 条问答（PPT 截图用）
    python rag/build_demo_panel.py --index 1      # 渲染第 2 条
    python rag/build_demo_panel.py --all          # 渲染全部条目
    python rag/build_demo_panel.py --max-answer 600   # 回答截断到 600 字

输出：rag/rag_demo_panel.html
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / "rag_demo_capture.json"
OUT_PATH = HERE / "rag_demo_panel.html"

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "Microsoft YaHei","PingFang SC",sans-serif; background:#eef1f6; padding:24px; }
  .app { max-width: 1180px; margin: 0 auto 22px; background:#fff; border-radius:14px; overflow:hidden;
         box-shadow:0 8px 30px rgba(0,0,0,.12); border:1px solid #e3e8f0; }
  .topbar { background:#111827; color:#fff; padding:14px 22px; display:flex; align-items:center; gap:10px; }
  .dot { width:10px; height:10px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px #22c55e; }
  .topbar .t { font-size:17px; font-weight:700; }
  .topbar .s { font-size:13px; color:#9ca3af; margin-left:auto; }
  .body { display:grid; grid-template-columns: 1.05fr 1fr; gap:0; }
  .chat { padding:22px; border-right:1px solid #eef1f6; background:#fafbfc; }
  .q { background:#eef2ff; border:1px solid #c7d2fe; color:#1e3a8a; padding:14px 16px;
       border-radius:12px 12px 12px 4px; font-size:15px; line-height:1.6; margin-bottom:16px; }
  .q .lab { font-size:12px; color:#6366f1; font-weight:700; display:block; margin-bottom:4px; }
  .a { background:#fff; border:1px solid #e5e7eb; padding:16px; border-radius:12px 12px 12px 4px;
       font-size:13px; line-height:1.7; color:#1f2937; }
  .a .lab { font-size:12px; color:#059669; font-weight:700; display:block; margin-bottom:6px; }
  .ret { padding:18px 20px; }
  .ret .h { font-size:14px; font-weight:700; color:#374151; margin-bottom:12px; display:flex; align-items:center; gap:8px; }
  .ret .h .badge { background:#111827; color:#fff; font-size:11px; padding:2px 8px; border-radius:10px; }
  .doc { background:#fff; border:1px solid #e5e7eb; border-left:4px solid #6366f1; border-radius:8px;
         padding:10px 12px; margin-bottom:10px; }
  .doc.case { border-left-color:#f59e0b; }
  .doc .meta { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
  .doc .tag { font-size:11px; font-weight:700; padding:1px 7px; border-radius:8px; background:#eef2ff; color:#4338ca; }
  .doc.case .tag { background:#fef3c7; color:#92400e; }
  .doc .src { font-size:11px; color:#6b7280; margin-left:auto; }
  .doc .txt { font-size:12.5px; line-height:1.55; color:#374151; }
  .foot { background:#111827; color:#9ca3af; font-size:12px; padding:10px 22px; display:flex; gap:18px; flex-wrap:wrap; }
  .foot b { color:#e5e7eb; font-weight:600; }
"""


def domain_of(url: str) -> str:
    """从 URL 提取裸域名（去 www.），大厂链接太长不适合直接铺在卡片上"""
    if not url:
        return ""
    netloc = urlparse(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or url[:40]


def _balance_bold(s: str) -> str:
    """截断回答时可能把 **加粗** 标记切成两半，这里补掉落单的标记。

    否则页面上会露出裸 ** ，看着像渲染 bug。
    """
    if s.count("**") % 2 == 1:
        idx = s.rfind("**")
        s = s[:idx] + s[idx + 2:]
    return s


def md_lite(text: str) -> str:
    """极简 Markdown 渲染：**加粗** + 换行。够用于本项目的回答文本。"""
    s = html.escape(_balance_bold(text))
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.S)
    s = s.replace("\n", "<br>")
    return s


def render_case(item: dict, max_answer: int = 0) -> str:
    q = html.escape(item.get("question", ""))
    answer = item.get("answer", "") or "(无回答)"
    if max_answer and len(answer) > max_answer:
        answer = answer[:max_answer] + "……"
    docs = item.get("retrieved", [])
    timing = item.get("timing", {})
    captured = item.get("captured_at", "")

    doc_cards = []
    for d in docs:
        sheet = d.get("sheet", "")
        is_case = "案例" in sheet
        txt = html.escape((d.get("content", "") or "")[:260])
        doc_cards.append(
            f'<div class="doc{" case" if is_case else ""}">'
            f'<div class="meta"><span class="tag">{html.escape(sheet)}</span>'
            f'<span class="src">{html.escape(domain_of(d.get("source", "")))}</span></div>'
            f'<div class="txt">{txt}</div></div>'
        )
    docs_html = "".join(doc_cards) or '<div class="doc"><div class="txt">（本次无命中）</div></div>'

    return f"""<div class="app">
  <div class="topbar">
    <span class="dot"></span>
    <span class="t">StudyPath AI · RAG 检索增强问答</span>
    <span class="s">本地 Gradio Demo · 真实运行记录 {html.escape(captured)}</span>
  </div>
  <div class="body">
    <div class="chat">
      <div class="q"><span class="lab">用户</span>{q}</div>
      <div class="a"><span class="lab">StudyPath AI（仅基于检索资料回答）</span>{md_lite(answer)}</div>
    </div>
    <div class="ret">
      <div class="h">检索命中 Top-{item.get("top_k", len(docs))} <span class="badge">Chroma 向量库 · MMR</span></div>
      {docs_html}
    </div>
  </div>
  <div class="foot">
    <span>基座 <b>qwen-plus</b></span>
    <span>嵌入 <b>text-embedding-v3</b></span>
    <span>向量库 <b>Chroma（180 条真实数据）</b></span>
    <span>检索 <b>{timing.get("retrieve_s", "-")}s</b></span>
    <span>生成 <b>{timing.get("generate_s", "-")}s</b></span>
  </div>
</div>"""


def main():
    ap = argparse.ArgumentParser(description="从 rag_demo_capture.json 生成 demo 面板 HTML")
    ap.add_argument("--index", type=int, default=0, help="渲染第几条问答（从 0 开始，默认 0）")
    ap.add_argument("--all", action="store_true", help="渲染全部条目")
    ap.add_argument("--max-answer", type=int, default=0, help="回答截断字数（0=不截断）")
    args = ap.parse_args()

    if not JSON_PATH.exists():
        print(f"[panel] 找不到 {JSON_PATH}")
        print("[panel] 请先运行：python rag/demo_capture.py")
        sys.exit(1)

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if not data:
        print("[panel] json 为空，无内容可渲染。")
        sys.exit(1)

    if args.all:
        items = data
    else:
        if not 0 <= args.index < len(data):
            print(f"[panel] --index {args.index} 越界（共 {len(data)} 条）")
            sys.exit(1)
        items = [data[args.index]]

    blocks = "\n".join(render_case(it, args.max_answer) for it in items)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>StudyPath AI · RAG Demo 面板</title>
<style>{CSS}</style>
</head>
<body>
{blocks}
</body>
</html>
"""
    OUT_PATH.write_text(page, encoding="utf-8")
    print(f"[panel] 已生成 -> {OUT_PATH}")
    print(f"[panel] 渲染 {len(items)} / {len(data)} 条问答，来源：{JSON_PATH.name}")


if __name__ == "__main__":
    main()
