"""Real-product stress test: flops -> hits -> market-monopoly products.

Consumes models/benchmarks/retro_bridged.jsonl (specs-only predictions for real
products) and grades the system against what actually happened in the market:
  - named table across the success spectrum (worst flops to biggest hits)
  - tier ordering: do actual flops score lower than actual monopolies?
  - calibration: mean specs-only viability per actual-success quintile

Run AFTER scripts/retro_validation.py:  python scripts/real_product_stress.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BRIDGED_PATH = Path("models/benchmarks/retro_bridged_v2.jsonl")  # v2 = production prompt
OUT_PATH = Path("models/benchmarks/real_product_stress.json")


def main() -> None:
    recs = {r["product_uid"]: r for r in
            (json.loads(l) for l in open(BRIDGED_PATH, encoding="utf-8") if l.strip())}
    df = pd.read_parquet("data/extracted/features_physical.parquet").set_index("product_uid")
    with open("data/final/products_physical.json", encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}

    rows = []
    for uid, r in recs.items():
        if uid not in df.index:
            continue
        p = products[uid]
        rows.append({
            "uid": uid, "name": p["name"][:60], "category": r["category"],
            "rating_count": p["rating_count"], "avg_rating": p["avg_rating"],
            "actual_success": float(df.at[uid, "success_score"]),
            "pred_viability": r["viability"],
        })
    t = pd.DataFrame(rows).sort_values("actual_success")
    n = len(t)
    print(f"=== REAL-PRODUCT STRESS TEST: {n} launched products, specs-only predictions ===\n")

    # named spectrum: 8 worst flops, 8 middle, 8 biggest successes
    def show(block: pd.DataFrame, title: str) -> None:
        print(title)
        for _, x in block.iterrows():
            print(f"  actual={x.actual_success:5.1f} pred={x.pred_viability:5.1f} "
                  f"({x.rating_count:>7,} ratings, {x.avg_rating}*) "
                  f"{x.category:19s} {x['name']}")
        print()

    show(t.head(8), "-- FLOPS (lowest actual success) --")
    mid = n // 2
    show(t.iloc[mid - 4: mid + 4], "-- MID-MARKET --")
    show(t.tail(8), "-- HITS / MONOPOLY-GRADE (highest actual success) --")

    # tier calibration: quintiles of ACTUAL success -> mean predicted viability
    t["tier"] = pd.qcut(t["actual_success"], 5,
                        labels=["flop", "weak", "mid", "strong", "monopoly"])
    cal = t.groupby("tier", observed=True)["pred_viability"].agg(["mean", "std", "count"])
    print("-- CALIBRATION: actual-success quintile -> specs-only predicted viability --")
    print(cal.round(1).to_string())
    means = cal["mean"].tolist()
    mono = all(means[i] <= means[i + 1] for i in range(len(means) - 1))
    gap = means[-1] - means[0]
    print(f"\n  monotonic across tiers? {'PASS' if mono else 'FAIL'}")
    print(f"  monopoly-vs-flop predicted gap: {gap:+.1f} pts")

    # discrimination: can it separate top-quintile from bottom-quintile?
    top = t[t.tier == "monopoly"]["pred_viability"]
    bot = t[t.tier == "flop"]["pred_viability"]
    auc_pairs = sum((tv > bv) + 0.5 * (tv == bv) for tv in top for bv in bot)
    auc = auc_pairs / (len(top) * len(bot))
    print(f"  flop-vs-monopoly discrimination (AUC): {auc:.2f} "
          f"(0.5 = coin flip, 1.0 = perfect)")

    report = {
        "n": n, "tier_means": {str(k): round(v, 1) for k, v in cal["mean"].items()},
        "monotonic": bool(mono), "monopoly_minus_flop_gap": round(float(gap), 1),
        "flop_vs_monopoly_auc": round(float(auc), 3),
        "spectrum": t[["name", "category", "actual_success", "pred_viability",
                       "rating_count"]].to_dict("records"),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved {OUT_PATH}")


if __name__ == "__main__":
    main()
