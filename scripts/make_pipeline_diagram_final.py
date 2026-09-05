"""Figure 1 (final): system architecture pipeline, senior-grade recreation.

Faithful to the numbered-band layout the author preferred, with typos fixed
(load_final.py, reviews) and the styling tightened: consistent palette,
numbered badges, cylinder data-store and document icons, clean arrows.

Output: papers/figures/fig1_pipeline_v3.png (review copy).
Run: python scripts/make_pipeline_diagram_final.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Ellipse, PathPatch
from matplotlib.path import Path as MPath

OUT = Path(__file__).resolve().parents[1] / "papers" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUTED, ARROW = "#1D2733", "#5B6470", "#46505C"
B = {
    "data":  ("#E9F1FD", "#4285C4", "#1B5FA6"),
    "load":  ("#EBECFB", "#6B6FD6", "#3B40B0"),
    "llm":   ("#F4EAFB", "#A46FD6", "#7A34AE"),
    "train": ("#FEF5DE", "#E0A93B", "#A66F13"),
    "serve": ("#E7F6EC", "#4FA96A", "#2C7A45"),
    "app":   ("#FDE9E9", "#DB5C5C", "#AF3535"),
}
plt.rcParams.update({"font.family": "DejaVu Sans"})


def draw():
    fig, ax = plt.subplots(figsize=(15.2, 10.6))
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 10.6)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    def band_strip(y0, h, key):
        ax.add_patch(Rectangle((0.15, y0), 14.9, h, facecolor=B[key][0],
                     edgecolor="none", alpha=0.4, zorder=0))

    def badge(cx, cy, num, key, name):
        ax.add_patch(Circle((cx, cy), 0.32, facecolor=B[key][2], edgecolor="white",
                     linewidth=1.5, zorder=5))
        ax.text(cx, cy, str(num), ha="center", va="center", color="white",
                fontsize=13, fontweight="bold", zorder=6)
        ax.text(cx, cy - 0.60, name, ha="center", va="top", color=B[key][2],
                fontsize=9.5, fontweight="bold", zorder=6, linespacing=0.95)

    def card(x, y, w, h, title, sub, key, tfs=10.0, sfs=7.2, icon=None):
        fill, border, _ = B[key]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                     facecolor="white", edgecolor=border, linewidth=1.7, zorder=3))
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                     facecolor=fill, edgecolor="none", alpha=0.5, zorder=3))
        tx = x + w / 2
        if icon == "doc":
            _doc(ax, x + 0.32, y + h / 2, border)
            tx += 0.16
        elif icon == "globe":
            _globe(ax, x + 0.38, y + h / 2, border)
            tx += 0.18
        ax.text(tx, y + h / 2 + (0.16 if sub else 0), title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color=INK, zorder=5)
        if sub:
            ax.text(tx, y + h / 2 - 0.19, sub, ha="center", va="center",
                    fontsize=sfs, color=MUTED, style="italic", zorder=5, linespacing=1.15)

    def cylinder(x, y, w, h, title, sub, key):
        fill, border, _ = B[key]
        ry = 0.15
        cx = x + w / 2
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor="none", alpha=0.55, zorder=3))
        ax.add_patch(Ellipse((cx, y), w, 2 * ry, facecolor=fill, edgecolor=border,
                     linewidth=1.7, alpha=0.9, zorder=3))
        ax.plot([x, x], [y, y + h], color=border, lw=1.7, zorder=3)
        ax.plot([x + w, x + w], [y, y + h], color=border, lw=1.7, zorder=3)
        ax.add_patch(Ellipse((cx, y + h), w, 2 * ry, facecolor="white", edgecolor=border,
                     linewidth=1.7, zorder=4))
        ax.text(cx, y + h / 2 + 0.14, title, ha="center", va="center", fontsize=11,
                fontweight="bold", color=INK, zorder=5)
        ax.text(cx, y + h / 2 - 0.18, sub, ha="center", va="center", fontsize=7.2,
                color=MUTED, style="italic", zorder=5)

    def arrow(p1, p2, label=None, dashed=False, color=ARROW, lw=1.9, loff=(0.12, 0.12)):
        ax.annotate("", xy=p2, xytext=p1, zorder=2,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                    linestyle="--" if dashed else "-",
                                    shrinkA=1, shrinkB=1, mutation_scale=15))
        if label:
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            ax.text(mx + loff[0], my + loff[1], label, fontsize=7, color=MUTED,
                    ha="left", va="center", zorder=2,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                              edgecolor="none", alpha=0.85))

    CX0, CX1 = 2.25, 15.0

    def slots(n, gap):
        w = (CX1 - CX0 - gap * (n - 1)) / n
        return [CX0 + i * (w + gap) for i in range(n)], w

    def cx(x, w):
        return x + w / 2

    # ---- title ---------------------------------------------------------
    ax.text(7.7, 10.25, "Hybrid AI Product Success Predictor", ha="center",
            fontsize=17, fontweight="bold", color=INK)
    ax.text(7.7, 9.86, "Seven independently re-runnable stages, plus the serving layer",
            ha="center", fontsize=10, color=MUTED)

    # ===== BAND 1 — Data Acquisition ===================================
    band_strip(8.45, 1.15, "data")
    badge(0.95, 9.02, 1, "data", "Data\nAcquisition")
    xs1, w1 = slots(4, 0.30)
    Y1, H1 = 8.60, 0.82
    card(xs1[0], Y1, w1, H1, "Amazon Reviews 2023", "6 categories · 732 products · 50K+ reviews", "data", tfs=9.6, sfs=7.0)
    card(xs1[1], Y1, w1, H1, "Google Play Scraper", "4 categories · 319 apps · 24K+ reviews", "data", tfs=9.6, sfs=7.0)
    card(xs1[2], Y1, w1, H1, "Reddit (Arctic Shift)", "1,089 buying-intent comments · 10 cats", "data", tfs=9.6, sfs=7.0)
    card(xs1[3], Y1, w1, H1, "Fraud Filter", "burst / J-shape / dup → 71 excluded", "data", tfs=9.6, sfs=7.0)

    # ===== BAND 2 — Contract Verification ==============================
    band_strip(6.80, 1.25, "load")
    badge(0.95, 7.50, 2, "load", "Contract\nVerification")
    LDx, LDy, LDw, LDh = 2.6, 7.02, 4.7, 0.82
    card(LDx, LDy, LDw, LDh, "Load & Verify Contract",
         "load_final.py · manifest.json · typed dataclasses", "load", tfs=10.5, sfs=7.2)
    STx, STy, STw, STh = 9.6, 7.02, 3.7, 0.82
    cylinder(STx, STy, STw, STh, "data/final/", "products · reviews · reddit_context · manifest", "load")

    arrow((cx(xs1[0], w1), Y1), (LDx + 1.2, LDy + LDh))
    arrow((cx(xs1[1], w1), Y1), (LDx + 3.0, LDy + LDh))
    arrow((cx(xs1[2], w1), Y1), (STx + 1.0, STy + STh + 0.15))
    arrow((cx(xs1[3], w1), Y1), (STx + 2.6, STy + STh + 0.15))
    arrow((LDx + LDw, LDy + LDh / 2), (STx, STy + STh / 2))

    # ===== BAND 3 — LLM Aspect Extraction ==============================
    band_strip(4.85, 1.65, "llm")
    badge(0.95, 5.85, 3, "llm", "LLM Aspect\nExtraction")
    xs3, w3 = slots(4, 0.30)
    Y3, H3 = 5.15, 0.98
    card(xs3[0], Y3, w3, H3, "Multi-Provider LLM Pool",
         "Gemini Flash · Groq Llama-3.3-70B\nOllama local fallback", "llm", tfs=9.8, sfs=7.0)
    card(xs3[1], Y3, w3, H3, "Null-Forcing Prompt",
         "9 physical / 11 app aspects\nscored only when mentioned", "llm", tfs=9.8, sfs=7.0)
    card(xs3[2], Y3, w3, H3, "Pydantic Validation",
         "typed schema · retry\nprovider failover", "llm", tfs=9.8, sfs=7.0)
    card(xs3[3], Y3, w3, H3, "aspect_scores.jsonl",
         "74K+ rows\ncrash-safe append-only", "llm", tfs=9.4, sfs=7.0, icon="doc")

    arrow((cx(LDx, LDw), LDy), (cx(xs3[0], w3), Y3 + H3), "reviews")
    mid3 = Y3 + H3 / 2
    arrow((xs3[0] + w3, mid3), (xs3[1], mid3))
    arrow((xs3[1] + w3, mid3), (xs3[2], mid3))
    arrow((xs3[2] + w3, mid3), (xs3[3], mid3))

    # ===== BAND 4 — Training Pipeline ==================================
    band_strip(3.00, 1.55, "train")
    badge(0.95, 3.90, 4, "train", "Training\nPipeline")
    xs4, w4 = slots(5, 0.28)
    Y4, H4 = 3.28, 0.88
    card(xs4[0], Y4, w4, H4, "Label Engineering", "within-category\ncomposite · log1p", "train", tfs=8.8, sfs=6.9)
    card(xs4[1], Y4, w4, H4, "Feature Assembly", "aspect means +\nrates + metadata", "train", tfs=8.8, sfs=6.9)
    card(xs4[2], Y4, w4, H4, "XGBoost 5-fold CV", "full + aspects-only\nseed 42", "train", tfs=8.8, sfs=6.9)
    card(xs4[3], Y4, w4, H4, "SHAP", "TreeExplainer", "train", tfs=9.5, sfs=7.2)
    card(xs4[4], Y4, w4, H4, "Models", "xgb_*.json", "train", tfs=9.5, sfs=7.2, icon="doc")

    arrow((cx(xs4[0], w4), Y3), (cx(xs4[0], w4), Y4 + H4), "labels.json")
    arrow((cx(xs3[3], w3), Y3), (cx(xs4[1], w4), Y4 + H4), "features")
    mid4 = Y4 + H4 / 2
    for i in range(4):
        arrow((xs4[i] + w4, mid4), (xs4[i + 1], mid4))

    # ===== BAND 5 — Bridging & Serving =================================
    band_strip(1.00, 1.65, "serve")
    badge(0.95, 1.92, 5, "serve", "Bridging &\nServing")
    xs5, w5 = slots(4, 0.30)
    Y5, H5 = 1.42, 0.90
    card(xs5[0], Y5, w5, H5, "Category Profiles", "price stats · pain\npoints · strengths", "serve", tfs=9.2, sfs=6.9)
    card(xs5[1], Y5, w5, H5, "Bridging Layer", "skeptic prompt v2\nGemini Flash", "serve", tfs=9.2, sfs=6.9)
    card(xs5[2], Y5, w5, H5, "Predictor", "viability ± 5 range\nSHAP-derived risks", "serve", tfs=9.2, sfs=6.9)
    card(xs5[3], Y5, w5, H5, "React + FastAPI App",
         "Simulator · Spec Coach\nAnalyzer · Trust Badges", "app", tfs=9.6, sfs=6.9, icon="globe")

    arrow((cx(xs4[0], w4), Y4), (cx(xs5[0], w5), Y5 + H5), "profiles")
    mid5 = Y5 + H5 / 2
    for i in range(3):
        arrow((xs5[i] + w5, mid5), (xs5[i + 1], mid5))
    arrow((cx(xs4[4], w4), Y4), (cx(xs5[3], w5), Y5 + H5), "loads models", loff=(0.14, 0))

    ub = cx(xs5[1], w5)
    ax.annotate("", xy=(ub, Y5), xytext=(ub, 0.70),
                arrowprops=dict(arrowstyle="-|>", color=B["app"][1], lw=1.6,
                                linestyle="--", mutation_scale=13), zorder=2)
    ax.text(ub, 0.52, "User: category + price + specification", ha="center",
            fontsize=8, color=B["app"][1], fontweight="bold")

    fig.savefig(OUT / "fig1_pipeline_v3.png", bbox_inches="tight", dpi=300, facecolor="white")
    plt.close(fig)
    print(f"Saved: {OUT / 'fig1_pipeline_v3.png'}")


def _doc(ax, cx, cy, color):
    w, h, fold = 0.28, 0.38, 0.10
    x, y = cx - w / 2, cy - h / 2
    verts = [(x, y), (x, y + h), (x + w - fold, y + h), (x + w, y + h - fold),
             (x + w, y), (x, y)]
    codes = [MPath.MOVETO, MPath.LINETO, MPath.LINETO, MPath.LINETO, MPath.LINETO, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor="white", edgecolor=color,
                 linewidth=1.4, zorder=6))
    ax.plot([x + w - fold, x + w - fold, x + w], [y + h, y + h - fold, y + h - fold],
            color=color, lw=1.0, zorder=6)
    for dy in (0.09, 0.01, -0.07):
        ax.plot([x + 0.05, x + w - 0.05], [cy + dy, cy + dy], color=color, lw=0.8, zorder=6)


def _globe(ax, cx, cy, color):
    r = 0.18
    ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor=color, lw=1.4, zorder=6))
    ax.add_patch(Ellipse((cx, cy), r * 0.9, 2 * r, facecolor="none", edgecolor=color, lw=0.9, zorder=6))
    ax.plot([cx - r, cx + r], [cy, cy], color=color, lw=0.9, zorder=6)
    ax.plot([cx, cx], [cy - r, cy + r], color=color, lw=0.9, zorder=6)


if __name__ == "__main__":
    draw()
