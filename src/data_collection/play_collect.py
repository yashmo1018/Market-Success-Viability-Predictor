"""Google Play collection: discover apps per category via search, fetch metadata
and reviews.

  python src/data_collection/play_collect.py [--category finance_apps]
  [--limit-apps N] [--reviews-per-app N]

Discovery: search each term in PLAY_SEARCH_TERMS, keep apps passing install/
rating thresholds, dedupe, cap at TARGET_APPS_PER_CATEGORY. Resumable: apps
already in the output files are skipped.

Outputs: data/raw/play_apps.jsonl, data/raw/play_reviews_raw.jsonl
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

socket.setdefaulttimeout(30)  # google_play_scraper uses urllib with no timeout — a
                              # dead socket otherwise hangs the whole collection forever

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_collection.category_rules import (MIN_APP_INSTALLS, MIN_APP_RATINGS,
                                                PLAY_SEARCH_TERMS, REVIEWS_PER_APP,
                                                TARGET_APPS_PER_CATEGORY)

RAW_DIR = Path("data/raw")
APPS_PATH = RAW_DIR / "play_apps.jsonl"
REVIEWS_PATH = RAW_DIR / "play_reviews_raw.jsonl"
PAUSE = 1.5  # seconds between requests — be polite, avoid throttling


def _append(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _existing(path: Path, key: str) -> set[str]:
    out: set[str] = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.add(json.loads(line)[key])
    return out


def discover(category: str, done_apps: set[str], needed: int) -> list[str]:
    """Collect fresh candidate app ids; over-provision 3x since many fail thresholds."""
    from google_play_scraper import search
    found: list[str] = []
    seen = set(done_apps)
    for term in PLAY_SEARCH_TERMS[category]:
        try:
            results = search(term, lang="en", country="us", n_hits=30)
        except Exception as exc:
            print(f"  search '{term}' failed: {exc}")
            continue
        for r in results:
            app_id = r["appId"]
            if app_id not in seen:
                seen.add(app_id)
                found.append(app_id)
        time.sleep(PAUSE)
        if len(found) >= needed * 3:  # enough fresh candidates for this category
            break
    print(f"  {category}: {len(found)} fresh candidates from search")
    return found


def collect_app(app_id: str, category: str, reviews_per_app: int) -> bool:
    from google_play_scraper import Sort, app, reviews
    try:
        meta = app(app_id, lang="en", country="us")
    except Exception:
        return False
    installs = meta.get("realInstalls") or 0
    ratings = meta.get("ratings") or 0
    if installs < MIN_APP_INSTALLS or ratings < MIN_APP_RATINGS or not meta.get("score"):
        return False
    time.sleep(PAUSE)
    try:
        revs, _ = reviews(app_id, lang="en", country="us",
                          sort=Sort.NEWEST, count=reviews_per_app)
    except Exception as exc:
        print(f"  reviews failed for {app_id}: {exc}")
        return False
    if len(revs) < 20:
        return False

    _append(APPS_PATH, {
        "app_id": app_id, "category": category, "title": meta.get("title"),
        "developer": meta.get("developer"), "price": float(meta.get("price") or 0.0),
        "free": bool(meta.get("free", True)),
        "monetization": ("free" if meta.get("free") and not meta.get("offersIAP")
                         else "freemium" if meta.get("free") else "paid"),
        "score": meta.get("score"), "ratings": ratings, "installs": installs,
        "updated_ts": int(meta.get("updated") or 0),
        "released": meta.get("released"),  # e.g. "Feb 26, 2015" or None
        "genre": meta.get("genre"),
    })
    for r in revs:
        at = r.get("at")
        _append(REVIEWS_PATH, {
            "app_id": app_id,
            "review_id": r.get("reviewId"),
            "rating": r.get("score"),
            "text": r.get("content") or "",
            "ts": int(at.timestamp()) if at else None,
            "helpful_votes": int(r.get("thumbsUpCount") or 0),
            "user": r.get("userName") or "",
            "app_version": r.get("reviewCreatedVersion"),
        })
    time.sleep(PAUSE)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", choices=list(PLAY_SEARCH_TERMS), default=None)
    ap.add_argument("--limit-apps", type=int, default=TARGET_APPS_PER_CATEGORY)
    ap.add_argument("--reviews-per-app", type=int, default=REVIEWS_PER_APP)
    args = ap.parse_args()

    categories = [args.category] if args.category else list(PLAY_SEARCH_TERMS)
    existing = _existing(APPS_PATH, "app_id")
    existing_by_cat: dict[str, int] = {}
    if APPS_PATH.exists():
        with open(APPS_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)["category"]
                    existing_by_cat[c] = existing_by_cat.get(c, 0) + 1

    for category in categories:
        have = existing_by_cat.get(category, 0)
        need = args.limit_apps - have
        if need <= 0:
            print(f"{category}: already have {have} apps — skipping.")
            continue
        print(f"{category}: have {have}, collecting up to {need} more...")
        candidates = discover(category, existing, need)
        collected = 0
        for app_id in candidates:
            if collected >= need:
                break
            if app_id in existing:
                continue
            if collect_app(app_id, category, args.reviews_per_app):
                existing.add(app_id)
                collected += 1
                if collected % 10 == 0:
                    print(f"  {category}: {have + collected}/{args.limit_apps}", flush=True)
        print(f"{category}: +{collected} apps (total {have + collected}).")


if __name__ == "__main__":
    main()
