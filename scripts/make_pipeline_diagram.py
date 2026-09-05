"""Generate the pipeline architecture diagram (fig1) from the actual codebase.

Current architecture (7 stages + serving layer):
  A. Data Acquisition: Amazon Reviews 2023 + Google Play + Reddit (Arctic Shift)
  B. Loading & Contract Verification (load_final.py)
  C. LLM Aspect Extraction (batch_extractor.py, multi-provider pool)
  D. Label Engineering (label_engineering.py)
  E. Feature Assembly (feature_builder.py)
  F. XGBoost Training + SHAP (run_training.py)
  G. Category Profiling (category_profiler.py)
  H. Bridging + Prediction (bridging_layer.py, predictor.py)
  I. Application Layer: React + FastAPI + Spec Coach

Run: python scripts/make_pipeline_diagram.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "papers" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Color palette ───────────────────────────────────────────────────────
BG          = "#FAFAFA"
DATA_SRC    = "#DBEAFE"   # blue-100
DATA_BORDER = "#3B82F6"   # blue-500
LOAD_BG     = "#E0E7FF"   # indigo-100
LOAD_BORDER = "#6366F1"   # indigo-500
LLM_BG      = "#F3E8FF"   # purple-100
LLM_BORDER  = "#A855F7"   # purple-500
TRAIN_BG    = "#FEF3C7"   # amber-100
TRAIN_BORDER= "#F59E0B"   # amber-500
PRED_BG     = "#D1FAE5"   # emerald-100
PRED_BORDER = "#10B981"   # emerald-500
APP_BG      = "#FFE4E6"   # rose-100
APP_BORDER  = "#F43F5E"   # rose-500
ARROW_CLR   = "#334155"   # slate-700
TEXT_DARK   = "#0F172A"


def draw():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    def box(x, y, w, h, label, sublabel, bg, border, fontsize=10, sublabel_size=7):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                              facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2 + 0.12, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color=TEXT_DARK)
        if sublabel:
            ax.text(x + w / 2, y + h / 2 - 0.2, sublabel, ha="center", va="center",
                    fontsize=sublabel_size, color="#475569", style="italic")

    def arrow(x1, y1, x2, y2, label=None, color=ARROW_CLR):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color,
                                    lw=1.8, connectionstyle="arc3,rad=0"))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx + 0.15, my + 0.12, label, fontsize=6.5,
                    color="#64748B", ha="left", va="center")

    def section_label(x, y, text, color):
        ax.text(x, y, text, fontsize=8, fontweight="bold", color=color,
                ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor=color, linewidth=1.2, alpha=0.9))

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(8, 10.6, "System Architecture: Hybrid AI Product Success Predictor",
            ha="center", va="center", fontsize=14, fontweight="bold", color=TEXT_DARK)
    ax.text(8, 10.25, "Seven independently re-runnable stages + serving layer",
            ha="center", va="center", fontsize=9, color="#64748B")

    # ═══════════════════════════════════════════════════════════════════
    # ROW 1: Data Sources (y ≈ 9)
    # ═══════════════════════════════════════════════════════════════════
    section_label(0.3, 9.6, "Stage A: Data Acquisition", DATA_BORDER)

    box(0.5,  8.7, 3.5, 0.9, "Amazon Reviews 2023",
        "6 categories · 732 products · 50K+ reviews", DATA_SRC, DATA_BORDER)
    box(4.5,  8.7, 3.5, 0.9, "Google Play Scraper",
        "4 categories · 319 apps · 24K+ reviews", DATA_SRC, DATA_BORDER)
    box(8.5,  8.7, 3.5, 0.9, "Reddit (Arctic Shift)",
        "1,089 buying-intent comments · 10 categories", DATA_SRC, DATA_BORDER)
    box(12.5, 8.7, 3.0, 0.9, "Fraud Filter",
        "burst / J-shape / duplicates → 71 excluded", DATA_SRC, DATA_BORDER)

    # ═══════════════════════════════════════════════════════════════════
    # ROW 2: Loading & Contract (y ≈ 7.3)
    # ═══════════════════════════════════════════════════════════════════
    section_label(0.3, 7.9, "Stage B: Contract Verification", LOAD_BORDER)

    box(2, 6.9, 5, 0.9, "Load & Verify Contract",
        "load_final.py · manifest.json · typed dataclasses", LOAD_BG, LOAD_BORDER)
    box(9, 6.9, 5, 0.9, "data/final/",
        "products · reviews · reddit_context · manifest", LOAD_BG, LOAD_BORDER)

    arrow(2.25, 8.7, 2.25, 7.85)       # amazon → loader
    arrow(6.25, 8.7, 6.0, 7.85)        # gplay → loader
    arrow(10.25, 8.7, 10.5, 7.85)      # reddit → output
    arrow(14.0, 8.7, 12.0, 7.85)       # fraud → output
    arrow(7.0, 7.35, 9.0, 7.35)        # loader → data/final

    # ═══════════════════════════════════════════════════════════════════
    # ROW 3: LLM Extraction (y ≈ 5.5)
    # ═══════════════════════════════════════════════════════════════════
    section_label(0.3, 6.2, "Stage C: LLM Aspect Extraction", LLM_BORDER)

    box(0.5, 5.1, 3.5, 0.9, "Multi-Provider Pool",
        "Gemini Flash · Groq Llama 70B · Ollama", LLM_BG, LLM_BORDER)
    box(4.5, 5.1, 4.0, 0.9, "Null-Forcing Prompt",
        "9 physical / 11 app aspects · evidence-quoted", LLM_BG, LLM_BORDER)
    box(9.0, 5.1, 3.5, 0.9, "Pydantic Validation",
        "typed schema · retry · crash-safe JSONL", LLM_BG, LLM_BORDER)
    box(13.0, 5.1, 2.5, 0.9, "aspect_scores\n.jsonl",
        "74K+ rows", LLM_BG, LLM_BORDER, fontsize=9)

    arrow(4.5, 6.9, 2.25, 6.05, "reviews")     # data/final → providers
    arrow(3.9, 5.55, 4.5, 5.55)                 # pool → prompt
    arrow(8.5, 5.55, 9.0, 5.55)                 # prompt → validation
    arrow(12.5, 5.55, 13.0, 5.55)               # validation → jsonl

    # ═══════════════════════════════════════════════════════════════════
    # ROW 4: Training pipeline (y ≈ 3.3)
    # ═══════════════════════════════════════════════════════════════════
    section_label(0.3, 4.5, "Stages D–F: Label → Features → Training", TRAIN_BORDER)

    box(0.5, 3.1, 3.0, 0.9, "Label Engineering",
        "within-category composite · log1p", TRAIN_BG, TRAIN_BORDER, fontsize=9)
    box(4.0, 3.1, 3.2, 0.9, "Feature Assembly",
        "aspect means + mention rates + meta", TRAIN_BG, TRAIN_BORDER, fontsize=9)
    box(7.8, 3.1, 3.0, 0.9, "XGBoost 5-fold CV",
        "full + aspects-only · seed 42", TRAIN_BG, TRAIN_BORDER, fontsize=9)
    box(11.3, 3.1, 2.2, 0.9, "SHAP",
        "TreeExplainer", TRAIN_BG, TRAIN_BORDER, fontsize=9)
    box(14.0, 3.1, 1.8, 0.9, "Models",
        "xgb_*.json", TRAIN_BG, TRAIN_BORDER, fontsize=9)

    arrow(2.0, 5.1, 2.0, 4.05, "labels.json")   # jsonl → labels
    arrow(14.25, 5.1, 7.0, 4.05, "features")     # jsonl → features
    arrow(3.5, 3.55, 4.0, 3.55)                   # labels → features
    arrow(7.2, 3.55, 7.8, 3.55)                   # features → xgb
    arrow(10.8, 3.55, 11.3, 3.55)                 # xgb → shap
    arrow(13.5, 3.55, 14.0, 3.55)                 # shap → models

    # ═══════════════════════════════════════════════════════════════════
    # ROW 5: Prediction + App (y ≈ 1.0)
    # ═══════════════════════════════════════════════════════════════════
    section_label(0.3, 2.5, "Stages G–H: Bridging & Serving", PRED_BORDER)

    box(0.5, 1.0, 3.0, 0.9, "Category Profiles",
        "price · pain points · strengths", PRED_BG, PRED_BORDER, fontsize=9)
    box(4.0, 1.0, 3.5, 0.9, "Bridging Layer",
        "skeptic prompt v2 · Gemini Flash", PRED_BG, PRED_BORDER, fontsize=9)
    box(8.0, 1.0, 3.0, 0.9, "Predictor",
        "viability ± 5 · SHAP risks", PRED_BG, PRED_BORDER, fontsize=9)

    # Application
    box(11.5, 1.0, 4.2, 0.9, "React + FastAPI App",
        "Simulator · Spec Coach · Analyzer · Trust Badges", APP_BG, APP_BORDER, fontsize=9)

    arrow(2.0, 3.1, 2.0, 1.95, "profiles")     # labels/features → profiles
    arrow(3.5, 1.45, 4.0, 1.45)                 # profiles → bridging
    arrow(7.5, 1.45, 8.0, 1.45)                 # bridging → predictor
    arrow(11.0, 1.45, 11.5, 1.45)               # predictor → app
    arrow(14.9, 3.1, 14.9, 1.95, "models")      # models → app (loads xgb)

    # User input arrow into bridging
    ax.annotate("", xy=(5.75, 1.0), xytext=(5.75, 0.4),
                arrowprops=dict(arrowstyle="-|>", color=APP_BORDER,
                                lw=1.5, linestyle="--"))
    ax.text(5.75, 0.2, "User: category + price + specs", ha="center",
            fontsize=7.5, color=APP_BORDER, fontweight="bold")

    # ── Legend ──────────────────────────────────────────────────────────
    legend_items = [
        (DATA_SRC, DATA_BORDER, "Data Acquisition"),
        (LOAD_BG, LOAD_BORDER, "Contract Verification"),
        (LLM_BG, LLM_BORDER, "LLM Extraction"),
        (TRAIN_BG, TRAIN_BORDER, "Training Pipeline"),
        (PRED_BG, PRED_BORDER, "Prediction Service"),
        (APP_BG, APP_BORDER, "Application Layer"),
    ]
    for i, (bg, border, label) in enumerate(legend_items):
        lx = 0.5 + i * 2.6
        rect = FancyBboxPatch((lx, 0.35), 0.3, 0.2, boxstyle="round,pad=0.03",
                              facecolor=bg, edgecolor=border, linewidth=1.2)
        ax.add_patch(rect)
        ax.text(lx + 0.4, 0.45, label, fontsize=6.5, va="center", color=TEXT_DARK)

    fig.savefig(OUT / "fig1_pipeline.png", bbox_inches="tight", dpi=300,
                facecolor=BG)
    plt.close(fig)
    print(f"Saved: {OUT / 'fig1_pipeline.png'}")


if __name__ == "__main__":
    draw()
