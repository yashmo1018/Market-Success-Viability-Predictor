# Chapter 4 — Data Pipeline

Every technical concept below is explained in plain English first, then named.

## 4.1 Data sources — what and why

| Source | What it gives us | Why chosen |
|---|---|---|
| **Amazon Reviews 2023** (McAuley Lab, UCSD) via Hugging Face streaming | Physical products across 6 categories: wireless headphones, Bluetooth speakers, smartphones, smartwatches, power banks, kitchen appliances | It's a peer-reviewed academic dataset (571M reviews) with stable product IDs, verified-purchase flags, and pre-existing price/rating metadata — free, reproducible, and no scraping or terms-of-service risk. |
| **Google Play** via `google-play-scraper` | Apps across 4 categories: finance, health & fitness, productivity, education | It's the only source that gives fresh `install_count` and `last_updated`, which the app success formula needs and no static academic dataset provides. |
| **Reddit** via the Arctic Shift archive | 1,089 buying-intent comments across all 10 categories | Captures something reviews can't: what buyers *wished they'd known before purchasing*, used only as exploratory context for the bridging prompt (Reddit's live API is 403-blocked without paid auth, so an archive was used instead). |

**In plain English:** think of Amazon reviews as "what people said after they bought it," and Reddit as "what people wish someone had told them before they bought it." Both are useful, but only Amazon/Google Play reviews are reliable enough (large volume, tied to a specific real product) to train a model on. Reddit is treated as a bonus hint, not a foundation.

## 4.2 Data collection

Amazon data streams in via resumable HTTP-range requests (`hf_stream.py`) — meaning if the connection drops halfway through a multi-gigabyte download, it picks up from where it left off instead of restarting. Google Play data is scraped with polite 1.5-second pacing between requests to avoid getting blocked. Both processes checkpoint their progress so a crash never means starting over (`data/raw/ckpt_*` files).

**Category selection rule (physical):** a product enters a category only if its title matches at least one *include* keyword and zero *exclude* keywords (`category_rules.py`). The exclude lists exist because Amazon's own category taxonomy is noisy for this purpose: a search for "wireless headphones" also returns phone cases, charging cables, and replacement ear tips, all of which would corrupt the category's aspect statistics if left in. Selection targets ~150 products per category, price between \$0.50–\$5000, at least 50 public ratings, and is stratified across budget/mid/premium price terciles so the category isn't accidentally all bestsellers or all premium items.

**Category selection rule (apps):** discovered via 8 search terms per category, kept only if the app has ≥50,000 installs, ≥500 ratings, and ≥20 usable reviews. Target ~130 apps/category, mixing free and paid.

## 4.3 Cleaning — every rule mapped to the failure it prevents

Cleaning happens in `clean_and_build.py`, and — importantly for a capstone defense — **every rule below exists because of a specific failure it prevents, not as generic "best practice."**

| Cleaning rule | What breaks without it |
|---|---|
| Strip HTML/entities/URLs/control characters | An LLM asked to quote "verbatim evidence" would quote markup garbage, and hand-validation would fail |
| English-only text (language detection) | The extraction LLM would half-understand foreign text and hallucinate scores instead of grounding them in what's actually said |
| 10–400 words per review | Under 10 words, there's no real aspect signal ("Great!" tells you nothing about durability); over 400, evidence quotes drift from what a human would call "verbatim" |
| Ratings in [1,5], timestamps in a sane range | Prevents corrupting the velocity/rating math in label engineering |
| Exact-duplicate and template-spam removal | Prevents a single review, or a bot campaign posting identical praise across many products, from being double-counted |
| ≥5 cleaned reviews per product, else the product is dropped | A product's aspect mean computed from 1–2 reviews is mostly noise, not signal |
| ≤300 reviews/product (seeded sample) | Keeps extraction cost bounded and stops one mega-popular product from dominating a category's statistics |

Every drop is counted and written to `data/final/validation_report.txt`, so the cleaning process is auditable, not a black box.

## 4.4 Feature engineering — turning text into numbers

**Step 1 — per-review extraction.** An LLM reads each review and scores it against a *frozen* aspect schema (explained fully in [Chapter 7](07-design-decisions.md)): 6 shared aspects (value for money, utility, ease of use, reliability, design appeal, after-sales), 3 physical-only (build quality, durability, repairability), 5 app-only (performance, stability, ad experience, update support, privacy/trust). Crucially, an aspect the review never mentions gets `null`, not a guess.

**Step 2 — per-product aggregation.** For each product, each aspect becomes two numbers: the **mean** of its non-null scores, and the **mention rate** (what fraction of that product's reviews discussed it at all). An aspect with zero mentions becomes a missing value (`NaN`) — never filled in, because XGBoost can learn from missingness directly (see [Chapter 7](07-design-decisions.md) for why this matters).

**Step 3 — metadata features.** Price, average rating, `log(1 + rating_count)` (the log compresses the heavy right tail — a product with 50,000 ratings shouldn't dominate the scale next to one with 50), review velocity, and `category` (used natively as a categorical feature, no one-hot encoding).

## 4.5 Feature selection

There was no separate statistical feature-selection step (e.g., dropping low-variance columns) — instead, the project relies on two structural decisions that do the same job more honestly:

1. **The "aspects-only" vs "full" model split** ([Chapter 5](05-model-development.md)) directly measures which features are doing real work, rather than trusting a black-box importance score.
2. **XGBoost's own feature-importance and SHAP values** (`models/shap_summary_*.png`) reveal which columns actually move predictions after training, which is a more honest signal than a pre-training filter.

## 4.6 Data validation

Two independent validation layers exist, and they check different things:

- **Contract validation** (Stage A, `load_final.py`) checks *structure*: every review's `product_uid` resolves, ratings are in range, types are correct. This runs before extraction ever starts.
- **The fraud filter** (Stage C, `label_engineering.py`) checks *authenticity*: it flags a product if more than 40% of its sampled reviews land in a single 14-day burst window, if its rating distribution is extreme-J-shaped (mostly 5-star with a thin spike of 1-star and almost nothing in between — a classic manipulated-review signature), or if more than 30% of its reviews are near-duplicates (Jaccard similarity > 0.7 on word sets). **71 products were flagged and excluded from training** — kept in the data for analysis, but never used to teach the model what "success" looks like.

## 4.7 Dataset creation — the label

The regression target, `success_score`, is a **within-category composite**, computed in `label_engineering.py`:

```
velocity = review_count / months_active

Physical: success = 100 · (0.40·volume_norm + 0.35·rating_norm + 0.25·velocity_norm)
App:      success = 100 · (0.30·install_norm + 0.30·rating_norm
                             + 0.20·velocity_norm + 0.20·retention_norm)
```

where `retention_norm` comes from `retention_proxy = rating_count / install_count`, and every normalized component is **min-max scaled within its own category** — a smartwatch and a kitchen appliance are never compared on the same raw scale. Counts (volume, installs) go through `log1p` first, because raw review/install counts are heavily right-skewed (a handful of viral products would otherwise dominate the normalization).

**Why this specific formula, in plain English:** a genuinely successful product should be popular (volume/installs), well-liked (rating), and gaining traction quickly (velocity) — not just one of those in isolation. A product with 10,000 mediocre reviews and one with 500 excellent ones can both be "successful" in different ways, and the weighted composite reflects that instead of picking a single metric.

## 4.8 Why each important feature was included

- **Aspect means and mention rates** — the actual signal the project is testing: does what customers *say* about a product predict its success?
- **Price, rating, rating count, velocity** — standard metadata that any e-commerce model would include; kept as a *separate* "full model" variant specifically so the paper can show how much of the R² they contribute versus the aspect data alone (they contribute a lot — see [Chapter 5](05-model-development.md) on the leakage discussion).
- **Category** — success looks structurally different across categories (a headphone succeeds differently than a kitchen appliance), so the model needs to know which category it's scoring within.

## 4.9 Common challenges and how they were handled

| Challenge | How it was handled |
|---|---|
| Amazon Reviews 2023 is frozen at September 2023 — no post-2023 products exist | Disclosed openly as a temporal-scope limitation rather than hidden ([Chapter 9](09-project-evaluation.md)) |
| Google Play scraping is an unofficial library that can be throttled or broken by Google | Collection was made resumable with polite pacing, and run once rather than repeatedly |
| Amazon's own category taxonomy is too noisy to use directly | Custom include/exclude keyword rules (`category_rules.py`) built specifically to prevent accessory products from polluting a category |
| Reddit's live API is blocked without paid authentication | Fell back to the Arctic Shift historical archive; the pipeline degrades gracefully with an empty `reddit_context.json` if unavailable, rather than crashing |
| Manipulated/gamed reviews inflate apparent success | The 71-product fraud filter (§4.6) |
| A model could silently misalign feature order between training and prediction | The frozen feature manifest, covered in [Chapter 2](02-system-architecture.md) and [Chapter 7](07-design-decisions.md) |
| Products with too few reviews would produce noisy aspect means | The ≥5-review floor (§4.3) |

## 4.10 The numbers that resulted

- 740 physical products / 382 app products collected → **732 physical / 319 app** after the fraud filter
- 62,462 physical reviews + 72,230+ app reviews collected; **74,000+ reviews** were LLM-extracted
- 71 products excluded as suspect (fraud filter)
- 1,089 Reddit buying-intent comments, unevenly distributed (237 for health & fitness apps, as few as 18 for smartphones)
