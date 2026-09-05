"""Generate a synthetic data/final/-shaped dataset for end-to-end pipeline testing.

This lets the whole pipeline (Stages A-G + app) be verified BEFORE the data team
delivers real data. Products get latent aspect qualities; reviews mention a random
subset of aspects with sentiment words the mock LLM provider can pick up, so the
extraction -> features -> training chain carries real (synthetic) signal.

Usage: python scripts/make_synthetic_data.py --out data/synthetic_final
       [--products-per-category 25] [--reviews-per-product 20] [--seed 42]

NEVER write to data/final/ — that directory belongs to the data team.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

PHYSICAL_CATEGORIES = ["wireless_headphones", "bluetooth_speakers", "smartphones",
                       "smartwatches", "power_banks", "kitchen_appliances"]
APP_CATEGORIES = ["finance_apps", "health_fitness_apps", "productivity_apps",
                  "education_apps"]

PRICE_RANGES = {
    "wireless_headphones": (20, 350), "bluetooth_speakers": (15, 300),
    "smartphones": (150, 1200), "smartwatches": (30, 500),
    "power_banks": (10, 80), "kitchen_appliances": (25, 400),
    "finance_apps": (0, 10), "health_fitness_apps": (0, 8),
    "productivity_apps": (0, 15), "education_apps": (0, 12),
}

# aspect -> (positive phrase templates, negative phrase templates)
ASPECT_PHRASES = {
    "value_for_money": (["great value for the price", "totally worth the money"],
                        ["way too expensive for what you get", "not worth the price at all"]),
    "utility": (["works great and the sound is excellent", "does the job perfectly, very useful"],
                ["the core function works terribly", "barely useful, poor sound"]),
    "ease_of_use": (["setup was easy and intuitive", "simple controls, comfortable to use daily"],
                    ["confusing setup, not easy at all", "controls are confusing and awkward"]),
    "reliability": (["reliable, works consistent every single day", "never fails, always connects"],
                    ["keeps having disconnect issues, unreliable", "constant malfunction after a week"]),
    "design_appeal": (["beautiful sleek design, love the look", "stylish aesthetic, looks premium"],
                      ["ugly design, looks cheap", "the look is dated and ugly"]),
    "after_sales": (["customer service replaced it quickly, great support", "warranty support was excellent"],
                    ["terrible customer service, warranty was useless", "support never responded, bad after sales"]),
    "build_quality": (["solid build with premium materials", "sturdy construction, great build"],
                      ["flimsy plastic build, feels cheap", "poor build, materials feel bad"]),
    "durability": (["still going strong after two years, durable", "survived drops, lasted for months"],
                   ["broke after two weeks", "wear shows quickly, not durable"]),
    "repairability": (["easy to repair with spare parts available", "replaceable battery, serviceable"],
                      ["impossible to repair, no spare parts", "cannot fix anything on it"]),
    "performance": (["fast and smooth, snappy load times", "smooth performance, no battery drain"],
                    ["slow and laggy, battery drain is terrible", "lag everywhere, loads are slow"]),
    "stability": (["stable, no crash in months", "bug-free and stable operation"],
                  ["crashes constantly, full of bugs", "app would freeze and glitch daily"]),
    "ad_experience": (["ads are minimal and never intrusive", "barely any ads, pleasant"],
                      ["ads popup everywhere, unbearable", "riddled with intrusive ads"]),
    "update_support": (["regular updates with new features", "developers ship updates weekly"],
                       ["abandoned, no update in a year", "no updates, feels abandoned"]),
    "privacy_trust": (["clear privacy policy, minimal permissions, I trust it", "respects my data and privacy"],
                      ["asks for scary permissions, privacy nightmare", "do not trust it with my data"]),
}
PHYSICAL_ASPECTS = ["value_for_money", "utility", "ease_of_use", "reliability",
                    "design_appeal", "after_sales", "build_quality", "durability",
                    "repairability"]
APP_ASPECTS = ["value_for_money", "utility", "ease_of_use", "reliability",
               "design_appeal", "after_sales", "performance", "stability",
               "ad_experience", "update_support", "privacy_trust"]

FILLER = ["I bought this last month.", "Using it every day since.",
          "My previous one was different.", "Bought it as a gift originally.",
          "I did a lot of research before buying.", "Shipping was on time.",
          "This is my second one of these.", "I use it mostly at home.",
          "My whole family tried it.", "I compared several options first."]

NOW = 1751500000  # fixed 'now' (2025-07) so the dataset is deterministic


def make_review_text(rng: random.Random, aspects: list[str], quality: dict[str, float]) -> tuple[str, float]:
    n_mention = rng.randint(2, 4)
    mentioned = rng.sample(aspects, n_mention)
    sentences = [rng.choice(FILLER)]
    sentiment_sum = 0.0
    for a in mentioned:
        positive = rng.random() < quality[a]
        pool = ASPECT_PHRASES[a][0 if positive else 1]
        sentences.append(rng.choice(pool).capitalize() + ".")
        sentiment_sum += 1.0 if positive else 0.0
    sentences.append(rng.choice(FILLER))
    rng.shuffle(sentences)
    frac = sentiment_sum / n_mention
    rating = max(1, min(5, round(1 + 4 * (0.15 + 0.7 * frac) + rng.uniform(-0.5, 0.5))))
    return " ".join(sentences), float(rating)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/synthetic_final")
    ap.add_argument("--products-per-category", type=int, default=25)
    ap.add_argument("--reviews-per-product", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    real_final = Path(__file__).resolve().parents[1] / "data" / "final"
    assert out.resolve() != real_final, "Refusing to write into the real data/final/"
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    def build(categories: list[str], aspects: list[str], is_app: bool):
        products, reviews = [], []
        for cat in categories:
            lo, hi = PRICE_RANGES[cat]
            for i in range(args.products_per_category):
                uid = f"{cat}_{i:03d}"
                # latent quality drives review sentiment -> aspects -> success
                overall = rng.betavariate(2.5, 2.0)
                quality = {a: min(0.95, max(0.05, overall + rng.uniform(-0.25, 0.25)))
                           for a in aspects}
                n_rev = max(5, int(args.reviews_per_product * (0.4 + 1.4 * overall)
                                   * rng.uniform(0.7, 1.3)))
                span = rng.randint(120, 900) * 86400
                first_ts = NOW - span - rng.randint(0, 200) * 86400
                ratings = []
                for j in range(n_rev):
                    text, rating = make_review_text(rng, aspects, quality)
                    ratings.append(rating)
                    reviews.append({
                        "review_uid": f"{uid}_r{j:04d}", "product_uid": uid,
                        "source": "google_play" if is_app else "amazon",
                        "rating": rating, "title": "Review",
                        "text": text, "verified": rng.random() < 0.8,
                        "helpful_votes": rng.randint(0, 50),
                        "review_ts": first_ts + int(span * rng.random()),
                        "reviewer_hash": f"h{rng.getrandbits(40):010x}",
                        "app_version": "1.0" if is_app else None,
                        "word_count": len(text.split()),
                    })
                avg_rating = round(sum(ratings) / len(ratings), 2)
                rating_count = int(n_rev * rng.uniform(3, 30))
                prod = {
                    "product_uid": uid, "source": "google_play" if is_app else "amazon",
                    "source_id": uid, "product_type": "app" if is_app else "physical",
                    "category": cat, "name": f"{cat.replace('_', ' ').title()} {i}",
                    "brand": f"Brand{i % 7}",
                    "price": round(lo + (hi - lo) * rng.betavariate(2, 3), 2),
                    "currency": "USD", "avg_rating": min(5.0, max(1.0, avg_rating)),
                    "rating_count": rating_count,
                    "first_review_ts": first_ts, "latest_review_ts": first_ts + span,
                    "specs": {}, "extra": {},
                }
                if is_app:
                    prod.update({
                        "monetization": rng.choice(["free", "freemium", "paid", "subscription"]),
                        "install_count": int(rating_count * rng.uniform(20, 400)),
                        "last_updated_ts": NOW - rng.randint(5, 600) * 86400,
                        "released_ts": first_ts - rng.randint(0, 300) * 86400,
                    })
                products.append(prod)
        return products, reviews

    prods_phys, revs_phys = build(PHYSICAL_CATEGORIES, PHYSICAL_ASPECTS, is_app=False)
    prods_app, revs_app = build(APP_CATEGORIES, APP_ASPECTS, is_app=True)

    files = {
        "products_physical.json": prods_phys, "products_app.json": prods_app,
        "reviews_physical.json": revs_phys, "reviews_app.json": revs_app,
        "reddit_context.json": {"wireless_headphones": [
            "People mostly care about sound quality and battery life",
            "Comfort for long sessions is a recurring complaint",
        ]},
        "manifest.json": {
            "generated_at": "2026-07-07T00:00:00", "pipeline_version": "synthetic-1.0",
            "categories": {}, "totals": {
                "products_physical": len(prods_phys), "products_app": len(prods_app),
                "reviews_physical": len(revs_phys), "reviews_app": len(revs_app)},
            "reddit_available": True, "validation_passed": True,
            "validation_report": "synthetic",
        },
    }
    for name, obj in files.items():
        with open(out / name, "w", encoding="utf-8") as f:
            json.dump(obj, f)
    print(f"Synthetic dataset written to {out}: "
          f"{len(prods_phys)}+{len(prods_app)} products, "
          f"{len(revs_phys)}+{len(revs_app)} reviews")


if __name__ == "__main__":
    main()
