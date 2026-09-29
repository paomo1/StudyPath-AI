# -*- coding: utf-8 -*-
"""
query_norm.py — 查询侧学校别名归一化（Query Rewriting 的最小可用版）。

背景（真实问题驱动，不是纸上谈兵）：
  建库时 data_loader.load_schools() 会把 _SCHOOL_ALIAS 的别名拼到文档开头，例如
      "Imperial（帝国理工学院）（Imperial College London） 的 计算机硕士 项目..."
  但**用户侧的 query 没做同样的归一化**。于是评测里出现真实 MISS：
      query = "我想申 Imperial 的计算机硕士，GPA 大概要多少"
  裸别名 "Imperial" 与文档里的 "帝国理工学院 / Imperial College London" 语义距离不够近，
  在 MMR(fetch_k=20) 阶段被挤出 Top-8 → HitRate 掉到 93.3%（15 条中 1 条 miss）。

做什么：
  把 query 里出现的学校别名/简称/中文口语名，改写成「库内文档前缀同款」的写法：
      "Imperial"  -> "Imperial（帝国理工学院）Imperial College London"
  这样 embedding 与文档前缀高度对齐，召回稳定。

设计取舍（答辩能讲）：
  - 纯规则 + 词典，**零 LLM 调用、零额外延迟**（对比：用 LLM 做 query rewriting 每次多 ~1s，
    对 100 条的小库属于过度设计）。
  - 词典**从 xlsx 院校库动态构建**，不是硬编码校名 —— 库里加学校自动生效。
  - 命中不到就原样返回，绝不改写用户语义（不做同义扩展，避免引入幻觉）。
"""
import re

import openpyxl

from config import XLSX_PATH, SHEET_SCHOOLS
from data_loader import _SCHOOL_ALIAS

# 库里没有、但真实用户常挂嘴边的口语叫法（-> _SCHOOL_ALIAS 的 key）
_CN_SLANG = {
    "卡梅": "carnegie mellon university",
    "新国立": "national university of singapore",
    "坡县": "national university of singapore",
    "香槟": "university of illinois urbana-champaign",
    "uiuc": "university of illinois urbana-champaign",
    "港城大": "city university of hong kong",
    "城大": "city university of hong kong",
    "首尔大": "seoul national university",
    "东大": "the university of tokyo",
    "港大": "the university of hong kong",
    "港理工": "the hong kong polytechnic university",
    "南洋理工": "nanyang technological university",
    "南加大": "university of southern california",
    "密歇根": "university of michigan",
    "德州奥斯汀": "the university of texas at austin",
}

_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")  # 去掉 "University of California, Irvine (UCI)" 的尾部
_CJK = re.compile(r"[\u4e00-\u9fff]")

_index = None  # {token_lower: canonical_str}


def _build_index():
    """从院校库真实 school_name 反查别名表，构建 token -> 规范化写法的映射。

    注意：xlsx 里很多校名带括号后缀（如 "Northeastern University (Align)"），
    直接拿它查 _SCHOOL_ALIAS 会失配，所以先剥后缀再查。
    """
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_SCHOOLS]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    idx = {}
    bare2canon = {}  # 英文全名(小写, 已剥后缀) -> 规范化写法，供口语别名精确挂载

    for r in rows[1:]:
        if not r or not r[0]:
            continue
        d = dict(zip(header, r))
        school = str(d.get("school_name") or "").strip()
        if not school:
            continue
        bare = _SUFFIX_RE.sub("", school).strip()
        alias_val = _SCHOOL_ALIAS.get(bare.lower(), "")  # 形如 "Imperial（帝国理工学院）"
        # 与 data_loader 生成的文档前缀保持一致：alias（school）
        canonical = f"{alias_val}{school}" if alias_val else school
        bare2canon[bare.lower()] = canonical

        tokens = {school.lower(), bare.lower()}
        if alias_val:
            short = alias_val.split("（")[0]                 # "Imperial"
            cn = alias_val.split("（")[-1].rstrip("）")       # "帝国理工学院"
            tokens.add(short.lower())
            tokens.add(cn)
            tokens.add(cn.replace("大学", ""))               # "帝国理工"
        for t in tokens:
            if len(t) >= 2:
                idx[t] = canonical

    # 口语别名：按英文全名**精确**挂载，避免 "the university of ..." 前缀误配到别的学校
    for slang, en_key in _CN_SLANG.items():
        canon = bare2canon.get(en_key.lower())
        if canon:
            idx[slang] = canon
    return idx


def _get_index():
    global _index
    if _index is None:
        _index = _build_index()
    return _index


def normalize_query(q: str) -> str:
    """把 query 里的学校别名改写成库内文档前缀同款写法；命中不到原样返回。

    策略：按 token 长度降序、只替换**最长的一个命中**（一次查询通常只涉及一所学校），
    避免 "UW" 这类短别名误伤普通英文单词。
    """
    if not q:
        return q
    idx = _get_index()
    ql = q.lower()
    best = None  # (token_len, token, canonical)
    for token, canon in idx.items():
        if token in ql:
            if best is None or len(token) > best[0]:
                best = (len(token), token, canon)
    if not best:
        return q
    _, token, canon = best
    # 英文 token 要求词边界；中文直接子串替换。统一忽略大小写（用户可能写 Imperial / IMPERIAL）
    if _CJK.search(token):
        pattern = re.escape(token)
        new_q, n = re.subn(pattern, canon, q, count=1)
    else:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
        new_q, n = re.subn(pattern, canon, q, count=1, flags=re.IGNORECASE)
    return new_q if n else q


if __name__ == "__main__":
    tests = [
        "我想申 Imperial 的计算机硕士，GPA 大概要多少",
        "卡梅 cs 硕士申请截止什么时候",
        "港大 计算机研究生一年学费多少",
        "Northeastern University (Align) cs 好申吗",
        "Durham University 计算机专业排名怎么样",
        "CMU 的 AI 硕士雅思得几分",
        "今天天气怎么样",
    ]
    for t in tests:
        print(f"{t}\n  -> {normalize_query(t)}\n")
