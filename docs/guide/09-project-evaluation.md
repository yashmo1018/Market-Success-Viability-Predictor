# Chapter 9 — Project Evaluation

## 9.1 How the project was tested — three layers

1. **Model-level testing:** 5-fold cross-validation on the trained XGBoost models, reported per-category to catch category-specific failure.
2. **System-level testing:** a full launch-blind validation harness that asks, for real historical products, "if we'd only known the spec, would we have predicted the outcome that actually happened?"
3. **Confirmatory testing:** a pre-registered holdout — the gold-standard test, run once, on data the pipeline had never touched, with the pipeline frozen beforehand.

## 9.2 The pre-registered holdout — the paper's primary evidence

- **n = 59** real physical products, drawn with a fixed seed, disjoint from the 90-product development set
- Pipeline frozen before the run; nothing tuned after seeing the result
- **Spearman ρ = 0.317**, bootstrap 95% CI **[0.059, 0.543]** — excludes zero, so the signal is statistically real
- **p = 0.014**
- **AUC = 0.743** (top-quintile vs bottom-quintile discrimination), CI [0.51, 0.93]
- Mean predicted viability rose **monotonically** across all five actual-success quintiles: 58.5 → 60.8 → 61.7 → 62.8 → 64.1

**Why this specific number matters and what it doesn't claim:** ρ = 0.317 explains roughly 10% of rank variance at this sample size. That is a **screening signal for a portfolio of candidate designs**, not a verdict on any single product — and the paper says so explicitly. Know this distinction cold; it's the first thing a sharp judge will probe ("so if my ρ is only 0.32, why should anyone trust this at all?").

## 9.3 Why it isn't just rediscovering price

Three baselines were tested using only the same launch-knowable inputs:

| Baseline | ρ |
|---|---|
| Price distance from category median | −0.178 |
| Marketing-copy length | −0.259 (longer copy weakly signals *worse* outcomes) |
| Within-category price percentile (strongest baseline) | 0.250 |
| **Full bridging pipeline** | **0.317** |

The full pipeline beats the strongest baseline only modestly in raw magnitude, but the two signals are **almost orthogonal (r = 0.135)** — meaning the pipeline isn't just re-deriving "expensive products do better," it's carrying separate information. A post-hoc ensemble of the two reaches ρ = 0.320, reported as exploratory (not pre-registered).

## 9.4 What made the biggest measured difference: the prompt ablation

| Prompt variant | ρ | AUC |
|---|---|---|
| v1 — trusting | 0.241 | 0.653 |
| **v2 — skeptic (shipped)** | **0.313** | **0.761** |
| Validity-weighted shrinkage (tried, rejected) | 0.249 | 0.718 |

The skeptic prompt alone accounts for most of the pipeline's usable signal — a partial correlation controlling for spec length confirms the lift isn't just "the skeptic prompt makes the LLM write more, and more text helps" (ρ = 0.303 even after controlling for length). The shrinkage experiment is reported precisely because it *seemed* like a good idea and measurably wasn't ([Chapter 7 §7.3](07-design-decisions.md#73-rejecting-validity-weighted-shrinkage-even-though-intuition-favored-it)).

## 9.5 Which aspects can actually be estimated from a spec

| Aspect | r (bridged vs review-derived ground truth) | Trust tier |
|---|---|---|
| Ease of use | 0.44 [0.23, 0.61] | STRONG |
| Build quality | 0.40 [0.20, 0.58] | STRONG |
| Durability | 0.39 | MODERATE |
| Reliability | 0.39 | MODERATE |
| Utility | 0.38 | STRONG |
| Value for money | 0.33 | MODERATE |
| Design appeal | 0.19 | WEAK / NO SIGNAL |
| After-sales service | 0.05 [−0.18, 0.28] | WEAK / NO SIGNAL |

**In plain English:** a specification can tell you a lot about how a product will feel to use and whether it's built well, and almost nothing about how good the company's customer service will turn out to be, or whether people will find it beautiful — both of those are inherently invisible on a spec sheet. This is exactly why the app shows trust badges per aspect instead of one undifferentiated confidence number.

## 9.6 The negative finding — mobile apps (report this with total confidence, not embarrassment)

Against the pre-registered acceptance gate (aspects-only CV R² ≥ 0.35):

| Target tested | CV R² |
|---|---|
| Composite success (the original label) | 0.101 |
| Average rating alone | 0.153 |
| Retention proxy | −0.012 |
| Normalized install count | 0.231 (best, still fails the gate) |
| Review velocity | 0.072 |

None clears the gate. Most tellingly: review aspects can't even predict an app's own average rating (R² = 0.153) — so this isn't an artifact of a badly chosen composite label, it's a more basic fact about the app market: ratings are squeezed into a narrow 4.0–4.6 band, review sentiment in these categories centers on monetization/ads rather than durable quality, and success is distribution-driven (marketing spend, store placement, network effects) rather than quality-driven. **Action taken:** the app track is disabled in the live product, visibly, with the failed experiment cited rather than the feature quietly removed ([Chapter 7 §7.8](07-design-decisions.md#78-reporting-the-app-track-failure-instead-of-hiding-it)).

## 9.7 The exploratory Reddit result — reported as unconfirmed, on purpose

Adding Reddit-derived community priorities to the bridging prompt: ρ rose from 0.311 → 0.359, AUC from 0.728 → 0.752, on a paired A/B over the same 89 development products. But the bootstrap 95% CI on the *difference* is **[−0.025, +0.125] — it includes zero**, so this was reported as suggestive, not confirmed, and explicitly flagged as not pre-registered (unlike the main holdout). This is a second demonstration of the same discipline as §9.3: a positive-looking number was not oversold past what its own uncertainty interval actually supports.

## 9.8 Algorithm comparison — the full picture

Already covered in depth in [Chapter 5](05-model-development.md); the headline: XGBoost wins on R² (0.564), RMSE (11.4), and AUC-ROC (0.983, tied) among six algorithms benchmarked identically, while training 8× faster than its closest rival on regression quality.

## 9.9 Strengths of the final system

- A real, statistically significant, pre-registered launch-blind signal that is not just rediscovering price
- Full disclosure of what does and doesn't work, at the aspect level, at the category level, and at the market-type level (physical vs app)
- A model-selection process that is itself evidence-based, not assumed
- A negative result treated as a finding, acted on in the product (disabled, not deleted)
- An uncertainty-aware user interface (viability ranges, trust badges, abstention) instead of a single falsely-precise number

## 9.10 Current limitations (own these — a judge asking about them is testing whether you understand your own work, not trying to catch you)

- **Survivorship bias**, the most important one: the ≥5-review floor means products that launched and got no attention at all — arguably the truest flops — are absent entirely. Every claim here is about *ranking among products that reached the market's attention.*
- **Statistical power:** n = 59 at the holdout; the CI is compatible with a weak-to-moderate true effect. Right use: screening many candidate designs, not deciding one launch.
- **Scope:** validated for 6 physical categories only; the app track fails under every tested definition; the Reddit lift is unconfirmed.
- **Input fidelity:** "specifications" here are launch-day marketing copy, not the internal engineering spec a real team holds pre-production — the closest recoverable proxy, but not identical, and optimistic in ways the skeptic prompt reduces without fully removing.
- **Reproducibility:** depends on hosted LLMs whose underlying models can change over time even with frozen prompts/seeds — mitigated by publishing the archived extraction outputs alongside the code.
- **Adversarial review risk:** the fraud filter caught 71 products on burst/J-shape/duplicate signatures, but a sufficiently sophisticated manipulation campaign could still slip through.

## 9.11 Possible future improvements

- Confirm the Reddit-priorities lift with a proper pre-registered replication on a fresh holdout
- Extend validation to more physical categories to test how far the ρ ≈ 0.32 signal generalizes
- Investigate the build-quality trust-tier instability noted between the development set (r = 0.44) and the holdout (r = 0.13) — flagged in the paper as something to investigate rather than smooth over
- Explore whether a genuine, un-marketing-filtered internal spec (rather than launch-day copy) narrows the gap between "specs-only" and "full model" performance
- A larger, purpose-built holdout to tighten the current wide confidence interval and increase the statistical power available for single-product decisions, not just portfolio screening
