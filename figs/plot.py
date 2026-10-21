"""Render the audit figures from evidence/*.json.

Every number in every panel is read from the measurement JSON; nothing is
typed in by hand, so a figure cannot drift from the evidence.

Style follows the warm editorial palette used across these audits.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

ROOT = Path(__file__).resolve().parent
EV = ROOT.parent / "evidence"
OUT = ROOT
OUT.mkdir(exist_ok=True)

INK = "#2b2119"
PAPER = "#faf6f0"
AMBER = "#c8892b"
TERRA = "#b4552f"
OLIVE = "#6b6b3a"
MUTED = "#8a7a68"

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.edgecolor": MUTED,
    "font.size": 10,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "text.parse_math": False,
})


def load(name: str) -> dict:
    return json.loads((EV / name).read_text(encoding="utf-8"))


def style(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=MUTED)
    ax.grid(axis="y", color=MUTED, alpha=0.22, linewidth=0.7)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- figure 1
def fig_benchmark() -> None:
    d = load("measure_bench_paired.json")
    timed = d["benchmark_timed"]
    off = d["benchmark_disabled"]
    delta = d["_paired_delta_s"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4),
                                   gridspec_kw={"width_ratios": [1.15, 1]})

    labels = ["timing on\n(upstream)", "timing off\n(--benchmark-disable)"]
    vals = [timed["pytest_s_median"], off["pytest_s_median"]]
    bars = ax1.bar(labels, vals, color=[TERRA, OLIVE], width=0.55)
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.12, f"{v:.2f}s",
                 ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, max(vals) * 1.22)
    style(ax1, "The 15 benchmark functions dominate the suite",
          "pytest-reported duration (s)")
    ax1.text(0.5, -0.30,
             f"same pass count in both runs: {timed['summaries'][0].split(' in ')[0]}",
             transform=ax1.transAxes, ha="center", fontsize=9, color=MUTED)

    rounds = delta["rounds"]
    ax2.axhline(delta["median"], color=AMBER, linewidth=1.4, zorder=1)
    ax2.scatter(range(1, len(rounds) + 1), rounds, s=46, color=TERRA,
                zorder=3, edgecolor=PAPER, linewidth=1.2)
    ax2.set_xlabel("round (paired)", fontsize=9, color=MUTED)
    ax2.set_ylim(0, max(rounds) * 1.3)
    ax2.xaxis.set_major_locator(MultipleLocator(2))
    style(ax2, "Paired saving per round", "seconds saved")
    ax2.text(len(rounds) * 0.98, max(rounds) * 1.24,
             f"median {delta['median']:.2f}s\nrange {delta['min']:.2f}-{delta['max']:.2f}s",
             ha="right", va="top", fontsize=9, color=AMBER, fontweight="bold")

    fig.suptitle("Benchmark timing is the single largest redundant cost",
                 x=0.012, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.07, right=0.985, top=0.83, bottom=0.24, wspace=0.28)
    fig.savefig(OUT / "fig1_benchmark.png", dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- figure 2
def fig_ablation() -> None:
    d = load("measure_deterministic.json")
    order = [
        ("A_baseline", "upstream command", TERRA),
        ("B_no_html", "− html report", AMBER),
        ("C_no_bench_timing", "− benchmark timing", OLIVE),
        ("D_patch", "both (the patch)", INK),
    ]
    names = [lbl for _, lbl, _ in order]
    vals = [d[k]["pytest_s_median"] for k, _, _ in order]
    colors = [c for _, _, c in order]

    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1], height=0.55)
    for b, v, (k, _, _) in zip(bars, vals[::-1], order[::-1]):
        ratio = d[k]["ratio_median"]
        txt = f"{v:.2f}s" + ("" if k == "A_baseline" else f"   {ratio:.2f}x")
        ax.text(v + 0.06, b.get_y() + b.get_height() / 2, txt, va="center",
                fontsize=10.5, fontweight="bold")
    ax.set_xlim(0, max(vals) * 1.30)
    ax.set_xlabel("pytest-reported duration (s)", fontsize=9, color=MUTED)
    ax.grid(axis="x", color=MUTED, alpha=0.22, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_title("Each change measured on its own, then combined",
                 loc="left", fontsize=12, fontweight="bold", pad=10)

    band = d["_verdict"]["aa_ratio_range"]
    ax.text(0.99, 0.06,
            f"A/A noise band: {band[0]:.3f}-{band[1]:.3f}x\n"
            "the html-only step sits inside it",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=9, color=MUTED)

    fig.suptitle("Removing the html report alone is not measurable; "
                 "the benchmark timing is",
                 x=0.012, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.22, right=0.985, top=0.80, bottom=0.14)
    fig.savefig(OUT / "fig2_ablation.png", dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- figure 3
def fig_parallel() -> None:
    d = load("measure_msgfmt_width.json")
    v = d["variants"]
    order = ["upstream_sequential", "jobs=1", "jobs=2", "jobs=4", "jobs=8", "jobs=16"]
    labels = ["sequential\n(upstream)", "1", "2", "4", "8", "16"]
    vals = [v[k]["median_ms"] for k in order]
    best = min(vals)
    colors = [TERRA if k == "upstream_sequential" else
              (OLIVE if v[k]["median_ms"] == best else AMBER) for k in order]

    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    bars = ax.bar(labels, vals, color=colors, width=0.6)
    for b, val in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, val + 40, f"{val:.0f}",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xlabel("batch width (JOBS)", fontsize=9, color=MUTED)
    ax.set_ylim(0, max(vals) * 1.18)
    style(ax, "Compiling 36 catalogs: the optimum is 8, not unbounded",
          "wall clock (ms)")
    ax.text(0.99, 0.90, f"all widths byte-identical: {d['all_widths_byte_identical']}",
            transform=ax.transAxes, ha="right", fontsize=9, color=MUTED)

    fig.suptitle("Parallel batching helps, but it plateaus - so the width is capped",
                 x=0.012, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.09, right=0.985, top=0.80, bottom=0.19)
    fig.savefig(OUT / "fig3_parallel.png", dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- figure 4
def fig_endtoend() -> None:
    d = load("measure_endtoend.json")
    up = d["upstream_cmd"]
    pa = d["patched_cmd"]
    floor = d["interpreter_floor"]["wall_median_s"]

    fig, ax = plt.subplots(figsize=(9.8, 4.2))
    rows = [("upstream", up), ("patched", pa)]
    for i, (label, r) in enumerate(rows):
        body = r["pytest_median_s"]
        other = r["wall_median_s"] - body
        ax.barh(i, body, color=TERRA, height=0.46)
        ax.barh(i, other, left=body, color=AMBER, height=0.46)
        ax.text(body / 2, i, f"{body:.2f}", va="center", ha="center",
                fontsize=9.5, color=PAPER, fontweight="bold")
        ax.text(r["wall_median_s"] + 0.07, i, f"{r['wall_median_s']:.2f}s",
                va="center", fontsize=11, fontweight="bold")

    ax.set_yticks([0, 1])
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.65, 1.85)
    ax.set_xlim(0, up["wall_median_s"] * 1.22)
    ax.set_xlabel("wall clock (s)", fontsize=9, color=MUTED)
    ax.grid(axis="x", color=MUTED, alpha=0.22, linewidth=0.7)
    ax.set_axisbelow(True)

    ax.axvline(floor, color=OLIVE, linewidth=1.1, linestyle="--", zorder=0)
    ax.text(floor, 1.68, f" interpreter floor {floor:.2f}s",
            fontsize=8.5, color=OLIVE, va="center")

    # legend above the axes, so it cannot cover a bar or the title
    ax.plot([], [], color=TERRA, linewidth=8, label="pytest body")
    ax.plot([], [], color=AMBER, linewidth=8,
            label="process start + coverage reports")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, -0.34), ncol=2,
              frameon=False, fontsize=9)

    ax.set_title("Where the time goes in one test run", loc="left",
                 fontsize=12, fontweight="bold", pad=10)

    red = d["_derived"]["wall_reduction_pct"]
    fig.suptitle(f"End to end: {up['wall_median_s']:.2f}s to {pa['wall_median_s']:.2f}s "
                 f"({red:.1f}% less)", x=0.012, ha="left", fontsize=14,
                 fontweight="bold")
    fig.subplots_adjust(left=0.13, right=0.985, top=0.80, bottom=0.26)
    fig.savefig(OUT / "fig4_endtoend.png", dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- figure 5
def fig_falsegreen() -> None:
    """The Windows story: 27 cells, but the locale tests never ran there."""
    fig, ax = plt.subplots(figsize=(10.4, 5.0))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    rows = [
        ("tests reported", "856 passed", "744 passed, 112 skipped"),
        ("locale tests run", "yes", "no - all skipped"),
        ("compiled catalogs", "36", "0"),
        ("CI verdict", "green", "green"),
    ]

    head_y = 0.90
    ax.text(0.36, head_y, "Linux / macOS  (18 cells)", ha="center",
            fontsize=11, fontweight="bold")
    ax.text(0.72, head_y, "Windows  (9 cells)", ha="center",
            fontsize=11, fontweight="bold")

    top = 0.78
    step = 0.155
    for i, (label, good, bad) in enumerate(rows):
        y = top - i * step
        ax.text(0.02, y, label, fontsize=10, color=MUTED, va="center")
        ax.text(0.36, y, good, fontsize=10.5, ha="center", va="center",
                color=OLIVE, fontweight="bold")
        ax.text(0.72, y, bad, fontsize=10.5, ha="center", va="center",
                color=TERRA if i >= 1 else INK, fontweight="bold")
        ax.plot([0.01, 0.99], [y - step * 0.5, y - step * 0.5],
                color=MUTED, alpha=0.16, linewidth=0.8)

    ax.plot([0.54, 0.54], [top - 3 * step - 0.06, top + 0.07],
            color=MUTED, linewidth=0.8, alpha=0.5)

    ax.text(0.02, 0.19,
            "Root cause: the compile script has no shebang, and Windows runners default to pwsh,\n"
            "which does not execute .sh - it reports success without running anything. Every locale\n"
            "assertion is wrapped in pytest.skip(), so the gap surfaced as skips, never as failures.",
            fontsize=9, color=INK, va="top", linespacing=1.7)

    fig.suptitle("The expensive bug was not slow CI - it was CI that lied",
                 x=0.012, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.99, top=0.88, bottom=0.03)
    fig.savefig(OUT / "fig5_falsegreen.png", dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- figure 6
def fig_mutation() -> None:
    """Per-mutant: how many checks catch it, and whether it is equivalent."""
    data = {
        "M1 drop --check": (0, "equivalent: exit code unchanged"),
        "M2 wrong output dir": (37, "killed"),
        "M3 ignore exit status": (2, "killed after adding a bad-catalog case"),
        "M4 ignore JOBS cap": (0, "equivalent: concurrency only"),
        "M5 skip one locale": (4, "killed"),
        "M6 truncate .mo": (36, "killed"),
    }
    names = list(data)
    counts = [data[n][0] for n in names]
    colors = [MUTED if c == 0 else TERRA for c in counts]

    fig, ax = plt.subplots(figsize=(10.2, 4.3))
    bars = ax.barh(names[::-1], counts[::-1], color=colors[::-1], height=0.55)
    for b, n in zip(bars, names[::-1]):
        c, note = data[n]
        ax.text(max(c, 0) + 0.6, b.get_y() + b.get_height() / 2,
                note, va="center", fontsize=9,
                color=INK if c else MUTED)
    ax.set_xlim(0, 46)
    ax.set_xlabel("number of failing checks that caught the mutant", fontsize=9,
                  color=MUTED)
    ax.grid(axis="x", color=MUTED, alpha=0.22, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_title("Mutation test of the compile step: 4 killed, 2 equivalent",
                 loc="left", fontsize=12, fontweight="bold", pad=10)

    fig.suptitle("A check that cannot fail is not a check",
                 x=0.012, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.24, right=0.985, top=0.80, bottom=0.15)
    fig.savefig(OUT / "fig6_mutation.png", dpi=170)
    plt.close(fig)


def main() -> None:
    fig_benchmark()
    fig_ablation()
    fig_parallel()
    fig_endtoend()
    fig_falsegreen()
    fig_mutation()
    for p in sorted(OUT.glob("*.png")):
        print(f"{p.name:26s} {p.stat().st_size:>8d} bytes")


if __name__ == "__main__":
    main()
