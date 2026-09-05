"""Collect buying-intent Reddit comments per category via the Arctic Shift API.

Why Arctic Shift: Reddit's official API is blocked for us; Arctic Shift serves
the community archive over plain HTTP (no auth) and allows subreddit/title/date
filtering. We pull ONLY intent-rich threads (recommend / regret / avoid ...),
then keep high-score, mid-length, deduped comments — mirroring the review
cleaning rules in DATA_PLAYBOOK.md.

Output: data/staging/reddit_context.json   {category: [comment strings]}
        (staging on purpose — data/final/ is only written by collect_all.py)
Raw per-category pulls are cached in data/staging/reddit_raw/<cat>.jsonl and
re-used on rerun; delete a file to force a refresh.

Usage:
  python scripts/collect_reddit.py --category wireless_headphones
  python scripts/collect_reddit.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API = "https://arctic-shift.photon-reddit.com/api"
STAGING = Path("data/staging")
RAW_DIR = STAGING / "reddit_raw"
OUT_PATH = STAGING / "reddit_context.json"

# category -> (subreddits, extra title keywords beyond the shared intent set)
CATEGORY_SOURCES: dict[str, tuple[list[str], list[str]]] = {
    "wireless_headphones": (["headphones", "HeadphoneAdvice", "Earbuds"], ["earbuds", "headphones"]),
    "bluetooth_speakers": (["Bluetooth_Speakers", "audiophile"], ["speaker"]),
    "smartphones": (["PickAnAndroidForMe", "smartphones"], ["phone"]),
    "smartwatches": (["smartwatch", "GalaxyWatch", "AndroidWear"], ["watch"]),
    "power_banks": (["UsbCHardware", "batteries", "AndroidQuestions"], ["power bank", "powerbank"]),
    "kitchen_appliances": (["BuyItForLife", "Cooking", "KitchenConfidential"], ["blender", "air fryer", "kettle", "toaster"]),
    "finance_apps": (["personalfinance", "budget"], ["app"]),
    "health_fitness_apps": (["fitness", "loseit"], ["app"]),
    "productivity_apps": (["productivity", "ProductivityApps"], ["app"]),
    "education_apps": (["languagelearning", "GetStudying"], ["app"]),
}

# shared buying-decision title keywords — threads dense in priorities/failures
INTENT_KEYWORDS = ["recommend", "worth it", "regret", "avoid", "broke",
                   "what should i", "buying", "disappointed"]

MIN_COMMENT_SCORE = 5
MIN_WORDS, MAX_WORDS = 10, 400
MAX_POSTS_PER_QUERY = 25
MAX_COMMENTS_PER_POST = 40
TARGET_PER_CATEGORY = 400
REQUEST_GAP_S = 1.2  # the API asks to "slow down" if hit faster


def _get(url: str, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_GAP_S * (attempt + 1))
            req = urllib.request.Request(  # API 403s python's default UA
                url, headers={"User-Agent": "capstone-research/1.0 (academic project)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data.get("error"):
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            if attempt == retries - 1:
                print(f"    giving up on {url[:90]}... ({exc})")
                return {"data": []}
    return {"data": []}


def _search_posts(subreddit: str, title_kw: str, limit: int) -> list[dict]:
    q = urllib.parse.urlencode({
        "subreddit": subreddit, "title": title_kw, "limit": limit,
        "after": "2022-01-01",
    })
    return _get(f"{API}/posts/search?{q}").get("data") or []


def _comments_for(link_id: str, limit: int) -> list[dict]:
    q = urllib.parse.urlencode({"link_id": link_id, "limit": limit})
    return _get(f"{API}/comments/search?{q}").get("data") or []


def _clean(body: str) -> str | None:
    body = " ".join(body.split())
    if body in ("[deleted]", "[removed]") or "http" in body.lower():
        return None
    n = len(body.split())
    if not (MIN_WORDS <= n <= MAX_WORDS):
        return None
    # crude English/ascii guard, same spirit as the review cleaner
    if sum(c.isascii() for c in body) / len(body) < 0.95:
        return None
    return body


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / max(len(a | b), 1)


def collect_category(category: str) -> list[dict]:
    raw_path = RAW_DIR / f"{category}.jsonl"
    if raw_path.exists():
        print(f"  [cache] {raw_path}")
        return [json.loads(l) for l in raw_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    subs, extra_kw = CATEGORY_SOURCES[category]
    keywords = INTENT_KEYWORDS + extra_kw
    posts: dict[str, dict] = {}
    for sub in subs:
        for kw in keywords:
            for p in _search_posts(sub, kw, MAX_POSTS_PER_QUERY):
                if p.get("num_comments", 0) >= 3:
                    posts[p["id"]] = p
        print(f"  r/{sub}: {len(posts)} candidate posts so far")

    # highest-engagement threads first; cap API calls
    ranked = sorted(posts.values(), key=lambda p: -(p.get("score") or 0))[:60]
    comments: list[dict] = []
    for p in ranked:
        if len(comments) >= TARGET_PER_CATEGORY * 3:
            break
        for c in _comments_for(f"t3_{p['id']}", MAX_COMMENTS_PER_POST):
            if (c.get("score") or 0) < MIN_COMMENT_SCORE:
                continue
            body = _clean(c.get("body") or "")
            if body:
                comments.append({"body": body, "score": c["score"],
                                 "post_title": p.get("title", "")[:150],
                                 "subreddit": p.get("subreddit", "")})
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        for c in comments:
            f.write(json.dumps(c) + "\n")
    print(f"  fetched {len(comments)} raw comments -> {raw_path}")
    return comments


def dedupe_and_rank(comments: list[dict]) -> list[str]:
    kept: list[tuple[set[str], dict]] = []
    for c in sorted(comments, key=lambda x: -x["score"]):
        words = set(c["body"].lower().split())
        if any(_jaccard(words, w) > 0.7 for w, _ in kept):
            continue
        kept.append((words, c))
        if len(kept) >= TARGET_PER_CATEGORY:
            break
    return [c["body"] for _, c in kept]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", choices=sorted(CATEGORY_SOURCES))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    cats = sorted(CATEGORY_SOURCES) if args.all else [args.category]
    if not cats[0]:
        ap.error("pass --category X or --all")

    context = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}
    for cat in cats:
        print(f"== {cat} ==")
        raw = collect_category(cat)
        context[cat] = dedupe_and_rank(raw)
        print(f"  kept {len(context[cat])} deduped high-signal comments")

    STAGING.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(context, indent=1), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} ({sum(len(v) for v in context.values())} comments, "
          f"{len(context)} categories)")
    print("NOTE: staging only — copy into data/final/reddit_context.json yourself "
          "once you've eyeballed it (data/final is contract-protected).")


if __name__ == "__main__":
    main()
