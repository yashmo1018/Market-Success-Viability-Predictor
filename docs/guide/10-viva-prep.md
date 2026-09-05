# Chapter 10 — Viva & Presentation Preparation

Answer these out loud, not just silently. If a number surprises you while reading, that's the one to drill on before the viva.

## 10.1 Project Overview

**Q: What does this project actually do, in one sentence?**
A: It estimates whether a not-yet-launched product will succeed with customers, using only its specification, by learning from 74,000+ real reviews what quality signals predict success in that category, then having an LLM estimate what quality signals a new spec would earn.

**Q: Who is this for?**
A: Small businesses and independent makers deciding whether to manufacture a physical product, who don't have access to the market-research departments and paid consumer panels large companies use.

**Q: Why can't existing review-analysis tools do this already?**
A: Every one of them — sentiment dashboards, ABSA pipelines, e-WOM economics models — requires *post-launch* data: reviews, ratings, sales. At the exact moment a manufacturing decision is being made, none of that exists yet for an unreleased product.

**Q: What's the closest prior work, and how is this different?**
A: Narayanan et al.'s pre-launch prediction work, which forecasts reception from chatter about an *already-announced* product. This project's setting is strictly harder — it assumes no product-specific chatter exists at all, only the specification and the category's history.

## 10.2 Architecture

**Q: Walk me through the pipeline.**
A: Seven independently re-runnable stages, each persisting its output to disk: data acquisition → contract verification → LLM aspect extraction → label engineering → feature assembly → XGBoost training with SHAP → category profiling → bridging and prediction, then a FastAPI/React serving layer on top. Full detail in [Chapter 2](02-system-architecture.md).

**Q: Why does every stage write to disk instead of just running as one script?**
A: The extraction stage alone runs for days across rate-limited APIs. Disk persistence means a crash, or a fix to a later stage's formula, doesn't force re-running the expensive earlier stages.

**Q: What stops training and prediction from silently using features in a different order?**
A: A single frozen feature-manifest file, written once by training, read by iteration at prediction time — never a second hand-maintained copy of the column order anywhere else in the code.

**Q: What would break if the aspect schema changed after extraction started?**
A: Every downstream artifact — labels, features, trained models, category profiles — would silently misalign, because they'd all assume a schema that no longer matches what's actually in `aspect_scores.jsonl`. This is exactly why the schema is explicitly frozen.

## 10.3 Data

**Q: Where does the data come from, and why those sources?**
A: Amazon Reviews 2023 (physical products, 6 categories) via Hugging Face streaming, and live Google Play scraping (apps, 4 categories). Amazon was chosen for being a free, peer-reviewed, reproducible academic dataset with stable IDs; Google Play was necessary specifically because it's the only source with fresh install counts, which no static dataset has. Full rationale in [Chapter 4](04-data-pipeline.md).

**Q: How much data, exactly?**
A: 732 physical products / 319 app products after cleaning and fraud filtering, from an initial 740/382 collected. Over 74,000 reviews were LLM-extracted.

**Q: How do you know the reviews aren't fake or gamed?**
A: A fraud filter flags products with burst-timed reviews (>40% inside one 14-day window), extreme-J-shaped rating distributions, or >30% near-duplicate text (Jaccard > 0.7). 71 products were flagged and excluded from training.

**Q: How is "success" defined, and why that formula?**
A: A within-category, min-max normalized composite: for physical products, 40% review volume + 35% rating + 25% velocity; for apps, install count, rating, velocity, and a retention proxy each weighted. Within-category normalization matters because raw review counts mean completely different things across categories.

## 10.4 Model

**Q: Why XGBoost and not a neural network?**
A: It won a head-to-head benchmark against 5 alternatives (Random Forest, sklearn Gradient Boosting, SVR, Ridge, an MLP) on identical data — highest R² (0.564), lowest RMSE, tied-best AUC-ROC, and trained 8× faster than its closest rival. On top of that, it natively handles the aspect data's structural missingness and works exactly with SHAP for exact, fast explanations. Full comparison in [Chapter 5](05-model-development.md).

**Q: What's your actual R², and is that good?**
A: Two numbers, and the distinction matters: the "full" model (with price/rating included) reaches R² = 0.893, but that's partly leakage — average rating alone correlates with the target at ~0.56 because it's 35% of how the label was built. The honest number is the "aspects-only" model: R² = 0.567 for physical products. That's the number behind every claim in the paper.

**Q: 0.567 means 43% of variance is unexplained — isn't that a weak model?**
A: It's an honest model of a genuinely hard problem — predicting market success from review-derived quality signals alone, with metadata stripped out. The paper doesn't claim near-perfect prediction; it claims a real, statistically validated *signal*, confirmed independently on a pre-registered holdout (ρ = 0.317), useful for screening candidate designs, not for certainty on a single product.

## 10.5 Design Decisions

**Q: Why force nulls instead of letting the LLM infer missing aspects?**
A: Inference on an unmentioned aspect is fabrication with a confidence score attached. A review that only discusses sound quality contains zero real information about durability — scoring it anyway would corrupt the training data with invented signal.

**Q: What's the single biggest lever in your validation results?**
A: The skeptic prompt. Switching from a trusting bridging prompt to one with explicit skepticism rules (adjective blindness, absence rule, anchor discipline) raised ρ from 0.241 to 0.313 and AUC from 0.653 to 0.761, on the exact same products.

**Q: Did you try anything that didn't work?**
A: Yes, and we kept it in the paper on purpose: validity-weighted shrinkage (pulling uncertain aspect estimates toward the category mean) seemed obviously correct, but a leave-one-out test showed it *lowered* ρ from 0.313 to 0.249 by destroying cross-aspect covariance the downstream model relied on. We report it as a cautionary result.

## 10.6 Research Contribution

**Q: What's the actual scientific contribution here, distinct from "we built an app"?**
A: A pre-registered, launch-blind validation methodology for pre-launch success prediction, plus the finding itself: a real, price-orthogonal signal (ρ = 0.317, 95% CI excludes zero) confirmed on a frozen, disjoint holdout — and a companion negative result showing precisely where the method stops working (mobile apps, under five different target definitions).

**Q: How do you know this isn't just overfitting to your development set?**
A: That's exactly what pre-registration is for. All tuning happened on a 90-product development set; a *separate*, disjoint 59-product holdout was drawn in advance, the pipeline frozen, and the analysis pre-specified. The holdout result landed within thousandths of the development result — that consistency is what a real signal looks like.

## 10.7 Limitations

**Q: What's the biggest limitation of this work?**
A: Survivorship bias. The ≥5-review floor means products that launched and drew zero attention — arguably the truest flops — are absent from the data entirely. Every claim in the paper is about ranking among products that at least reached the market's attention.

**Q: Your holdout is only 59 products — is that enough?**
A: It's enough to detect a real effect (the CI excludes zero, p = 0.014), but not enough for high statistical power on a single decision. ρ ≈ 0.32 explains about 10% of rank variance — the honest use case is screening a portfolio of candidate designs, not settling one launch decision alone.

## 10.8 Future Work

**Q: What would you do with more time?**
A: Confirm the Reddit-priorities lift with a proper pre-registered replication (currently it's exploratory — CI includes zero); extend validated categories beyond the current six; investigate why build-quality's estimability dropped between development (r=0.44) and holdout (r=0.13); and get a larger holdout to tighten the confidence interval.

---

## 10.9 Hard follow-up questions judges actually ask

**"If your app-track model failed, why did you even build it?"**
Because we didn't assume it would fail — we built the pipeline symmetrically for both product types, and the failure *is* a genuine finding: it tells you app-store success is distribution-driven (marketing, placement, network effects) rather than quality-driven, at least under every target we tried, including the app's own average rating. A negative result obtained honestly is still real science, and hiding it would have been worse than reporting it.

**"Your correlation is only 0.317 — couldn't that just be noise?"**
No — that's precisely what the bootstrap confidence interval rules out. [0.059, 0.543] excludes zero, and p = 0.014. It's a modest-strength signal, not a strong one, and the paper says so explicitly rather than overselling it — but modest and real is different from noise.

**"Isn't 'success' just a proxy you made up? What if it's wrong?"**
It's a disclosed, formula-defined proxy (review volume, rating, velocity), not ground truth handed down from nowhere — every paper in this space has to define an outcome variable somehow. We stress-tested this concern directly for apps: we tried five different definitions of success and none worked, which tells us the *problem* is that quality signals don't predict app-store outcomes at all, not that we picked one bad formula.

**"Couldn't a company just game your system by writing better marketing copy?**"
That's exactly what the skeptic prompt is built to resist — adjective blindness means adjectives without verifiable facts don't move the score, and the absence rule actively *penalizes* specs that assert value without evidence. It's not immune to a sufficiently sophisticated gaming attempt, but it's specifically hardened against generic marketing-speak inflation, which is the most common case.

**"Why should I trust an LLM's guess about a product's aspect scores?"**
We don't trust it blind — we validated it. Per-aspect, the bridged estimates correlate with real review-derived outcomes at r = 0.44 for ease of use down to r = 0.05 for after-sales service, and we show that spread to the user directly as trust tiers, rather than presenting one undifferentiated confidence number. Where the LLM's estimate is unreliable, the app says so.

**"What happens if I lie in my product description?"**
The skeptic prompt won't reward adjectives-only claims regardless, but if you fabricate a specific fact (like a battery-life number), the system has no way to independently verify it — this is a real, disclosed limitation ([Chapter 9 §9.10](09-project-evaluation.md#910-current-limitations-own-these--a-judge-asking-about-them-is-testing-whether-you-understand-your-own-work-not-trying-to-catch-you)), and the honest answer is that "specification" here means the closest launch-knowable proxy we could recover, not a lie-detector.

**"Why physical products and not apps for your main claim?"**
Because that's what the evidence supports. We didn't choose physical products in advance and then only test there — we ran the identical pipeline on both, and reported what actually happened: it works for physical products and it doesn't for apps. That asymmetry is itself a finding, not a convenient omission.
