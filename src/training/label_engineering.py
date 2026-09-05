"""Stage C: label engineering — success_score per product + fake-review filter.

Output: data/extracted/labels.json
  {product_uid: {success_score, components: {...}, suspect_reviews: bool, category, product_type}}

Formulas (CLAUDE.md §4):
  velocity = review_count / max(months_between(first_review_ts, latest_review_ts), 1)
  PHYSICAL: 100 * (0.40*volume_norm + 0.35*rating_norm + 0.25*velocity_norm)
  APP:      100 * (0.30*install_norm + 0.30*rating_norm + 0.20*velocity_norm + 0.20*retention_norm)
All normalizations are min-max WITHIN CATEGORY; volume/install use log1p first.

Mandatory diagnostic: per-category std-dev + 10-bin histogram; flags any category
with std < 8 (flat labels) and exits nonzero so training does not proceed blindly.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.loading.load_final import ContractData, load_contract

LABELS_PATH = Path("data/extracted/labels.json")
FLAT_STD_THRESHOLD = 8.0

PHYSICAL_WEIGHTS = {"volume": 0.40, "rating": 0.35, "velocity": 0.25}
APP_WEIGHTS = {"install": 0.30, "rating": 0.30, "velocity": 0.20, "retention": 0.20}


def months_between(ts_a: int, ts_b: int) -> float:
    return abs(ts_b - ts_a) / (86400 * 30.44)


def minmax(values: np.ndarray) -> np.ndarray:
    lo, hi = float(np.min(values)), float(np.max(values))
    if hi - lo < 1e-12:
        return np.full_like(values, 0.5, dtype=float)
    return (values - lo) / (hi - lo)


# ---------------------------------------------------------------------------
# Fake-review robustness filter
# ---------------------------------------------------------------------------

def _burst_flag(review_ts: list[int]) -> bool:
    """>40% of reviews within a single 14-day window."""
    if len(review_ts) < 5:
        return False
    ts = sorted(review_ts)
    window = 14 * 86400
    threshold = 0.4 * len(ts)
    j = 0
    for i in range(len(ts)):
        while ts[i] - ts[j] > window:
            j += 1
        if i - j + 1 > threshold:
            return True
    return False


def _extreme_j_flag(ratings: list[float]) -> bool:
    """>85% 5-star AND >5% 1-star AND <5% middle (2-4 star)."""
    n = len(ratings)
    if n == 0:
        return False
    five = sum(1 for r in ratings if r >= 4.5) / n
    one = sum(1 for r in ratings if r <= 1.5) / n
    mid = sum(1 for r in ratings if 1.5 < r < 4.5) / n
    return five > 0.85 and one > 0.05 and mid < 0.05


def _near_duplicate_flag(texts: list[str], max_sample: int = 60) -> bool:
    """>30% of (sampled) reviews are near-duplicates (Jaccard > 0.7 on word sets)."""
    if len(texts) < 5:
        return False
    rng = np.random.RandomState(42)
    sample = texts if len(texts) <= max_sample else [
        texts[i] for i in rng.choice(len(texts), max_sample, replace=False)
    ]
    sets = [set(t.lower().split()) for t in sample]
    dup = set()
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            if union and len(sets[i] & sets[j]) / len(union) > 0.7:
                dup.add(i)
                dup.add(j)
    return len(dup) / len(sample) > 0.3


def flag_suspect_products(data: ContractData) -> dict[str, list[str]]:
    """Return {product_uid: [reasons]} for products failing any fake-review check."""
    by_product: dict[str, list] = defaultdict(list)
    for r in data.reviews_physical + data.reviews_app:
        by_product[r.product_uid].append(r)
    suspects: dict[str, list[str]] = {}
    for uid, reviews in by_product.items():
        reasons = []
        if _burst_flag([r.review_ts for r in reviews]):
            reasons.append("burst")
        if _extreme_j_flag([r.rating for r in reviews]):
            reasons.append("extreme_j")
        if _near_duplicate_flag([r.text for r in reviews]):
            reasons.append("near_duplicates")
        if reasons:
            suspects[uid] = reasons
    return suspects


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def compute_labels(data: ContractData) -> dict[str, dict]:
    suspects = flag_suspect_products(data)
    print(f"Fake-review filter: {len(suspects)} suspect products "
          f"({sorted(set(r for v in suspects.values() for r in v))or 'none'})")

    review_counts: dict[str, int] = defaultdict(int)
    for r in data.reviews_physical + data.reviews_app:
        review_counts[r.product_uid] += 1

    labels: dict[str, dict] = {}

    # ---- physical: per-category normalization
    by_cat: dict[str, list] = defaultdict(list)
    for p in data.products_physical:
        by_cat[p.category].append(p)
    for cat, prods in by_cat.items():
        volume = np.log1p([review_counts[p.product_uid] for p in prods])
        rating = np.array([p.avg_rating for p in prods], dtype=float)
        velocity = np.array([
            review_counts[p.product_uid]
            / max(months_between(p.first_review_ts, p.latest_review_ts), 1.0)
            for p in prods
        ])
        vn, rn, veln = minmax(volume), minmax(rating), minmax(velocity)
        for i, p in enumerate(prods):
            score = 100 * (PHYSICAL_WEIGHTS["volume"] * vn[i]
                           + PHYSICAL_WEIGHTS["rating"] * rn[i]
                           + PHYSICAL_WEIGHTS["velocity"] * veln[i])
            labels[p.product_uid] = {
                "success_score": round(float(score), 3),
                "components": {"volume_norm": round(float(vn[i]), 4),
                               "rating_norm": round(float(rn[i]), 4),
                               "velocity_norm": round(float(veln[i]), 4),
                               "velocity_raw": round(float(velocity[i]), 3)},
                "suspect_reviews": p.product_uid in suspects,
                "suspect_reasons": suspects.get(p.product_uid, []),
                "category": p.category,
                "product_type": "physical",
            }

    # ---- app: per-category normalization
    by_cat = defaultdict(list)
    for p in data.products_app:
        by_cat[p.category].append(p)
    for cat, prods in by_cat.items():
        install = np.log1p([p.install_count for p in prods])
        rating = np.array([p.avg_rating for p in prods], dtype=float)
        velocity = np.array([
            review_counts[p.product_uid]
            / max(months_between(p.first_review_ts, p.latest_review_ts), 1.0)
            for p in prods
        ])
        retention = np.clip(
            [p.rating_count / max(p.install_count, 1) for p in prods], 0.0, 1.0
        )
        inn, rn, veln, retn = (minmax(install), minmax(rating),
                               minmax(velocity), minmax(np.asarray(retention)))
        for i, p in enumerate(prods):
            score = 100 * (APP_WEIGHTS["install"] * inn[i]
                           + APP_WEIGHTS["rating"] * rn[i]
                           + APP_WEIGHTS["velocity"] * veln[i]
                           + APP_WEIGHTS["retention"] * retn[i])
            labels[p.product_uid] = {
                "success_score": round(float(score), 3),
                "components": {"install_norm": round(float(inn[i]), 4),
                               "rating_norm": round(float(rn[i]), 4),
                               "velocity_norm": round(float(veln[i]), 4),
                               "retention_norm": round(float(retn[i]), 4),
                               "retention_proxy": round(float(retention[i]), 5)},
                "suspect_reviews": p.product_uid in suspects,
                "suspect_reasons": suspects.get(p.product_uid, []),
                "category": p.category,
                "product_type": "app",
            }

    return labels


def print_diagnostics(labels: dict[str, dict]) -> list[str]:
    """Per-category std-dev + 10-bin histogram. Returns list of flat categories."""
    by_cat: dict[str, list[float]] = defaultdict(list)
    for row in labels.values():
        if not row["suspect_reviews"]:
            by_cat[row["category"]].append(row["success_score"])
    flat = []
    print("\nLABEL DIAGNOSTICS (non-suspect products)")
    for cat in sorted(by_cat):
        scores = np.array(by_cat[cat])
        std = float(np.std(scores))
        hist, _ = np.histogram(scores, bins=10, range=(0, 100))
        bar = " ".join(f"{c:3d}" for c in hist)
        status = "FLAT!" if std < FLAT_STD_THRESHOLD else "ok"
        print(f"  {cat:24s} n={len(scores):4d} std={std:6.2f} [{status}]  hist: {bar}")
        if std < FLAT_STD_THRESHOLD:
            flat.append(cat)
    return flat


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage C label engineering")
    ap.add_argument("--data-dir", default="data/final")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-flat", action="store_true",
                    help="do not exit on flat-label categories (document why!)")
    args = ap.parse_args()

    if LABELS_PATH.exists() and not args.force:
        print(f"{LABELS_PATH} exists — skipping (use --force to recompute).")
        return

    data = load_contract(args.data_dir)
    labels = compute_labels(data)
    n_suspect = sum(1 for v in labels.values() if v["suspect_reviews"])
    print(f"Labels computed for {len(labels)} products ({n_suspect} suspect, excluded from training).")

    flat = print_diagnostics(labels)

    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2)
    print(f"Wrote {LABELS_PATH}")

    if flat and not args.allow_flat:
        sys.exit(f"STOP: flat labels (std < {FLAT_STD_THRESHOLD}) in {flat}. "
                 "Adjust label weights before training, or rerun with --allow-flat.")


if __name__ == "__main__":
    main()
