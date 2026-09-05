"""Restyle algorithm-comparison figures 7-10 from the saved benchmark JSON.

Reads models/benchmarks/algorithm_comparison.json (produced by
ml_algorithm_comparison.py) and regenerates figs 7-10 in the shared house
style, without re-training. Run: python scripts/make_algo_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "models/benchmarks"
OUT = ROOT / "papers/figures"
OUT.mkdir(parents=True, exist_ok=True)

INK    = "#1D2733"
MUTED  = "#5B6470"
BLUE   = "#2166AC"
NAVY   = "#274060"
TEAL   = "#2A9D8F"
GREEN  = "#4C9F70"
AMBER  = "#E09F3E"
PURPLE = "#7D5BA6"
RED    = "#C1443C"
ROSE   = "#B5445A"
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

results = json.loads((BENCH / "algorithm_comparison.json").read_text(encoding="utf-8"))
NAMES = list(results.keys())
SHORT = {n: n.replace(" Regression", "").replace(" Regressor", "").replace(" (RBF)", "")
         for n in NAMES}


def fig7_metrics() -> None:
    metrics = ["r2", "accuracy", "precision", "recall", "f1", "auc_roc", "mcc"]
    labels = ["R²", "Accuracy", "Precision", "Recall", "F1", "AUC-ROC", "MCC"]
    colors = [BLUE, NAVY, GREEN, AMBER, TEAL, PURPLE, ROSE]

    fig, ax = plt.subplots(figsize=(11, 5.2))
    x = np.arange(len(NAMES))
    w = 0.115
    offs = np.arange(len(metrics)) - len(metrics) / 2 + 0.5

    for i, (m, lab, c) in enumerate(zip(metrics, labels, colors)):
        vals = [results[n][m] for n in NAMES]
        bars = ax.bar(x + offs[i] * w, vals, w, label=lab, color=c, zorder=3,
                      edgecolor="white", linewidth=0.4)
        for b, v in zip(bars, vals):
            if abs(v) > 0.05:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.012,
                        f"{v:.2f}", ha="center", va="bottom", fontsize=5.4,
                        rotation=90, color=MUTED)
    ax.set_xticks(x, [SHORT[n].replace(" ", "\n") for n in NAMES], fontsize=9)
    ax.set_ylabel("Score")
    ax.set_ylim(-0.03, 1.20)
    ax.axhline(0, color="#3A424B", lw=0.8)
    ax.text(0.5, 1.13, "Algorithm comparison across all evaluation metrics",
            transform=ax.transAxes, ha="center", fontsize=12.5, fontweight="bold", color=INK)
    ax.text(0.5, 1.075, "Aspects-only features · 5-fold CV · physical products ($n = 732$)",
            transform=ax.transAxes, ha="center", fontsize=8.5, color=MUTED)
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncol=7,
              columnspacing=0.9, handlelength=1.1, bbox_to_anchor=(0.5, 1.03))
    ax.grid(axis="x", visible=False)
    fig.savefig(OUT / "fig7_algorithm_metrics.png")
    plt.close(fig)
    print("fig7_algorithm_metrics.png")


def _hbar_panel(ax, vals, title, xlabel, best="max", fmt="{:.3f}", pad=0.012,
                show_labels=True):
    ys = np.arange(len(NAMES))
    best_v = max(vals) if best == "max" else min(vals)
    colors = [GREEN if v == best_v else GRAYB for v in vals]
    bars = ax.barh(ys, vals, color=colors, height=0.62, zorder=3,
                   edgecolor="white", linewidth=0.5)
    if show_labels:
        ax.set_yticks(ys, [SHORT[n] for n in NAMES], fontsize=8.5)
    else:
        ax.set_yticks(ys, [])
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)
    span = (max(vals) - min(0, min(vals))) or 1
    ax.set_xlim(0, max(vals) * 1.16)
    for b, v in zip(bars, vals):
        ax.text(v + span * pad, b.get_y() + b.get_height() / 2, fmt.format(v),
                va="center", fontsize=7.8, color=INK)
    ax.grid(axis="y", visible=False)


def fig8_tradeoffs() -> None:
    r2 = [results[n]["r2"] for n in NAMES]
    times = [results[n]["train_time_s"] for n in NAMES]
    rmse = [results[n]["rmse"] for n in NAMES]

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9),
                             gridspec_kw={"wspace": 0.12})
    _hbar_panel(axes[0], r2, "Predictive accuracy", "R²  (higher is better)",
                best="max", show_labels=True)
    _hbar_panel(axes[1], times, "Training efficiency", "Mean training time, s (lower is better)",
                best="min", fmt="{:.2f}s", show_labels=False)
    _hbar_panel(axes[2], rmse, "Error magnitude", "RMSE  (lower is better)",
                best="min", fmt="{:.1f}", show_labels=False)
    fig.suptitle("Why XGBoost: accuracy, efficiency, and error across six algorithms",
                 fontsize=12, fontweight="bold", color=INK, y=1.02)
    fig.savefig(OUT / "fig8_algorithm_tradeoffs.png")
    plt.close(fig)
    print("fig8_algorithm_tradeoffs.png")


def fig10_confusion() -> None:
    n = len(NAMES)
    fig, axes = plt.subplots(1, n, figsize=(2.7 * n, 3.0))
    if n == 1:
        axes = [axes]
    cm_labels = ["Flop", "Hit"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("bl", ["#F2F6FA", BLUE])

    for ax, name in zip(axes, NAMES):
        cm = np.array(results[name]["confusion_matrix"])
        pct = cm.astype(float) / cm.sum() * 100
        ax.imshow(pct, cmap=cmap, vmin=0, vmax=60)
        for i in range(2):
            for j in range(2):
                col = "white" if pct[i, j] > 33 else INK
                ax.text(j, i, f"{cm[i, j]}\n{pct[i, j]:.1f}%", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=col)
        ax.set_xticks([0, 1], cm_labels, fontsize=8)
        ax.set_yticks([0, 1], cm_labels, fontsize=8)
        ax.set_xlabel("Predicted", fontsize=8)
        if ax is axes[0]:
            ax.set_ylabel("Actual", fontsize=8)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        ax.grid(False)
        ax.set_title(f"{SHORT[name]}\nacc {results[name]['accuracy']:.1%}", fontsize=9, pad=6)
    fig.suptitle("Aggregated confusion matrices (5-fold CV · top-20% vs. bottom-20%)",
                 fontsize=11, fontweight="bold", color=INK, y=1.05)
    fig.savefig(OUT / "fig10_confusion_matrices.png")
    plt.close(fig)
    print("fig10_confusion_matrices.png")


if __name__ == "__main__":
    fig7_metrics()
    fig8_tradeoffs()
    fig10_confusion()
    print("Done: figs 7, 8, 10 restyled.")
