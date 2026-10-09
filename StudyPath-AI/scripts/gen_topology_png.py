# -*- coding: utf-8 -*-
"""
重新生成 LangGraph 拓扑图（并行版），供答辩 PPT 使用。

输出：F:\\13.答辩材料\\ppt素材\\langgraph_topology.png
（覆盖前会把旧图备份为 langgraph_topology.png.bak-<日期>）

节点与连线严格对应 rag/agents.py 里 build_graph() 的真实拓扑：
    START -> supervisor -> {worker_school, worker_admission, worker_essay} -> synthesizer -> END
三个 worker 挂在 supervisor 的同一条出边上，属于同一个 superstep，并发执行。
"""
import shutil
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"F:\13.答辩材料\ppt素材\langgraph_topology.png")

# ---- 配色 ----
NAVY = "#1F4E79"
BLUE_BG = "#EAF1F8"
WORKER_BG = "#E8F4EC"
GREEN = "#2E7D52"
GRAY = "#6B7580"
GRAY_BG = "#F2F4F7"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, text, fc=BLUE_BG, ec=NAVY, fs=11, bold=True, tc="#12263A"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.03",
            linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=3,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal", color=tc, zorder=4)


def arrow(ax, x1, y1, x2, y2, color=NAVY, lw=1.6, style="-|>", ls="-"):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                        linestyle=ls, shrinkA=2, shrinkB=2,
                        connectionstyle="arc3,rad=0"),
        zorder=2,
    )


def main():
    if OUT.exists():
        bak = OUT.with_suffix(f".png.bak-{date.today().isoformat()}")
        shutil.copy2(OUT, bak)
        print(f"旧图已备份 -> {bak.name}")

    fig, ax = plt.subplots(figsize=(11.6, 2.9), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # ---- 节点坐标 ----
    H = 0.20
    sup_x, sup_w = 0.13, 0.155
    wk_x, wk_w = 0.405, 0.20
    syn_x, syn_w = 0.735, 0.145
    ys = [0.72, 0.40, 0.08]        # 三个 worker 的 y（自下往上数第 3/2/1 个）
    mid = ys[1] + H / 2            # supervisor / synthesizer 的垂直中心

    # START / END 圆点
    ax.add_patch(Circle((0.065, mid), 0.022, color=GRAY_BG, ec=GRAY, lw=1.4, zorder=3))
    ax.text(0.065, mid - 0.085, "__start__", ha="center", fontsize=7.5, color=GRAY)
    ax.add_patch(Circle((0.955, mid), 0.022, color=GRAY_BG, ec=GRAY, lw=1.4, zorder=3))
    ax.text(0.955, mid - 0.085, "__end__", ha="center", fontsize=7.5, color=GRAY)

    # 主节点
    box(ax, sup_x, mid - H / 2, sup_w, H, "supervisor\nLLM 智能路由")
    box(ax, syn_x, mid - H / 2, syn_w, H, "synthesizer\n汇总整合")

    labels = [
        ("worker_school\n院校项目库", "school_*"),
        ("worker_admission\n录取案例库", "admission_*"),
        ("worker_essay\n文书范例库", "essay_*"),
    ]
    for y, (label, _field) in zip(ys[::-1], labels):
        box(ax, wk_x, y, wk_w, H, label, fc=WORKER_BG, ec=GREEN, fs=10, tc="#123B27")

    # ---- 连线 ----
    arrow(ax, 0.087, mid, sup_x, mid)
    for y in ys:                                    # fan-out / fan-in
        arrow(ax, sup_x + sup_w, mid, wk_x, y + H / 2, color=GREEN)
        arrow(ax, wk_x + wk_w, y + H / 2, syn_x, mid, color=GREEN)
    arrow(ax, syn_x + syn_w, mid, 0.933, mid)

    # ---- 标注 ----
    ax.text((sup_x + sup_w + wk_x) / 2, 0.965, "并行 fan-out", ha="center",
            fontsize=9.5, color=GREEN, fontweight="bold")
    ax.text((wk_x + wk_w + syn_x) / 2, 0.965, "fan-in 汇合", ha="center",
            fontsize=9.5, color=GREEN, fontweight="bold")
    ax.text(wk_x + wk_w / 2, 0.008,
            "三个 worker 同属一个 superstep · LangGraph 并发执行 · 各写专属 State 字段，无同 key 竞态",
            ha="center", fontsize=8.2, color=GRAY)

    fig.tight_layout(pad=0.25)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    print(f"已生成 -> {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
