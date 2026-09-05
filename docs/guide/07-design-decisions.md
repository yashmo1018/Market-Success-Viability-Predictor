# Chapter 7 — Design Decisions

Each decision below follows the same structure: what was chosen, what else was on the table, why the alternative lost, what it costs, and what's still imperfect.

## 7.1 The null-forcing extraction prompt

**Chosen:** the extraction LLM may score an aspect only if the review explicitly discusses it, and must return `null` otherwise; every non-null score requires a verbatim evidence phrase.
**Alternative considered:** let the LLM infer plausible scores for unmentioned aspects (e.g., "this seems like a durable brand, so estimate durability ~7").
**Why rejected:** inference is fabrication wearing a confidence score. A review that only praises sound quality genuinely contains zero information about durability — scoring it anyway would be inventing data, not measuring it.
**Trade-off:** more missing values (NaN) in the feature table, which needed a model that handles missingness natively — this is one of the direct causes of choosing XGBoost ([Chapter 5](05-model-development.md)).
**Remaining limitation:** aspects with structurally low mention rates in real reviews (e.g., repairability) still end up with sparse, noisy per-product means, simply because customers rarely write about them at all.

## 7.2 The skeptic bridging prompt (v2) over the trusting prompt (v1)

**Chosen:** the bridging LLM is instructed under three explicit rules — **adjective blindness** (only verifiable facts justify a score; "powerful bass" is noise, "50mm drivers" is evidence), the **absence rule** (a spec offering no evidence for an aspect is scored *below* the category mean, not left neutral, since a competent product description states its strengths), and **anchor discipline** (any score more than two points above the category mean needs a cited spec fact).
**Alternative considered (v1):** trust the specification at face value.
**Why rejected:** marketing copy is optimistic by construction — it promotes flops and hits with the same enthusiasm, so a trusting prompt collapsed every product's estimate into a narrow, uninformatively optimistic band.
**Measured effect:** this single change raised Spearman ρ from 0.241 to 0.313 and AUC from 0.653 to 0.761 on the *identical* set of products — the single largest lever in the whole validation story ([Chapter 9](09-project-evaluation.md)).
**Trade-off:** a skeptical model will sometimes under-rate a genuinely good but under-specified product.
**Remaining limitation:** "specification" here means launch-day marketing copy, the closest thing recoverable after the fact — not the internal engineering spec a real team would have before committing to manufacture, which is generally more complete and less persuasive in tone.

## 7.3 Rejecting validity-weighted shrinkage, even though intuition favored it

**Chosen:** bridged aspect estimates are used as-is, not pulled ("shrunk") toward the category mean in proportion to how reliably that aspect is known to be estimable.
**Why it was tried:** it seems obviously correct — if an aspect (like after-sales service) is known to be poorly estimable from a spec, shouldn't its estimate be pulled toward a safe average rather than trusted at face value?
**Why it was rejected anyway:** a leave-one-out evaluation showed shrinkage actually *lowered* ρ from 0.313 to 0.249 — it destroyed the cross-aspect covariance structure the downstream model was relying on.
**Why this decision matters for a viva:** it's the project's clearest demonstration that intuition was checked against evidence rather than trusted on its own, and that a plausible-sounding idea was killed the moment the data disagreed with it. This is reported as a *cautionary result* in the paper, not quietly dropped.

## 7.4 Within-category normalization for the success label

**Chosen:** every component of the success formula (volume, rating, velocity, installs) is min-max normalized *inside its own category* before being combined.
**Alternative considered:** a single global normalization across all products.
**Why rejected:** 500 reviews means something completely different for a kitchen appliance than for a smartphone — a global scale would systematically favor high-volume categories and make cross-category comparison meaningless.
**Trade-off:** a "success score" of 70 for wireless headphones and 70 for kitchen appliances are not directly comparable in absolute terms — they each mean "does well *relative to its own category*," which has to be explained carefully whenever the number is shown to a user.

## 7.5 NaN-native design — no imputation, anywhere

**Chosen:** a missing aspect score stays missing all the way through the pipeline; nothing fills it in with a mean, median, or model-based guess.
**Why:** imputation would silently inject fabricated information into a system whose entire premise (§7.1) is refusing to fabricate. It would also introduce a second, hidden design decision (*which* imputation strategy) that nobody could audit downstream.
**Direct consequence:** this is a primary reason XGBoost was the right algorithmic fit — it's one of the few common regressors that learns a split direction for missing values natively.

## 7.6 The full-model vs aspects-only-model split

**Chosen:** train and report two separate models for every product type — one with all features (including price/rating/rating-count), one with metadata stripped to LLM-derived aspect features only.
**Why:** average rating alone correlates with the target at r ≈ 0.56, because it's literally 35% of how the label was built. Reporting only the "full model" R² (0.893 for physical) would be presenting a form of label leakage as if it were model insight.
**What it reveals:** the aspects-only model's honest R² (0.567 physical, 0.101 app) is dramatically lower, and *that number* is the one every claim in the paper is built on. This decision is what makes the app-track negative finding ([Chapter 9](09-project-evaluation.md)) possible to see at all — a project that only reported the full model would never have noticed the app track was actually broken.

## 7.7 Pre-registration: freezing the pipeline before the confirmatory test

**Chosen:** after all development-set tuning was finished, a disjoint 59-product holdout sample was drawn with a fixed seed, the entire pipeline was frozen, the analysis was specified in advance, and nothing was changed after seeing the result.
**Why:** tuning repeatedly against the same 90-product development set is a textbook overfitting risk — it's easy to unconsciously keep adjusting a prompt or a formula until a specific sample looks good, which tells you nothing about how it'll perform on new data.
**Why this matters more than the R² number itself:** the holdout result (ρ = 0.317) landed within a few thousandths of the development-set result (ρ = 0.313). That's what a real signal looks like; a tuned artifact usually doesn't survive contact with fresh data that cleanly. This discipline is the paper's primary methodological contribution, arguably more than any single number it produced.

## 7.8 Reporting the app-track failure instead of hiding it

**Chosen:** when the identical pipeline failed for mobile apps (aspects-only R² = 0.101 against a pre-registered 0.35 gate), that result was kept in the paper with equal prominence to the successes, tested against five different target definitions to rule out "we just picked a bad label," and the failed track was **disabled but left visible** in the live app, with the experiment cited rather than the option silently removed.
**Alternative considered:** quietly drop the app track and only present the working physical-products result.
**Why rejected:** a tool meant to inform real financial decisions has to show where its competence ends as plainly as where it works. Silently deleting a failed feature would misrepresent what was actually attempted, and would waste a genuinely interesting finding (that app-store success is distribution-driven, not quality-driven, at least by every measure tried).

## 7.9 Dual frontend: React+FastAPI as primary, Streamlit as a secondary tool

**Chosen:** build the primary product on React + FastAPI, but also keep a Streamlit UI over the same prediction functions.
**Why:** React gives the polish and custom interaction a real product demo needs; Streamlit gives a near-zero-build way to sanity-check the prediction logic directly and deploy an instant public demo (Streamlit Cloud).
**Trade-off:** maintaining two UI surfaces over the same backend logic is extra surface area, but both call the exact same `Predictor`/`coach_spec` functions, so there's no duplicated prediction logic to keep in sync — only presentation differs.

## 7.10 Disk-persisted, independently re-runnable stages

**Chosen:** every pipeline stage reads from and writes to disk, rather than the whole thing running as one monolithic in-memory script.
**Why:** the extraction stage alone runs for days across a rate-limited, multi-provider LLM pool. If a single stage crashes, or a downstream formula needs fixing, disk persistence means only that stage needs to be re-run — not the entire multi-day pipeline from scratch.
**Direct consequence:** this is what makes the crash-safe extraction daemon and resume-on-restart behavior (`extract_daemon.py`, `watchdog.ps1`) practical at all.

## 7.11 The frozen feature manifest as the single source of column order

**Chosen:** the exact ordered list of feature columns is written to disk once, by the training stage (`xgb_{type}_features.json`), and the prediction code builds every input vector by *iterating that file* — never by hardcoding column order a second time anywhere else.
**Why:** the single most common way a real ML system silently breaks in production is training and serving disagreeing about what column 7 means. A hand-maintained second copy of the column order is a bug waiting to happen; a single file both sides read is not.
**What it prevents:** even if the feature-building code changes in the future, training and prediction can never drift out of alignment, because there is structurally only one place the order is defined.
