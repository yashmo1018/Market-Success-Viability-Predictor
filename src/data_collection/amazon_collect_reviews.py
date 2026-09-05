"""Amazon step 2: stream review dumps, keep reviews of selected products.

  python src/data_collection/amazon_collect_reviews.py --source Appliances
  (repeat per source file; each is resumable and appends to the same output)

Reads data/raw/amazon_selected.json for the target ASIN set; writes matches to
data/raw/amazon_reviews_raw.jsonl, capped at MAX_REVIEWS_KEPT_PER_PRODUCT per
product (first-encountered; file order is user-grouped, i.e. effectively random
per product — acceptable, documented in DATA_PLAYBOOK.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_collection.category_rules import (AMAZON_SOURCE,
                                                MAX_REVIEWS_KEPT_PER_PRODUCT)
from src.data_collection.hf_stream import is_done, stream_jsonl

RAW_DIR = Path("data/raw")
OUT_PATH = RAW_DIR / "amazon_reviews_raw.jsonl"
SELECTED_PATH = RAW_DIR / "amazon_selected.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=sorted(set(AMAZON_SOURCE.values())))
    ap.add_argument("--max-bytes", type=int, default=None)
    args = ap.parse_args()

    with open(SELECTED_PATH, encoding="utf-8") as f:
        selected = json.load(f)
    targets = {asin for asin, meta in selected.items()
               if AMAZON_SOURCE[meta["category"]] == args.source}
    print(f"{args.source}: watching {len(targets)} target products")

    ckpt = RAW_DIR / f"ckpt_reviews_{args.source}.json"
    if is_done(ckpt):
        print("Review scan for this source already complete.")
        return

    counts: dict[str, int] = defaultdict(int)
    seen_uids: set[str] = set()
    if OUT_PATH.exists():  # resume: rebuild caps + dedup from output
        with open(OUT_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    counts[row["parent_asin"]] += 1
                    seen_uids.add(row["_uid"])

    kept = 0
    with open(OUT_PATH, "a", encoding="utf-8") as out:
        for row in stream_jsonl(f"raw/review_categories/{args.source}.jsonl", ckpt,
                                max_bytes=args.max_bytes):
            asin = row.get("parent_asin")
            if asin not in targets or counts[asin] >= MAX_REVIEWS_KEPT_PER_PRODUCT:
                continue
            uid = f"{asin}_{row.get('user_id','u')}_{row.get('timestamp',0)}"
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            counts[asin] += 1
            kept += 1
            out.write(json.dumps({
                "_uid": uid, "parent_asin": asin,
                "rating": row.get("rating"), "title": row.get("title") or "",
                "text": row.get("text") or "",
                "timestamp": row.get("timestamp"),  # ms since epoch in this dataset
                "verified": bool(row.get("verified_purchase")),
                "helpful_votes": int(row.get("helpful_vote") or 0),
                "user_id": row.get("user_id") or "",
            }, ensure_ascii=False) + "\n")
            if kept % 500 == 0:
                out.flush()
    full = sum(1 for a in targets if counts[a] >= MAX_REVIEWS_KEPT_PER_PRODUCT)
    print(f"{args.source}: kept {kept} new reviews; "
          f"{full}/{len(targets)} products at cap.")


if __name__ == "__main__":
    main()
