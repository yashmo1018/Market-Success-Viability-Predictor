"""Council-mandated baseline: does the LLM pipeline beat trivial predictors?

Predictors compared on the SAME 90 retro products:
  1. price-position only: -|price - category_median| (closer to median = better)
  2. price percentile within category
  3. spec-copy length (chars of marketing features)
  4. full pipeline (specs-only viability from retro_bridged.jsonl)

Also bootstraps 95% CIs for the pipeline's per-aspect r and end-to-end Spearman.

Run: python scripts/baseline_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.extraction.extraction_prompt import PHYSICAL_ASPECT_KEYS

SEED = 42


def spearman(a, b) -> float:
    return float(stats.spearmanr(a, b)[0])


def boot_ci(f, n: int, n_boot: int = 2000) -> tuple[float, float]:
    rng = np.random.RandomState(SEED)
    vals = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        v = f(idx)
        if np.isfinite(v):
            vals.append(v)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> None:
    recs = [json.loads(l) for l in
            open("models/benchmarks/retro_bridged.jsonl", encoding="utf-8") if l.strip()]
    df = pd.read_parquet("data/extracted/features_physical.parquet").set_index("product_uid")
    with open("data/final/products_physical.json", encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}
    recs = [r for r in recs if r["product_uid"] in df.index]

    cat_median_price = {c: g["price"].median() for c, g in df.groupby("category", observed=True)}
    actual = np.array([df.at[r["product_uid"], "success_score"] for r in recs])
    pipeline = np.array([r["viability"] for r in recs])
    price = np.array([products[r["product_uid"]]["price"] for r in recs])
    med = np.array([cat_median_price[r["category"]] for r in recs])
    price_pos = -np.abs(price - med)
    price_pctl = np.array([
        stats.percentileofscore(df[df.category == r["category"]]["price"], p)
        for r, p in zip(recs, price)])
    copy_len = np.array([len(" | ".join(products[r["product_uid"]].get("specs", {})
                                        .get("features") or [])) for r in recs])

    n = len(recs)
    print(f"=== BASELINE CHECK on the same {n} retro products ===\n")
    rows = [("price-position (|p - cat median|)", price_pos),
            ("price percentile in category", price_pctl),
            ("marketing-copy length", copy_len),
            ("FULL PIPELINE (specs-only viability)", pipeline)]
    for name, pred in rows:
        rho = spearman(pred, actual)
        lo, hi = boot_ci(lambda i, p=pred: spearman(p[i], actual[i]), n)
        print(f"  {name:38s} rho={rho:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")

    print("\n=== BOOTSTRAP CIs: per-aspect bridging validity (n=90) ===\n")
    aspect_ci = {}
    for a in PHYSICAL_ASPECT_KEYS:
        pairs = [(r["bridged"].get(a), df.at[r["product_uid"], a]) for r in recs
                 if r["bridged"].get(a) is not None]
        pairs = [(b, t) for b, t in pairs if pd.notna(t)]
        if len(pairs) < 15:
            print(f"  {a:22s} n={len(pairs):3d}  (too few)")
            continue
        b = np.array([p[0] for p in pairs]); t = np.array([p[1] for p in pairs])
        r0 = float(np.corrcoef(b, t)[0, 1])
        lo, hi = boot_ci(lambda i, b=b, t=t: float(np.corrcoef(b[i], t[i])[0, 1]), len(b))
        sig = "excludes 0" if lo > 0 else "INCLUDES 0"
        aspect_ci[a] = {"r": round(r0, 3), "ci": [round(lo, 3), round(hi, 3)], "n": len(pairs)}
        print(f"  {a:22s} n={len(pairs):3d}  r={r0:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]  {sig}")

    out = Path("models/benchmarks/baseline_check.json")
    out.write_text(json.dumps({
        "baselines": {name: round(spearman(pred, actual), 3) for name, pred in rows},
        "per_aspect_ci": aspect_ci}, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
