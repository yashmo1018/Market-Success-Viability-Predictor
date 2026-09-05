"""A/B: does injecting Reddit consumer-priorities into the bridging prompt
improve launch-blind validity?

Fair design — for each of the same ~90 real products (seed 42), bridge TWICE
with the SAME provider pool, differing ONLY in whether the profile's
consumer_priorities are present. Same seed, same specs, same model → the delta
isolates the Reddit effect and needs no specific provider (self-contained even
when the Gemini daily quota is exhausted; both arms then use Groq equally).

Output: models/benchmarks/ab_reddit_priorities.json
Run: python scripts/ab_reddit_priorities.py
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.retro_validation import launch_spec, sample_products  # reuse identical sampling
from src.prediction.bridging_layer import bridge_aspects
from src.prediction.predictor import Predictor

OUT = Path("models/benchmarks/ab_reddit_priorities.json")
BRIDGED = Path("models/benchmarks/ab_reddit_bridged.jsonl")


def _metrics(viab: np.ndarray, succ: np.ndarray) -> dict:
    rho, p = stats.spearmanr(viab, succ)
    t = pd.DataFrame({"v": viab, "s": succ})
    t["tier"] = pd.qcut(t["s"], 5, labels=False, duplicates="drop")
    top = t[t.tier == t.tier.max()]["v"]; bot = t[t.tier == 0]["v"]
    auc = float(sum((tv > bv) + 0.5 * (tv == bv) for tv in top for bv in bot)
                / max(len(top) * len(bot), 1))
    return {"spearman_rho": round(float(rho), 3), "p_value": round(float(p), 4),
            "auc": round(auc, 3), "n": int(len(viab))}


def main() -> None:
    with open("data/final/products_physical.json", encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}
    df = pd.read_parquet("data/extracted/features_physical.parquet")
    actual = df.set_index("product_uid")
    uids = sample_products(df, products, n_per_cell=3)

    predictor = Predictor()
    done = set()
    if BRIDGED.exists():
        done = {json.loads(l)["product_uid"] for l in open(BRIDGED, encoding="utf-8") if l.strip()}
    todo = [u for u in uids if u in actual.index and u not in done]
    print(f"A/B over {len([u for u in uids if u in actual.index])} products; to bridge: {len(todo)}")

    for i, uid in enumerate(todo):
        p = products[uid]; cat = p["category"]; spec = launch_spec(p)
        prof_with = predictor.profiles[cat]
        prof_without = copy.deepcopy(prof_with)
        prof_without["consumer_priorities"] = None  # the only difference
        try:
            br_w = bridge_aspects(spec, cat, prof_with, "physical", prompt_version=2)
            br_n = bridge_aspects(spec, cat, prof_without, "physical", prompt_version=2)
        except Exception as exc:  # never let one product kill the run
            print(f"  [{i}] {uid} FAILED: {exc}")
            continue
        v_w = predictor.predict_from_bridged({a: s.score for a, s in br_w.scores.items()},
                                             cat, {"price": spec["price"]})["viability_pct"]
        v_n = predictor.predict_from_bridged({a: s.score for a, s in br_n.scores.items()},
                                             cat, {"price": spec["price"]})["viability_pct"]
        rec = {"product_uid": uid, "category": cat,
               "viab_with": v_w, "viab_without": v_n,
               "success": float(actual.at[uid, "success_score"])}
        with open(BRIDGED, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  [{i + 1}/{len(todo)}] {cat:20s} with={v_w:5.1f} without={v_n:5.1f}")

    recs = [json.loads(l) for l in open(BRIDGED, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if r["product_uid"] in actual.index]
    succ = np.array([r["success"] for r in recs])
    m_with = _metrics(np.array([r["viab_with"] for r in recs]), succ)
    m_without = _metrics(np.array([r["viab_without"] for r in recs]), succ)

    report = {
        "n": len(recs),
        "with_priorities": m_with,
        "without_priorities": m_without,
        "delta_rho": round(m_with["spearman_rho"] - m_without["spearman_rho"], 3),
        "delta_auc": round(m_with["auc"] - m_without["auc"], 3),
        "verdict": ("Reddit priorities HELP" if m_with["spearman_rho"] > m_without["spearman_rho"]
                    else "Reddit priorities do NOT help (honest negative finding)"),
        "note": "same provider + seed + specs both arms; only consumer_priorities differ",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n=== A/B RESULT (n={len(recs)}) ===")
    print(f"  with    priorities: rho={m_with['spearman_rho']} auc={m_with['auc']}")
    print(f"  without priorities: rho={m_without['spearman_rho']} auc={m_without['auc']}")
    print(f"  delta rho={report['delta_rho']:+.3f}  auc={report['delta_auc']:+.3f}")
    print(f"  -> {report['verdict']}")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
