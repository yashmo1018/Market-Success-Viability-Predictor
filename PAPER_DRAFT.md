# Launch-Blind Product Viability Estimation from Specifications via LLM Aspect Bridging

**Capstone paper draft — skeleton with all measured numbers pre-placed.**
Every `[WRITE: ...]` is prose for Raj to author. Every number below is final and
traceable to an artifact in `models/benchmarks/`. Do not soften or inflate any
of them — the honesty framing IS the contribution.

---

## Abstract

Product teams commit manufacturing and development budgets before any consumer
has used their product, yet existing success-prediction methods require
post-launch signals such as reviews or sales. We present a launch-blind
pipeline: a large language model extracts aspect-level sentiment from 74,000+
real consumer reviews under a null-forcing prompt, gradient-boosted models
learn which aspect profiles succeed within each category, and a
skeptic-prompted bridging layer estimates the aspect profile of an unseen
product from its specifications alone, grounded in category statistics. On a
pre-registered holdout of 59 real products — sampled disjointly before any
tuning, with the pipeline frozen — specs-only predictions rank products
against their actual market outcomes with Spearman ρ = 0.317 (95% CI [0.06,
0.54]) and discriminate eventual bottom-quintile from top-quintile products
with AUC = 0.743. The signal is nearly orthogonal to a price-percentile
baseline (r = 0.135), indicating it captures information beyond price
position. We report two disciplined negative results: the identical method
fails for mobile applications across five outcome definitions (best R² =
0.231), suggesting quality signals decouple from success where markets reward
distribution; and an injection of Reddit-derived consumer priorities lifts
performance (ρ +0.049) but its bootstrap interval includes zero, so we label
it exploratory. The system exposes its own measured limits — per-aspect trust
tiers, grounding flags, and abstention — which we argue is a requirement for
honest pre-production decision support.

## 1. Introduction

**WRITTEN — final prose lives in paper_ieee/main.tex (Section I).** Motivation:
small businesses lack analytical tooling; investment protection; user
satisfaction per dollar spent. Contributions C1-C5:
- C1: null-forcing extraction schema (9 physical / 11 app aspects) + crash-safe
  multi-provider pipeline over 74k+ reviews
- C2: the bridging layer — skeptic prompt v2 with absence penalties, grounding
  flags, and anchor discipline (Section 4)
- C3: a retrospective launch-blind validation harness + a PRE-REGISTERED
  confirmatory holdout (the methodological contribution)
- C4: an honest map of where the method works (physical) and fails (apps),
  with per-aspect trust tiers
- C5: measured integration of community priors (Reddit A/B)

## 2. Related work

**WRITTEN — final prose in paper_ieee/main.tex (Section II), 44 references in paper_ieee/refs.bib** (13 from papers/ + 31 canonical).

## 3. Data

We assembled a corpus spanning two market types. Physical products come from
the Amazon Reviews 2023 dataset across six categories (wireless headphones,
Bluetooth speakers, smartphones, smartwatches, power banks, kitchen
appliances); mobile applications from Google Play across four (finance,
health & fitness, productivity, education). Reviews were cleaned to English
text of 10–400 words; every product retained has at least five reviews; all
ratings lie in [1, 5] and timestamps are normalized. After cleaning, the corpus
contains 1,051 products (732 physical, 319 app) with over 74,000 reviews
processed by the extraction stage.

Because review streams are a gameable signal, we applied a fraud filter before
label construction: products where more than 40% of sampled reviews fall
inside a single 14-day window, whose rating distribution is extreme-J-shaped,
or where more than 30% of reviews are near-duplicates (Jaccard > 0.7 on word
sets) were flagged. Seventy-one products were excluded from training on this
basis (retained for analysis).

The regression target is a within-category composite. For physical products:
success = 100 × (0.40·volume + 0.35·rating + 0.25·velocity), each component
min-max normalized inside its category, with log1p applied to heavy-tailed
volume counts. Apps add install counts and a retention proxy (rating count /
install count). Normalizing within category is essential — 500 reviews means
something different for a kitchen appliance than for a smartphone.

**Survivorship disclosure.** The five-review floor means products that
launched and attracted no attention at all are structurally absent from this
corpus. Every claim in this paper therefore concerns ranking among products
that reached the market's attention; "flop" means the bottom success quintile
of these survivors, not products nobody bought. Section 9 discusses the
consequences.

Finally, for the exploratory study of §7 we collected 1,089 buying-intent
Reddit comments across all ten categories through the Arctic Shift archive
(threads with purchase-decision titles; comment score ≥ 5; 10–400 words;
near-duplicates removed). Coverage is uneven and disclosed: from 237 comments
for health & fitness apps down to 18 for smartphones; no per-category claims
are made from this source.

## 4. Method

### 4.1 Aspect extraction

Each review is decomposed into aspect-level sentiment against a frozen schema:
six aspects shared across market types (value for money, utility, ease of use,
reliability, design appeal, after-sales), three physical-only (build quality,
durability, repairability), and five app-only (performance, stability, ad
experience, update support, privacy/trust). The extraction prompt is
deliberately *null-forcing*: an aspect may be scored (0–10) only if the review
explicitly discusses it, every non-null score must be accompanied by a
verbatim evidence phrase copied from the review, and the reviewer's star
rating is provided as context but forbidden as a score source. A review
praising only sound quality yields nulls for durability — silence is data we
refuse to fabricate. Outputs are validated with typed schemas (score bounds,
evidence length, exact aspect-key match); invalid responses are retried once
with the error appended, then failed over to the next provider, and after a
third failure the review is logged and skipped, so no single bad response
halts a multi-day batch. Extraction ran over 74,000+ reviews on a
multi-provider pool (Gemini Flash, Groq Llama-3.3-70B, local fallback) with
per-key rate tracking, append-only crash-safe logging, and resume support.
Before the full batch, a 30-review hand-validation gate verified nulls for
unmentioned aspects and evidence-phrase fidelity.

### 4.2 Success models

Product-level features aggregate the extraction stream: per-aspect mean score
and mention rate (aspects never mentioned remain NaN — XGBoost handles
missingness natively, so no imputation is invented), plus metadata (price,
average rating, log rating count, review velocity, category as a categorical
feature). We train gradient-boosted regressors (XGBoost, 600 estimators, depth
5, lr 0.05, seed 42) under 5-fold CV, and report two variants with very
different epistemic status. The *full* model reaches CV R² = 0.893 (physical),
but its target is 35% composed of the average rating it receives as a feature;
we disclose this leakage and treat the number as an upper bound on fit, not
evidence of insight. The *aspects-only* variant — metadata stripped, LLM
features only — reaches R² = 0.567 (physical), and every claim in this paper
uses it. The same variant for apps scores R² = 0.101, the negative finding
examined in §6.

### 4.3 Bridging: estimating aspects from specifications

The bridging layer asks an LLM to estimate the aspect profile a product
*would* earn after months of real use, given only its specifications and a
category profile (price quartiles, mean aspect scores, top pain points and
strengths mined from real reviews, and optionally the community priorities of
§7). Our first prompt trusted its input and failed informatively: marketing
copy is adversarially optimistic — flops and hits are promoted with identical
enthusiasm — and predictions compressed into a narrow optimistic band. The
production prompt (v2) is built on three skeptic rules. *Adjective blindness*:
only verifiable facts (materials, standards, numbers, warranty terms) may
justify scores; "powerful bass" is noise, "50 mm drivers" is evidence.
*Absence rule*: if a spec offers no concrete evidence for an aspect, that
silence is itself a signal — competent teams state their strengths — so the
aspect is scored below the category mean and flagged `grounded: false`.
*Anchor discipline*: the category mean is what the median real product
achieves; any score more than two points above it requires a cited spec fact.
Section 5.3 quantifies the effect (ρ 0.241 → 0.313, AUC 0.653 → 0.761) and
rules out a verbosity confound by partial correlation.

### 4.4 The honesty layer

Because bridged estimates vary in reliability by aspect, the system surfaces
its own measured validity. Each aspect carries a trust badge derived from the
retrospective validation (§5.4): STRONG (utility, ease of use, build quality),
MODERATE (value for money, reliability, durability), or NO SIGNAL (design
appeal, after-sales, repairability). Predictions where at least half the
aspects are ungrounded trigger an explicit abstention banner directing the
user to the spec coach rather than to the score. Viability is displayed as a
±5 range — a single decimal would claim precision the validation does not
support — alongside a percentile rank against the 90 retrospectively bridged
real products.

## 5. Validation (the core contribution)

### 5.1 Retrospective launch-blind harness

The central validation question is counterfactual: *had our system existed on
the day a real product launched, would its specs-only estimate have anticipated
that product's eventual market outcome?* We answer it retrospectively. From the
732 physical products in our corpus we drew a stratified sample of 90 —
three per (category × success-quintile) cell across all six categories — so
that flops and hits are represented equally rather than in their natural,
success-skewed proportions.

For each sampled product, the bridging layer received only information knowable
at launch: the product name, brand, price, and the manufacturer's marketing
copy (feature bullets). Reviews, ratings, and sales signals were withheld. The
bridged aspect profile was fed to the aspects-only XGBoost model, and the
resulting viability estimate was compared against the product's actual success
score, computed from the thousands of reviews it subsequently accumulated. One
caveat is disclosed rather than hidden: category profiles used for grounding
include each target product's own reviews at approximately 1/130 weight; we
consider this leakage negligible but note it.

On this 90-product development set the pipeline achieved Spearman ρ = 0.313
(p = 0.003), Pearson r = 0.361, and a flop-versus-monopoly discrimination AUC
of 0.761 — where AUC is computed between the top and bottom actual-success
quintiles. Mean predicted viability rose monotonically across all five
actual-success quintiles (59.1 → 61.1 → 61.4 → 63.2 → 65.7), a spread of 6.6
points between products that became category leaders and products that
languished.

### 5.2 Pre-registered confirmatory holdout

Every design decision above — the skeptic prompt, the grounding flags, the
rejection of shrinkage (§5.3) — was tuned on the same 90 products, creating a
textbook overfitting risk: the harness could be fitting its own development
sample. We therefore pre-registered a confirmatory study. Before the
confirmatory run, we drew 59 products disjoint from the development set (fixed
seed 4242), froze the entire pipeline including prompt version and provider
configuration, and pre-specified the analysis: Spearman ρ, top-versus-bottom
quintile AUC, tier monotonicity, and per-aspect correlations. No tuning
occurred after the result was observed.

The holdout confirmed the development findings: **ρ = 0.317 (p = 0.014), with a
bootstrap 95% CI of [0.059, 0.543] that excludes zero; AUC = 0.743, CI [0.51,
0.93]; and tier means again strictly monotonic** (58.5 → 60.8 → 61.7 → 62.8 →
64.1). The point estimates land within a few thousandths of the development
values (0.317 vs. 0.313; 0.743 vs. 0.761), which is the pattern expected of a
real signal rather than a tuned artifact. We treat this pre-registered
replication, not any single correlation, as the paper's primary evidence. The
interval width is reported as prominently as the point estimate: at n = 59, a
ρ of 0.317 is compatible with a true effect anywhere from weak to moderate, and
explains on the order of 10% of rank variance. This is a screening signal for
portfolios of candidate designs, not a verdict on any single product.

### 5.3 Baselines, ablations, and rejected alternatives

A launch-blind correlation is only interesting if it is not a rediscovery of
something trivial. Three baselines using the same launch-knowable inputs:
price-distance from category median achieves ρ = −0.178; marketing-copy length
ρ = −0.259 (longer copy weakly signals *worse* outcomes); and the strongest,
within-category price percentile, achieves ρ = 0.250 — reproducing the folk
wisdom that pricier products in a category tend to be better regarded. The full
pipeline (ρ = 0.256 under prompt v1, 0.313 under v2) beats this baseline only
modestly on magnitude, but the two signals are nearly orthogonal: their
correlation is r = 0.135. The pipeline is not re-deriving price position; it
extracts complementary information, and a simple average of the two ranks
reaches ρ = 0.320 (reported as exploratory, since the ensemble was formed
post hoc).

Two ablations shaped the final system, one adopted and one rejected. The
adopted one is the skeptic bridging prompt (v2). Under a naive prompt (v1),
marketing copy's adversarial optimism compressed all predictions into a
47.8–80.9 band with flops routinely scoring above 60; v2's absence rule (an
aspect with no concrete supporting fact is scored below the category mean and
flagged ungrounded) and anchor discipline (scores more than two points above
the category mean require a cited spec fact) raised ρ from 0.241 to 0.313 and
AUC from 0.653 to 0.761 on identical products. Because the absence rule could
in principle reward verbose listings rather than informative ones, we computed
the partial Spearman correlation controlling for spec length: the v2 signal
survives essentially unchanged (ρ = 0.303, p = 0.004).

The rejected alternative is validity-weighted shrinkage: pulling each bridged
aspect toward its category mean in proportion to that aspect's measured
validity. Intuition strongly favored it; a leave-one-out evaluation did not.
Shrinkage *reduced* end-to-end ρ from 0.313 to 0.249, evidently because it
destroys cross-aspect covariance that the downstream model exploits. We report
it as a cautionary result: plausible calibration steps must be tested with
held-out weights before shipping.

### 5.4 Which aspects can be estimated from specs — and which cannot

Aggregating the development sample per aspect, bridged estimates correlate
with review-derived ground truth at r = 0.44 [0.23, 0.61] for ease of use,
0.40 [0.20, 0.58] for build quality, 0.39 for durability and reliability, 0.38
[0.14, 0.59] for utility, and 0.33 [0.15, 0.50] for value for money. At the
other extreme, after-sales (r = 0.05 [−0.18, 0.28]) and design appeal
(r = 0.19 [0.01, 0.37]) are effectively or nearly unestimable from
specifications — service quality is invisible in a spec sheet, and aesthetics
are subjective in ways category norms do not capture. These measured tiers are
surfaced verbatim in the application as per-aspect trust badges (STRONG /
MODERATE / NO SIGNAL), so users see the system's confidence structure rather
than a uniform veneer of precision. Holdout per-aspect correlations broadly
reproduce the tiers (ease of use 0.53, utility 0.51), with one deviation noted
honestly: build quality dropped to r = 0.13 on the holdout, flagged as an
instability to investigate rather than smoothed over.

### 5.5 Named-product spectrum

Finally, as a face-validity check, we examined the ranked spectrum by name. At
the top of the specs-only predictions sit products that in reality accumulated
30,000–78,000 ratings (established Bose, JBL, and DOSS speaker and headphone
lines); at the bottom, products like a ₹-tier smartwatch clone with a 2.9-star
average. The system, seeing nothing but launch copy, orders the extremes of
the market correctly — while the middle of the distribution remains noisy, as
the ρ makes explicit.

## 6. Negative finding: the mobile-app track

The pipeline was designed symmetrically for physical products and mobile
applications, and for applications it fails — a result we report with the same
prominence as the successes. Against our pre-registered acceptance gate
(cross-validated R² ≥ 0.35 for the aspects-only model), the app track scores
R² = 0.101 (n = 319). The full model reaches R² = 0.889, but only by leaning
on install counts and rating volume — post-launch popularity metadata that a
pre-production tool cannot have.

The natural rescue hypothesis is that the *target* is at fault: our composite
success score weights installs and velocity at 50%, and those are distribution
outcomes — driven by marketing spend, store placement, and network effects —
that product quality cannot see. If so, review aspects should still predict
quality-side outcomes. We tested this directly, retraining the identical
aspects-only model against five outcome definitions under the same 5-fold CV:
the composite (R² = 0.101), average rating (0.153), a retention proxy
(−0.012), normalized installs (0.231), and review velocity (0.072). None
approaches the gate; most strikingly, review aspects cannot even predict an
app's *own average rating*. The failure is therefore not a target-definition
artifact but something more fundamental about the domain: app store ratings
are compressed into a narrow 4.0–4.6 band, the categories studied are
dominated by free apps whose review sentiment orbits monetization and ads
rather than durable quality, and success is distribution-driven end to end.

We draw two conclusions. Methodologically, the framework functions as an
instrument for discovering *which* market outcomes are learnable from quality
signals — physical-product success partially is; app-store success, under any
definition we tested, is not. Practically, we retired the app track from the
tool's user-facing surface: the option remains visible but disabled, with the
experiment cited, because silently deleting a failed track would misrepresent
the scope of what was attempted.

## 7. Exploratory: community priors (Reddit)

Category profiles ground the bridging prompt in review-derived statistics, but
reviews describe products people already bought; community discussions capture
what buyers *wish they had known*. We collected 1,089 buying-intent comments
(threads matching recommend/regret/avoid-style titles; comments with score ≥ 5,
10–400 words, near-duplicates removed) across all ten categories via the
Arctic Shift archive of Reddit, summarized each category's consumer priorities
with a single LLM call, and injected the summary into the bridging prompt.

The effect was measured with a paired A/B: the same 89 development products
were each bridged twice with the same provider and seed, differing only in the
presence of the priorities field. With priorities, ρ rose from 0.311 to 0.359
and AUC from 0.728 to 0.752. However, the paired bootstrap 95% CI on the ρ
difference is [−0.025, +0.125], which includes zero: **we report the lift as
suggestive, not confirmed.** Unlike the holdout of §5.2, this comparison was
not pre-registered. Two observations temper and contextualize the result. The
without-priorities arm independently reproduces the original baseline (0.311
vs. 0.313), indicating the harness is stable. And the input was small — a
thousand comments across ten categories, with tails as thin as 18 comments for
smartphones — so if the effect is real, its data-efficiency would be notable;
confirming that is future work, ideally with a pre-registered replication on
the holdout set.

## 8. System

The pipeline is implemented as seven independently re-runnable stages
(Figure 1): loading and contract verification, LLM aspect extraction, label
engineering, feature assembly, model training with SHAP explanation, category
profiling, and the bridging/prediction service. Each stage writes its output
to disk and never repeats expensive work unless forced; the extraction stage
is crash-safe and resumable, which mattered in practice — the full batch spans
days of rate-limited API calls across a rotating pool of providers. Feature
manifests are serialized to disk and prediction code constructs input vectors
by iterating them, so the serving path can never silently misalign with
training. A single end-to-end smoke test regenerates synthetic data and runs
every stage in a sandbox; it gates every code change.

The user-facing application (Figure 6a) is a React front end served through a
FastAPI backend. A founder describes a product — category, price, and
free-text specifications — and receives the full analysis: a viability range
(deliberately ±5 wide; §4.4), a percentile rank against the 90 retrospectively
bridged real products, per-aspect estimates plotted against category averages,
SHAP-derived top risks and strengths phrased in terms of design levers the
founder controls, and a market-gap report quoting verbatim customer complaints
for category pain points the design does not convincingly address. Every
aspect estimate carries its trust badge and grounding flag; when at least half
the aspects are ungrounded, an abstention banner replaces confidence with a
redirect to the spec coach.

The spec coach (Figure 6b) closes the loop for users who are not skilled spec
writers. One LLM call classifies the draft's coverage of each aspect
(covered / vague / missing), asks at most five questions ordered by how much
their answers would sharpen the prediction — prioritizing aspects that are
both missing and top category pain points — and rewrites the spec preserving
every stated fact while inserting explicit `[ADD: ...]` placeholders. The
coach is constitutionally forbidden from inventing materials, numbers, or
features the user did not state.

Finally, the Model Performance Analyzer view (Figure 6c) renders the training
report directly from its JSON artifact — including the mobile-application
aspects-only row with its red FAIL badge. Surfacing the system's own failed
benchmark in the product UI, alongside the disabled app-track option in the
simulator, is a deliberate design position: a decision-support tool earns
trust by displaying the boundaries of its competence as prominently as its
successes.

*Figure 6: (a) prediction dashboard with viability range, percentile rank,
aspect-vs-category chart, and disabled app track; (b) spec coach with
per-aspect coverage and prioritized questions; (c) analyzer view showing the
honest benchmark table including the failed app-track gate.*

## 9. Limitations

**Survivorship bias is the most important limitation and bounds every claim in
this paper.** Our corpus requires at least five reviews per product, so
products that launched and attracted no attention at all — arguably the truest
flops — are structurally absent. All results concern *ranking among products
that reached the market's attention*: "flop" throughout means the bottom
success quintile of survivors. The system's ability to identify products that
would fail to gain any traction whatsoever is untested and untestable with
this data.

Second, statistical power. The pre-registered holdout has n = 59; its CI
[0.06, 0.54] is compatible with a weak-to-moderate true effect, and ρ ≈ 0.32
explains roughly 10% of rank variance. The appropriate use of such a signal is
screening many candidate designs — where a modest per-item edge compounds —
not adjudicating a single launch decision.

Third, scope. The validated claims cover six physical-product categories only;
the app track failed all five outcome definitions we tested (§6), and the
Reddit lift is unconfirmed (§7). Fourth, our "specifications" are launch-day
marketing copy — the closest launch-knowable proxy available retrospectively,
but not identical to the engineering specs a team would hold pre-production;
copy is adversarially optimistic in ways the skeptic prompt mitigates but
cannot eliminate. Fifth, the pipeline depends on hosted LLMs: prompts and seeds
are frozen, but provider models evolve, so exact reproduction requires the
archived extraction outputs we publish alongside the code. Finally, review
text itself is a gameable signal; our burst/duplicate/J-shape filter excluded
71 suspect products, but sophisticated review fraud would pass it.

## 10. Conclusion

We asked whether a product's market fate can be partially read from its
specifications alone, before any consumer has touched it. The answer, within
carefully stated bounds, is yes: an LLM that extracts aspect sentiment from
74,000 reviews, a gradient-boosted model that learns which aspect profiles
succeed, and a skeptic-prompted bridging layer that estimates those profiles
from specs combine into a launch-blind signal of ρ = 0.317 (CI [0.06, 0.54])
against real market outcomes — confirmed on a pre-registered holdout, nearly
orthogonal to price (r = 0.135), and monotonic across success tiers from flops
to category leaders.

The contribution we consider most durable is not the point estimate but the
map: which aspects specifications can predict (ease of use, utility, build
quality), which they cannot (after-sales service, aesthetics), and which
markets the method works in at all (physical goods, where quality is rewarded)
versus where it fails under every outcome definition tested (app stores, where
distribution dominates). A pre-production tool that knows and displays its own
limits — trust badges, abstention, uncertainty ranges — is, we argue, the only
honest form such a tool can take at the current state of the art.

---

## Figures to generate (all from existing artifacts)
1. Pipeline diagram (exists: papers/work flow block diagram.png)
2. Holdout scatter: predicted viability vs actual success, tier means overlay
3. Per-aspect validity bar chart with trust-tier colors (bridging_validity.json)
4. v1 vs v2 prompt comparison (prompt_comparison.json)
5. App target-swap bar chart (app_target_experiment.json)
6. UI screenshot with trust badges + market gaps

## Artifact -> section map
| Artifact | Section |
|---|---|
| models/benchmarks/holdout_validation.json | 5.2 |
| models/benchmarks/headline_cis.json | 5.2, 7 |
| models/benchmarks/baseline_check.json | 5.3 |
| models/benchmarks/prompt_comparison.json | 4.3, 5.3 |
| models/benchmarks/real_product_stress.json | 5.4 |
| models/benchmarks/app_target_experiment.json | 6 |
| models/benchmarks/ab_reddit_priorities.json | 7 |
| models/training_report.json | 4.2 |
| REDDIT_IMPACT_REPORT.md | 7 |
