"""Which app-success metrics are learnable from review aspects alone?

The app aspects-only model FAILS its gate (R2=0.101) against the composite
success score (30% installs + 30% rating + 20% velocity + 20% retention).
Hypothesis: aspects capture QUALITY, and the composite is dominated by
DISTRIBUTION (installs/velocity) that quality cannot see. Test: retrain the
identical aspects-only model against each label component separately.

Read-only w.r.t. production artifacts — writes only
models/benchmarks/app_target_experiment.json.

Run: python scripts/app_target_experiment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import KFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "models/benchmarks/app_target_experiment.json"

PARAMS = dict(objective="reg:squarederror", n_estimators=600, learning_rate=0.05,
              max_depth=5, min_child_weight=3, subsample=0.8, colsample_bytree=0.8,
              enable_categorical=True, tree_method="hist", random_state=42,
              early_stopping_rounds=50)

# aspects-only feature set = manifest of the shipped aspects-only model
MANIFEST = json.loads((ROOT / "models/xgb_app_aspects_only_features.json").read_text())


def cv_r2(X: pd.DataFrame, y: np.ndarray) -> tuple[float, float]:
    scores, aucs = [], []
    top_thr = np.quantile(y, 0.75)
    for tr, te in KFold(5, shuffle=True, random_state=42).split(X):
        m = xgb.XGBRegressor(**PARAMS)
        m.fit(X.iloc[tr], y[tr], eval_set=[(X.iloc[te], y[te])], verbose=False)
        pred = m.predict(X.iloc[te])
        ss_res = ((y[te] - pred) ** 2).sum()
        ss_tot = ((y[te] - y[te].mean()) ** 2).sum()
        scores.append(1 - ss_res / ss_tot)
        # top-quartile discrimination on this fold
        is_top = (y[te] >= top_thr).astype(int)
        if 0 < is_top.sum() < len(is_top):
            order = pred.argsort()
            ranks = np.empty_like(order, dtype=float); ranks[order] = np.arange(len(pred))
            n1, n0 = is_top.sum(), (1 - is_top).sum()
            aucs.append((ranks[is_top == 1].sum() - n1 * (n1 - 1) / 2) / (n1 * n0))
    return float(np.mean(scores)), float(np.mean(aucs)) if aucs else float("nan")


def main() -> None:
    df = pd.read_parquet(ROOT / "data/extracted/features_app.parquet")
    labels = json.loads((ROOT / "data/extracted/labels.json").read_text(encoding="utf-8"))

    comp = pd.DataFrame({uid: labels[uid]["components"] for uid in df["product_uid"]
                         if uid in labels}).T
    df = df.set_index("product_uid").join(comp, how="inner")
    X = df[MANIFEST].copy()
    X["category"] = X["category"].astype("category")
    print(f"n={len(df)} apps, {len(MANIFEST)} aspects-only features\n")

    targets = {
        "composite_success (current, FAILED)": df["success_score"].to_numpy(float),
        "avg_rating (pure quality)": df["avg_rating_raw"].to_numpy(float)
                                     if "avg_rating_raw" in df else df["rating_norm"].to_numpy(float),
        "retention_proxy (engagement)": df["retention_proxy"].to_numpy(float),
        "install_norm (pure distribution)": df["install_norm"].to_numpy(float),
        "velocity_norm (distribution)": df["velocity_norm"].to_numpy(float),
    }

    results = {}
    print(f"{'target':38s} {'CV R2':>7s} {'top-q AUC':>10s}")
    for name, y in targets.items():
        y = np.asarray(y, dtype=float)
        mask = ~np.isnan(y)
        r2, auc = cv_r2(X[mask], y[mask])
        results[name] = {"cv_r2": round(r2, 3), "top_quartile_auc": round(auc, 3),
                         "n": int(mask.sum())}
        print(f"{name:38s} {r2:7.3f} {auc:10.3f}")

    ranked = sorted(results.items(), key=lambda kv: -kv[1]["cv_r2"])
    verdict = (f"Aspects best predict '{ranked[0][0]}' (R2={ranked[0][1]['cv_r2']}). "
               + ("QUALITY targets are learnable; the composite fails because it is "
                  "distribution-dominated." if ranked[0][1]["cv_r2"] >= 0.25
                  else "No target clears R2=0.25 — app aspects carry little signal for any "
                       "outcome; removal/reframe justified."))
    OUT.write_text(json.dumps({"results": results, "verdict": verdict}, indent=2),
                   encoding="utf-8")
    print(f"\n{verdict}\nSaved {OUT}")


if __name__ == "__main__":
    main()
