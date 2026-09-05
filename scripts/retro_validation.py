"""Retrospective bridging validation — the honesty test for the bridging step.

For a stratified sample of REAL products, feed the bridging LLM ONLY what was
knowable at launch (name, brand, price, marketing feature copy — never reviews),
then compare its estimated aspect scores against the scores actually extracted
from thousands of real reviews.

Outputs (models/benchmarks/):
  retro_bridged.jsonl          — per-product bridged scores (append-mode, resume-safe)
  retro_validation.json        — per-aspect r/MAE + end-to-end viability-vs-success stats

Run: python scripts/retro_validation.py [--n-per-cell 3] [--mock]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.extraction.extraction_prompt import PHYSICAL_ASPECT_KEYS
from src.prediction.bridging_layer import bridge_aspects
from src.prediction.predictor import Predictor

OUT_DIR = Path("models/benchmarks")
BRIDGED_PATH = OUT_DIR / "retro_bridged.jsonl"
REPORT_PATH = OUT_DIR / "retro_validation.json"
SEED = 42


def launch_spec(product: dict) -> dict:
    """Only what a manufacturer knows BEFORE launch: name, brand, price, marketing copy."""
    feats = product.get("specs", {}).get("features") or []
    desc = " | ".join(feats)[:2500]
    if product.get("brand"):
        desc = f"Brand: {product['brand']}. {desc}"
    return {"name": product["name"][:120], "price": product["price"], "description": desc}


def sample_products(df: pd.DataFrame, products: dict, n_per_cell: int) -> list[dict]:
    """Stratified: category x success-quintile, n per cell, seeded."""
    rng = np.random.RandomState(SEED)
    chosen = []
    for cat, g in df.groupby("category", observed=True):
        g = g[g["product_uid"].isin(products)]
        g = g[g["product_uid"].map(lambda u: bool(products[u].get("specs", {}).get("features")))]
        g = g.assign(tier=pd.qcut(g["success_score"], 5, labels=False, duplicates="drop"))
        for _, tier_g in g.groupby("tier", observed=True):
            take = tier_g.sample(min(n_per_cell, len(tier_g)), random_state=rng)
            chosen.extend(take["product_uid"].tolist())
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-cell", type=int, default=3,
                    help="products per (category x success-quintile) cell; 3 -> ~90 products")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--prompt-version", type=int, default=1, choices=(1, 2))
    args = ap.parse_args()

    global BRIDGED_PATH, REPORT_PATH
    if args.prompt_version == 2:
        BRIDGED_PATH = OUT_DIR / "retro_bridged_v2.jsonl"
        REPORT_PATH = OUT_DIR / "retro_validation_v2.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open("data/final/products_physical.json", encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}
    df = pd.read_parquet("data/extracted/features_physical.parquet")
    actual = df.set_index("product_uid")

    uids = sample_products(df, products, args.n_per_cell)
    done = set()
    if BRIDGED_PATH.exists():
        with open(BRIDGED_PATH, encoding="utf-8") as f:
            done = {json.loads(line)["product_uid"] for line in f if line.strip()}
    todo = [u for u in uids if u not in done]
    print(f"Sample: {len(uids)} products; already bridged: {len(uids) - len(todo)}; to do: {len(todo)}")

    predictor = Predictor(use_mock_llm=args.mock)
    for i, uid in enumerate(todo):
        p = products[uid]
        spec = launch_spec(p)
        cat = p["category"]
        t0 = time.time()
        try:
            br = bridge_aspects(spec, cat, predictor.profiles[cat], "physical",
                                use_mock=args.mock,
                                prompt_version=args.prompt_version)
        except Exception as exc:  # never let one product kill the run
            print(f"  [{i}] {uid} BRIDGE FAILED: {exc}")
            continue
        bridged = {a: s.score for a, s in br.scores.items()}
        out = predictor.predict_from_bridged(bridged, cat, {"price": spec["price"]},
                                             confidence=br.confidence)
        rec = {"product_uid": uid, "category": cat, "bridged": bridged,
               "confidence": br.confidence, "viability": out["viability_pct"],
               "full_model": out["full_model_pct"],
               "latency_s": round(time.time() - t0, 1)}
        with open(BRIDGED_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  [{i + 1}/{len(todo)}] {cat:20s} {uid} viab={out['viability_pct']:5.1f} "
              f"({rec['latency_s']}s)")

    analyze(actual)


def analyze(actual: pd.DataFrame) -> None:
    recs = [json.loads(l) for l in open(BRIDGED_PATH, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if r["product_uid"] in actual.index]
    print(f"\n=== RETRO VALIDATION over {len(recs)} real products ===\n")

    # per-aspect: bridged estimate vs actual review-extracted mean
    per_aspect = {}
    print(f"{'aspect':22s} {'n':>4s} {'r':>6s} {'MAE':>5s}  verdict")
    for a in PHYSICAL_ASPECT_KEYS:
        pairs = [(r["bridged"].get(a), actual.at[r["product_uid"], a])
                 for r in recs if r["bridged"].get(a) is not None]
        pairs = [(b, t) for b, t in pairs if pd.notna(t)]
        if len(pairs) < 10:
            per_aspect[a] = {"n": len(pairs), "r": None, "mae": None}
            print(f"{a:22s} {len(pairs):4d}  (too few actuals to score)")
            continue
        b, t = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
        r = float(np.corrcoef(b, t)[0, 1])
        mae = float(np.abs(b - t).mean())
        verdict = "STRONG" if r >= 0.4 else "MODERATE" if r >= 0.2 else "WEAK"
        per_aspect[a] = {"n": len(pairs), "r": round(r, 3), "mae": round(mae, 2),
                         "verdict": verdict}
        print(f"{a:22s} {len(pairs):4d} {r:6.3f} {mae:5.2f}  {verdict}")

    # end-to-end: specs-only viability vs actual market success
    from scipy import stats
    v = np.array([r["viability"] for r in recs])
    s = np.array([actual.at[r["product_uid"], "success_score"] for r in recs])
    rho, pval = stats.spearmanr(v, s)
    pearson = float(np.corrcoef(v, s)[0, 1])
    # ceiling: aspects-only model on TRUE extracted aspects for the same products
    print(f"\nEND-TO-END (specs-only viability vs actual success score):")
    print(f"  spearman rho = {rho:.3f} (p={pval:.2g}), pearson r = {pearson:.3f}")
    top = s >= np.percentile(s, 75)
    hit = v >= np.percentile(v, 75)
    precision = (top & hit).sum() / max(hit.sum(), 1)
    print(f"  top-quartile hit precision: {precision:.0%} "
          f"({(top & hit).sum()}/{hit.sum()} flagged actually top-25%)")

    report = {"n_products": len(recs), "per_aspect": per_aspect,
              "end_to_end": {"spearman_rho": round(float(rho), 3),
                             "pearson_r": round(pearson, 3),
                             "p_value": float(pval),
                             "top_quartile_precision": round(float(precision), 3)},
              "note": "bridged from launch-knowable specs only (name/brand/price/features); "
                      "actuals from review extraction; category profiles include the "
                      "product's own reviews at ~1/130 weight (negligible leakage)"}
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved {REPORT_PATH}")


if __name__ == "__main__":
    main()
