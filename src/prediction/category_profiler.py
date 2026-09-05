"""Stage F: category profiles — the bridging context.

Output: data/extracted/category_profiles.json keyed by category, each with:
  price stats, mean aspect scores + mention rates, top pain points/strengths with
  evidence phrases, optional Reddit priorities summary, success_score stats.

Usage: python src/prediction/category_profiler.py [--force] [--mock]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extraction.extraction_prompt import APP_ASPECT_KEYS, PHYSICAL_ASPECT_KEYS

SCORES_PATH = Path("data/extracted/aspect_scores.jsonl")
LABELS_PATH = Path("data/extracted/labels.json")
PROFILES_PATH = Path("data/extracted/category_profiles.json")
REDDIT_PATH = Path("data/final/reddit_context.json")
N_EVIDENCE = 15
N_PAIN_STRENGTH = 3

REDDIT_SUMMARY_PROMPT = """Summarize what consumers in the "{category}" category prioritize \
when choosing a product, based on these Reddit discussions. Return 3-6 short bullet points, \
plain text, most important first.

REDDIT DISCUSSIONS:
{reddit_text}
"""


def _collect_evidence(product_type: str, product_uids: set[str]) -> dict[str, list[tuple[float, str]]]:
    """aspect -> [(score, evidence), ...] for the given products."""
    out: dict[str, list[tuple[float, str]]] = defaultdict(list)
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["product_type"] != product_type or row["product_uid"] not in product_uids:
                continue
            for aspect, val in row["scores"].items():
                if val is not None:
                    out[aspect].append((val["score"], val["evidence"]))
    return out


def _reddit_priorities(category: str, reddit_context: dict, use_mock: bool) -> str | None:
    entry = reddit_context.get(category)
    if not entry:
        return None
    if isinstance(entry, list):
        text = "\n".join(str(x) for x in entry[:50])
    elif isinstance(entry, dict):
        text = json.dumps(entry)[:8000]
    else:
        text = str(entry)[:8000]
    try:
        from src.extraction.llm_provider import ProviderPool
        # groq fallback: a silent None here (e.g. gemini daily quota) would
        # quietly strip consumer_priorities from every profile
        pool = (ProviderPool(config={}, providers=["mock"]) if use_mock
                else ProviderPool(providers=["gemini_flash", "groq_llama70b"]))
        prompt = REDDIT_SUMMARY_PROMPT.format(category=category, reddit_text=text)
        summary, _ = pool.generate(prompt, json_mode=False)
        return summary.strip()[:2000]
    except Exception:
        return None  # skip silently per spec


import re

def build_profiles(use_mock: bool = False) -> dict:
    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = json.load(f)
    reddit_context = {}
    if REDDIT_PATH.exists():
        with open(REDDIT_PATH, encoding="utf-8") as f:
            reddit_context = json.load(f) or {}

    phys_meta = {}
    if Path("data/final/products_physical.json").exists():
        with open("data/final/products_physical.json", encoding="utf-8") as f:
            phys_meta = {p["product_uid"]: p for p in json.load(f)}

    app_meta = {}
    if Path("data/final/products_app.json").exists():
        with open("data/final/products_app.json", encoding="utf-8") as f:
            app_meta = {p["product_uid"]: p for p in json.load(f)}

    profiles: dict[str, dict] = {}
    for product_type in ("physical", "app"):
        parquet = Path(f"data/extracted/features_{product_type}.parquet")
        if not parquet.exists():
            print(f"WARNING: {parquet} missing — skipping {product_type} profiles")
            continue
        df = pd.read_parquet(parquet)
        aspects = PHYSICAL_ASPECT_KEYS if product_type == "physical" else APP_ASPECT_KEYS

        for cat, group in df.groupby("category", observed=True):
            cat = str(cat)
            uids = set(group["product_uid"])
            evidence = _collect_evidence(product_type, uids)

            avg_scores = {a: (round(float(group[a].mean()), 2)
                              if group[a].notna().any() else None) for a in aspects}
            mention_rates = {a: round(float(group[f"{a}_mention_rate"].mean()), 3)
                             for a in aspects}
            scored = {a: s for a, s in avg_scores.items() if s is not None}
            worst = sorted(scored, key=scored.get)[:N_PAIN_STRENGTH]
            best = sorted(scored, key=scored.get, reverse=True)[:N_PAIN_STRENGTH]

            def _phrases(aspect_list: list[str], low: bool) -> dict[str, list[str]]:
                out = {}
                for a in aspect_list:
                    ranked = sorted(evidence.get(a, []), key=lambda t: t[0], reverse=not low)
                    out[a] = [e for _, e in ranked[:N_EVIDENCE]]
                return out

            success = group["success_score"]
            cat_labels = [v for v in labels.values() if v["category"] == cat]
            
            # Extract top competitor products for positioning grid
            meta_dict = phys_meta if product_type == "physical" else app_meta
            cat_products = []
            sorted_group = group.sort_values(by="rating_count_log", ascending=False)
            for _, row in sorted_group.iterrows():
                uid = row["product_uid"]
                m = meta_dict.get(uid, {})
                raw_title = m.get("title") or m.get("name") or m.get("app_name") or uid
                brand = m.get("brand") or m.get("developer") or m.get("manufacturer") or ""
                
                # Clean name
                c_name = raw_title.strip()
                if len(c_name) > 38:
                    parts = re.split(r'[,|–—\(\)]', c_name)
                    c_name = parts[0].strip() if (parts and len(parts[0].strip()) >= 5) else c_name[:38].strip()
                if brand and brand.lower() not in c_name.lower() and len(brand) < 15:
                    c_name = f"{brand} {c_name}"
                c_name = c_name[:42].strip()
                
                r_count_log = float(row.get("rating_count_log", 2.0))
                reviews_count = int(round(np.expm1(r_count_log))) if r_count_log > 0 else 100
                
                cat_products.append({
                    "name": c_name,
                    "full_name": raw_title,
                    "brand": brand,
                    "price": round(float(row["price"]), 2),
                    "viability": round(float(np.clip(row["success_score"], 0, 100)), 1),
                    "reviews": max(10, reviews_count)
                })
                if len(cat_products) >= 20:
                    break

            profiles[cat] = {
                "product_type": product_type,
                "n_products": int(len(group)),
                "category_products": cat_products,
                "price": {
                    "mean": round(float(group["price"].mean()), 2),
                    "median": round(float(group["price"].median()), 2),
                    "p25": round(float(group["price"].quantile(0.25)), 2),
                    "p75": round(float(group["price"].quantile(0.75)), 2),
                },
                "avg_aspect_scores": avg_scores,
                "avg_mention_rates": mention_rates,
                "pain_points": {"aspects": worst, "evidence": _phrases(worst, low=True)},
                "strengths": {"aspects": best, "evidence": _phrases(best, low=False)},
                "consumer_priorities": _reddit_priorities(cat, reddit_context, use_mock),
                "success_score": {
                    "mean": round(float(success.mean()), 2),
                    "p75_threshold": round(float(success.quantile(0.75)), 2),
                },
                # neutral priors used by the predictor for metadata features
                "median_rating_count_log": round(float(group["rating_count_log"].median()), 4),
                "median_review_velocity": round(float(group["review_velocity"].median()), 4),
                "median_avg_rating": round(float(group["avg_rating"].median()), 3),
                "median_install_count_log": (
                    round(float(group["install_count_log"].median()), 4)
                    if "install_count_log" in group else None),
                "median_days_since_update": (
                    round(float(group["days_since_update"].median()), 2)
                    if "days_since_update" in group else None),
                "n_suspect_excluded": sum(1 for v in cat_labels if v["suspect_reviews"]),
            }
            print(f"  {cat}: {len(group)} products, pain={worst}, strengths={best}")
    return profiles


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage F category profiles")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--mock", action="store_true", help="mock LLM for Reddit summaries")
    args = ap.parse_args()
    if PROFILES_PATH.exists() and not args.force:
        print(f"{PROFILES_PATH} exists — skipping (use --force).")
        return
    profiles = build_profiles(use_mock=args.mock)
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    print(f"Wrote {PROFILES_PATH} ({len(profiles)} categories)")


if __name__ == "__main__":
    main()
