# Chapter 8 — Research Paper Mapping

Paper: **"Launch-Blind Product Viability Estimation from Specifications via LLM Aspect Bridging"**, Raj Jagtap, `paper_ieee/main.tex` (compiles to `paper_ieee/main.pdf`, 9 pages, IEEEtran format, 52+ references, 12 figures, 1 table).

## 8.1 The five contributions, mapped to code

The paper's introduction stakes five explicit contributions (C1–C5). Each one is a claim about a specific piece of this codebase — knowing the mapping cold is what lets you defend the paper *as* the project, not as a separate document written about it.

| Contribution | Paper's claim | Where it actually lives in the code |
|---|---|---|
| **C1** | A null-forcing aspect-extraction scheme over 74,000+ reviews, typed validation, crash-safe multi-provider pipeline | `src/extraction/extraction_prompt.py` (the prompt), `src/extraction/validators.py` (pydantic schemas), `src/extraction/llm_provider.py` (the provider pool + retry/failover), `src/extraction/batch_extractor.py` (the resumable batch runner) — see [Chapter 2 §2.4](02-system-architecture.md#24-stage-b--llm-aspect-extraction) and [Chapter 7 §7.1](07-design-decisions.md#71-the-null-forcing-extraction-prompt) |
| **C2** | The bridging layer: skeptic-prompted, category-grounded aspect estimation with absence penalties, grounding flags, anchor discipline | `src/prediction/bridging_layer.py` — see [Chapter 2 §2.9](02-system-architecture.md#29-stage-g--bridging--prediction) and [Chapter 7 §7.2](07-design-decisions.md#72-the-skeptic-bridging-prompt-v2-over-the-trusting-prompt-v1) |
| **C3** | A retrospective launch-blind harness and a pre-registered confirmatory holdout: ρ = 0.317, CI [0.06, 0.54], AUC = 0.743 | `scripts/retro_validation.py` (development-set harness), `scripts/holdout_validation.py` (the pre-registered confirmatory run) → `models/benchmarks/{retro_validation_v2,holdout_validation}.json` — see [Chapter 9](09-project-evaluation.md) |
| **C4** | An honest map of scope: which aspects are predictable, and a five-target negative result showing failure for mobile apps | `models/bridging_validity.json` (per-aspect trust tiers) + `scripts/app_target_experiment.py` → `models/benchmarks/app_target_experiment.json` |
| **C5** | A measured A/B evaluation of Reddit-derived priorities, and a deployed decision-support application | `scripts/ab_reddit_priorities.py` for the A/B; `src/app/api.py` + `src/app/frontend/` and `src/app/app.py` for the application |

## 8.2 Section-by-section mapping

| Paper section | What it argues | Grounded in |
|---|---|---|
| **Introduction** | States the pre-launch gap and the aspect-bridging idea | The whole pipeline, summarized narratively — see [Chapter 1](01-project-overview.md) |
| **Related Work** | Positions the work against e-WOM economics, ABSA, LLM-as-estimator literature, and gradient boosting for tabular data | `papers/*.pdf` — the literature actually cited in `refs.bib` |
| **Data** | 732 physical + 319 app products after cleaning, the within-category composite success formula, the fraud filter (71 excluded), the Reddit corpus | `src/data_collection/*`, `src/training/label_engineering.py` — see [Chapter 4](04-data-pipeline.md) |
| **Method §Aspect Extraction** | The frozen 9/11-aspect schema, the null-forcing rule, the multi-provider pool | `src/extraction/` — see [Chapter 2 §2.4](02-system-architecture.md) |
| **Method §Success Models and Algorithm Selection** | Full vs aspects-only split; six-algorithm benchmark; why XGBoost | `src/training/run_training.py`, `scripts/ml_algorithm_comparison.py` → `models/training_report.json`, `models/benchmarks/algorithm_comparison.json` — see [Chapter 5](05-model-development.md) in full |
| **Method §Bridging** | The skeptic prompt's three rules | `src/prediction/bridging_layer.py` — see [Chapter 7 §7.2](07-design-decisions.md) |
| **Method §The Honesty Layer** | Trust badges, abstention when ≥half of aspects are ungrounded, the ±5 viability range | `src/prediction/predictor.py` (`_validity`, trust badge logic) |
| **Validation §Retrospective Harness** | 90-product stratified development sample, ρ = 0.313 | `scripts/retro_validation.py` |
| **Validation §Pre-Registered Holdout** | 59 disjoint products, frozen pipeline, ρ = 0.317, CI [0.059, 0.543], AUC = 0.743 | `scripts/holdout_validation.py` → `models/benchmarks/holdout_validation.json` — this is the paper's primary evidence |
| **Validation §Baselines, Ablations** | Price/length baselines, the v1→v2 prompt ablation, the rejected shrinkage experiment | `scripts/baseline_check.py`, `scripts/compare_prompts.py` → `models/benchmarks/{baseline_check,prompt_comparison}.json` |
| **Validation §Which Aspects Can Be Estimated** | Per-aspect validity (ease of use r=0.44 down to after-sales r=0.05) | `models/bridging_validity.json` |
| **Negative Finding** | Five-target sweep, none clears R² ≥ 0.35 | `scripts/app_target_experiment.py` → `models/benchmarks/app_target_experiment.json` |
| **Exploratory: Community Priors** | Reddit A/B, ρ 0.311→0.359 but CI includes zero | `scripts/ab_reddit_priorities.py`, `src/data_collection/reddit_collect.py` |
| **System** | The 7-stage architecture, the React/FastAPI app, the spec coach, the analyzer view | The entire `src/` tree — see [Chapter 2](02-system-architecture.md) and [Chapter 3](03-project-structure.md) |
| **Limitations** | Survivorship bias, statistical power at n=59, scope, spec-vs-real-engineering-spec gap, reproducibility, adversarial review risk | Discussed honestly in [Chapter 9 §9.6](09-project-evaluation.md) |
| **Conclusion** | ρ = 0.317, orthogonal to price, monotonic across tiers; the "map of what's learnable" is the durable contribution | Synthesizes everything above |

## 8.3 How the methodology became the implementation

The paper is not a write-up produced after the fact — the code *is* the methodology, and the sequence in which the codebase was actually built mirrors the sequence the paper argues in:

1. **The measurement instrument first** (aspect extraction) — you cannot ask "what predicts success" until you have a way to measure quality dimensions from raw text.
2. **The honest baseline second** (aspects-only vs full model) — this decision is what let the team *notice* the app track was failing, rather than assuming both tracks worked because the full model's R² looked fine.
3. **The bridging layer third** — only buildable once there was a trained model that knew what a "good" aspect profile looked like per category.
4. **Validation last, but pre-registered before results were seen** — the holdout was drawn and the pipeline frozen *before* running the confirmatory analysis, which is the opposite order of "build something, then find numbers that support it."

## 8.4 Connecting the research contribution to the final product

The paper's central empirical claim — a launch-blind viability signal of ρ = 0.317, "almost orthogonal to price" — is not just a number in a table. It is the exact value the FastAPI `/api/predict` endpoint is built to approximate for a *new* product a user describes. Every honesty mechanism the paper argues for in the abstract ("the system reports its own measured limits through trust tiers, grounding flags, and abstention") is a literal, visible UI element in `PredictorResults.jsx` and the Streamlit `app.py` — not a rhetorical flourish. When a judge asks "does the paper match the product," the honest answer is: they're the same artifact, described twice, once as a scientific claim and once as running software.
