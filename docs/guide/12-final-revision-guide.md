# Chapter 12 — Final Revision Guide

## 12.1 Key concepts to remember

- **Aspect bridging** — the core idea: extract aspect-level sentiment from real reviews, train a model on it, then use an LLM to *estimate* the aspect profile a new, unreleased product's spec would earn, and score that estimate with the trained model.
- **Null-forcing** — the extraction LLM must return `null` for any aspect a review doesn't explicitly discuss; never infer.
- **Skeptic prompt (v2)** — adjective blindness, absence rule, anchor discipline. Raised ρ from 0.241 to 0.313.
- **Full model vs aspects-only model** — full model leaks via `avg_rating` (R²=0.893); aspects-only is the honest number (R²=0.567 physical, R²=0.101 app) and the one every claim rests on.
- **Pre-registration** — froze the pipeline, drew a disjoint 59-product holdout, specified the analysis, before running it. This is *why* the result is trustworthy, more than the number itself.
- **Launch-blind** — every validated prediction only used information knowable at the product's actual launch date; real outcomes were compared afterward.
- **Within-category normalization** — every label component is min-max scaled inside its own category, because raw counts mean different things across categories.
- **NaN-native** — missing aspect data is never imputed; XGBoost was chosen partly because it handles this natively.
- **The negative finding** — the identical method fails for mobile apps under five different target definitions; reported and acted on (disabled in-app), not hidden.

## 12.2 Important design decisions (one line each)

| Decision | One-line reason |
|---|---|
| Null-forcing extraction | Refuses to fabricate signal for unmentioned aspects |
| Skeptic bridging prompt | Marketing copy is uniformly optimistic; skepticism recovers real signal |
| Rejected shrinkage | Measurably lowered ρ (0.313→0.249) despite seeming correct |
| Within-category label normalization | 500 reviews means different things per category |
| NaN-native, no imputation | Avoids injecting fabricated data anywhere in the pipeline |
| Full vs aspects-only split | Prevents leakage (avg_rating) from masquerading as insight |
| Pre-registered holdout | Prevents overfitting-by-tuning from being mistaken for a real result |
| Reported the app-track failure | A pre-production tool has to show where its competence ends |
| Dual frontend (React + Streamlit) | Polish for the product demo, near-zero-build for quick iteration/deploy |
| Disk-persisted, re-runnable stages | A multi-day extraction batch must survive crashes without restarting |
| Frozen feature manifest | Prevents training/serving column-order drift — the most common silent ML bug |

## 12.3 Common viva questions (rapid-fire — see [Chapter 10](10-viva-prep.md) for full answers)

1. What problem does this solve, and for whom? → Pre-launch viability estimation for small manufacturers/makers with no market-research budget.
2. Why XGBoost? → Won a 6-algorithm benchmark on R², RMSE, and AUC-ROC, 8× faster than its closest rival, native missing-value + categorical support, exact SHAP compatibility.
3. What's your real R²? → 0.567 (aspects-only, physical) — the honest number; 0.893 (full model) has leakage via avg_rating.
4. What's your headline validation number? → ρ = 0.317, 95% CI [0.06, 0.54], AUC = 0.743, on a pre-registered 59-product holdout.
5. Does it beat just using price? → Yes, and the two signals are almost orthogonal (r = 0.135), so it's not just re-deriving price.
6. What doesn't work? → Mobile apps — R² = 0.101 against a 0.35 gate, across five different target definitions.
7. How do you stop fake reviews from corrupting the model? → A fraud filter (burst timing, extreme-J ratings, near-duplicates) excluded 71 products.
8. What's the biggest limitation? → Survivorship bias — products with fewer than 5 reviews never enter the dataset at all.
9. What would you do with more time? → Confirm the Reddit-priorities lift with a real pre-registered replication; expand validated categories; investigate the build-quality trust-tier instability.
10. Is this deployed? → Yes — a FastAPI backend + React frontend (primary), and a Streamlit alternative (also deployed to Streamlit Cloud).

## 12.4 One-page cheat sheet

```
PROJECT: Launch-Blind Product Viability Estimation from Specifications via LLM Aspect Bridging
AUTHOR:  Raj Jagtap — Capstone 2026

CORE IDEA:  74,000+ real reviews → aspect scores (null-forced) → XGBoost learns
            aspect profile → success. New product spec → skeptic LLM "bridges"
            to an estimated aspect profile → same model scores it.

DATA:       732 physical products (6 cats) + 319 app products (4 cats), post-filter.
            71 products excluded (fraud filter). 74,000+ reviews extracted.

LABEL:      success = 100·(0.40·volume + 0.35·rating + 0.25·velocity)  [physical]
            all components min-max normalized WITHIN category, log1p on counts.

MODEL:      XGBoost, 600 est., depth 5, lr 0.05, seed 42, 5-fold CV.
            Beat: Random Forest (.532), Grad.Boosting (.549, 8x slower),
                  MLP (.490), SVR (.421), Ridge (.368)  — all R² on same data.
            Full model R²=0.893 (LEAKS via avg_rating) vs
            Aspects-only R²=0.567 physical / 0.101 app (HONEST number, used for all claims)

VALIDATION: Pre-registered holdout, n=59, frozen pipeline before run.
            ρ = 0.317, 95% CI [0.059, 0.543], p=0.014, AUC=0.743.
            Monotonic across quintiles: 58.5→60.8→61.7→62.8→64.1
            Near-orthogonal to price baseline (r=0.135 with price-percentile ρ=0.250)

KEY ABLATION: Skeptic prompt (v2) vs trusting (v1): ρ 0.241→0.313, AUC 0.653→0.761
              Shrinkage TRIED & REJECTED: lowered ρ to 0.249 — kept as cautionary result

NEGATIVE FINDING: App track fails ALL 5 target definitions tested (best R²=0.231,
                  gate was 0.35). Disabled in product, not deleted from paper.

PRODUCT:    FastAPI + React (primary) / Streamlit (secondary+deployed).
            Viability % (±5 range), percentile rank, SHAP risks/strengths,
            trust badges per aspect, spec coach, market-gap report.

BIGGEST LIMITATION: Survivorship bias (≥5-review floor excludes true flops entirely)
```

## 12.5 Five-minute presentation script

> "Companies that want to know if a product will succeed usually find out from reviews — after launch, after the manufacturing money is already spent. We built a system that estimates viability *before* that, from the specification alone.
>
> Here's how. First, we extracted aspect-level opinions — build quality, ease of use, value for money — from over 74,000 real Amazon and Google Play reviews, using an LLM that's only allowed to score an aspect if the review explicitly says something about it. If it doesn't, we record 'no data,' not a guess.
>
> Second, we trained a model — XGBoost, chosen after benchmarking it against five other algorithms on identical data, where it won on accuracy, speed, and explainability — to learn how those aspect profiles relate to a product's real market success, within each category.
>
> Third, the actual idea: when someone gives us a brand-new product specification, we prompt an LLM as a skeptical market analyst — not a hype-man — grounded in real category statistics, to estimate the aspect profile that spec would earn from real customers. That estimate goes through the same trained model.
>
> We didn't just build this and claim it works. We pre-registered a held-out test: 59 real products, sampled in advance, pipeline frozen before we ran it. The result: a Spearman correlation of 0.317, statistically significant, and almost independent of a simple price-based guess — so it's carrying real information.
>
> And when we ran the identical method on mobile apps, it failed — completely, under five different definitions of success. We report that with the same weight as the success, because app-store outcomes turned out to be driven by distribution and marketing, not quality, and a decision-support tool has to show where its competence ends as clearly as where it works.
>
> The result is a working web application — viability score, uncertainty range, per-aspect trust badges, and an explanation of the biggest risks and strengths in terms a founder can actually act on."

## 12.6 Fifteen-minute final presentation script

**0:00–1:30 — The problem.** Open with the founder's dilemma: committing manufacturing money before a single customer has touched the product. Every existing tool (review analytics, e-WOM models, sentiment dashboards) needs post-launch data. State the goal: an affordable, evidence-based pre-launch viability estimate.

**1:30–3:30 — The idea: aspect bridging.** Explain the two-model structure: (1) learn from history what aspect profiles predict success, per category; (2) bridge a new spec into an estimated aspect profile via a skeptic-prompted LLM, grounded in real category statistics. Emphasize this is *not* the LLM reading reviews of the new product — there are none. It's estimating from the spec plus category history.

**3:30–6:30 — How it's built.** Walk the seven-stage pipeline (reference the architecture diagram, [Chapter 2](02-system-architecture.md)): data acquisition (Amazon 2023 + Google Play + Reddit) → contract verification → null-forcing LLM extraction (74,000+ reviews, multi-provider pool for resilience) → label engineering (within-category composite success score, fraud filter excluding 71 suspect products) → feature assembly (frozen column manifest) → XGBoost training with SHAP, benchmarked against five other algorithms → category profiling → bridging and prediction.

**6:30–9:30 — Proving it, not just claiming it.** This is the section to slow down on. Explain pre-registration in plain terms: all tuning happened on one set of products; a separate, untouched set was then used exactly once, with the pipeline frozen beforehand, to prevent fooling ourselves. State the result plainly: ρ = 0.317, 95% CI [0.06, 0.54], AUC = 0.743. Show it's almost orthogonal to a price-based baseline (r = 0.135) — real information, not a repackaged obvious guess. Show the monotonic quintile chart if visuals are available.

**9:30–11:30 — The honest part: what doesn't work.** Present the app-track negative finding with confidence, not apology. The same method, tested against five different app-success definitions, failed every one against a pre-registered gate. Explain the likely reason (app-store success is distribution-driven, ratings are compressed into a narrow band, review sentiment centers on ads/monetization). State the action taken: disabled in the product, visibly, not silently removed.

**11:30–13:30 — The product.** Demo or describe the FastAPI/React application: enter a product spec, get a viability range (deliberately ±5 wide, not falsely precise), a percentile rank against real bridged products, SHAP-derived top risks and strengths tied to design levers, trust badges per aspect, a market-gap report quoting real customer pain points, and the spec coach for users who haven't written a full specification yet.

**13:30–15:00 — Close.** Restate the durable contribution: not the single ρ number, but the *map* — which aspects a spec can predict (ease of use, build quality, utility) and which it can't (after-sales, aesthetics), and which markets the method works in at all (physical goods) versus where it fails under every test tried (app stores). End on the honesty-layer thesis: "A tool that knows its own limits and shows them — through trust badges, abstention, and uncertainty ranges — is the only honest form a pre-production decision-support tool can take at the current state of the art."
