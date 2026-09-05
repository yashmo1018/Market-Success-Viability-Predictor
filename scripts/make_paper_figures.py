"""Generate the paper's analytical figures 2-5 from benchmark artifacts.

Restyled for a consistent, publication-grade look (muted palette, light grids,
direct value labels, CI bands). Output: papers/figures/fig{2..5}_*.png at 300 dpi.
Run: python scripts/make_paper_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "models/benchmarks"
OUT = ROOT / "papers/figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Shared house style ──────────────────────────────────────────────────
INK    = "#1D2733"
MUTED  = "#5B6470"
BLUE   = "#2166AC"
TEAL   = "#2A9D8F"
GREEN  = "#4C9F70"
AMBER  = "#E09F3E"
RED    = "#C1443C"
GRAYB  = "#9AA5B1"
GRID   = "#E6EAEE"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.labelsize": 9.5,
    "axes.labelcolor": INK,
    "axes.edgecolor": "#6B7480",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.axisbelow": True,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "figure.dpi": 300,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.bbox": "tight",
})


def _statbox(ax, text, loc="lower right"):
    x, ha = (0.97, "right") if "right" in loc else (0.03, "left")
    y, va = (0.05, "bottom") if "lower" in loc else (0.95, "top")
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va, fontsize=8,
            color=INK, bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                                 edgecolor="#CBD2D9", linewidth=0.8, alpha=0.95))


def fig2_holdout_scatter() -> None:
    df = pd.read_parquet(ROOT / "data/extracted/features_physical.parquet").set_index("product_uid")
    recs = [json.loads(l) for l in open(BENCH / "holdout_bridged.jsonl", encoding="utf-8") if l.strip()]
    recs = [r for r in recs if r["product_uid"] in df.index]
    v = np.array([r["viability"] for r in recs])
    s = np.array([float(df.at[r["product_uid"], "success_score"]) for r in recs])

    t = pd.DataFrame({"v": v, "s": s})
    t["tier"] = pd.qcut(t["s"], 5, labels=False, duplicates="drop")
    tier_mean_v = t.groupby("tier")["v"].mean()
    tier_mean_s = t.groupby("tier")["s"].mean()
    tier_sem_v = t.groupby("tier")["v"].sem()

    b, a = np.polyfit(s, v, 1)
    xs = np.linspace(s.min(), s.max(), 100)

    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    ax.scatter(s, v, s=30, alpha=0.45, color=BLUE, edgecolors="white",
               linewidths=0.6, label="Holdout product ($n{=}59$)", zorder=3)
    ax.plot(xs, a + b * xs, color=GRAYB, lw=1.4, ls="--", zorder=2, label="OLS trend")
    ax.errorbar(tier_mean_s, tier_mean_v, yerr=tier_sem_v, fmt="o-", color=RED,
                markersize=7, linewidth=2.0, capsize=3, elinewidth=1.2,
                label="Success-quintile mean ±SEM", zorder=4)
    ax.set_xlabel("Actual market success score (from subsequent reviews)")
    ax.set_ylabel("Specs-only predicted viability")
    ax.set_title("Pre-registered holdout: launch-blind prediction vs. reality")
    _statbox(ax, r"$\rho = 0.317$   95% CI [0.06, 0.54]" + "\n" + r"AUC $= 0.743$   $p = 0.014$",
             loc="lower right")
    ax.legend(frameon=False, fontsize=7.6, loc="upper left")
    fig.savefig(OUT / "fig2_holdout_scatter.png")
    plt.close(fig)
    print("fig2_holdout_scatter.png")


def fig3_aspect_validity() -> None:
    data = json.loads((ROOT / "models/bridging_validity.json").read_text(encoding="utf-8"))["aspects"]
    order = sorted(data.items(), key=lambda kv: kv[1]["r"])
    names = [k.replace("_", " ") for k, _ in order]
    r = np.array([v["r"] for _, v in order])
    lo = np.array([v["ci"][0] for _, v in order])
    hi = np.array([v["ci"][1] for _, v in order])
    badge = [v["badge"] for _, v in order]
    cmap = {"STRONG": GREEN, "MODERATE": AMBER}
    colors = [cmap.get(b, GRAYB) for b in badge]

    fig, ax = plt.subplots(figsize=(5.8, 4.0))
    y = np.arange(len(names))
    ax.barh(y, r, color=colors, height=0.66, zorder=3, edgecolor="white", linewidth=0.5)
    ax.errorbar(r, y, xerr=[r - lo, hi - r], fmt="none", ecolor="#3A424B",
                elinewidth=1.0, capsize=2.5, zorder=4)
    ax.axvline(0, color="#3A424B", linewidth=1.0, zorder=2)
    for yi, ri in zip(y, r):
        ax.text(ri + (0.012 if ri >= 0 else -0.012), yi, f"{ri:.2f}",
                va="center", ha="left" if ri >= 0 else "right", fontsize=7.5, color=INK)
    ax.set_yticks(y, names)
    ax.set_xlabel("Correlation $r$ with review-derived truth (95% CI)")
    ax.set_title("Which aspects can be estimated from a specification?")
    ax.set_xlim(-0.28, 0.72)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, AMBER, GRAYB)]
    ax.legend(handles, ["STRONG", "MODERATE", "NO SIGNAL"], frameon=False,
              fontsize=8, loc="lower right", title="Trust tier shown to users",
              title_fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.savefig(OUT / "fig3_aspect_validity.png")
    plt.close(fig)
    print("fig3_aspect_validity.png")


def fig4_prompt_comparison() -> None:
    e = json.loads((BENCH / "prompt_comparison.json").read_text(encoding="utf-8"))["end_to_end"]
    labels = ["v1\ntrusting", "v2\nskeptic", "v2 + shrinkage\nrejected"]
    rho = [e["v1"]["rho"], e["v2"]["rho"], e["shrunk"]["rho"]]
    auc = [e["v1"]["auc"], e["v2"]["auc"], e["shrunk"]["auc"]]
    colors = [GRAYB, BLUE, RED]

    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.2))
    for ax, vals, name, base, blabel in (
        (axes[0], rho, r"Spearman $\rho$", 0.0, "no signal"),
        (axes[1], auc, "Flop-vs-top AUC", 0.5, "chance"),
    ):
        bars = ax.bar(labels, vals, color=colors, width=0.62, zorder=3,
                      edgecolor="white", linewidth=0.6)
        ax.axhline(base, color="#3A424B", lw=0.9, ls=":")
        ax.text(2.42, base + 0.004, blabel, fontsize=6.8, color=MUTED, ha="right", va="bottom")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.3f}",
                    ha="center", fontsize=8, color=INK, fontweight="bold")
        ax.set_title(name, fontsize=10)
        ax.tick_params(axis="x", labelsize=7.2)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylim(0, max(rho) * 1.25)
    axes[1].set_ylim(0.5, max(auc) * 1.06)
    fig.suptitle("Ablation: the prompt decides the signal (same 89 products)",
                 fontsize=11, fontweight="bold", color=INK, y=1.04)
    fig.savefig(OUT / "fig4_prompt_ablation.png")
    plt.close(fig)
    print("fig4_prompt_ablation.png")


def fig5_app_targets() -> None:
    res = json.loads((BENCH / "app_target_experiment.json").read_text(encoding="utf-8"))["results"]
    pretty = {"composite_success (current, FAILED)": "composite\nsuccess",
              "avg_rating (pure quality)": "average\nrating",
              "retention_proxy (engagement)": "retention\nproxy",
              "install_norm (pure distribution)": "install\ncount",
              "velocity_norm (distribution)": "review\nvelocity"}
    names = [pretty[k] for k in res]
    r2 = [v["cv_r2"] for v in res.values()]
    colors = [RED if v < 0.35 else GREEN for v in r2]

    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    bars = ax.bar(names, r2, color=colors, width=0.62, zorder=3,
                  edgecolor="white", linewidth=0.6)
    ax.axhline(0.35, color=INK, lw=1.2, ls="--", zorder=2)
    ax.text(len(names) - 0.45, 0.362, "acceptance gate  $R^2 = 0.35$",
            fontsize=8, ha="right", color=INK, fontweight="bold")
    ax.axhline(0, color="#3A424B", lw=0.9)
    for b, v in zip(bars, r2):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.012 if v >= 0 else -0.028),
                f"{v:.3f}", ha="center", fontsize=8, color=INK, fontweight="bold")
    ax.set_ylabel("Aspects-only CV $R^2$   ($n = 319$ apps)")
    ax.set_ylim(min(min(r2) - 0.05, -0.05), 0.45)
    ax.set_title("Negative result: no app outcome is learnable from review aspects")
    ax.grid(axis="x", visible=False)
    fig.savefig(OUT / "fig5_app_target_sweep.png")
    plt.close(fig)
    print("fig5_app_target_sweep.png")


if __name__ == "__main__":
    fig2_holdout_scatter()
    fig3_aspect_validity()
    fig4_prompt_comparison()
    fig5_app_targets()
    print("Done: figs 2-5 restyled.")
