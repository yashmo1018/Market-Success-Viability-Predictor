# Chapter 1 — Project Overview

> Paper title: **"Launch-Blind Product Viability Estimation from Specifications via LLM Aspect Bridging"** — Raj Jagtap, final-year capstone, 2026.

## 1.1 What problem this project solves

A founder deciding whether to manufacture a wireless headphone, or a solo developer deciding whether to build a finance app, has to commit money and months of work **before a single customer has used the thing.** Every tool that predicts product success — sentiment dashboards, review analytics, e-WOM (electronic word-of-mouth) models — needs data that only exists *after* launch: reviews, ratings, sales. At the exact moment the decision is being made, none of that exists yet. All that exists is a specification: a description, a price, a set of claimed features.

This project builds a system that estimates product viability from **that specification alone**, before launch, by "bridging" from a specification to the aspect-level opinions a real customer would eventually form — grounded in what thousands of real reviews in that product category actually say.

## 1.2 Why this problem matters

- Small businesses and independent makers do not have market-research departments or paid consumer panels. Big companies do. This project's stated goal is closing that gap.
- The cost of guessing wrong is concrete: an unsold inventory run can end a small manufacturer; a wasted development cycle can sink a solo app developer.
- It also matters to consumers, who are the ones who end up owning products that were never well matched to what they needed.

## 1.3 Existing approaches — and why this project doesn't just repeat them

The related-work landscape splits into a few camps, all covered in the paper's Related Work section:

| Existing approach | What it does | Its blind spot |
|---|---|---|
| Review/e-WOM → sales models (Chevalier & Mayzlin, Dellarocas, Luca, etc.) | Show that review valence and volume move real sales | Needs the product to already be on the market with reviews |
| Aspect-Based Sentiment Analysis (ABSA), SemEval-2014, neural ABSA surveys | Extract fine-grained opinions (aspect + sentiment) from review text | Still an *after-the-fact* measurement tool, not a predictor of an unreleased product |
| Pre-launch chatter prediction (Narayanan et al.) | Forecasts reception from chatter about an *already-announced* product | Assumes product-specific buzz exists — this project assumes **none does** |
| LLMs as annotators/estimators in e-commerce | Zero-shot classification, description generation | Rarely evaluated against real, later-observed market outcomes |

This project's position: use ABSA-style extraction not as an end in itself, but as a **measurement instrument** that trains a success model on real historical products, then use an LLM a second time — not to read reviews, but to *imagine* what reviews an unreleased product's specification would eventually earn, checked against real category statistics.

## 1.4 Why this is a strong capstone project

1. **It doesn't stop at "does the model score well."** It pre-registers a confirmatory holdout (a scientific-method safeguard against fooling yourself with tuning) and reports the result honestly, including the width of the uncertainty interval.
2. **It reports a negative result with the same weight as the positive one.** The identical method was tried on mobile apps and failed under five different target definitions — and that failure is treated as a *finding*, not hidden. This is the single biggest thing that separates a capstone that understands the scientific process from one that just wants a big R² number.
3. **It benchmarks the modeling choice instead of assuming it.** Six algorithms were compared head-to-head on identical data before committing to XGBoost.
4. **It ships a working, deployed application** (React + FastAPI, plus a Streamlit variant) that a real user — not just a judge — could use.
5. **It builds real data infrastructure**: 74,000+ real Amazon and Google Play reviews, a multi-provider LLM extraction pipeline with retries and resume support, and a fraud filter that excludes manipulated review patterns before they can pollute the labels.

## 1.5 The overall workflow, start to finish

```
Raw reviews (Amazon 2023 + Google Play + Reddit)
        │
        ▼
Contract-verified, cleaned dataset (data/final/)
        │
        ▼
LLM extracts per-review aspect scores, evidence-quoted, nulls forced   ──▶ 74,000+ scored reviews
        │
        ▼
Aggregate to per-product aspect profile + success label (from real review outcomes)
        │
        ▼
XGBoost learns: aspect profile → success score          (per category, 5-fold CV)
        │
        ▼
NEW, unreleased product's specification
        │
        ▼
Bridging LLM (skeptic-prompted) estimates the aspect profile that spec would earn
        │
        ▼
Trained XGBoost scores that estimated profile → viability %, ± range, SHAP explanation
        │
        ▼
React/FastAPI app: viability, percentile rank, risks/strengths, spec coach, market gaps
```

Every arrow in that diagram is a disk-persisted, independently re-runnable stage — this matters and is covered in full in [Chapter 2](02-system-architecture.md).

## 1.6 The three pitches

### 30-second version
"We built a system that predicts whether a new product — before it's even made — will succeed with customers. It reads over 74,000 real product reviews, teaches a model what makes headphones or speakers succeed in the market, and then uses an AI 'skeptic' to estimate how a *brand-new* product's specification would be received, grounded in that real data. We validated it on real products held out in advance, and it beats a naive price-based guess while staying honest about where it doesn't work — it fails, on purpose and by design, for mobile apps, and we say so."

### 2-minute version
"Companies that want to know if a product idea will succeed usually wait until after launch and look at reviews — but by then the manufacturing money is already spent. We built a pre-launch alternative. First, we extract aspect-level opinions — build quality, ease of use, value for money, and so on — from over 74,000 real Amazon and Google Play reviews, using an LLM that's only allowed to score an aspect if the review actually talks about it; if it doesn't, we record 'no data' instead of guessing. Second, we train an XGBoost model, benchmarked against five other algorithms, that learns how those aspect profiles relate to a product's actual market success within its category. Third — the core idea — is 'bridging': when someone gives us a brand-new product specification, we prompt an LLM as a skeptical analyst, grounded in real category statistics, to estimate what aspect profile that spec would earn from real customers. That estimate feeds the trained model, producing a viability score with an honest uncertainty range and a SHAP-based explanation of the biggest risks and strengths.

We didn't just claim this works — we pre-registered a held-out test of 59 real products before running it, froze the whole pipeline, and reported the actual correlation: 0.317, statistically significant, and almost independent of a simple price-based guess. And when the identical method failed for mobile apps — because app-store success is driven by distribution, not quality — we reported that as a finding instead of hiding it."

### 5-minute presentation version
Use this as a speaking outline; expand with the numbers from [Chapter 9](09-project-evaluation.md) as needed.

1. **The gap** (30s): Big companies have market research; small makers have guesswork. All existing sentiment/review tools need post-launch data.
2. **The idea — aspect bridging** (60s): Learn from 74k+ real reviews what aspect profiles predict success, in each of 6 physical + 4 app categories. Then use an LLM, prompted to be skeptical of marketing language, to estimate what aspect profile a *new* spec would earn — grounded in real category statistics, not vibes.
3. **How we built it** (90s): Walk the 7-stage pipeline — extraction (null-forcing, evidence-quoted), label engineering (within-category composite success score), feature assembly, XGBoost training (benchmarked against 5 other algorithms, picked on merit), category profiling, bridging, and the serving app.
4. **How we proved it, not just claimed it** (90s): Pre-registered holdout on 59 unseen products — Spearman ρ = 0.317, 95% CI [0.06, 0.54], AUC = 0.743. Almost orthogonal to a price-based baseline (r = 0.135), so it's carrying real information, not rediscovering price. Then the honest part: the exact same method scored R² = 0.101 on mobile apps against a 0.35 acceptance gate — a negative result we report and act on, by disabling that track in the live app rather than deleting the evidence.
5. **The product** (30s): A React/FastAPI web app returns a viability range, percentile rank, per-aspect trust badges, SHAP-based risks/strengths, a market-gap report quoting real customer complaints, and a spec coach that helps a non-expert user write a better specification.
6. **Close**: "The most important design decision in this whole project wasn't a model hyperparameter — it was deciding to show the system's own limits instead of hiding them."
