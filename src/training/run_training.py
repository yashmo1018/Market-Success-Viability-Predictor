"""Stage E: THE single training command — runs Stages C -> D -> E end-to-end.

  python src/training/run_training.py [--force] [--data-dir data/final]

Skips cached stage outputs unless --force. Trains 4 models:
  xgb_physical.json, xgb_app.json                  (full feature set)
  xgb_physical_aspects_only.json, xgb_app_aspects_only.json  (leakage-honest variant)

Writes models/training_report.json + SHAP summary plots, and prints acceptance gates:
  R^2 >= 0.35 PASS | [0.2, 0.35) WARN | < 0.2 FAIL.
The paper's headline claim uses the aspects-only number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.training.feature_builder import feature_columns

MODELS_DIR = Path("models")
FEATURES_DIR = Path("data/extracted")
SEED = 42

XGB_PARAMS = dict(
    objective="reg:squarederror",
    n_estimators=600,
    learning_rate=0.05,
    max_depth=5,
    min_child_weight=3,
    subsample=0.8,
    colsample_bytree=0.8,
    enable_categorical=True,
    tree_method="hist",
    random_state=SEED,
)
EARLY_STOPPING_ROUNDS = 50

# columns removed for the honest "aspects-only" variant (CLAUDE.md §6 leakage guard).
# days_since_update is app metadata, not a review aspect — it must be excluded so the
# aspects-only model measures PURE sentiment contribution.
LEAKY_COLUMNS = ["price", "avg_rating", "rating_count_log", "review_velocity",
                 "install_count_log", "days_since_update"]


def _run_stage(script: str, force: bool, extra: list[str] | None = None) -> None:
    cmd = [sys.executable, script] + (["--force"] if force else []) + (extra or [])
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"Stage failed: {script} (exit {result.returncode})")


def _data_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def cross_validate(X: pd.DataFrame, y: np.ndarray, categories: np.ndarray,
                   label: str) -> dict:
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    fold_metrics, best_iters = [], []
    oof_pred = np.full(len(y), np.nan)
    for fold, (tr, va) in enumerate(kf.split(X), 1):
        model = xgb.XGBRegressor(**XGB_PARAMS,
                                 early_stopping_rounds=EARLY_STOPPING_ROUNDS)
        model.fit(X.iloc[tr], y[tr], eval_set=[(X.iloc[va], y[va])], verbose=False)
        pred = model.predict(X.iloc[va])
        oof_pred[va] = pred
        best_iters.append(int(model.best_iteration + 1) if model.best_iteration
                          is not None else XGB_PARAMS["n_estimators"])
        fold_metrics.append({
            "fold": fold,
            "rmse": float(np.sqrt(mean_squared_error(y[va], pred))),
            "mae": float(mean_absolute_error(y[va], pred)),
            "r2": float(r2_score(y[va], pred)),
        })

    per_category = {}
    for cat in np.unique(categories):
        mask = categories == cat
        if mask.sum() >= 5 and np.var(y[mask]) > 1e-9:
            per_category[str(cat)] = {
                "n": int(mask.sum()),
                "r2": float(r2_score(y[mask], oof_pred[mask])),
                "rmse": float(np.sqrt(mean_squared_error(y[mask], oof_pred[mask]))),
            }
        else:
            per_category[str(cat)] = {"n": int(mask.sum()), "r2": None, "rmse": None}

    mean = lambda k: float(np.mean([m[k] for m in fold_metrics]))
    summary = {
        "folds": fold_metrics,
        "mean_rmse": mean("rmse"), "mean_mae": mean("mae"), "mean_r2": mean("r2"),
        "per_category": per_category,
        "best_iteration": int(np.mean(best_iters)),
    }
    print(f"  {label}: CV R2={summary['mean_r2']:.3f} "
          f"RMSE={summary['mean_rmse']:.2f} MAE={summary['mean_mae']:.2f} "
          f"best_iter={summary['best_iteration']}")
    for cat, m in per_category.items():
        r2s = f"{m['r2']:.3f}" if m["r2"] is not None else "n/a (too few / no variance)"
        print(f"    {cat:24s} n={m['n']:4d} R2={r2s}")
    return summary


def train_final(X: pd.DataFrame, y: np.ndarray, n_estimators: int,
                out_path: Path) -> xgb.XGBRegressor:
    params = {**XGB_PARAMS, "n_estimators": max(n_estimators, 50)}
    model = xgb.XGBRegressor(**params)
    model.fit(X, y, verbose=False)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(out_path)
    print(f"  saved {out_path}")
    return model


def shap_summary(model: xgb.XGBRegressor, X: pd.DataFrame, out_path: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    X_shap = X.copy()
    if "category" in X_shap.columns:  # shap plotting needs numeric codes
        X_shap["category"] = X_shap["category"].cat.codes
    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(X_shap)
    plt.figure()
    shap.summary_plot(values, X_shap, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close("all")
    print(f"  saved {out_path}")
    importance = dict(zip(X.columns, np.abs(values).mean(axis=0).round(4).tolist()))
    return dict(sorted(importance.items(), key=lambda kv: -kv[1]))


def gate(r2: float, label: str) -> str:
    if r2 >= 0.35:
        verdict = "PASS"
    elif r2 >= 0.2:
        verdict = "WARN (usable; document the limitation)"
    else:
        verdict = ("FAIL — check: label variance (Stage C histogram), extraction quality "
                   "(hand-validation), mention-rate coverage, possible leakage/joins")
    print(f"  GATE {label}: R2={r2:.3f} -> {verdict}")
    return verdict


def train_product_type(product_type: str, report: dict) -> None:
    print(f"\n=== TRAINING: {product_type} ===")
    df = pd.read_parquet(FEATURES_DIR / f"features_{product_type}.parquet")
    cols = feature_columns(product_type)
    X = df[cols].copy()
    X["category"] = X["category"].astype("category")
    y = df["success_score"].to_numpy(dtype=float)
    categories = df["category"].astype(str).to_numpy()

    # Leakage guard: print correlation of avg_rating with the target
    corr = float(np.corrcoef(df["avg_rating"], y)[0, 1])
    print(f"  leakage check: corr(avg_rating, success_score) = {corr:.3f} "
          "(expected high — rating is part of the label; see aspects-only variant)")

    cv_full = cross_validate(X, y, categories, f"{product_type} FULL")
    model_full = train_final(X, y, cv_full["best_iteration"],
                             MODELS_DIR / f"xgb_{product_type}.json")
    imp_full = shap_summary(model_full, X,
                            MODELS_DIR / f"shap_summary_{product_type}.png")

    aspects_cols = [c for c in cols if c not in LEAKY_COLUMNS]
    Xa = X[aspects_cols]
    cv_aspects = cross_validate(Xa, y, categories, f"{product_type} ASPECTS-ONLY")
    model_aspects = train_final(Xa, y, cv_aspects["best_iteration"],
                                MODELS_DIR / f"xgb_{product_type}_aspects_only.json")
    imp_aspects = shap_summary(model_aspects, Xa,
                               MODELS_DIR / f"shap_summary_{product_type}_aspects_only.png")
    with open(MODELS_DIR / f"xgb_{product_type}_aspects_only_features.json", "w",
              encoding="utf-8") as f:
        json.dump(aspects_cols, f, indent=2)

    print(f"\n  ACCEPTANCE GATES ({product_type}):")
    report[product_type] = {
        "n_products": int(len(df)),
        "avg_rating_target_correlation": corr,
        "full": {**cv_full, "feature_importance": imp_full,
                 "gate": gate(cv_full["mean_r2"], f"{product_type} full")},
        "aspects_only": {**cv_aspects, "feature_importance": imp_aspects,
                         "gate": gate(cv_aspects["mean_r2"],
                                      f"{product_type} aspects-only (headline)")},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage E: C->D->E training pipeline")
    ap.add_argument("--force", action="store_true", help="recompute cached stage outputs")
    ap.add_argument("--data-dir", default="data/final")
    ap.add_argument("--allow-flat", action="store_true",
                    help="pass through to label engineering")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    extra = ["--data-dir", args.data_dir] + (["--allow-flat"] if args.allow_flat else [])
    _run_stage(str(root / "src/training/label_engineering.py"), args.force, extra)
    _run_stage(str(root / "src/training/feature_builder.py"), args.force,
               ["--data-dir", args.data_dir])

    report: dict = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": SEED,
        "xgb_params": {k: v for k, v in XGB_PARAMS.items()},
        "data_hash": _data_hash([FEATURES_DIR / "features_physical.parquet"]),
    }
    with open(Path("data/extracted/labels.json"), encoding="utf-8") as f:
        labels = json.load(f)
    report["n_excluded_suspect"] = sum(1 for v in labels.values() if v["suspect_reviews"])

    # apps removed from the system — physical models only
    for product_type in ("physical",):
        train_product_type(product_type, report)

    out = MODELS_DIR / "training_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nTraining report written to {out}")


if __name__ == "__main__":
    main()
