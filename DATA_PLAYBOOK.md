# DATA PLAYBOOK — Acquisition, Categorization, Assessment, Cleaning
## Hybrid AI Product Success Predictor — Data Track

> **Companion to** `OPERATING_MANUAL.md` (ML track runbook). This file documents where the
> data comes from, why those sources, what is kept vs excluded, and how cleaning protects
> the LLM extractor from hallucination.
> **One command runs everything:** `python scripts/collect_all.py` (resumable — rerun after
> any crash/disconnect and it continues from checkpoints).

---

## 1. Sources — what we use and why

| Need | Source | Access method | Cost |
|---|---|---|---|
| Physical products + reviews (6 categories) | **Amazon Reviews 2023** (McAuley Lab, UCSD) via HuggingFace | Resumable HTTP-range streaming of `raw/review_categories/*.jsonl` | Free; ~41 GB bandwidth, no keys |
| Apps + reviews (4 categories) | **Google Play** | `google-play-scraper` (search discovery → app metadata → newest reviews) | Free; polite 1.5 s pacing |
| Consumer priorities (optional) | **Reddit** | Public JSON endpoints; **currently 403-blocked** → PRAW with free API creds is the upgrade path | Optional — contract allows `{}` |

### Benefits and drawbacks (the honest assessment)

**Amazon Reviews 2023**
- ✔ Peer-reviewed academic dataset: 571M reviews, verified-purchase flags, helpful votes, stable ASIN keys — no scraping, no ToS violations, fully reproducible for the paper.
- ✔ Rich metadata (price, avg rating, rating counts) = exactly the label ingredients Stage C needs.
- ✘ Frozen at **Sep 2023** — no post-2023 products; review_velocity reflects that era. Document in the paper as temporal scope.
- ✘ Price is missing for many items (we drop those — selection bias toward listings with buy-box prices).
- ✘ Category assignment is ours (title keyword rules), not Amazon's taxonomy — precision depends on the exclude lists (see §2).

**Google Play (live scraping)**
- ✔ Fresh, real `install_count`, `last_updated` — the exact fields the app label formula needs and that no static dataset provides.
- ✔ Reviews sorted NEWEST = current app state (matters: apps change monthly).
- ✘ Unofficial library; Google can throttle/break it. Mitigation: resumable, polite pacing, collect once.
- ✘ Newest-N sampling ≠ lifetime sample: review text reflects the current version while `avg_rating` is lifetime. Known, documented asymmetry.
- ✘ Discovery via search terms biases toward search-visible apps (that's acceptable: same visibility bias affects real market success).

**Reddit** — blocked without auth as of collection date. Pipeline degrades gracefully (bridging prompt says "not available"). If wanted: create a free Reddit app at reddit.com/prefs/apps, `pip install praw`, adapt `reddit_collect.py` (30-min task).

## 2. Categorization — keep vs exclude

Rules live in [category_rules.py](src/data_collection/category_rules.py) and are the single source of truth.

**Physical (Amazon):** a product enters a category iff its title matches ≥1 include-keyword and 0 exclude-keywords. The exclude lists kill the classic poison: cases, straps, cables, chargers, replacement parts, screen protectors — accessories that would otherwise dominate (a "case for AirPods" is NOT a wireless headphone) and corrupt category profiles. Source-file mapping: headphones/speakers/smartwatches ← Electronics; smartphones/power banks ← Cell_Phones_and_Accessories; kitchen appliances ← Appliances.

**Selection quotas (per category):** target 150 products, requiring price ∈ [$0.50, $5000] and ≥50 public ratings. Stratified across price terciles (budget/mid/premium), most-rated first within each tercile — so profiles aren't premium-only or bestseller-only.

**Apps (Play):** discovered via 8 search terms per category; kept iff ≥50k installs, ≥500 ratings, has a score, and ≥20 usable reviews. Target 130 apps/category, free+paid mixed.

**Review keep/exclude:** cap 400/product at collection (first-encountered in a user-grouped file ≈ random per product), cleaned then sampled to ≤300/product (seed 42) so extraction cost is bounded and no product dominates.

## 3. Cleaning — every rule mapped to the failure it prevents

The gauntlet is [clean_and_build.py](src/data_collection/clean_and_build.py); every drop is counted in `data/final/validation_report.txt`.

| Rule | Prevents |
|---|---|
| Strip HTML/entities/URLs/emails/control chars, collapse whitespace | Evidence phrases containing markup → hand-validation "evidence not found" failures; PII leakage into LLM calls |
| English only (langdetect, seed 42; ASCII pre-filter) | LLM scoring text it half-understands → hallucinated scores; non-verbatim "translated" evidence |
| 10–400 words | <10: no aspect signal, model invents ("Great!" says nothing about durability). >400: truncation and evidence drift |
| Rating ∈ [1,5], timestamp ∈ [2000, now] (auto ms→s) | Label corruption in Stage C velocity/rating math |
| Exact-duplicate removal within product | Review bombs double-counted in aspect means |
| Template-spam removal (identical text on >3 products) | Bot campaigns injecting identical praise across a brand's catalog |
| ≥5 cleaned reviews per product, else drop product | Products whose aspect means would be 1–2 review noise |
| ≤300 reviews/product (seeded sample) | Extraction budget blowout; mega-product dominance |

Deeper fraud detection (burst timing, extreme-J rating shapes, near-duplicate Jaccard) intentionally lives in the ML track's Stage C — it flags *products*, not reviews, and its exclusions must be reported in the paper.

## 4. How to run

```bash
python scripts/collect_all.py           # everything, in order, resumable
```
Or step-by-step:
```bash
python src/data_collection/play_collect.py                                  # ~1-2 h
python src/data_collection/amazon_select_products.py --source Appliances    # 0.3 GB
python src/data_collection/amazon_select_products.py --source Cell_Phones_and_Accessories  # 4 GB
python src/data_collection/amazon_select_products.py --source Electronics   # 5.2 GB
python src/data_collection/amazon_select_products.py --finalize             # instant
python src/data_collection/amazon_collect_reviews.py --source Appliances    # 0.9 GB
python src/data_collection/amazon_collect_reviews.py --source Cell_Phones_and_Accessories  # 9.3 GB
python src/data_collection/amazon_collect_reviews.py --source Electronics   # 22.6 GB
python src/data_collection/reddit_collect.py                                # optional
python src/data_collection/clean_and_build.py --out data/final              # minutes
```
Interruptions: **just rerun the same command** — byte-offset checkpoints (`data/raw/ckpt_*.json`) and append-only outputs make every step idempotent. `--max-bytes N` limits a session for testing.

After the build: `data/final/manifest.json` gets `validation_passed: true` **only if** the ML track's own Stage A loader passes on the output (the builder runs it automatically). Then continue at OPERATING_MANUAL.md §3 (pilot extraction + hand-validation).

## 5. Acceptance criteria for the dataset

- Every category ≥60 products after cleaning (target 150/130); if a category lands <60, widen include-keywords or lower `MIN_RATING_COUNT_PHYSICAL`, rerun the meta scan (checkpoint delete: `data/raw/ckpt_meta_<source>.json` + candidates file) — escalate before doing this.
- `validation_passed: true` in the manifest (automatic).
- Drop histogram sane: `too_short` should dominate; `non_english` ≲ 10%; if `template_spam` is huge for one category, inspect before trusting it.
- Total reviews in the 25k–45k envelope (extraction budget: ~3–4 days on pooled free keys).

## 6. Verified live (2026-07-07)

- Play: 3 finance apps + reviews collected end-to-end ✔
- Amazon: 211 kitchen-appliance candidates from 40 MB meta; 3,096 reviews from 80 MB stream; resume checkpoints exercised ✔
- Cleaning + build: real sample → `CONTRACT VERIFIED`, Stage A PASSED ✔
- Reddit: 403-blocked, graceful skip ✔ (upgrade path documented above)
