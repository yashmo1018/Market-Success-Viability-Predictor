"""Hand-validation gate: pretty-print each extracted review beside its scores/evidence.

Run after `batch_extractor.py --limit 30`. Verify manually:
  (a) unmentioned aspects are null,
  (b) every evidence phrase actually appears in the review (mismatches are flagged).

Usage: python src/extraction/review_extraction_sample.py [--n 30] [--type physical|app]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SCORES_PATH = Path("data/extracted/aspect_scores.jsonl")


def _load_review_texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for name in ("reviews_physical.json", "reviews_app.json"):
        path = Path("data/final") / name
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for r in json.load(f):
                    texts[r["review_uid"]] = r["text"]
    return texts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--type", default=None, choices=["physical", "app"])
    args = ap.parse_args()

    if not SCORES_PATH.exists():
        sys.exit(f"{SCORES_PATH} not found — run batch_extractor.py --limit 30 first.")

    texts = _load_review_texts()
    rows = []
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if args.type and row["product_type"] != args.type:
                    continue
                rows.append(row)
    rows = rows[-args.n:]

    evidence_mismatches = 0
    for i, row in enumerate(rows, 1):
        text = texts.get(row["review_uid"], "<review text not found>")
        print("=" * 78)
        print(f"[{i}/{len(rows)}] {row['review_uid']}  model={row['model_used']}  "
              f"confidence={row['confidence']}")
        print("-" * 78)
        print(text)
        print("-" * 78)
        def _norm(s: str) -> str:
            s = s.replace("’", "'").replace("‘", "'")
            s = s.replace("“", '"').replace("”", '"')
            return " ".join(s.lower().split())

        for aspect, val in row["scores"].items():
            if val is None:
                print(f"  {aspect:28s}  null")
            else:
                ev, tx = _norm(val["evidence"]), _norm(text)
                if ev in tx:
                    flag = ""
                else:
                    # near-verbatim: every substantive evidence word appears in the review
                    words = [w.strip("\"'.,!?()") for w in ev.split()]
                    words = [w for w in words if len(w) >= 3]
                    if words and all(w in tx for w in words):
                        flag = "  (~ near-verbatim splice)"
                    else:
                        flag = "  << EVIDENCE NOT FOUND IN REVIEW"
                        evidence_mismatches += 1
                print(f"  {aspect:28s}  {val['score']:4.1f}  \"{val['evidence']}\"{flag}")
        print()

    print("=" * 78)
    print(f"Reviewed {len(rows)} extractions. Evidence mismatches: {evidence_mismatches}")
    if evidence_mismatches:
        print("WARNING: verify the flagged rows before launching the full batch.")
    else:
        print("All evidence phrases found verbatim. If nulls look right, launch the full batch.")


if __name__ == "__main__":
    main()
