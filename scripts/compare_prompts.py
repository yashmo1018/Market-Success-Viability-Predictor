"""Measured comparison: bridging prompt v1 (trusting) vs v2 (skeptic).

Same 90 products, same specs, same model fleet. Also tests validity-weighted
shrinkage with leave-one-out weights (council rule: ship only if LOO improves).

Run: python scripts/compare_prompts.py
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
from src.prediction.predictor import Predictor

BENCH = Path("models/benchmarks")


def load(path: Path, actual: pd.DataFrame) -> list[dict]:
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return [r for r in recs if r["product_uid"] in actual.index]


def per_aspect(recs: list[dict], actual: pd.DataFrame) -> dict:
    out = {}
    for a in PHYSICAL_ASPECT_KEYS:
        pairs = [(r["bridged"].get(a), actual.at[r["product_uid"], a]) for r in recs
                 if r["bridged"].get(a) is not None]
        pairs = [(b, t) for b, t in pairs if pd.notna(t)]
        if len(pairs) < 15:
            out[a] = None
            continue
        b = np.array([p[0] for p in pairs]); t = np.array([p[1] for p in pairs])
        out[a] = {"r": float(np.corrcoef(b, t)[0, 1]),
                  "mae": float(np.abs(b - t).mean()),
                  "spread": float(np.std(b))}
    return out


def end_to_end(recs: list[dict], actual: pd.DataFrame, key: str = "viability") -> dict:
    v = np.array([r[key] for r in recs])
    s = np.array([actual.at[r["product_uid"], "success_score"] for r in recs])
    rho, p = stats.spearmanr(v, s)
    t = pd.DataFrame({"v": v, "s": s})
    t["tier"] = pd.qcut(t["s"], 5, labels=False, duplicates="drop")
    means = t.groupby("tier")["v"].mean()
    top, bot = t[t.tier == t.tier.max()]["v"], t[t.tier == 0]["v"]
    auc = float(sum((tv > bv) + 0.5 * (tv == bv) for tv in top for bv in bot)
                / (len(top) * len(bot)))
    return {"rho": float(rho), "p": float(p), "auc": auc,
            "gap": float(means.iloc[-1] - means.iloc[0]),
            "spread_std": float(np.std(v)), "min": float(v.min()), "max": float(v.max())}


def loo_shrunk_viability(recs: list[dict], actual: pd.DataFrame,
                         predictor: Predictor) -> list[dict]:
    """Shrink each product's bridged scores toward category mean with weights
    w=max(r,0) computed from the OTHER 89 products (leave-one-out)."""
    out = []
    for i, rec in enumerate(recs):
        others = recs[:i] + recs[i + 1:]
        weights = {}
        for a in PHYSICAL_ASPECT_KEYS:
            pairs = [(r["bridged"].get(a), actual.at[r["product_uid"], a]) for r in others
                     if r["bridged"].get(a) is not None]
            pairs = [(b, t) for b, t in pairs if pd.notna(t)]
            if len(pairs) < 15:
                weights[a] = 0.0
                continue
            b = np.array([p[0] for p in pairs]); t = np.array([p[1] for p in pairs])
            weights[a] = max(float(np.corrcoef(b, t)[0, 1]), 0.0)
        profile = predictor.profiles[rec["category"]]
        shrunk = {a: weights.get(a, 0.0) * s +
                     (1 - weights.get(a, 0.0)) * (profile["avg_aspect_scores"].get(a) or 5.0)
                  for a, s in rec["bridged"].items()}
        pred = predictor.predict_from_bridged(shrunk, rec["category"], {"price": 0})
        out.append({**rec, "viability_shrunk": pred["viability_pct"]})
    return out


def main() -> None:
    actual = pd.read_parquet("data/extracted/features_physical.parquet").set_index("product_uid")
    v1 = load(BENCH / "retro_bridged.jsonl", actual)
    v2 = load(BENCH / "retro_bridged_v2.jsonl", actual)
    common = {r["product_uid"] for r in v1} & {r["product_uid"] for r in v2}
    v1 = [r for r in v1 if r["product_uid"] in common]
    v2 = [r for r in v2 if r["product_uid"] in common]
    print(f"Comparing on {len(common)} common products\n")

    a1, a2 = per_aspect(v1, actual), per_aspect(v2, actual)
    print(f"{'aspect':22s} {'v1 r':>7s} {'v2 r':>7s} {'v1 MAE':>7s} {'v2 MAE':>7s} {'v1 spd':>7s} {'v2 spd':>7s}")
    for a in PHYSICAL_ASPECT_KEYS:
        if a1.get(a) and a2.get(a):
            print(f"{a:22s} {a1[a]['r']:7.3f} {a2[a]['r']:7.3f} "
                  f"{a1[a]['mae']:7.2f} {a2[a]['mae']:7.2f} "
                  f"{a1[a]['spread']:7.2f} {a2[a]['spread']:7.2f}")

    e1, e2 = end_to_end(v1, actual), end_to_end(v2, actual)
    print(f"\n{'metric':18s} {'v1':>8s} {'v2':>8s}")
    for k in ("rho", "p", "auc", "gap", "spread_std", "min", "max"):
        print(f"{k:18s} {e1[k]:8.3f} {e2[k]:8.3f}")

    # grounded-flag stats (v2 only)
    n_ung = [sum(1 for g in r.get("grounded", {}).values() if not g) for r in v2
             if r.get("grounded")]
    if n_ung:
        print(f"\nv2 ungrounded aspects/product: mean {np.mean(n_ung):.1f}")

    # LOO shrinkage on the better prompt version
    best_recs, best_name = (v2, "v2") if e2["rho"] >= e1["rho"] else (v1, "v1")
    print(f"\nLOO shrinkage test on {best_name}...")
    predictor = Predictor(use_mock_llm=True)  # no LLM needed for predict_from_bridged
    shrunk = loo_shrunk_viability(best_recs, actual, predictor)
    es = end_to_end(shrunk, actual, key="viability_shrunk")
    print(f"  raw     rho={end_to_end(best_recs, actual)['rho']:.3f}")
    print(f"  shrunk  rho={es['rho']:.3f}  auc={es['auc']:.3f}")
    verdict = "SHIP shrinkage" if es["rho"] > end_to_end(best_recs, actual)["rho"] + 0.01 \
        else "DO NOT ship shrinkage (no LOO improvement)"
    print(f"  -> {verdict}")

    report = {"n_common": len(common), "per_aspect": {"v1": a1, "v2": a2},
              "end_to_end": {"v1": e1, "v2": e2, "shrunk": es},
              "shrinkage_verdict": verdict}
    (BENCH / "prompt_comparison.json").write_text(json.dumps(report, indent=2),
                                                  encoding="utf-8")
    print(f"\nSaved {BENCH / 'prompt_comparison.json'}")


if __name__ == "__main__":
    main()
