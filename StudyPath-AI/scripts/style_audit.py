# -*- coding: utf-8 -*-
"""LoRA 蒸馏效果的批量审计。

背景：实验①证明 LoRA 迁移的是「表达范式」（顾问口吻、不写宏观铺垫），
据此把该范式固化成 prompt 规则，落到三段：单链 qa.py 的规则 3、
三个 worker 与整合器的 role prompt（WORKER_STYLE_RULE / SYNTH_STYLE_RULE）。

本脚本回答的问题：这条规则到底生效了没有、稳不稳、覆盖到哪几段。
每段的做法都是「固定输入、只切换带不带这条规则」：
  · 单链      —— 同一批检索 docs，旧模板 vs 现行模板
  · 三个 worker —— 同一批 docs，摘掉规则的 role vs 现行 role
  · 整合器     —— 同一批专家结论，旧 system vs 现行 system
再对输出自动打风格指标，避免「看一两条觉得还行」的主观判断。

    python scripts/style_audit.py            # 默认 6 条 query，全链路
    python scripts/style_audit.py --n 2      # 只跑前 2 条（省额度）
    python scripts/style_audit.py --out r.md --raw r.txt

产物：报告 markdown + 全文对照 txt，默认落在仓库根目录。
"""
import argparse
import io
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag"))

from langchain_core.messages import SystemMessage, HumanMessage   # noqa: E402
from langchain_core.prompts import ChatPromptTemplate             # noqa: E402

import qa        # noqa: E402
import agents    # noqa: E402


# ---------------------------------------------------------------- query 集
# 刻意混三种题型：开放规划型（最容易触发宏观铺垫，规则的主战场）、
# 事实型（大概率两边都不铺垫，用作「不该被规则带偏」的对照）、
# 对比/预算型（半开放）。
QUERIES = [
    ("开放·规划", "我想申请美国 CS 硕士，GPA 3.5、托福 100，帮我规划一下整条申请路线"),
    ("开放·定位", "本科双非、GPA 3.3，想读数据分析方向，我该怎么定位和准备？"),
    ("事实·字段", "CMU 的计算机硕士项目申请截止日期和语言要求是什么？"),
    ("对比·择校", "英国 G5 和香港三大的 CS 硕士，哪个更适合双非背景的学生？"),
    ("开放·文书", "帮我规划一下申请美国 CS 硕士的 PS 写作思路"),
    ("半开放·预算", "预算 30 万人民币左右，能申到什么样的英国硕士？"),
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
# 顾问口吻信号：直接下结论、给动作
ACTION_PAT = re.compile(
    r"建议你|你应该|你现在|建议|优先|务必|尽快|第一步|着手|行动|"
    r"时间线|清单|checklist|目标|下一步"
)
SRC_PAT = re.compile(r"https?://|\[资料\d+\]")


def metric(text: str, finish: str = None) -> dict:
    """抽取可自动判定的风格指标。空文本返回全零，不抛异常。"""
    t = text or ""
    return {
        "chars": len(t),
        "macro": list(dict.fromkeys(m.group(0) for m in MACRO_PAT.finditer(t))),
        "report": list(dict.fromkeys(m.group(0) for m in REPORT_PAT.finditer(t))),
        "nin": t.count("您"),                       # 敬语「您」= 客服腔信号，顾问腔用「你」
        "you": t.count("你"),
        "struct": ("###" in t) or bool(re.search(r"^\s*[-*]\s", t, re.M)),
        "src": bool(SRC_PAT.search(t)),
        "action": list(dict.fromkeys(m.group(0) for m in ACTION_PAT.finditer(t))),
        "trunc": (finish == "length"),
        "finish": finish or "-",
    }


def mark(m: dict) -> str:
    """把一条指标压成一行摘要（不含竖线，可直接进 markdown 表格）。"""
    if not m["chars"]:
        return "（空 / 调用失败）"
    tags = ["宏观铺垫×%d" % len(m["macro"]) if m["macro"] else "无宏观铺垫"]
    tags.append("报告腔×%d" % len(m["report"]) if m["report"] else "无报告腔")
    tags.append("您×%d" % m["nin"])
    tags.append("结构" if m["struct"] else "无结构")
    tags.append("来源" if m["src"] else "无来源")
    tags.append("动作×%d" % len(m["action"]))
    tags.append("截断" if m["trunc"] else "完整")
    return "%d 字 · %s" % (m["chars"], " · ".join(tags))


# ---------------------------------------------------------------- 旧版 prompt
# 旧版一律从现行的 STYLE_RULE 常量派生，不复制模板文本——
# 否则 qa.py 改一次措辞，对照实验就悄悄失去「唯一变量」的前提。
_QA_OLD_TMPL = (
    qa.PROMPT_TEMPLATE.replace(qa.STYLE_RULE, "")
    .replace("4. 用中文回答", "3. 用中文回答")
    .replace("5. 回答末尾", "4. 回答末尾")
)
QA_OLD = ChatPromptTemplate.from_template(_QA_OLD_TMPL)

# 整合器旧版：只摘掉语体那一段，其余逐字不动
SYNTH_OLD = agents.synth_system_prompt(False).replace(agents.SYNTH_STYLE_RULE, "")
# worker 旧版角色：同理，只摘掉 WORKER_STYLE_RULE
WORKER_OLD = {k: v.replace(agents.WORKER_STYLE_RULE, "") for k, v in agents.WORKER_ROLE_PROMPTS.items()}


def run_single(q: str):
    """单链 A/B：同一批 docs，旧模板 vs 现行模板。"""
    docs, _ = qa.retrieve_docs(q)
    ctx = qa.format_docs(docs)
    llm = qa.build_llm()
    out = {}
    for tag, tmpl in (("old", QA_OLD), ("new", qa.PROMPT)):
        try:
            r = (tmpl | llm).invoke({"context": ctx, "question": q})
            out[tag] = (r.content, r.response_metadata.get("finish_reason"))
        except Exception as e:
            out[tag] = ("", "ERR:" + str(e)[:90])
    return docs, out


def _synth_user_msg(res: dict, q: str) -> str:
    """按 agents.synthesizer 的同一套逻辑重建整合器输入（保证 A/B 同源）。"""
    plan = res.get("school_plan", "")
    risk = res.get("admission_risk", "")
    outline = res.get("essay_outline", "")
    all_docs = []
    for k in ("school", "admission", "essay"):
        all_docs.extend(res.get(f"{k}_docs") or [])
    deduped = agents._dedup_docs(all_docs)
    sources_text = "\n".join(
        "[%d] %s" % (i + 1, d.metadata.get("source_url", ""))
        for i, d in enumerate(deduped)
    )
    secs = []
    if plan:
        secs.append("【选校策略结论】\n" + plan)
    if risk:
        secs.append("【录取风险评估结论】\n" + risk)
    if outline:
        secs.append("【文书规划结论】\n" + outline)
    return (
        "\n\n".join(secs)
        + "\n\n【可引用来源】\n" + sources_text
        + "\n\n【用户问题】\n" + q
        + "\n\n【整合后的申请规划】"
    )


def analyze_with_role(role_text: str, query: str, docs):
    """用指定角色 prompt 跑一次 worker 分析（供 A/B 的旧版用）。"""
    if not docs:
        return "", None
    ctx = qa.format_docs(docs)
    sys = SystemMessage(content=role_text)
    user = HumanMessage(content="【检索资料】\n%s\n\n【用户问题】\n%s\n\n【角色结论】" % (ctx, query))
    r = agents.llm.invoke([sys, user])
    return agents._clean_answer(r.content), r.response_metadata.get("finish_reason")


def run_multi(q: str, tid: str):
    """跑现行图拿三个 worker 结论 + 终稿；再逐段跑「摘掉规则」的旧版做对照。"""
    g = agents._get_graph()
    init = {
        "messages": [HumanMessage(content=q)], "query": q, "route": [],
        "school_docs": [], "admission_docs": [], "essay_docs": [],
        "school_plan": "", "admission_risk": "", "essay_outline": "", "answer": "",
    }
    try:
        res = g.invoke(init, config={"configurable": {"thread_id": tid}})
    except Exception as e:
        return None, None, None, {"err": str(e)[:140]}

    # 整合器 A/B
    synth = {"new": (res.get("answer", ""), None)}
    try:
        r = agents.llm.invoke([
            SystemMessage(content=SYNTH_OLD),
            HumanMessage(content=_synth_user_msg(res, q)),
        ])
        synth["old"] = (r.content, r.response_metadata.get("finish_reason"))
    except Exception as e:
        synth["old"] = ("", "ERR:" + str(e)[:90])

    # worker A/B：现行（图上跑出来的）vs 旧版（摘掉语体规则的 role）
    wk = {}
    for k in ("school", "admission", "essay"):
        docs = res.get(f"{k}_docs") or []
        new_txt = res.get(agents.CONCL_FIELD[k], "")
        if not docs:                                  # 未被路由命中，无对照意义
            wk[k] = {"hit": False, "old": ((), None), "new": (new_txt, None)}
            continue
        try:
            old_txt, old_fin = analyze_with_role(WORKER_OLD[k], q, docs)
        except Exception as e:
            old_txt, old_fin = "", "ERR:" + str(e)[:90]
        wk[k] = {"hit": True, "old": (old_txt, old_fin), "new": (new_txt, None)}
    return res, synth, wk, {}


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=len(QUERIES), help="只跑前 N 条")
    ap.add_argument("--out", default=str(ROOT / "style_audit_report.md"))
    ap.add_argument("--raw", default=str(ROOT / "style_audit_raw.txt"))
    ap.add_argument("--no-multi", action="store_true", help="只跑单链（省额度）")
    args = ap.parse_args()

    todo = QUERIES[: max(1, args.n)]
    raw = io.StringIO()
    singles, multis = [], []

    for i, (kind, q) in enumerate(todo, 1):
        print("[%d/%d] %s | %s" % (i, len(todo), kind, q[:34]), flush=True)
        docs, s = run_single(q)
        sm = {k: metric(v[0], v[1]) for k, v in s.items()}
        singles.append((kind, q, sm))
        raw.write("\n" + "=" * 78 + "\n【单链】%s | %s\n" % (kind, q))
        for k in ("old", "new"):
            raw.write("\n----- %s -----\n%s\n" % (k, s[k][0] or "(失败: %s)" % s[k][1]))

        if not args.no_multi:
            t0 = time.time()
            res, synth, wk, err = run_multi(q, "audit_%d_%d" % (int(t0), i))
            if res is None:
                multis.append((kind, q, None, None, None))
                raw.write("\n【多智能体】失败: %s\n" % err.get("err"))
                print("    多智能体失败:", err.get("err"))
                continue
            am = {k: metric(v[0], v[1]) for k, v in synth.items()}
            wm = {k: {"hit": v["hit"],
                      "old": metric(v["old"][0], v["old"][1]),
                      "new": metric(v["new"][0], v["new"][1])} for k, v in wk.items()}
            multis.append((kind, q, res.get("route", []), am, wm))
            raw.write("\n【多智能体】route=%s\n" % res.get("route"))
            for k in ("school", "admission", "essay"):
                raw.write("\n----- worker:%s (旧/摘规则) -----\n%s\n" % (k, wk[k]["old"][0] or "(未命中)"))
                raw.write("\n----- worker:%s (现行/带规则) -----\n%s\n" % (k, wk[k]["new"][0] or "(未命中)"))
            raw.write("\n----- synthesizer old -----\n%s\n" % synth["old"][0])
            raw.write("\n----- synthesizer new -----\n%s\n" % synth["new"][0])
        print("    单链 %s" % "|".join("%s:%d字" % (k, sm[k]["chars"]) for k in ("old", "new")), flush=True)

    # ---------------------------------------------------------- 汇总
    def cnt(xs, fn):
        return sum(1 for x in xs if fn(x))

    L = []
    L.append("# LoRA 蒸馏效果批量审计\n")
    L.append("样本 **%d** 条 · 模型 `qwen-plus` · 每段都做「带 / 不带语体规则」对照"
             "（固定输入，唯一变量 = 那段规则）\n" % len(todo))

    # 总览
    s_old = [r[2]["old"] for r in singles]
    s_new = [r[2]["new"] for r in singles]
    m_old = [r[3]["old"] for r in multis if r[3]]
    m_new = [r[3]["new"] for r in multis if r[3]]
    w_old, w_new = [], []
    for r in multis:
        if not r[4]:
            continue
        for k in ("school", "admission", "essay"):
            if r[4][k]["hit"]:
                w_old.append(r[4][k]["old"])
                w_new.append(r[4][k]["new"])

    L.append("## 一、总览\n")
    L.append("| 链路 | 对照样本 | 宏观铺垫（旧→新） | 「您」出现（旧→新） | 截断（旧→新） | 均长（旧→新） |")
    L.append("|---|---|---|---|---|---|")
    for name, o, n in (("单链 qa.py", s_old, s_new),
                       ("三个 worker", w_old, w_new),
                       ("整合器", m_old, m_new)):
        avg = lambda xs: sum(x["chars"] for x in xs) // max(1, len(xs))
        L.append("| %s | %d | %d → %d | %d → %d | %d → %d | %d → %d |" % (
            name, len(o),
            cnt(o, lambda x: x["macro"]), cnt(n, lambda x: x["macro"]),
            cnt(o, lambda x: x["nin"] > 0), cnt(n, lambda x: x["nin"] > 0),
            cnt(o, lambda x: x["trunc"]), cnt(n, lambda x: x["trunc"]),
            avg(o), avg(n)))
    L.append("")
    tot_o = sum(x["nin"] for x in s_old + w_old + m_old)
    tot_n = sum(x["nin"] for x in s_new + w_new + m_new)
    L.append("敬语「您」总次数：**%d → %d**（顾问腔用「你」，客服腔才用「您」）\n" % (tot_o, tot_n))

    # 单链
    L.append("## 二、单链（qa.py）逐条\n")
    L.append("| query | 旧 prompt（摘规则） | 现行 prompt（带规则） |")
    L.append("|---|---|---|")
    for kind, q, m in singles:
        L.append("| %s | %s | %s |" % (kind, mark(m["old"]), mark(m["new"])))
    L.append("")

    # worker
    L.append("## 三、三个 worker 逐条（摘规则 vs 带规则）\n")
    L.append("| query | worker | 旧 role（摘规则） | 现行 role（带规则） |")
    L.append("|---|---|---|---|")
    for r in multis:
        if not r[4]:
            continue
        for k in ("school", "admission", "essay"):
            v = r[4][k]
            if not v["hit"]:
                L.append("| %s | %s | （未路由命中） | （未路由命中） |" % (r[0], k))
                continue
            L.append("| %s | %s | %s | %s |" % (r[0], k, mark(v["old"]), mark(v["new"])))
    L.append("")
    L.append("worker 小计：宏观铺垫 %d → %d ｜ 「您」出现 %d → %d ｜ 截断 %d → %d（分母 %d）\n" % (
        cnt(w_old, lambda x: x["macro"]), cnt(w_new, lambda x: x["macro"]),
        cnt(w_old, lambda x: x["nin"] > 0), cnt(w_new, lambda x: x["nin"] > 0),
        cnt(w_old, lambda x: x["trunc"]), cnt(w_new, lambda x: x["trunc"]), len(w_old)))

    # 整合器
    L.append("## 四、整合器（synthesizer）逐条\n")
    L.append("| query | route | 旧 system（摘规则） | 现行 system（带规则） |")
    L.append("|---|---|---|---|")
    for r in multis:
        if not r[3]:
            continue
        L.append("| %s | `%s` | %s | %s |" % (r[0], r[2], mark(r[3]["old"]), mark(r[3]["new"])))
    L.append("")

    Path(args.out).write_text("\n".join(L), encoding="utf-8")
    Path(args.raw).write_text(raw.getvalue(), encoding="utf-8")
    print("\n报告:", args.out)
    print("全文:", args.raw)


if __name__ == "__main__":
    main()
