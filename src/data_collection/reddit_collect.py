"""Optional Reddit context collection via public JSON endpoints (no API key).

  python src/data_collection/reddit_collect.py

Writes data/raw/reddit_context_raw.json: {category: [post texts...]}.
Failures (rate limits, blocked) skip that category silently — reddit_context
is allowed to be {} by the contract.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_collection.category_rules import REDDIT_SUBS

OUT_PATH = Path("data/raw/reddit_context_raw.json")
UA = {"User-Agent": "capstone-academic-research/1.0"}


def fetch_sub(sub: str, limit: int = 50) -> list[str]:
    url = f"https://www.reddit.com/r/{sub}/top.json?t=year&limit={limit}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        text = (d.get("title") or "") + ". " + (d.get("selftext") or "")[:400]
        if len(text) > 25 and not d.get("stickied"):
            posts.append(text.strip())
    return posts


def main() -> None:
    out: dict[str, list[str]] = {}
    for category, subs in REDDIT_SUBS.items():
        texts: list[str] = []
        for sub in subs:
            try:
                texts.extend(fetch_sub(sub))
                time.sleep(2.5)
            except Exception as exc:
                print(f"  r/{sub} skipped: {exc}")
        if texts:
            out[category] = texts[:80]
            print(f"{category}: {len(out[category])} posts")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT_PATH} ({len(out)} categories; missing ones are fine)")


if __name__ == "__main__":
    main()
