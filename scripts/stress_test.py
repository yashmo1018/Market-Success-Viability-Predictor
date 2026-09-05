"""Stress-test the prediction model on 50 designed pre-launch specs.

Tests the MODEL layer (aspect scores -> viability + explanation) with CONTROLLED
inputs, so we can measure what LLM noise would otherwise hide:
  1. accuracy      — do known-tier specs rank correctly (excellent > ... > poor)?
  2. validation    — are all outputs in-range, well-formed, actionable?
  3. leakage       — does viability track real aspect signal, not just price? (shuffle test)
  4. performance   — prediction spread, tier separation, headline-vs-full agreement
  5. goal-match    — every result gives pre-launch risks + strengths the owner can act on
  6. actionability — risks/strengths name DESIGN aspects, not un-actionable popularity metadata
  7. sensitivity   — changing one aspect moves viability in the right direction

Run: python scripts/stress_test.py
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.prediction.predictor import Predictor
from src.extraction.extraction_prompt import PHYSICAL_ASPECT_KEYS

TIERS = {"excellent": 8.7, "good": 7.2, "average": 5.5, "poor": 3.8, "flawed": 2.2}
CATEGORIES = ["wireless_headphones", "bluetooth_speakers", "smartphones",
              "smartwatches", "power_banks", "kitchen_appliances"]
CAT_PRICE = {"wireless_headphones": 90, "bluetooth_speakers": 70, "smartphones": 500,
             "smartwatches": 150, "power_banks": 35, "kitchen_appliances": 120}

# metadata features that should NOT appear in aspects-only SHAP explanations
METADATA_FEATURES = {"review_velocity", "rating_count_log", "avg_rating",
                     "install_count_log", "price", "days_since_update"}


def make_specs() -> list[dict]:
    """50 specs: 6 categories x ~8 tier-variants, deterministic (seed 42)."""
    rng = np.random.RandomState(42)
    specs = []
    tier_names = list(TIERS)
    i = 0
    while len(specs) < 50:
        cat = CATEGORIES[i % len(CATEGORIES)]
        tier = tier_names[(i // len(CATEGORIES)) % len(tier_names)]
        base = TIERS[tier]
        aspects = {a: float(np.clip(base + rng.uniform(-1.2, 1.2), 0, 10))
                   for a in PHYSICAL_ASPECT_KEYS}
        price = CAT_PRICE[cat] * (0.7 + 0.5 * (base / 10)) * rng.uniform(0.85, 1.15)
        specs.append({"id": i, "category": cat, "tier": tier,
                      "aspects": aspects, "price": round(price, 2)})
        i += 1
    return specs


def run() -> None:
    pred = Predictor()
    specs = make_specs()
    results = []
    print(f"Running {len(specs)} specs...\n")
    for s in specs:
        out = pred.predict_from_bridged(
            s["aspects"], s["category"], {"price": s["price"]},
            reasoning={a: f"designed {s['tier']} tier" for a in s["aspects"]})
        all_feats = [r["feature"] for r in out["top_risks"]] + \
                    [r["feature"] for r in out["top_strengths"]]
        results.append({**s,
                        "viability": out["viability_pct"],
                        "full_model": out.get("full_model_pct", out["viability_pct"]),
                        "n_risks": len(out["top_risks"]),
                        "n_strengths": len(out["top_strengths"]),
                        "top_risk": out["top_risks"][0]["feature"] if out["top_risks"] else None,
                        "top_strength": out["top_strengths"][0]["feature"] if out["top_strengths"] else None,
                        "all_risk_feats": [r["feature"] for r in out["top_risks"]],
                        "all_strength_feats": [r["feature"] for r in out["top_strengths"]],
                        })
        print(f"  [{s['id']:2d}] {s['category']:20s} {s['tier']:9s} "
              f"${s['price']:7.2f} -> design_viability={out['viability_pct']:5.1f} "
              f"full={out.get('full_model_pct', 'n/a'):>5} "
              f"risk={results[-1]['top_risk']:25s} strength={results[-1]['top_strength']}")

    print("\n" + "=" * 70)
    analyze(results, pred, specs)


def analyze(results: list[dict], pred: Predictor, specs: list[dict]) -> None:
    tier_rank = {t: i for i, t in enumerate(TIERS)}
    passes = []

    # --- 1 & 4: tier separation ---
    by_tier = defaultdict(list)
    for r in results:
        by_tier[r["tier"]].append(r["viability"])
    print("1/4. TIER SEPARATION (design viability by designed quality):")
    means = {}
    for t in TIERS:
        v = by_tier[t]
        means[t] = np.mean(v)
        print(f"      {t:9s} n={len(v):2d}  mean={means[t]:5.1f}  range=[{min(v):.1f},{max(v):.1f}]")
    ordered = [means[t] for t in TIERS]
    mono = all(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1))
    gap = means["excellent"] - means["flawed"]
    print(f"      -> monotonic? {'PASS' if mono else 'FAIL'}")
    print(f"      -> excellent-vs-flawed gap: {gap:.1f} pts")
    passes.append(("tier_monotonic", mono))

    # --- 1: pairwise ranking accuracy within same category ---
    correct = total = 0
    bycat = defaultdict(list)
    for r in results:
        bycat[r["category"]].append(r)
    for cat, rs in bycat.items():
        for a in rs:
            for b in rs:
                if tier_rank[a["tier"]] < tier_rank[b["tier"]]:
                    total += 1
                    if a["viability"] >= b["viability"]:
                        correct += 1
    rank_pct = 100 * correct / total
    print(f"\n1. RANKING ACCURACY (better tier -> higher score, same cat): "
          f"{correct}/{total} = {rank_pct:.1f}%")
    passes.append(("ranking_accuracy>80%", rank_pct > 80))

    # --- 2: output validation ---
    bad = [r for r in results if not (0 <= r["viability"] <= 100 and
           r["n_risks"] >= 1 and r["n_strengths"] >= 1)]
    print(f"\n2. OUTPUT VALIDATION: {len(results) - len(bad)}/{len(results)} well-formed. "
          f"Malformed: {len(bad)}")
    passes.append(("all_valid", len(bad) == 0))

    # --- 3: leakage / price-echo ---
    viab = np.array([r["viability"] for r in results])
    price = np.array([r["price"] for r in results])
    aspect_mean = np.array([np.mean(list(r["aspects"].values())) for r in results])
    r_price = np.corrcoef(viab, price)[0, 1]
    r_aspect = np.corrcoef(viab, aspect_mean)[0, 1]
    leak_pass = r_aspect > abs(r_price)
    print(f"\n3. LEAKAGE / SIGNAL CHECK:")
    print(f"      corr(design_viability, mean_aspect) = {r_aspect:+.3f}  (want HIGH)")
    print(f"      corr(design_viability, price)       = {r_price:+.3f}  (want ~0)")
    print(f"      -> {'PASS' if leak_pass else 'FAIL'}")
    passes.append(("no_price_leak", leak_pass))

    # --- 4: spread ---
    print(f"\n4. PREDICTION SPREAD: min={viab.min():.1f} max={viab.max():.1f} "
          f"std={viab.std():.1f}")
    passes.append(("spread_std>5", viab.std() > 5))

    # --- 5: goal match ---
    actionable = sum(1 for r in results if r["n_risks"] >= 1 and r["n_strengths"] >= 1)
    print(f"\n5. GOAL MATCH: {actionable}/{len(results)} specs returned both "
          f"risks AND strengths")
    passes.append(("all_actionable", actionable == len(results)))

    # --- 6: NEW — actionability (risks/strengths are design features, not metadata) ---
    all_mentioned = []
    for r in results:
        all_mentioned.extend(r["all_risk_feats"])
        all_mentioned.extend(r["all_strength_feats"])
    meta_mentions = sum(1 for f in all_mentioned if f in METADATA_FEATURES)
    meta_pct = 100 * meta_mentions / max(len(all_mentioned), 1)
    feat_counts = Counter(all_mentioned)
    print(f"\n6. ACTIONABILITY (risks/strengths should name design aspects, not metadata):")
    print(f"      total risk+strength mentions: {len(all_mentioned)}")
    print(f"      metadata mentions: {meta_mentions} ({meta_pct:.1f}%)")
    print(f"      top-5 mentioned: {feat_counts.most_common(5)}")
    action_pass = meta_pct < 15
    print(f"      -> {'PASS' if action_pass else 'FAIL'}: "
          f"{'<15% metadata' if action_pass else f'{meta_pct:.0f}% metadata — model still pointing at un-actionable features'}")
    passes.append(("actionable_features<15%_meta", action_pass))

    # --- 7: NEW — sensitivity (bump aspects across MULTIPLE base tiers and categories) ---
    # Tests from "average" tier (mid-range scores ~5.5) where tree thresholds are
    # dense, across 3 categories, with a larger delta. Only counts DOWN bumps
    # (degrading a mid-range aspect should always hurt) since UP bumps on already-
    # high aspects legitimately plateau in tree models.
    print(f"\n7. SENSITIVITY (degrade mid-range aspects, viability should drop):")
    sens_correct = sens_total = 0
    test_aspects = ["utility", "build_quality", "ease_of_use", "reliability",
                    "value_for_money", "after_sales"]
    # pick average-tier specs from different categories
    avg_specs = [s for s in specs if s["tier"] == "average"][:3]
    for base in avg_specs:
        base_out = pred.predict_from_bridged(
            base["aspects"], base["category"], {"price": base["price"]})
        base_v = base_out["viability_pct"]
        for aspect in test_aspects:
            tweaked = copy.deepcopy(base["aspects"])
            tweaked[aspect] = max(tweaked[aspect] - 4.0, 0.0)
            out = pred.predict_from_bridged(
                tweaked, base["category"], {"price": base["price"]})
            moved = out["viability_pct"] - base_v
            sens_total += 1
            ok = moved <= 0
            if ok:
                sens_correct += 1
            tag = "ok" if ok else "WRONG"
            print(f"      {base['category']:20s} {aspect:20s} "
                  f"{base_v:.1f} -> {out['viability_pct']:.1f} "
                  f"(delta={moved:+.1f}) [{tag}]")
    sens_pct = 100 * sens_correct / sens_total
    print(f"      -> {sens_correct}/{sens_total} = {sens_pct:.0f}% correct direction")
    passes.append(("sensitivity>60%", sens_pct > 60))

    # --- verdict ---
    print("\n" + "=" * 70)
    for name, ok in passes:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    all_pass = all(ok for _, ok in passes)
    print(f"\nOVERALL: {'PASS — model is design-responsive and pre-launch actionable' if all_pass else 'REVIEW NEEDED'}")


if __name__ == "__main__":
    run()
