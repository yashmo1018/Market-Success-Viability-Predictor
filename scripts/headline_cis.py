"""Bootstrap 95% CIs for the paper's two headline numbers.

1. Holdout Spearman rho (pre-registered, n=59) and AUC
2. Reddit A/B delta rho (paired bootstrap over the same products, n=89)

Writes models/benchmarks/headline_cis.json.
Run: python scripts/headline_cis.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BENCH = Path("models/benchmarks")
N_BOOT = 10_000
rng = np.random.RandomState(42)


def _auc(v: np.ndarray, s: np.ndarray) -> float:
    t = pd.DataFrame({"v": v, "s": s})
    t["tier"] = pd.qcut(t["s"], 5, labels=False, duplicates="drop")
    top, bot = t[t.tier == t.tier.max()]["v"].values, t[t.tier == 0]["v"].values
    if not len(top) or not len(bot):
        return np.nan
    return float(sum((tv > bv) + 0.5 * (tv == bv) for tv in top for bv in bot)
                 / (len(top) * len(bot)))


def boot_ci(fn, n: int, *arrays) -> tuple[float, float]:
    vals = []
    for _ in range(N_BOOT):
        idx = rng.randint(0, n, n)
        vals.append(fn(*[a[idx] for a in arrays]))
    vals = np.array([v for v in vals if np.isfinite(v)])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> None:
    out = {}

    # -- holdout ----------------------------------------------------------------
    df = pd.read_parquet("data/extracted/features_physical.parquet").set_index("product_uid")
    recs = [json.loads(l) for l in open(BENCH / "holdout_bridged.jsonl", encoding="utf-8")
            if l.strip()]
    recs = [r for r in recs if r["product_uid"] in df.index]
    v = np.array([r["viability"] for r in recs])
    s = np.array([float(df.at[r["product_uid"], "success_score"]) for r in recs])
    rho = float(stats.spearmanr(v, s)[0])
    lo, hi = boot_ci(lambda a, b: stats.spearmanr(a, b)[0], len(v), v, s)
    alo, ahi = boot_ci(_auc, len(v), v, s)
    out["holdout"] = {"n": len(v), "spearman_rho": round(rho, 3),
                      "rho_ci95": [round(lo, 3), round(hi, 3)],
                      "rho_ci_excludes_zero": bool(lo > 0),
                      "auc": round(_auc(v, s), 3), "auc_ci95": [round(alo, 3), round(ahi, 3)]}

    # -- A/B delta (paired) -------------------------------------------------------
    ab = [json.loads(l) for l in open(BENCH / "ab_reddit_bridged.jsonl", encoding="utf-8")
          if l.strip()]
    vw = np.array([r["viab_with"] for r in ab])
    vn = np.array([r["viab_without"] for r in ab])
    sc = np.array([r["success"] for r in ab])
    delta = float(stats.spearmanr(vw, sc)[0] - stats.spearmanr(vn, sc)[0])
    dlo, dhi = boot_ci(
        lambda a, b, c: stats.spearmanr(a, c)[0] - stats.spearmanr(b, c)[0],
        len(sc), vw, vn, sc)
    out["reddit_ab"] = {"n": len(sc), "delta_rho": round(delta, 3),
                        "delta_ci95": [round(dlo, 3), round(dhi, 3)],
                        "ci_excludes_zero": bool(dlo > 0),
                        "note": "paired bootstrap (same products both arms); if CI includes 0 "
                                "report the lift as exploratory, not confirmed"}

    (BENCH / "headline_cis.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
