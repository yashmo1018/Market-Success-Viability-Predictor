"""Amazon step 1: stream category metadata, match category rules, select products.

  python src/data_collection/amazon_select_products.py --source Appliances
  python src/data_collection/amazon_select_products.py --source Electronics
  python src/data_collection/amazon_select_products.py --source Cell_Phones_and_Accessories
  python src/data_collection/amazon_select_products.py --finalize     # after all sources

Streams raw/meta_categories/meta_<source>.jsonl (resumable), writes matching
candidates to data/raw/amazon_candidates_<source>.jsonl, then --finalize picks
up to TARGET_PRODUCTS_PER_CATEGORY per category, stratified across price
terciles and popularity, into data/raw/amazon_selected.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_collection.category_rules import (
    AMAZON_SOURCE, MIN_RATING_COUNT_PHYSICAL, TARGET_PRODUCTS_PER_CATEGORY,
    categorize_title)
from src.data_collection.hf_stream import is_done, stream_jsonl

RAW_DIR = Path("data/raw")
SELECTED_PATH = RAW_DIR / "amazon_selected.json"


def _parse_price(price) -> float | None:
    if price is None:
        return None
    try:
        p = float(str(price).replace("$", "").replace(",", "").strip())
        return p if 0.5 <= p <= 5000 else None
    except ValueError:
        return None


def scan_source(source: str, max_bytes: int | None) -> None:
    out_path = RAW_DIR / f"amazon_candidates_{source}.jsonl"
    ckpt = RAW_DIR / f"ckpt_meta_{source}.json"
    if is_done(ckpt):
        print(f"{source} metadata scan already complete ({out_path}).")
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if out_path.exists():  # rebuild dedup set on resume
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    seen.add(json.loads(line)["parent_asin"])

    n_match = len(seen)
    with open(out_path, "a", encoding="utf-8") as out:
        for row in stream_jsonl(f"raw/meta_categories/meta_{source}.jsonl", ckpt,
                                max_bytes=max_bytes):
            title = row.get("title") or ""
            asin = row.get("parent_asin")
            if not asin or asin in seen:
                continue
            price = _parse_price(row.get("price"))
            rating_n = row.get("rating_number") or 0
            avg = row.get("average_rating")
            if price is None or rating_n < MIN_RATING_COUNT_PHYSICAL or not avg:
                continue
            cat = categorize_title(title, source)
            if cat is None:
                continue
            seen.add(asin)
            n_match += 1
            out.write(json.dumps({
                "parent_asin": asin, "category": cat, "title": title[:300],
                "brand": (row.get("details") or {}).get("Brand")
                         or (row.get("store") or "unknown"),
                "price": price, "avg_rating": float(avg), "rating_count": int(rating_n),
                "features": (row.get("features") or [])[:8],
            }, ensure_ascii=False) + "\n")
            if n_match % 200 == 0:
                out.flush()
    print(f"{source}: {n_match} candidate products matched.")


def finalize() -> None:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for source in set(AMAZON_SOURCE.values()):
        path = RAW_DIR / f"amazon_candidates_{source}.jsonl"
        if not path.exists():
            print(f"WARNING: {path} missing — run --source {source} first.")
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    by_cat[row["category"]].append(row)

    selected: dict[str, dict] = {}
    for cat, rows in sorted(by_cat.items()):
        # dedupe near-identical titles (same brand + same first 8 title words)
        seen_keys: set[str] = set()
        unique = []
        for r in sorted(rows, key=lambda r: -r["rating_count"]):
            key = (str(r["brand"]).lower(), " ".join(r["title"].lower().split()[:8]))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique.append(r)
        # stratify: 3 price terciles x popularity order, round-robin fill
        unique.sort(key=lambda r: r["price"])
        n = len(unique)
        terciles = [unique[: n // 3], unique[n // 3: 2 * n // 3], unique[2 * n // 3:]]
        for t in terciles:
            t.sort(key=lambda r: -r["rating_count"])
        picked, i = [], 0
        while len(picked) < TARGET_PRODUCTS_PER_CATEGORY and any(terciles):
            t = terciles[i % 3]
            if t:
                picked.append(t.pop(0))
            i += 1
            if i > 10 * TARGET_PRODUCTS_PER_CATEGORY:
                break
        for r in picked:
            selected[r["parent_asin"]] = r
        print(f"  {cat}: {len(rows)} candidates -> {len(unique)} unique -> {len(picked)} selected")

    with open(SELECTED_PATH, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=1)
    print(f"Wrote {SELECTED_PATH} ({len(selected)} products total)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=sorted(set(AMAZON_SOURCE.values())))
    ap.add_argument("--finalize", action="store_true")
    ap.add_argument("--max-bytes", type=int, default=None,
                    help="stop after N bytes this session (testing)")
    args = ap.parse_args()
    if args.source:
        scan_source(args.source, args.max_bytes)
    if args.finalize:
        finalize()
    if not args.source and not args.finalize:
        ap.error("give --source <file> and/or --finalize")


if __name__ == "__main__":
    main()
