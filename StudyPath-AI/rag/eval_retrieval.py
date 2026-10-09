# -*- coding: utf-8 -*-
"""
RAG 检索与生成的分层评测。

A. 规范问法集（50 条）：query 由 xlsx 字段生成，与入库文档同源，用来确认管线稳定精确。
   这层数字接近天花板，存在 data leakage，不能单独拿去对标业界水平。
B. 口语化 / 别名对抗集（15 条）：模拟真实用户口吻（"CMU 计算机硕士好不好申"），
   目标院校按 school_name 命中。这层反映真实泛化能力。

指标全部用规则实现，无额外依赖：
    HitRate@k       Top-k 是否含正确文档（k = 1/3/5/8）
    MRR             首个正确结果的平均倒数排名
    Recall@8        单文档 GT 下等价于 HitRate@8
    Faithfulness    citation_url_hit：答案是否引用正确 source_url
                    key_field_hit  ：答案是否给出关键数值（问学费 / 排名时不计语言分，
                                     以免误判）
"""
import json
import os
import random
import re
import statistics
import time

import openpyxl
from langchain_chroma import Chroma

from config import XLSX_PATH, SHEET_SCHOOLS, CHROMA_DIR, TOP_K
from qa import get_embeddings, build_qa
from data_loader import _SCHOOL_ALIAS
from query_norm import normalize_query

HERE = os.path.dirname(os.path.abspath(__file__))
EVALSET = os.path.join(HERE, "..", "data", "processed", "rag_evalset.jsonl")
METRICS = os.path.join(HERE, "..", "data", "processed", "rag_metrics.json")

TEMPLATES = [
    ("intro",    "介绍一下 {school} 的 {program} 项目，包括排名和基本要求"),
    ("gpa",      "{school} 的 {program} 对 GPA 有什么最低要求？"),
    ("deadline", "{school} 的 {program} 申请截止日期是什么时候？"),
    ("lang",     "{school} 的 {program} 托福和雅思分别要求多少分？"),
    ("tuition",  "{school} 的 {program} 一年学费大概多少美元？"),
    ("rank",     "{school} 在计算机方向的排名怎么样？"),
    ("duration", "{school} 的 {program} 学制是几年？"),
]

# 口语化 / 别名对抗集：从院校库「实际存在」的学校动态抽取，用其中文别名构造
# 真实用户口吻的 query，测试别名召回与泛化能力（而非教科书式规范问法）。
ADV_TEMPLATES = [
    ("我想申 {sn} 的计算机硕士，GPA 大概要多少", "gpa"),
    ("{sn} 的 AI 相关硕士雅思得几分", "lang"),
    ("{sn} cs 硕士申请截止什么时候", "deadline"),
    ("{sn} 计算机研究生一年学费多少", "tuition"),
    ("{sn} 的计算机硕士学制几年", "duration"),
    ("{sn} 计算机专业排名怎么样", "rank"),
    ("{sn} 计算机硕士好申吗，有什么要求", "intro"),
]

# 学校英文全名 -> 中文/缩写简称（用于口语化 query），取自 data_loader 别名表
_ALIAS_REV = {k.lower(): v.split("（")[0] for k, v in _SCHOOL_ALIAS.items()}


def _short_name(school_name: str) -> str:
    return _ALIAS_REV.get(school_name.lower(), school_name)


def _fields_for_type(typ, d):
    """只有 gpa/lang 类问题才期望答案出现数值字段，避免口径偏差。"""
    if typ == "gpa":
        return {"gpa_min": str(d.get("gpa_min") or "")}
    if typ == "lang":
        return {
            "toefl_min": str(d.get("toefl_min") or ""),
            "ielts_min": str(d.get("ielts_min") or ""),
        }
    return {}


def build_evalset(n=50, seed=42):
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_SCHOOLS]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    data = [dict(zip(header, r)) for r in rows[1:] if r and r[0]]
    valid = [d for d in data if d.get("source_url") and d.get("school_name")]
    random.seed(seed)
    random.shuffle(valid)
    sample = valid[:n]
    out = []
    for i, d in enumerate(sample):
        school = str(d["school_name"])
        program = str(d.get("program_name") or "")
        tid, tmpl = TEMPLATES[i % len(TEMPLATES)]
        q = tmpl.format(school=school, program=program)
        out.append({
            "id": i + 1,
            "query": q,
            "type": tid,
            "ground_truth_url": str(d["source_url"]),
            "expected_fields": _fields_for_type(tid, d),
        })
    os.makedirs(os.path.dirname(EVALSET), exist_ok=True)
    with open(EVALSET, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"[evalset] 生成规范集 {len(out)} 条 -> {EVALSET}")
    return out


def load_evalset():
    if not os.path.exists(EVALSET):
        return build_evalset()
    return [json.loads(l) for l in open(EVALSET, encoding="utf-8")]


def load_adversarial(n=15, seed=43):
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_SCHOOLS]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    schools = []
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dict(zip(header, r))
        sn = str(d["school_name"])
        url = str(d.get("source_url") or "")
        if not url:
            continue
        schools.append((sn, url, d))
    random.seed(seed)
    random.shuffle(schools)
    sample = schools[:n]
    out = []
    for i, (sn, url, d) in enumerate(sample):
        tmpl, typ = ADV_TEMPLATES[i % len(ADV_TEMPLATES)]
        q = tmpl.format(sn=_short_name(sn))
        out.append({
            "id": f"A{i + 1}",
            "query": q,
            "type": typ,
            "gt_school": sn,
            "gt_url": url,
            "expected_fields": _fields_for_type(typ, d),
        })
    print(f"[adv] 构造对抗集 {len(out)} 条（从院校库动态抽取）")
    return out


def _norm(s):
    return re.sub(r"\s+", "", str(s)).lower()


def eval_split(cases, doc_match_fn):
    ks = [1, 3, 5, 8]
    hit = {k: 0 for k in ks}
    rr = []
    per_type = {}
    n = 0
    for c in cases:
        gt = c.get("gt_url") or c.get("ground_truth_url") or c.get("gt_school")
        if not gt:
            continue
        n += 1
        # 检索前做查询侧别名归一化（与线上链路 qa.py 完全一致，保证测的就是线上行为）
        docs = retriever.invoke(normalize_query(c["query"]))
        vals = [doc_match_fn(d) for d in docs]
        rank = next((i for i, u in enumerate(vals, 1) if u == gt), None)
        if rank:
            rr.append(1.0 / rank)
            for k in ks:
                if rank <= k:
                    hit[k] += 1
        else:
            rr.append(0.0)
        per_type.setdefault(c["type"], []).append(1 if (rank and rank <= 8) else 0)
    if n == 0:
        return None
    return {
        "n": n,
        "hit_rate": {f"hit_rate@{k}": round(hit[k] / n, 4) for k in ks},
        "mrr": round(sum(rr) / n, 4),
        "recall@8": round(hit[8] / n, 4),
        "per_type_hit@8": {
            t: round(sum(v) / len(v), 4) for t, v in per_type.items()
        },
    }


# ---------------------------------------------------------------------------
# D. 路由准确率（多智能体独有指标）
#    每条标注「这个问题该由哪个 worker 主责」，跑真实 supervisor（LLM 出 JSON）比对。
#    两个口径同时报，避免只看好看的那个：
#      · coverage：期望 worker 是否被路由覆盖（不漏 = 检索资料不会缺）
#      · exact    ：路由集合是否与期望完全一致（不多不少 = 没有冗余检索）
ROUTE_CASES = [
    # --- 院校项目库主责：排名 / 申请要求 / 截止日期 / 学费 / 学制 ---
    ("CMU 计算机硕士的申请截止日期是什么时候？", ["school"]),
    ("斯坦福计算机硕士一年学费大概多少美元？", ["school"]),
    ("帝国理工学院计算机硕士学制是几年？", ["school"]),
    ("UIUC 的计算机硕士对 GPA 最低要求多少？", ["school"]),
    ("多伦多大学计算机硕士托福雅思要求多少分？", ["school"]),
    ("南洋理工计算机专业排名怎么样？", ["school"]),
    ("介绍一下卡内基梅隆的计算机硕士项目", ["school"]),
    ("港理工 cs 项目属于哪个学院，排名多少？", ["school"]),
    ("滑铁卢大学计算机硕士需要 GRE 吗？", ["school"]),
    ("波士顿大学计算机硕士偏好什么背景的学生？", ["school"]),
    # --- 录取案例库主责：背景匹配 / 往年录取结果 ---
    ("我 GPA 3.5 托福 100，有没有申上 CMU 的往年案例？", ["admission"]),
    ("双非背景申请美国 CS 硕士有成功案例吗？", ["admission"]),
    ("GPA 3.7、两段实习申 UIUC 录取概率大吗？", ["admission"]),
    ("有没有和我背景类似的学长被多伦多大学录取的？", ["admission"]),
    ("往年录取案例里申 CMU 的同学一般有几段实习？", ["admission"]),
    ("我这个背景能上南洋理工吗，参考下往年录取数据", ["admission"]),
    ("211 均分 85 申港理工 cs 有案例吗？", ["admission"]),
    ("案例库里被拒的同学通常 weak 在哪？", ["admission"]),
    ("想看看去年申帝国理工的录取结果统计", ["admission"]),
    ("我有两篇论文，参考案例看能冲什么档次的学校", ["admission"]),
    # --- 文书范例库主责：PS / SOP / CV / 推荐信 ---
    ("个人陈述 PS 该怎么写，有没有范文参考？", ["essay"]),
    ("SOP 的结构一般是怎样的？", ["essay"]),
    ("申请 CV 简历有什么模板吗？", ["essay"]),
    ("推荐信 LOR 找谁写比较合适，有范例吗？", ["essay"]),
    ("文书里怎么突出科研经历？", ["essay"]),
    ("有没有高质量 PS 范例可以学习下？", ["essay"]),
    ("文书写作常见坑有哪些？", ["essay"]),
    ("CV 里实习经历怎么写比较有说服力？", ["essay"]),
    ("SOP 开头怎么写才吸引人？", ["essay"]),
    ("给我一份计算机硕士申请的文书范例", ["essay"]),
]


def eval_routing(graph_mod, n_limit=None):
    """跑真实 supervisor，统计路由覆盖率与精确率。"""
    from agents import supervisor  # 复用线上同一个 supervisor，保证测的就是线上逻辑

    cases = ROUTE_CASES[:n_limit] if n_limit else ROUTE_CASES
    cov = exa = 0
    dist = {}
    detail = []
    for q, exp in cases:
        try:
            out = supervisor({"query": q})
            route = out.get("route", [])
        except Exception as e:  # 网络抖动不该让整轮评测挂掉
            print(f"[route] 调用失败，跳过: {e}")
            continue
        exp_set, rt_set = set(exp), set(route)
        ok_cov = exp_set.issubset(rt_set)
        ok_exa = exp_set == rt_set
        cov += 1 if ok_cov else 0
        exa += 1 if ok_exa else 0
        key = "+".join(sorted(rt_set)) or "EMPTY"
        dist[key] = dist.get(key, 0) + 1
        detail.append({
            "query": q, "expected": exp, "route": route,
            "coverage_ok": ok_cov, "exact_ok": ok_exa,
        })
    n = len(detail)
    if not n:
        return None
    return {
        "n": n,
        "coverage": round(cov / n, 4),      # 不漏：期望 worker 被覆盖
        "exact": round(exa / n, 4),         # 不多不少：路由集合完全一致
        "route_distribution": dist,
        "detail": detail,
    }


def _pct(samples, p):
    """线性插值分位数，样本少时比 numpy 除法更稳。"""
    if not samples:
        return None
    s = sorted(samples)
    if len(s) == 1:
        return round(s[0], 3)
    k = (len(s) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 3)


def eval_latency(chain, multi_fn, rag_queries, multi_queries):
    """端到端延迟（含云端 LLM 往返，非纯本地耗时，报告里会注明）。"""
    rag_t, multi_t = [], []
    for q in rag_queries:
        t0 = time.time()
        try:
            chain.invoke(q)
        except Exception:
            continue
        rag_t.append(time.time() - t0)
    for q in multi_queries:
        t0 = time.time()
        try:
            multi_fn(q)
        except Exception:
            continue
        multi_t.append(time.time() - t0)

    def pack(xs):
        if not xs:
            return None
        return {
            "n": len(xs),
            "p50": _pct(xs, 50),
            "p95": _pct(xs, 95),
            "mean": round(statistics.mean(xs), 3),
            "min": round(min(xs), 3),
            "max": round(max(xs), 3),
        }

    return {"rag_chain": pack(rag_t), "multi_agent": pack(multi_t)}


def main():
    global retriever  # 给 eval_split 用
    cases = load_evalset()
    adv = load_adversarial()
    emb = get_embeddings()
    vd = Chroma(persist_directory=CHROMA_DIR, embedding_function=emb)
    retriever = vd.as_retriever(
        search_type="mmr", search_kwargs={"k": TOP_K, "fetch_k": 20}
    )
    chain = build_qa()

    canon = eval_split(cases, lambda d: d.metadata.get("source_url"))
    advm = eval_split(adv, lambda d: d.metadata.get("source_url"))

    # 生成忠实度：对所有有 gt_url 的 case 抽 10 条测「引用 url 命中」；
    # 其中 gpa/lang 子类额外测「关键数值字段命中」（问学费/排名时本不该出现语言分）。
    faith_pool = [c for c in (cases + adv) if c.get("gt_url")]
    random.seed(7)
    samp = random.sample(faith_pool, min(10, len(faith_pool)))
    fu = 0
    field_cases = 0
    ff = 0
    detail = []
    for c in samp:
        ans = chain.invoke(c["query"]) or ""
        url_ok = c["gt_url"] in ans
        fu += 1 if url_ok else 0
        fv = [v for v in c.get("expected_fields", {}).values() if v]
        field_ok = None
        if fv:
            field_cases += 1
            field_ok = any(_norm(v) in _norm(ans) for v in fv)
            ff += 1 if field_ok else 0
        detail.append({
            "id": c["id"], "query": c["query"],
            "url_ok": url_ok, "field_ok": field_ok,
        })
    faith = {
        "n": len(samp),
        "citation_url_hit": round(fu / len(samp), 4),
        "key_field_hit": round(ff / field_cases, 4) if field_cases else None,
        "field_n": field_cases,
        "detail": detail,
    }

    # D. 路由准确率（多智能体独有）+ E. 端到端延迟
    from agents import ask_multi
    routing = eval_routing(None)
    latency = eval_latency(
        chain,
        ask_multi,
        [c["query"] for c in cases[:10]],   # RAG 单链 10 条
        [c["query"] for c in cases[:5]],    # 多智能体 5 条（链路更长，取样少些省时间）
    )

    # latency 下除了本轮测的 rag_chain / multi_agent，还可能有独立脚本写入的
    # topology_ab / retrieval（eval_topology.py）。这里合并而不是整体覆盖，
    # 免得重跑本脚本把那些字段冲掉。
    old_lat = {}
    if os.path.exists(METRICS):
        with open(METRICS, encoding="utf-8") as f:
            old_lat = json.load(f).get("latency", {})
    old_lat.update(latency)

    metrics = {
        "canonical": canon,
        "adversarial": advm,
        "faithfulness": faith,
        "routing": routing,
        "latency": old_lat,
    }
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("\n===== RAG 评测指标（StudyPath · 分层）=====")
    print(f"\n[A] 规范问法集 ({canon['n']} 条，KB 内已知院校 / 同源)")
    for k in [1, 3, 5, 8]:
        print(f"    HitRate@{k:<2}: {canon['hit_rate'][f'hit_rate@{k}']:.1%}")
    print(f"    MRR: {canon['mrr']:.4f}   Recall@8: {canon['recall@8']:.1%}")

    if advm:
        print(f"\n[B] 口语化对抗集 ({advm['n']} 条，模拟真实用户 / 泛化)")
        for k in [1, 3, 5, 8]:
            print(f"    HitRate@{k:<2}: {advm['hit_rate'][f'hit_rate@{k}']:.1%}")
        print(f"    MRR: {advm['mrr']:.4f}   Recall@8: {advm['recall@8']:.1%}")

    print(f"\n[C] 生成忠实度（抽 {faith['n']} 条真生成）")
    print(f"    引用正确 source_url 命中: {faith['citation_url_hit']:.1%}")
    print(f"    关键数值字段命中      : {faith['key_field_hit']:.1%}")

    if routing:
        print(f"\n[D] 路由准确率（Supervisor，{routing['n']} 条标注问题）")
        print(f"    覆盖率 coverage（不漏）  : {routing['coverage']:.1%}")
        print(f"    精确率 exact（不多不少） : {routing['exact']:.1%}")
        print(f"    路由分布: {routing['route_distribution']}")

    if latency:
        print(f"\n[E] 端到端延迟（含云端 LLM 往返）")
        for k, label in [("rag_chain", "RAG 单链   "), ("multi_agent", "多智能体链 ")]:
            m = latency.get(k)
            if m:
                print(f"    {label}: P50={m['p50']}s  P95={m['p95']}s  mean={m['mean']}s  (n={m['n']})")

    print(f"\n指标已写入: {METRICS}")


if __name__ == "__main__":
    main()
