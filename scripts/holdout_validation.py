"""Pre-registered confirmatory holdout — run ONCE, no tuning after.

60 fresh products (disjoint from the 90-product development set, seed 4242),
bridged with the FROZEN production pipeline (skeptic prompt v2). Pre-registered
metrics: Spearman rho vs actual success, flop-vs-monopoly AUC, tier monotonicity,
per-aspect r for the three badge tiers.

Run: python scripts/holdout_validation.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.extraction.extraction_prompt import PHYSICAL_ASPECT_KEYS
from src.prediction.bridging_layer import bridge_aspects
from src.prediction.predictor import Predictor

BENCH = Path("models/benchmarks")
BRIDGED = BENCH / "holdout_bridged.jsonl"
REPORT = BENCH / "holdout_validation.json"


def launch_spec(product: dict) -> dict:
    feats = product.get("specs", {}).get("features") or []
    desc = " | ".join(feats)[:2500]
    if product.get("brand"):
        desc = f"Brand: {product['brand']}. {desc}"
    return {"name": product["name"][:120], "price": product["price"], "description": desc}


def main() -> None:
    uids = json.loads((BENCH / "holdout_uids.json").read_text())
    with open("data/final/products_physical.json", encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}
    done = set()
    if BRIDGED.exists():
        done = {json.loads(l)["product_uid"] for l in open(BRIDGED, encoding="utf-8")
                if l.strip()}
    todo = [u for u in uids if u not in done]
    print(f"holdout: {len(uids)} products, {len(todo)} to bridge")

    predictor = Predictor()
    for i, uid in enumerate(todo):
        p = products[uid]
        t0 = time.time()
        try:
            br = bridge_aspects(launch_spec(p), p["category"],
                                predictor.profiles[p["category"]], "physical")
        except Exception as exc:
            print(f"  [{i}] {uid} FAILED: {exc}")
            continue
        bridged = {a: s.score for a, s in br.scores.items()}
        out = predictor.predict_from_bridged(bridged, p["category"], {"price": p["price"]})
        rec = {"product_uid": uid, "category": p["category"], "bridged": bridged,
               "viability": out["viability_pct"], "latency_s": round(time.time() - t0, 1)}
        with open(BRIDGED, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  [{i + 1}/{len(todo)}] {p['category']:20s} viab={out['viability_pct']:5.1f}")

    # -- pre-registered analysis (no further knobs) ---------------------------
    df = pd.read_parquet("data/extracted/features_physical.parquet").set_index("product_uid")
    recs = [json.loads(l) for l in open(BRIDGED, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if r["product_uid"] in df.index]
    v = np.array([r["viability"] for r in recs])
    s = np.array([df.at[r["product_uid"], "success_score"] for r in recs])
    rho, p = stats.spearmanr(v, s)
    t = pd.DataFrame({"v": v, "s": s})
    t["tier"] = pd.qcut(t["s"], 5, labels=False, duplicates="drop")
    means = t.groupby("tier")["v"].mean()
    top, bot = t[t.tier == t.tier.max()]["v"], t[t.tier == 0]["v"]
    auc = float(sum((tv > bv) + 0.5 * (tv == bv) for tv in top for bv in bot)
                / (len(top) * len(bot)))
    mono = all(means.iloc[i] <= means.iloc[i + 1] for i in range(len(means) - 1))

    per_aspect = {}
    for a in PHYSICAL_ASPECT_KEYS:
        pairs = [(r["bridged"].get(a), df.at[r["product_uid"], a]) for r in recs
                 if r["bridged"].get(a) is not None]
        pairs = [(b, x) for b, x in pairs if pd.notna(x)]
        if len(pairs) >= 15:
            b = np.array([x[0] for x in pairs]); x = np.array([x[1] for x in pairs])
            per_aspect[a] = {"r": round(float(np.corrcoef(b, x)[0, 1]), 3), "n": len(pairs)}

    print(f"\n=== HOLDOUT (n={len(recs)}, pre-registered, frozen pipeline) ===")
    print(f"  spearman rho = {rho:.3f} (p={p:.3g})   [dev set was 0.313]")
    print(f"  flop-vs-monopoly AUC = {auc:.3f}        [dev set was 0.761]")
    print(f"  tier means: {[round(m, 1) for m in means]}  monotonic: {mono}")
    print("  per-aspect r:", {a: d["r"] for a, d in per_aspect.items()})

    REPORT.write_text(json.dumps({
        "n": len(recs), "spearman_rho": round(float(rho), 3), "p_value": float(p),
        "auc": round(auc, 3), "tier_means": [round(float(m), 2) for m in means],
        "monotonic": bool(mono), "per_aspect": per_aspect,
        "preregistered": "sample drawn seed 4242 disjoint from dev set BEFORE this run; "
                         "pipeline frozen at v2; no tuning after this result"},
        indent=2), encoding="utf-8")
    print(f"\nSaved {REPORT}")


if __name__ == "__main__":
    main()
