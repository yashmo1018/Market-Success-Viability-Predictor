"""Compare ML algorithms on the physical-product success prediction task.

Trains 6 algorithms under identical 5-fold CV (seed 42) on the aspects-only
feature set, collects regression + classification metrics including accuracy,
specificity, MCC, and aggregated confusion matrices. Generates:
  - fig7_algorithm_metrics.png    (grouped bar: R², Acc, Prec, Rec, F1, AUC, MCC)
  - fig8_algorithm_tradeoffs.png  (3-panel: R², time, RMSE)
  - fig9_algorithm_table.png      (full metrics table)
  - fig10_confusion_matrices.png  (per-algorithm confusion matrices)

Also writes models/benchmarks/algorithm_comparison.json.

Run: python scripts/ml_algorithm_comparison.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.svm import SVR
from sklearn.model_selection import KFold
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, matthews_corrcoef, confusion_matrix,
)
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "models" / "benchmarks"
OUT = ROOT / "papers" / "figures"
BENCH.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
N_FOLDS = 5
np.random.seed(SEED)

BLUE, GRAY, GREEN, AMBER, RED = "#2563EB", "#94A3B8", "#059669", "#D97706", "#DC2626"
TEAL, PURPLE, NAVY = "#0D9488", "#7C3AED", "#1E3A5F"
ROSE = "#E11D48"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 300,
})


def load_aspects_only():
    df = pd.read_parquet(ROOT / "data/extracted/features_physical.parquet")
    feature_manifest = json.loads(
        (ROOT / "models/xgb_physical_features.json").read_text(encoding="utf-8")
    )
    meta_cols = {"price", "avg_rating", "rating_count_log", "review_velocity", "category"}
    aspect_cols = [c for c in feature_manifest if c not in meta_cols]
    X = df[aspect_cols].copy()
    for c in X.columns:
        if X[c].dtype.name == "category":
            X[c] = X[c].cat.codes
    y = df["success_score"].values
    return X, y, aspect_cols


def binarize_top_bottom(y, q=5):
    thresholds = np.percentile(y, [100 / q, 100 * (q - 1) / q])
    bottom = y <= thresholds[0]
    top = y >= thresholds[1]
    mask = bottom | top
    labels = np.zeros(len(y), dtype=int)
    labels[top] = 1
    return mask, labels


def get_models():
    return {
        "XGBoost": xgb.XGBRegressor(
            n_estimators=600, max_depth=5, learning_rate=0.05,
            min_child_weight=3, subsample=0.8, colsample_bytree=0.8,
            tree_method="hist", random_state=SEED,
            early_stopping_rounds=50,
        ),
        "Random Forest": RandomForestRegressor(
            n_estimators=600, max_depth=10, min_samples_leaf=3,
            random_state=SEED, n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=600, max_depth=5, learning_rate=0.05,
            min_samples_leaf=3, subsample=0.8, random_state=SEED,
        ),
        "SVR (RBF)": SVR(kernel="rbf", C=10, epsilon=0.1),
        "Ridge Regression": Ridge(alpha=1.0, random_state=SEED),
        "MLP Regressor": MLPRegressor(
            hidden_layer_sizes=(128, 64), max_iter=500,
            learning_rate_init=0.001, early_stopping=True,
            random_state=SEED,
        ),
    }


def run_comparison():
    X, y, cols = load_aspects_only()
    X_np = X.values.copy()
    X_np = np.nan_to_num(X_np, nan=0.0)

    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    results = {}

    for name, model in get_models().items():
        print(f"\n{'=' * 60}\nTraining: {name}\n{'=' * 60}")
        fold_r2, fold_rmse, fold_mae = [], [], []
        fold_acc, fold_prec, fold_rec, fold_f1 = [], [], [], []
        fold_spec, fold_auc, fold_mcc = [], [], []
        fold_times = []
        cm_total = np.zeros((2, 2), dtype=int)

        for fold_i, (train_idx, val_idx) in enumerate(kf.split(X_np)):
            X_train, X_val = X_np[train_idx], X_np[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            t0 = time.perf_counter()
            if "XGBoost" in name:
                model.fit(X_train, y_train,
                          eval_set=[(X_val, y_val)], verbose=False)
            else:
                model.fit(X_train, y_train)
            train_time = time.perf_counter() - t0
            fold_times.append(train_time)

            preds = model.predict(X_val)

            fold_r2.append(r2_score(y_val, preds))
            fold_rmse.append(np.sqrt(mean_squared_error(y_val, preds)))
            fold_mae.append(mean_absolute_error(y_val, preds))

            mask, labels = binarize_top_bottom(y_val)
            if mask.sum() >= 4 and len(np.unique(labels[mask])) == 2:
                pred_bin = (preds[mask] >= np.median(y_val)).astype(int)

                fold_acc.append(accuracy_score(labels[mask], pred_bin))
                fold_prec.append(precision_score(labels[mask], pred_bin, zero_division=0))
                fold_rec.append(recall_score(labels[mask], pred_bin, zero_division=0))
                fold_f1.append(f1_score(labels[mask], pred_bin, zero_division=0))
                fold_mcc.append(matthews_corrcoef(labels[mask], pred_bin))

                cm = confusion_matrix(labels[mask], pred_bin, labels=[0, 1])
                cm_total += cm
                tn, fp = cm[0, 0], cm[0, 1]
                fold_spec.append(tn / (tn + fp) if (tn + fp) > 0 else 0.0)

                try:
                    fold_auc.append(roc_auc_score(labels[mask], preds[mask]))
                except ValueError:
                    fold_auc.append(0.5)

            print(f"  Fold {fold_i + 1}: R²={fold_r2[-1]:.4f}, "
                  f"RMSE={fold_rmse[-1]:.2f}, Acc={fold_acc[-1]:.3f}, time={train_time:.2f}s")

        results[name] = {
            "r2": round(float(np.mean(fold_r2)), 4),
            "r2_std": round(float(np.std(fold_r2)), 4),
            "rmse": round(float(np.mean(fold_rmse)), 2),
            "rmse_std": round(float(np.std(fold_rmse)), 2),
            "mae": round(float(np.mean(fold_mae)), 2),
            "mae_std": round(float(np.std(fold_mae)), 2),
            "accuracy": round(float(np.mean(fold_acc)) if fold_acc else 0.0, 4),
            "precision": round(float(np.mean(fold_prec)) if fold_prec else 0.0, 4),
            "recall": round(float(np.mean(fold_rec)) if fold_rec else 0.0, 4),
            "specificity": round(float(np.mean(fold_spec)) if fold_spec else 0.0, 4),
            "f1": round(float(np.mean(fold_f1)) if fold_f1 else 0.0, 4),
            "auc_roc": round(float(np.mean(fold_auc)) if fold_auc else 0.5, 4),
            "mcc": round(float(np.mean(fold_mcc)) if fold_mcc else 0.0, 4),
            "train_time_s": round(float(np.mean(fold_times)), 3),
            "confusion_matrix": cm_total.tolist(),
        }
        print(f"  Mean: R²={results[name]['r2']}, Acc={results[name]['accuracy']}, "
              f"AUC={results[name]['auc_roc']}, MCC={results[name]['mcc']}, "
              f"time={results[name]['train_time_s']}s")
        print(f"  Aggregated CM: {cm_total.tolist()}")

    out_path = BENCH / "algorithm_comparison.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    return results


# ── Figure 7: grouped bar chart of all metrics ──────────────────────────
def make_bar_chart(results: dict) -> None:
    names = list(results.keys())
    metrics = ["r2", "accuracy", "precision", "recall", "f1", "auc_roc", "mcc"]
    labels = ["R²", "Accuracy", "Precision", "Recall", "F1", "AUC-ROC", "MCC"]
    colors = [BLUE, NAVY, GREEN, AMBER, TEAL, PURPLE, ROSE]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(names))
    w = 0.11
    offsets = np.arange(len(metrics)) - len(metrics) / 2 + 0.5

    for i, (m, label, color) in enumerate(zip(metrics, labels, colors)):
        vals = [results[n][m] for n in names]
        bars = ax.bar(x + offsets[i] * w, vals, w, label=label, color=color, alpha=0.88)
        for bar, val in zip(bars, vals):
            if abs(val) > 0.05:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.012,
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=5.5, rotation=55)

    ax.set_xticks(x)
    ax.set_xticklabels([n.replace(" ", "\n") for n in names], fontsize=9)
    ax.set_ylabel("Score")
    ax.set_title("Algorithm Comparison: All Evaluation Metrics\n"
                 "(Aspects-only features, 5-fold CV, physical products, n=732)",
                 fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=4)
    ax.set_ylim(-0.05, 1.25)
    ax.axhline(0, color="#0F172A", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(OUT / "fig7_algorithm_metrics.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved fig7_algorithm_metrics.png")


# ── Figure 8: R² / time / RMSE tradeoff ────────────────────────────────
def make_complexity_time_chart(results: dict) -> None:
    names = list(results.keys())

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    ax = axes[0]
    r2_vals = [results[n]["r2"] for n in names]
    colors_r2 = [GREEN if v == max(r2_vals) else (AMBER if v > 0.3 else RED) for v in r2_vals]
    bars = ax.barh(range(len(names)), r2_vals, color=colors_r2, height=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([n.replace(" ", "\n") for n in names], fontsize=8)
    ax.set_xlabel("R² Score (higher = better)")
    ax.set_title("Predictive Accuracy", fontsize=10)
    for bar, val in zip(bars, r2_vals):
        ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", fontsize=8)

    ax = axes[1]
    times = [results[n]["train_time_s"] for n in names]
    colors_t = [GREEN if t == min(times) else (AMBER if t < 5 else RED) for t in times]
    bars = ax.barh(range(len(names)), times, color=colors_t, height=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([n.replace(" ", "\n") for n in names], fontsize=8)
    ax.set_xlabel("Mean Training Time (seconds, lower = better)")
    ax.set_title("Training Efficiency", fontsize=10)
    for bar, val in zip(bars, times):
        ax.text(val + max(times) * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}s", va="center", fontsize=8)

    ax = axes[2]
    rmse_vals = [results[n]["rmse"] for n in names]
    colors_rmse = [GREEN if v == min(rmse_vals) else (AMBER if v < 15 else RED) for v in rmse_vals]
    bars = ax.barh(range(len(names)), rmse_vals, color=colors_rmse, height=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([n.replace(" ", "\n") for n in names], fontsize=8)
    ax.set_xlabel("RMSE (lower = better)")
    ax.set_title("Error Magnitude", fontsize=10)
    for bar, val in zip(bars, rmse_vals):
        ax.text(val + max(rmse_vals) * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=8)

    fig.suptitle("Why XGBoost? Multi-Algorithm Benchmark on Aspect-Based Product Features",
                 fontsize=12, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "fig8_algorithm_tradeoffs.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved fig8_algorithm_tradeoffs.png")


# ── Figure 9: full metrics table ────────────────────────────────────────
def make_summary_table(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(14, 3.8))
    ax.axis("off")

    columns = ["Algorithm", "R²", "RMSE", "MAE", "Accuracy",
               "Precision", "Recall", "Specificity", "F1",
               "AUC-ROC", "MCC", "Time(s)", "Verdict"]
    rows = []
    best_r2 = max(v["r2"] for v in results.values())

    for name, m in results.items():
        verdict = "BEST" if m["r2"] == best_r2 else ("Good" if m["r2"] > 0.4 else "Weak")
        rows.append([
            name,
            f'{m["r2"]:.3f}', f'{m["rmse"]:.1f}', f'{m["mae"]:.1f}',
            f'{m["accuracy"]:.3f}', f'{m["precision"]:.3f}',
            f'{m["recall"]:.3f}', f'{m["specificity"]:.3f}',
            f'{m["f1"]:.3f}', f'{m["auc_roc"]:.3f}',
            f'{m["mcc"]:.3f}', f'{m["train_time_s"]:.2f}', verdict,
        ])

    table = ax.table(cellText=rows, colLabels=columns, loc="center",
                     cellLoc="center", colColours=["#E2E8F0"] * len(columns))
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1.0, 1.5)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#CBD5E1")
        elif col == len(columns) - 1:
            text = cell.get_text().get_text()
            if text == "BEST":
                cell.set_facecolor("#D1FAE5")
                cell.set_text_props(fontweight="bold", color="#065F46")
            elif text == "Good":
                cell.set_facecolor("#FEF3C7")
            else:
                cell.set_facecolor("#FEE2E2")

    ax.set_title("Complete Algorithm Comparison — All Metrics\n"
                 "Aspects-Only Features, Physical Products (n=732, 5-fold CV, seed=42)",
                 fontsize=10, pad=20)
    fig.tight_layout()
    fig.savefig(OUT / "fig9_algorithm_table.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"Saved fig9_algorithm_table.png")


# ── Figure 10: confusion matrices ───────────────────────────────────────
def make_confusion_matrices(results: dict) -> None:
    names = list(results.keys())
    n = len(names)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.2))
    if n == 1:
        axes = [axes]

    cm_labels = ["Flop\n(bottom 20%)", "Hit\n(top 20%)"]

    for ax, name in zip(axes, names):
        cm = np.array(results[name]["confusion_matrix"])
        cm_pct = cm.astype(float) / cm.sum() * 100

        ax.imshow(cm_pct, interpolation="nearest", cmap="Blues", vmin=0, vmax=60)
        for i in range(2):
            for j in range(2):
                color = "white" if cm_pct[i, j] > 35 else "#0F172A"
                ax.text(j, i, f"{cm[i, j]}\n({cm_pct[i, j]:.1f}%)",
                        ha="center", va="center", fontsize=9,
                        fontweight="bold", color=color)

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(cm_labels, fontsize=7)
        ax.set_yticklabels(cm_labels, fontsize=7)
        ax.set_xlabel("Predicted", fontsize=8)
        if ax == axes[0]:
            ax.set_ylabel("Actual", fontsize=8)

        acc = results[name]["accuracy"]
        short = name.replace(" Regression", "").replace(" Regressor", "")
        ax.set_title(f"{short}\nAcc={acc:.1%}", fontsize=9, pad=8)

    fig.suptitle("Aggregated Confusion Matrices (5-fold CV, top-20% vs bottom-20%)",
                 fontsize=11, y=1.04)
    fig.tight_layout()
    fig.savefig(OUT / "fig10_confusion_matrices.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"Saved fig10_confusion_matrices.png")


if __name__ == "__main__":
    results = run_comparison()
    make_bar_chart(results)
    make_complexity_time_chart(results)
    make_summary_table(results)
    make_confusion_matrices(results)
    print("\nDone. All figures saved to papers/figures/")
