"""Select a clean `ice_makers` physical category from the Appliances candidate pool.

Motivation: the original `kitchen_appliances` category was contaminated (~47% of
tagged products were accessories/consumables — coffee filters, frothing pitchers,
replacement parts) because `category_rules.py` used bare-substring includes
("ice maker", "espresso") with incomplete excludes. This script replaces that
category with a single, coherent, strictly-filtered appliance: countertop/portable
ICE MAKER MACHINES.

Strict rule: title must match an ice-maker-machine include AND zero excludes
(parts, filters, replacement components, built-in fridges), price >= $50, and
rating_count >= MIN_RATING_COUNT_PHYSICAL.

It APPENDS the selected ASINs to data/raw/amazon_selected.json under
category "ice_makers" (idempotent — reruns replace the ice_makers entries).
Reviews are fetched separately by amazon_collect_reviews.py --source Appliances.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_collection.category_rules import MIN_RATING_COUNT_PHYSICAL

CAND = Path("data/raw/amazon_candidates_Appliances.jsonl")
SELECTED = Path("data/raw/amazon_selected.json")
PRICE_FLOOR = 50.0

MAX_PRODUCTS = 150  # cap: keep the most-reviewed machines (most reliable labels)

INCLUDE = re.compile(
    r"\b(ice maker|ice machine|nugget ice|countertop ice|portable ice|bullet ice)\b", re.I)
# EXCLUDE targets refrigerator replacement PARTS only (the real contaminant here).
# Deliberately does NOT exclude bin/tray/scoop/filter/kit — countertop MACHINES
# legitimately mention those as features, and excluding them dropped ~100 real units.
EXCLUDE = re.compile(
    r"(\bassembly\b|\bauger\b|\bmotor\b|\bsolenoid\b|water valve|inlet valve|"
    r"\bcompatible with\b|\bfits\b|\breplacement\b|door handle|"
    r"\bfor (whirlpool|kenmore|ge|frigidaire|lg|samsung|kitchenaid|hotpoint|maytag)\b|"
    r"\b(wr\d|w10\d|aeq\d|da\d{2}|5303\d|241\d{3,}|2198\d|im11\d|im\d{3})\b|"
    r"\b\d{7,}\b|french door|cu\.?\s?ft|\brefrigerator/freezer\b|\bicemaker for\b)",
    re.I)


def load_jsonl(p: Path) -> list[dict]:
    out = []
    for line in p.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def price_of(r: dict) -> float:
    try:
        return float(r.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def rc_of(r: dict) -> int:
    try:
        return int(r.get("rating_count") or 0)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    cands = load_jsonl(CAND)
    picked: dict[str, dict] = {}
    for r in cands:
        title = str(r.get("title") or "")
        if not INCLUDE.search(title) or EXCLUDE.search(title):
            continue
        if price_of(r) < PRICE_FLOOR or rc_of(r) < MIN_RATING_COUNT_PHYSICAL:
            continue
        asin = r.get("parent_asin") or r.get("asin")
        if not asin or asin in picked:
            continue
        picked[asin] = {
            "parent_asin": asin,
            "category": "ice_makers",
            "title": title,
            "brand": r.get("brand"),
            "price": price_of(r),
            "avg_rating": r.get("avg_rating"),
            "rating_count": rc_of(r),
            "features": r.get("features"),
        }

    # cap to the most-reviewed machines (most reliable success labels)
    if len(picked) > MAX_PRODUCTS:
        top = sorted(picked.items(), key=lambda kv: rc_of(kv[1]), reverse=True)[:MAX_PRODUCTS]
        picked = dict(top)

    selected = json.loads(SELECTED.read_text(encoding="utf-8"))
    # idempotent: drop any prior ice_makers, then add fresh selection
    selected = {a: m for a, m in selected.items() if m.get("category") != "ice_makers"}
    selected.update(picked)
    SELECTED.write_text(json.dumps(selected, ensure_ascii=False, indent=0), encoding="utf-8")

    prices = sorted(price_of(m) for m in picked.values())
    med = prices[len(prices) // 2] if prices else 0
    print(f"Selected {len(picked)} ice_maker machines "
          f"(price floor ${PRICE_FLOOR:.0f}, rating_count >= {MIN_RATING_COUNT_PHYSICAL}).")
    print(f"  median price ${med:.2f}")
    print(f"  amazon_selected.json now has {len(selected)} products.")


if __name__ == "__main__":
    main()
