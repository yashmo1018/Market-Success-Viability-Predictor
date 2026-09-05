"""Figure 1 v2 — polished system architecture pipeline (review copy).

Writes papers/figures/fig1_pipeline_v2.png for approval BEFORE replacing fig1.
Design: 5 tinted horizontal bands, uniform rounded cards with colored accent
borders, orthogonal + labeled cross-band arrows, bottom legend.

Run: python scripts/make_pipeline_diagram_v2.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "papers" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Palette (soft, modern) ──────────────────────────────────────────────
INK      = "#0F172A"
SUB      = "#64748B"
ARROW    = "#475569"
BANDS = {
    "data":  ("#EFF6FF", "#3B82F6", "#1D4ED8"),   # fill, border, band-strip
    "load":  ("#EEF2FF", "#6366F1", "#4338CA"),
    "llm":   ("#FAF5FF", "#A855F7", "#7E22CE"),
    "train": ("#FFFBEB", "#F59E0B", "#B45309"),
    "serve": ("#ECFDF5", "#10B981", "#047857"),
    "app":   ("#FFF1F2", "#F43F5E", "#BE123C"),
}

plt.rcParams.update({"font.family": "DejaVu Sans"})


def draw():
    fig, ax = plt.subplots(figsize=(15, 11.5))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 11.5)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # Band background strips (y0, height, tint-key, title)
    strips = [
        (9.55, 1.30, "data",  "A  ·  DATA ACQUISITION"),
        (8.05, 1.15, "load",  "B · CONTRACT"),
        (6.05, 1.55, "llm",   "C  ·  LLM ASPECT EXTRACTION"),
        (3.95, 1.65, "train", "D–F  ·  LABEL → FEATURES → TRAINING"),
        (1.70, 1.75, "serve", "G–H  ·  BRIDGING & SERVING"),
    ]
    for y0, h, key, title in strips:
        strip_color = BANDS[key][2]
        ax.add_patch(Rectangle((0.15, y0), 14.7, h, facecolor=BANDS[key][0],
                               edgecolor="none", alpha=0.35, zorder=0))
        ax.text(0.35, y0 + h - 0.16, title, fontsize=8.5, fontweight="bold",
                color=strip_color, va="top", ha="left", zorder=2)

    def card(x, y, w, h, title, sub, key, tfs=10.5, sfs=7.2):
        fill, border, _ = BANDS[key]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.11,rounding_size=0.14",
                     facecolor=fill, edgecolor=border, linewidth=1.9, zorder=3))
        ax.add_patch(Rectangle((x, y), 0.10, h, facecolor=border, edgecolor="none",
                     zorder=4))
        ax.text(x + w / 2 + 0.05, y + h / 2 + 0.14, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color=INK, zorder=5)
        ax.text(x + w / 2 + 0.05, y + h / 2 - 0.22, sub, ha="center", va="center",
                fontsize=sfs, color=SUB, style="italic", zorder=5)

    def arrow(p1, p2, label=None, dashed=False, color=ARROW, lw=2.0):
        ax.annotate("", xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                    linestyle="--" if dashed else "-",
                                    shrinkA=2, shrinkB=2), zorder=2)
        if label:
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            ax.text(mx + 0.12, my + 0.10, label, fontsize=6.6, color="#94A3B8",
                    ha="left", va="center", zorder=2)

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(7.5, 11.15, "System Architecture — Hybrid AI Product Success Predictor",
            ha="center", fontsize=15, fontweight="bold", color=INK)
    ax.text(7.5, 10.78, "Seven independently re-runnable stages, plus the serving layer",
            ha="center", fontsize=9.5, color=SUB)

    # ── Band A: data sources ────────────────────────────────────────────
    card(0.6,  9.75, 3.35, 0.85, "Amazon Reviews 2023",
         "6 categories · 732 products · 50K+ reviews", "data")
    card(4.15, 9.75, 3.35, 0.85, "Google Play Scraper",
         "4 categories · 319 apps · 24K+ reviews", "data")
    card(7.7,  9.75, 3.45, 0.85, "Reddit (Arctic Shift)",
         "1,089 buying-intent comments · 10 cats", "data")
    card(11.35, 9.75, 3.05, 0.85, "Fraud Filter",
         "burst / J-shape / dup → 71 excluded", "data")

    # ── Band B: loader ──────────────────────────────────────────────────
    card(2.1, 8.2, 4.6, 0.82, "Load & Verify Contract",
         "load_final.py · manifest.json · typed", "load")
    card(8.4, 8.2, 4.6, 0.82, "data/final/",
         "products · reviews · reddit · manifest", "load")

    arrow((2.28, 9.75), (2.28, 9.04))
    arrow((5.85, 9.75), (4.9, 9.04))
    arrow((9.4, 9.75), (10.3, 9.04))
    arrow((12.8, 9.75), (11.6, 9.04))
    arrow((6.7, 8.61), (8.4, 8.61))

    # ── Band C: extraction ──────────────────────────────────────────────
    card(0.6,  6.2, 3.15, 0.85, "Multi-Provider Pool",
         "Gemini Flash · Groq 70B · Ollama", "llm", tfs=10)
    card(3.95, 6.2, 3.55, 0.85, "Null-Forcing Prompt",
         "9 / 11 aspects · evidence-quoted", "llm", tfs=10)
    card(7.7,  6.2, 3.2, 0.85, "Pydantic Validation",
         "typed · retry · failover", "llm", tfs=10)
    card(11.1, 6.2, 3.3, 0.85, "aspect_scores.jsonl",
         "74K+ rows · crash-safe", "llm", tfs=9.5)

    arrow((4.6, 8.2), (2.28, 7.06), "reviews")
    arrow((3.75, 6.62), (3.95, 6.62))
    arrow((7.5, 6.62), (7.7, 6.62))
    arrow((10.9, 6.62), (11.1, 6.62))

    # ── Band D–F: training ──────────────────────────────────────────────
    card(0.6,  4.1, 2.75, 0.82, "Label Engineering",
         "within-cat composite · log1p", "train", tfs=9.5)
    card(3.55, 4.1, 2.95, 0.82, "Feature Assembly",
         "aspect means + rates + meta", "train", tfs=9.5)
    card(6.7,  4.1, 2.8, 0.82, "XGBoost 5-fold CV",
         "full + aspects-only · seed 42", "train", tfs=9.5)
    card(9.7,  4.1, 2.1, 0.82, "SHAP",
         "TreeExplainer", "train", tfs=9.5)
    card(12.0, 4.1, 2.4, 0.82, "Models",
         "xgb_*.json", "train", tfs=9.5)

    arrow((1.9, 6.2), (1.9, 4.92), "labels.json")
    arrow((11.6, 6.2), (5.0, 4.92), "features")
    arrow((3.35, 4.51), (3.55, 4.51))
    arrow((6.5, 4.51), (6.7, 4.51))
    arrow((9.5, 4.51), (9.7, 4.51))
    arrow((11.8, 4.51), (12.0, 4.51))

    # ── Band G–H: serving ───────────────────────────────────────────────
    card(0.6,  1.9, 2.75, 0.85, "Category Profiles",
         "price · pain points · strengths", "serve", tfs=9.5)
    card(3.55, 1.9, 3.15, 0.85, "Bridging Layer",
         "skeptic prompt v2 · Gemini Flash", "serve", tfs=9.5)
    card(6.9,  1.9, 2.75, 0.85, "Predictor",
         "viability ± 5 · SHAP risks", "serve", tfs=9.5)
    card(9.85, 1.9, 4.55, 0.85, "React + FastAPI App",
         "Simulator · Spec Coach · Analyzer · Trust Badges", "app", tfs=10)

    arrow((1.9, 4.1), (1.9, 2.75), "profiles")
    arrow((3.35, 2.32), (3.55, 2.32))
    arrow((6.7, 2.32), (6.9, 2.32))
    arrow((9.65, 2.32), (9.85, 2.32))
    arrow((13.2, 4.1), (13.2, 2.75), "loads models",
          color=BANDS["train"][1])
    # user input (dashed, upward into bridging)
    arrow((5.1, 1.35), (5.1, 1.9), "User: category + price + specs",
          dashed=True, color=BANDS["app"][1], lw=1.7)

    # ── Legend ──────────────────────────────────────────────────────────
    leg = [("data", "Data Acquisition"), ("load", "Contract Verification"),
           ("llm", "LLM Extraction"), ("train", "Training Pipeline"),
           ("serve", "Prediction Service"), ("app", "Application Layer")]
    for i, (key, label) in enumerate(leg):
        lx = 0.9 + i * 2.4
        ax.add_patch(FancyBboxPatch((lx, 0.5), 0.28, 0.19,
                     boxstyle="round,pad=0.02,rounding_size=0.04",
                     facecolor=BANDS[key][0], edgecolor=BANDS[key][1], linewidth=1.4))
        ax.text(lx + 0.38, 0.595, label, fontsize=6.8, va="center", color=INK)

    fig.savefig(OUT / "fig1_pipeline_v2.png", bbox_inches="tight", dpi=300,
                facecolor="white")
    plt.close(fig)
    print(f"Saved: {OUT / 'fig1_pipeline_v2.png'}")


if __name__ == "__main__":
    draw()
