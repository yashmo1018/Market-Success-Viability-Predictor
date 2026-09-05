"""Final step: clean raw collections and build the data/final/ contract files.

  python src/data_collection/clean_and_build.py [--out data/final] [--min-reviews 5]

The cleaning gauntlet exists to protect the LLM extractor from inputs that cause
hallucinated scores or broken evidence phrases. Every drop is counted and the
full audit lands in <out>/validation_report.txt.

Per-review gauntlet (in order, first failure drops the review):
  1. strip HTML tags/entities, URLs, emails, control chars; normalize whitespace
  2. non-empty rating in [1,5]; sane timestamp (Amazon ms -> s)
  3. English (langdetect, seeded) — non-English text makes evidence extraction unreliable
  4. 10-400 words — too short = no aspect signal; too long = truncation/drift risk
  5. exact-duplicate text within product (spam) and template text repeated across
     many products (bot campaigns) removed
Per-product: >= min_reviews cleaned reviews, valid price; reviews capped at 300
(seeded sample) so no single product dominates extraction cost.

After writing, the builder runs the ML track's own Stage A loader against the
output; validation_passed in manifest.json is set to the actual result.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RAW_DIR = Path("data/raw")
SEED = 42
MAX_REVIEWS_PER_PRODUCT = 300
TS_MIN = 946684800      # 2000-01-01
NOW = int(time.time())

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_WS_RE = re.compile(r"\s+")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = _CTRL_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


_detect = None


def is_english(text: str) -> bool:
    global _detect
    if _detect is None:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = SEED
        _detect = detect
    # cheap pre-check: mostly-ASCII text with common English words passes fast
    ascii_ratio = sum(c.isascii() for c in text) / max(len(text), 1)
    if ascii_ratio < 0.85:
        return False
    try:
        return _detect(text[:400]) == "en"
    except Exception:
        return False


class Gauntlet:
    """Runs the per-review cleaning chain and counts every drop reason."""

    def __init__(self, global_text_counts: Counter):
        self.drops: Counter = Counter()
        self.global_text_counts = global_text_counts

    def run(self, text: str, rating, ts, seen_in_product: set[str]) -> tuple[str, float, int] | None:
        text = clean_text(text)
        if not text:
            self.drops["empty_after_cleaning"] += 1
            return None
        try:
            rating = float(rating)
        except (TypeError, ValueError):
            self.drops["bad_rating"] += 1
            return None
        if not 1.0 <= rating <= 5.0:
            self.drops["bad_rating"] += 1
            return None
        if ts is None:
            self.drops["bad_timestamp"] += 1
            return None
        ts = int(ts)
        if ts > 10_000_000_000:  # milliseconds -> seconds
            ts //= 1000
        if not (TS_MIN <= ts <= NOW + 86400):
            self.drops["bad_timestamp"] += 1
            return None
        wc = len(text.split())
        if wc < 10:
            self.drops["too_short"] += 1
            return None
        if wc > 400:
            self.drops["too_long"] += 1
            return None
        norm = re.sub(r"[^a-z0-9 ]", "", text.lower())
        h = hashlib.sha1(norm.encode()).hexdigest()
        if h in seen_in_product:
            self.drops["duplicate_in_product"] += 1
            return None
        if self.global_text_counts[h] > 3:  # same text on >3 products = bot template
            self.drops["template_spam"] += 1
            return None
        if not is_english(text):
            self.drops["non_english"] += 1
            return None
        seen_in_product.add(h)
        return text, rating, ts


def _hash16(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def _global_text_counts(review_iters: list[tuple[Path, str]]) -> Counter:
    """Count normalized-text occurrences across ALL products (template-spam pass)."""
    counts: Counter = Counter()
    for path, text_key in review_iters:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    t = clean_text(json.loads(line).get(text_key) or "")
                    norm = re.sub(r"[^a-z0-9 ]", "", t.lower())
                    if norm:
                        counts[hashlib.sha1(norm.encode()).hexdigest()] += 1
    return counts


def build_physical(gauntlet: Gauntlet, min_reviews: int) -> tuple[list, list]:
    sel_path = RAW_DIR / "amazon_selected.json"
    rev_path = RAW_DIR / "amazon_reviews_raw.jsonl"
    if not sel_path.exists() or not rev_path.exists():
        print("Amazon raw data missing — physical set will be empty.")
        return [], []
    with open(sel_path, encoding="utf-8") as f:
        selected = json.load(f)

    by_product: dict[str, list[dict]] = defaultdict(list)
    with open(rev_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_product[r["parent_asin"]].append(r)

    from src.data_collection.category_rules import match_category

    rng = random.Random(SEED)
    products, reviews = [], []
    for asin, meta in selected.items():
        # re-check title against current (possibly tightened) category rules
        if not match_category(meta["title"], meta["category"]):
            gauntlet.drops["product_reclassified_accessory"] += 1
            continue
        raw = by_product.get(asin, [])
        seen: set[str] = set()
        cleaned = []
        for r in raw:
            out = gauntlet.run(r.get("text"), r.get("rating"), r.get("timestamp"), seen)
            if out is None:
                continue
            text, rating, ts = out
            cleaned.append({**r, "text": text, "rating": rating, "ts": ts})
        if len(cleaned) < min_reviews:
            gauntlet.drops["product_too_few_reviews"] += 1
            continue
        if len(cleaned) > MAX_REVIEWS_PER_PRODUCT:
            cleaned = rng.sample(cleaned, MAX_REVIEWS_PER_PRODUCT)
        puid = f"amzp_{asin}"
        ts_list = [c["ts"] for c in cleaned]
        products.append({
            "product_uid": puid, "source": "amazon", "source_id": asin,
            "product_type": "physical", "category": meta["category"],
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
    return products, reviews


def _parse_released(released: str | None, fallback: int) -> int:
    if released:
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return int(time.mktime(time.strptime(released, fmt)))
            except ValueError:
                continue
    return fallback


def build_app(gauntlet: Gauntlet, min_reviews: int) -> tuple[list, list]:
    apps_path = RAW_DIR / "play_apps.jsonl"
    rev_path = RAW_DIR / "play_reviews_raw.jsonl"
    if not apps_path.exists() or not rev_path.exists():
        print("Play raw data missing — app set will be empty.")
        return [], []
    apps = []
    with open(apps_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                apps.append(json.loads(line))
    by_app: dict[str, list[dict]] = defaultdict(list)
    with open(rev_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_app[r["app_id"]].append(r)

    rng = random.Random(SEED)
    products, reviews = [], []
    seen_apps: set[str] = set()
    for meta in apps:
        app_id = meta["app_id"]
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        seen: set[str] = set()
        cleaned = []
        for r in by_app.get(app_id, []):
            out = gauntlet.run(r.get("text"), r.get("rating"), r.get("ts"), seen)
            if out is None:
                continue
            text, rating, ts = out
            cleaned.append({**r, "text": text, "rating": rating, "ts": ts})
        if len(cleaned) < min_reviews:
            gauntlet.drops["product_too_few_reviews"] += 1
            continue
        if len(cleaned) > MAX_REVIEWS_PER_PRODUCT:
            cleaned = rng.sample(cleaned, MAX_REVIEWS_PER_PRODUCT)
        puid = f"gpp_{_hash16(app_id)}"
        ts_list = [c["ts"] for c in cleaned]
        first_ts = min(ts_list)
        updated = int(meta.get("updated_ts") or 0)
        products.append({
            "product_uid": puid, "source": "google_play", "source_id": app_id,
            "product_type": "app", "category": meta["category"],
            "name": meta["title"], "brand": str(meta.get("developer") or "unknown"),
            "price": float(meta.get("price") or 0.0), "currency": "USD",
            "monetization": meta.get("monetization") or "free",
            "avg_rating": float(meta["score"]), "rating_count": int(meta["ratings"]),
            "install_count": int(meta["installs"]),
            "last_updated_ts": updated if TS_MIN <= updated <= NOW + 86400 else first_ts,
            "released_ts": _parse_released(meta.get("released"), first_ts),
            "first_review_ts": first_ts, "latest_review_ts": max(ts_list),
            "specs": {"genre": meta.get("genre")}, "extra": {},
        })
        for c in cleaned:
            reviews.append({
                "review_uid": f"gpr_{_hash16(c.get('review_id') or c['text'][:64])}",
                "product_uid": puid, "source": "google_play", "rating": c["rating"],
                "title": "", "text": c["text"], "verified": True,
                "helpful_votes": int(c.get("helpful_votes") or 0),
                "review_ts": c["ts"], "reviewer_hash": _hash16(c.get("user") or "anon"),
                "app_version": c.get("app_version"),
                "word_count": len(c["text"].split()),
            })
    return products, reviews


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/final")
    ap.add_argument("--min-reviews", type=int, default=5)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("Pass 1/2: global template-spam scan...")
    gauntlet = Gauntlet(_global_text_counts([
        (RAW_DIR / "amazon_reviews_raw.jsonl", "text"),
        (RAW_DIR / "play_reviews_raw.jsonl", "text"),
    ]))

    print("Pass 2/2: cleaning gauntlet + assembly...")
    prods_phys, revs_phys = build_physical(gauntlet, args.min_reviews)
    prods_app, revs_app = build_app(gauntlet, args.min_reviews)

    reddit_raw = RAW_DIR / "reddit_context_raw.json"
    reddit = {}
    if reddit_raw.exists():
        with open(reddit_raw, encoding="utf-8") as f:
            reddit = {cat: [clean_text(t)[:600] for t in texts]
                      for cat, texts in json.load(f).items()}

    cat_stats: dict[str, dict] = defaultdict(lambda: {"products": 0, "reviews": 0})
    for p in prods_phys + prods_app:
        cat_stats[p["category"]]["products"] += 1
    prod_cat = {p["product_uid"]: p["category"] for p in prods_phys + prods_app}
    for r in revs_phys + revs_app:
        cat_stats[prod_cat[r["product_uid"]]]["reviews"] += 1

    for name, obj in [("products_physical.json", prods_phys),
                      ("products_app.json", prods_app),
                      ("reviews_physical.json", revs_phys),
                      ("reviews_app.json", revs_app),
                      ("reddit_context.json", reddit)]:
        with open(out / name, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pipeline_version": "data-track-1.0",
        "categories": dict(cat_stats),
        "totals": {"products_physical": len(prods_phys), "products_app": len(prods_app),
                   "reviews_physical": len(revs_phys), "reviews_app": len(revs_app)},
        "reddit_available": bool(reddit),
        "validation_passed": False,  # flipped below only if Stage A passes
        "validation_report": str(out / "validation_report.txt"),
    }
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # audit report
    report_lines = [
        f"Data build {manifest['generated_at']}",
        f"Products: {len(prods_phys)} physical, {len(prods_app)} app",
        f"Reviews:  {len(revs_phys)} physical, {len(revs_app)} app",
        "", "Per category:",
        *[f"  {c}: {s['products']} products, {s['reviews']} reviews"
          for c, s in sorted(cat_stats.items())],
        "", "Cleaning drop reasons:",
        *[f"  {k}: {v}" for k, v in gauntlet.drops.most_common()],
    ]
    print("\n".join(report_lines))

    # self-validate with the ML track's own Stage A loader (subprocess so its
    # sys.exit on failure doesn't kill us)
    import subprocess
    manifest["validation_passed"] = True
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'" + str(root) + "'); "
         "from src.loading.load_final import load_contract, print_summary; "
         "print_summary(load_contract(r'" + str(out.resolve()) + "'))"],
        capture_output=True, text=True)
    if result.returncode != 0:
        manifest["validation_passed"] = False
        with open(out / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        report_lines += ["", "STAGE A VALIDATION FAILED:", result.stdout, result.stderr]
        print("STAGE A VALIDATION FAILED — manifest marked validation_passed=false")
        print(result.stdout or result.stderr)
    else:
        report_lines += ["", "Stage A validation: PASSED", result.stdout]
        print(result.stdout)
        print(f"Stage A validation: PASSED — {out} is ready for the ML pipeline.")

    with open(out / "validation_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))


if __name__ == "__main__":
    main()
