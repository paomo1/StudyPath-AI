# -*- coding: utf-8 -*-
"""蒸馏效果对照：同一批检索结果，分别用「旧 prompt / 现行 prompt」生成一次。

唯一变量是现行 PROMPT 里的第 3 条（口吻规则）——它就是从 LoRA 实验的 A/B 差异
里蒸馏出来的那一条。检索结果、模型、温度、max_tokens 全部相同，因此两次输出的
差异可以直接归因到这条规则上。

    python scripts/prompt_ab_demo.py                 # 内置 8 条问题，并发跑
    python scripts/prompt_ab_demo.py "你的问题"       # 跑指定问题（可给多条）
    python scripts/prompt_ab_demo.py --n 3           # 只跑前 3 条
    python scripts/prompt_ab_demo.py --jobs 1        # 退回串行（排查限流用）
    python scripts/prompt_ab_demo.py --agent         # 改跑多智能体链，只出终稿
    python scripts/prompt_ab_demo.py --out r.txt     # 全文另存

产物：
  · prompt_ab_report.md —— 风格指标汇总（先看这个）
  · prompt_ab_out.txt   —— 旧/新全文对照（终端中文乱码时看这个）
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag"))

from langchain_core.prompts import ChatPromptTemplate          # noqa: E402
from langchain_core.output_parsers import StrOutputParser      # noqa: E402
from langchain_core.messages import SystemMessage, HumanMessage  # noqa: E402

from qa import (                                               # noqa: E402
    PROMPT, PROMPT_TEMPLATE, STYLE_RULE, retrieve_docs, format_docs, build_llm
)
import agents                                                  # noqa: E402

# 终端编码兜底：Windows 控制台默认 GBK，直接 print 中文会挂
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 旧版模板从现行常量派生：只摘掉第 3 条口吻规则，其余逐字不动。
# 派生而非复制，是为了 qa.py 改措辞时这里自动跟上，不会悄悄失去「唯一变量」。
OLD_TEMPLATE = (
    PROMPT_TEMPLATE.replace(STYLE_RULE, "")
    .replace("4. 用中文回答", "3. 用中文回答")
    .replace("5. 回答末尾", "4. 回答末尾")
)

OLD_PROMPT = ChatPromptTemplate.from_template(OLD_TEMPLATE)

# 8 条，刻意混题型：开放型（最容易触发宏观铺垫，规则的主战场）、
# 事实型（大概率两边都不铺垫，用作「不该被规则带偏」的对照）、对比/预算型（半开放）。
DEFAULT_QUESTIONS = [
    ("开放·规划", "我想申请美国 CS 硕士，GPA 3.5、托福 100，帮我规划一下整条申请路线。"),
    ("开放·定位", "本科双非、GPA 3.3，想读数据分析方向，我该怎么定位和准备？"),
    ("事实·字段", "CMU 的计算机硕士项目申请截止日期和语言要求是什么？"),
    ("对比·择校", "英国 G5 和香港三大的 CS 硕士，哪个更适合双非背景的学生？"),
    ("开放·文书", "帮我规划一下申请美国 CS 硕士的 PS 写作思路。"),
    ("半开放·预算", "预算 30 万人民币左右，能申到什么样的英国硕士？"),
    ("开放·时间线", "我现在大二下，想去美国读 CS 硕士，时间上该怎么安排？"),
    ("事实·费用", "英国硕士一年学费加生活费大概要多少钱？"),
]

# ---------------------------------------------------------------- 风格指标
# 宏观铺垫式开场：A 组纯基座的标志性毛病，规则点名要禁的就是这一类
MACRO_PAT = re.compile(
    r"数字化浪潮|席卷全球|在当今|众所周知|不可否认|日新月异|飞速发展|"
    r"随着[^，。；\n]{0,12}(的发展|的进步|的推进|的普及|的不断)|"
    r"在[^，。；\n]{0,10}的今天|大背景下|时代背景|竞争日益|越来越多人|"
    r"在此背景下"
)
# 分析报告腔：把「给学生的建议」写成「对某课题的分析」
REPORT_PAT = re.compile(
    r"分析如下|如下分析|可行性分析|规划路径分析|整体来看|总体而言|"
    r"以下是对|以下是针对|综合以上|基于上述分析"
)
SRC_PAT = re.compile(r"https?://|\[资料\d+\]")


def metric(text: str) -> dict:
    """抽取可自动判定的风格指标。空文本返回全零，不抛异常。"""
    t = text or ""
    return {
        "chars": len(t),
        "macro": list(dict.fromkeys(m.group(0) for m in MACRO_PAT.finditer(t))),
        "report": list(dict.fromkeys(m.group(0) for m in REPORT_PAT.finditer(t))),
        "nin": t.count("您"),                       # 敬语「您」= 客服腔信号，顾问腔用「你」
        "struct": ("###" in t) or bool(re.search(r"^\s*[-*]\s", t, re.M)),
        "src": bool(SRC_PAT.search(t)),
        "trunc": t.endswith(("…", "...")) or len(t) < 20,
    }


def mark(m: dict) -> str:
    """把一条指标压成一行摘要（不含竖线，可直接进 markdown 表格）。"""
    if not m["chars"]:
        return "（调用失败）"
    tags = ["宏观铺垫×%d" % len(m["macro"]) if m["macro"] else "无宏观铺垫"]
    tags.append("报告腔×%d" % len(m["report"]) if m["report"] else "无报告腔")
    tags.append("您×%d" % m["nin"])
    tags.append("结构" if m["struct"] else "无结构")
    tags.append("截断" if m["trunc"] else "完整")
    return "%d 字 · %s" % (m["chars"], " · ".join(tags))


# ---------------------------------------------------------------- 执行
def call(payload, llm):
    """跑一次生成。payload = (qi, tag, question, ctx, n_docs, template)。"""
    qi, tag, q, ctx, nd, tmpl = payload
    try:
        txt = (tmpl | llm | StrOutputParser()).invoke({"context": ctx, "question": q})
        return qi, tag, txt.strip(), None
    except Exception as e:
        return qi, tag, "", str(e)[:200]


# ---------------------------------------------------------------- 多智能体 A/B
# 旧版同样从现行常量派生，保证「唯一变量」成立；派生而非复制，避免漂移。
agents.SYNTH_OLD = agents.synth_system_prompt(False).replace(agents.SYNTH_STYLE_RULE, "")
agents.WORKER_OLD = {k: v.replace(agents.WORKER_STYLE_RULE, "")
                     for k, v in agents.WORKER_ROLE_PROMPTS.items()}


def _synth_user_msg(st: dict, q: str) -> str:
    """按 synthesizer 的同一套逻辑重建整合器输入（现行/旧版共用，保证同源）。"""
    secs = []
    for field, title in (("school_plan", "选校策略结论"),
                         ("admission_risk", "录取风险评估结论"),
                         ("essay_outline", "文书规划结论")):
        v = st.get(field) or ""
        if v:
            secs.append("【%s】\n%s" % (title, v))
    all_docs = []
    for k in ("school", "admission", "essay"):
        all_docs.extend(st.get(f"{k}_docs") or [])
    deduped = agents._dedup_docs(all_docs)
    sources_text = "\n".join(
        "[%d] %s" % (i + 1, d.metadata.get("source_url", "")) for i, d in enumerate(deduped)
    )
    return ("\n\n".join(secs) + "\n\n【可引用来源】\n" + sources_text
            + "\n\n【用户问题】\n" + q + "\n\n【整合后的申请规划】")


def run_agent_ab(question: str, tid: str, synth_only: bool = False) -> dict:
    """跑一次现行图，再逐段跑「摘掉语体规则」的旧版，得到整合器与 worker 的对照。

    现行侧直接取图上跑出来的结果（不重跑），旧版侧才额外调用——
    这样 A/B 的现行一侧就是产品真实输出，不是复刻。
    """
    g = agents._get_graph()
    init = {
        "messages": [HumanMessage(content=question)], "query": question, "route": [],
        "school_docs": [], "admission_docs": [], "essay_docs": [],
        "school_plan": "", "admission_risk": "", "essay_outline": "", "answer": "",
    }
    try:
        st = g.invoke(init, config={"configurable": {"thread_id": tid}})
    except Exception as e:
        return {"err": str(e)[:160]}

    # 整合器旧版：同一份专家结论，只换 system prompt
    try:
        r = agents.llm.invoke([SystemMessage(content=agents.SYNTH_OLD),
                               HumanMessage(content=_synth_user_msg(st, question))])
        synth_old = agents._clean_answer(r.content)
    except Exception as e:
        synth_old = "ERR:" + str(e)[:80]

    # worker 对照：命中才跑（未命中的 worker 没有对照意义）
    wk = {}
    for k in ("school", "admission", "essay"):
        docs = st.get(f"{k}_docs") or []
        new_txt = st.get(agents.CONCL_FIELD[k]) or ""
        if synth_only or not docs:
            wk[k] = {"hit": bool(docs), "old": None, "new": new_txt}
            continue
        ctx = format_docs(docs)
        try:
            r = agents.llm.invoke([
                SystemMessage(content=agents.WORKER_OLD[k]),
                HumanMessage(content="【检索资料】\n%s\n\n【用户问题】\n%s\n\n【角色结论】" % (ctx, question)),
            ])
            old_txt = agents._clean_answer(r.content)
        except Exception as e:
            old_txt = "ERR:" + str(e)[:80]
        wk[k] = {"hit": True, "old": old_txt, "new": new_txt}

    all_docs = []
    for k in ("school", "admission", "essay"):
        all_docs.extend(st.get(f"{k}_docs") or [])
    return {
        "route": st.get("route", []),
        "answer": (st.get("answer") or "").strip(),
        "synth_old": synth_old,
        "wk": wk,
        "n_sources": len(agents._dedup_docs(all_docs)),
    }


def write_agent_report(items, got, path):
    """整合器 + 三个 worker 的 A/B 指标汇总。"""
    L = []
    L.append("# 多智能体链 · 蒸馏效果对照（整合器 + 三个 worker）\n")
    L.append("样本 **%d** 条 · 模型 `qwen-plus` · 同一条图跑出的专家结论 · "
             "唯一变量 = 语体规则（`SYNTH_STYLE_RULE` / `WORKER_STYLE_RULE`）\n" % len(items))
    L.append("> 现行侧 = 图上真实跑出的结果（即产品输出）；旧版侧 = 摘掉规则后重跑一次。\n")
    L.append("> 整合器规则：%s\n" % agents.SYNTH_STYLE_RULE.replace("\n", " ").strip())
    L.append("> worker 规则：%s\n" % agents.WORKER_STYLE_RULE.replace("\n", " ").strip())

    ok = [(kind, q, g) for kind, q, g in got if g and not g.get("err")]
    if not ok:
        L.append("\n**全部失败**：\n")
        for kind, q, g in got:
            L.append("- [%s] %s -> %s" % (kind, q, (g or {}).get("err")))
        Path(path).write_text("\n".join(L), encoding="utf-8")
        return

    so = [metric(g["synth_old"]) for _, _, g in ok]
    sn = [metric(g["answer"]) for _, _, g in ok]
    avg = lambda xs: sum(x["chars"] for x in xs) // max(1, len(xs))
    cnt = lambda xs, fn: sum(1 for x in xs if fn(x))

    L.append("## 一、整合器（对外终稿）\n")
    L.append("| 指标 | 旧版（摘规则） | 现行（带规则） |")
    L.append("|---|---|---|")
    L.append("| 出现宏观铺垫的条数 | %d / %d | **%d / %d** |" % (
        cnt(so, lambda x: x["macro"]), len(so), cnt(sn, lambda x: x["macro"]), len(sn)))
    L.append("| 出现报告腔的条数 | %d / %d | **%d / %d** |" % (
        cnt(so, lambda x: x["report"]), len(so), cnt(sn, lambda x: x["report"]), len(sn)))
    L.append("| 敬语「您」总次数 | %d | **%d** |" % (
        sum(x["nin"] for x in so), sum(x["nin"] for x in sn)))
    L.append("| 带结构化排版 | %d / %d | **%d / %d** |" % (
        cnt(so, lambda x: x["struct"]), len(so), cnt(sn, lambda x: x["struct"]), len(sn)))
    L.append("| 平均字数 | %d | **%d** |" % (avg(so), avg(sn)))
    L.append("")

    L.append("## 二、三个 worker（中间结论）\n")
    L.append("| worker | 命中条数 | 旧版「您」总次数 | 现行「您」总次数 | 旧版均长 | 现行均长 |")
    L.append("|---|---|---|---|---|---|")
    for k, cn in (("school", "选校策略师"), ("admission", "录取风险评估师"), ("essay", "文书规划师")):
        o = [metric(g["wk"][k]["old"]) for _, _, g in ok if g["wk"][k]["hit"] and g["wk"][k]["old"]]
        n = [metric(g["wk"][k]["new"]) for _, _, g in ok if g["wk"][k]["hit"]]
        if not n:
            L.append("| %s | 0 | - | - | - | - |" % cn)
            continue
        L.append("| %s | %d | %s | %s | %s | %s |" % (
            cn, len(n),
            sum(x["nin"] for x in o) if o else "-",
            sum(x["nin"] for x in n),
            avg(o) if o else "-", avg(n)))
    L.append("")

    L.append("## 三、逐条明细\n")
    for i, (kind, q, g) in enumerate(ok, 1):
        L.append("### %d. [%s] %s" % (i, kind, q))
        L.append("- route: `%s` · 去重来源 %d 条" % (g["route"], g["n_sources"]))
        L.append("- **整合器** 旧: %s" % mark(metric(g["synth_old"])))
        L.append("- **整合器** 现行: %s" % mark(metric(g["answer"])))
        for k, cn in (("school", "选校"), ("admission", "录取"), ("essay", "文书")):
            w = g["wk"][k]
            if not w["hit"]:
                L.append("- worker/%s: 未路由命中" % cn)
            elif w["old"] is None:
                L.append("- worker/%s 现行: %s" % (cn, mark(metric(w["new"]))))
            else:
                L.append("- worker/%s 旧: %s" % (cn, mark(metric(w["old"]))))
                L.append("- worker/%s 现行: %s" % (cn, mark(metric(w["new"]))))
        L.append("")
    Path(path).write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", nargs="*", help="自定义问题（不填则用内置 8 条）")
    ap.add_argument("--n", type=int, default=0, help="只跑前 N 条")
    ap.add_argument("--jobs", type=int, default=6, help="并发生成的调用数（1=串行）")
    ap.add_argument("--agent", action="store_true", help="改跑多智能体链（整合器 + worker 的 A/B）")
    ap.add_argument("--synth-only", action="store_true", help="配合 --agent：只做整合器 A/B，跳过 worker 对照")
    ap.add_argument("--out", default=str(ROOT / "prompt_ab_out.txt"), help="全文输出路径")
    ap.add_argument("--report", default=str(ROOT / "prompt_ab_report.md"), help="指标汇总路径")
    args = ap.parse_args()

    # ---- 自定义问题 / 内置问题
    if args.questions:
        items = [("自定义", q) for q in args.questions]
    else:
        items = list(DEFAULT_QUESTIONS)
    if args.n:
        items = items[: max(1, args.n)]

    # ---- 多智能体分支：整合器 + 三个 worker 全链 A/B
    if args.agent:
        import time as _t
        agents._get_graph()                       # 主线程预热，避免多线程首次构造竞态
        jobs = max(1, min(args.jobs, len(items)))
        print("多智能体 A/B · query %d 条 · 并发 %d · 整合器%s" % (
            len(items), jobs, "（仅整合器）" if args.synth_only else " + 3 worker"), flush=True)
        t0 = _t.time()

        def work(idx_kind_q):
            idx, kind, q = idx_kind_q
            return idx, kind, q, run_agent_ab(
                q, "ab_%d_%d" % (int(t0), idx), args.synth_only)

        got = [None] * len(items)
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = [ex.submit(work, (i, k, q)) for i, (k, q) in enumerate(items)]
            for f in as_completed(futs):
                idx, kind, q, g = f.result()
                got[idx] = (kind, q, g)
                if g and not g.get("err"):
                    print("  ✓ [%d/%d] %s | route=%s" % (idx + 1, len(items), kind, g["route"]), flush=True)
                else:
                    print("  ✗ [%d/%d] %s | %s" % (idx + 1, len(items), kind, (g or {}).get("err")), flush=True)

        # 全文
        blocks = []
        for kind, q, g in got:
            blocks.append("=" * 78)
            blocks.append("【%s】%s" % (kind, q))
            if not g or g.get("err"):
                blocks.append("(失败: %s)" % (g or {}).get("err"))
                continue
            blocks.append("route=%s · 去重来源 %d 条" % (g["route"], g["n_sources"]))
            blocks.append("\n----- 整合器 旧版（摘掉语体规则）-----\n%s" % g["synth_old"])
            blocks.append("\n----- 整合器 现行（含蒸馏语体规则）-----\n%s" % g["answer"])
            for k, cn in (("school", "选校策略师"), ("admission", "录取风险评估师"), ("essay", "文书规划师")):
                w = g["wk"][k]
                if not w["hit"]:
                    continue
                if w["old"] is not None:
                    blocks.append("\n----- worker:%s 旧版 -----\n%s" % (cn, w["old"]))
                blocks.append("\n----- worker:%s 现行 -----\n%s" % (cn, w["new"]))
            blocks.append("")
        Path(args.out).write_text("\n".join(blocks), encoding="utf-8")

        rep = str(Path(args.report).with_name("prompt_ab_agent_report.md"))
        write_agent_report(items, got, rep)
        print("\n耗时 %.1f 分钟" % ((_t.time() - t0) / 60))
        print("指标汇总:", rep)
        print("全文对照:", args.out)
        return

    # ---- 1) 先把 8 条的检索做掉（本地 Chroma，很快），保证 A/B 同源
    llm = build_llm()
    payloads = []
    meta = {}
    for qi, (kind, q) in enumerate(items):
        docs, _ = retrieve_docs(q)
        ctx = format_docs(docs)
        meta[qi] = (kind, q, len(docs))
        for tag, tmpl in (("old", OLD_PROMPT), ("new", PROMPT)):
            payloads.append((qi, tag, q, ctx, len(docs), tmpl))

    jobs = max(1, min(args.jobs, len(payloads)))
    print("query %d 条 · 生成调用 %d 次 · 并发 %d（峰值）" % (len(items), len(payloads), jobs), flush=True)

    # ---- 2) 所有生成调用摊平并发（旧/新之间、不同 query 之间都互不依赖）
    got = {qi: {} for qi in range(len(items))}
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(call, p, llm) for p in payloads]
        done = 0
        for f in as_completed(futs):
            qi, tag, txt, err = f.result()
            got[qi][tag] = (txt, err)
            done += 1
            print("  [%d/%d] 完成 q%d %s%s" % (done, len(payloads), qi + 1, tag,
                                              "  ERR:" + err[:60] if err else ""), flush=True)

    # ---- 3) 全文对照
    raw = []
    for qi, (kind, q, nd) in meta.items():
        raw.append("=" * 78)
        raw.append("【%s】%s\n（检索命中 %d 条）" % (kind, q, nd))
        raw.append("\n----- 旧 prompt（摘掉口吻规则）-----\n%s" % (got[qi]["old"][0] or
                                                                  "(失败: %s)" % got[qi]["old"][1]))
        raw.append("\n----- 现行 prompt（含蒸馏口吻规则）-----\n%s" % (got[qi]["new"][0] or
                                                                      "(失败: %s)" % got[qi]["new"][1]))
        raw.append("")
    Path(args.out).write_text("\n".join(raw), encoding="utf-8")

    # ---- 4) 指标汇总
    rows = []
    for qi, (kind, q, nd) in meta.items():
        mo = metric(got[qi]["old"][0])
        mn = metric(got[qi]["new"][0])
        rows.append((kind, q, mo, mn))

    def cnt(xs, fn):
        return sum(1 for x in xs if fn(x))

    old = [r[2] for r in rows]
    new = [r[3] for r in rows]
    avg = lambda xs: sum(x["chars"] for x in xs) // max(1, len(xs))

    L = []
    L.append("# 蒸馏效果对照（口吻规则 · 旧 vs 现行）\n")
    L.append("样本 **%d** 条 · 模型 `qwen-plus` · 同一批检索结果 · "
             "唯一变量 = 现行 PROMPT 的第 3 条口吻规则\n" % len(rows))
    L.append("> 规则原文：%s\n" % STYLE_RULE.replace("\n", " ").strip())
    L.append("## 一、总览\n")
    L.append("| 指标 | 旧 prompt | 现行 prompt |")
    L.append("|---|---|---|")
    L.append("| 出现宏观铺垫的条数 | %d / %d | **%d / %d** |" % (
        cnt(old, lambda x: x["macro"]), len(old), cnt(new, lambda x: x["macro"]), len(new)))
    L.append("| 出现报告腔的条数 | %d / %d | **%d / %d** |" % (
        cnt(old, lambda x: x["report"]), len(old), cnt(new, lambda x: x["report"]), len(new)))
    L.append("| 敬语「您」总次数 | %d | **%d** |" % (
        sum(x["nin"] for x in old), sum(x["nin"] for x in new)))
    L.append("| 带结构化排版 | %d / %d | **%d / %d** |" % (
        cnt(old, lambda x: x["struct"]), len(old), cnt(new, lambda x: x["struct"]), len(new)))
    L.append("| 平均字数 | %d | **%d** |" % (avg(old), avg(new)))
    L.append("")
    L.append("## 二、逐条对照\n")
    L.append("| # | 题型 | 旧 prompt（摘规则） | 现行 prompt（带规则） |")
    L.append("|---|---|---|---|")
    for i, (kind, q, mo, mn) in enumerate(rows, 1):
        L.append("| %d | %s | %s | %s |" % (i, kind, mark(mo), mark(mn)))
    L.append("")
    L.append("## 三、问题清单\n")
    for i, (kind, q, mo, mn) in enumerate(rows, 1):
        L.append("%d. **[%s]** %s" % (i, kind, q))
    Path(args.report).write_text("\n".join(L), encoding="utf-8")

    print("\n指标汇总:", args.report)
    print("全文对照:", args.out)


if __name__ == "__main__":
    main()
