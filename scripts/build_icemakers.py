"""Build ONLY the ice_makers products + cleaned reviews, in isolation.

Reuses the exact cleaning gauntlet from clean_and_build so ice_maker reviews are
processed identically to the rest of the corpus, but writes to a staging file
instead of overwriting data/final. The merge step (rebuild_physical_final.py)
splices these into the existing physical set — this avoids re-running the full
clean_and_build, which would reshuffle the shared RNG and invalidate the ~75k
existing aspect extractions for the keeper categories.

Output: data/staging/icemaker_products.json, data/staging/icemaker_reviews.json
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_collection.category_rules import match_category
from src.data_collection.clean_and_build import (
    MAX_REVIEWS_PER_PRODUCT, SEED, Gauntlet, _global_text_counts, _hash16, clean_text,
)

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/staging")
CATEGORY = "ice_makers"
MIN_REVIEWS = 5


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = json.loads((RAW_DIR / "amazon_selected.json").read_text(encoding="utf-8"))
    ice = {a: m for a, m in selected.items() if m.get("category") == CATEGORY}
    print(f"ice_makers in selection: {len(ice)}")

    by_product: dict[str, list[dict]] = defaultdict(list)
    with open(RAW_DIR / "amazon_reviews_raw.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["parent_asin"] in ice:
                    by_product[r["parent_asin"]].append(r)

    gauntlet = Gauntlet(_global_text_counts([(RAW_DIR / "amazon_reviews_raw.jsonl", "text")]))
    rng = random.Random(SEED)
    products, reviews = [], []
    for asin, meta in ice.items():
        if not match_category(meta["title"], CATEGORY):
            gauntlet.drops["product_reclassified_accessory"] += 1
            continue
        seen: set[str] = set()
        cleaned = []
        for r in by_product.get(asin, []):
            out = gauntlet.run(r.get("text"), r.get("rating"), r.get("timestamp"), seen)
            if out is None:
                continue
            text, rating, ts = out
            cleaned.append({**r, "text": text, "rating": rating, "ts": ts})
        if len(cleaned) < MIN_REVIEWS:
            gauntlet.drops["product_too_few_reviews"] += 1
            continue
        if len(cleaned) > MAX_REVIEWS_PER_PRODUCT:
            cleaned = rng.sample(cleaned, MAX_REVIEWS_PER_PRODUCT)
        puid = f"amzp_{asin}"
        ts_list = [c["ts"] for c in cleaned]
        products.append({
            "product_uid": puid, "source": "amazon", "source_id": asin,
            "product_type": "physical", "category": CATEGORY,
            "name": meta["title"], "brand": str(meta.get("brand") or "unknown"),
            "price": float(meta["price"]), "currency": "USD",
            "avg_rating": float(meta["avg_rating"]),
            "rating_count": int(meta["rating_count"]),
            "first_review_ts": min(ts_list), "latest_review_ts": max(ts_list),
            "specs": {"features": meta.get("features") or []}, "extra": {},
        })
        for c in cleaned:
            reviews.append({
                "review_uid": f"amzr_{_hash16(c['_uid'])}", "product_uid": puid,
                "source": "amazon", "rating": c["rating"],
                "title": clean_text(c.get("title") or "")[:200], "text": c["text"],
                "verified": bool(c.get("verified")),
                "helpful_votes": int(c.get("helpful_votes") or 0),
                "review_ts": c["ts"], "reviewer_hash": _hash16(c.get("user_id") or "anon"),
                "app_version": None, "word_count": len(c["text"].split()),
            })

    (OUT_DIR / "icemaker_products.json").write_text(
        json.dumps(products, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "icemaker_reviews.json").write_text(
        json.dumps(reviews, ensure_ascii=False), encoding="utf-8")
    print(f"Built {len(products)} ice_maker products, {len(reviews)} cleaned reviews.")
    print("drop reasons:", dict(gauntlet.drops))


if __name__ == "__main__":
    main()
