# Chapter 3 — Project Structure

This chapter is a map, not a tour. [Chapter 2](02-system-architecture.md) already walked through what each *stage* does; this chapter tells you what each *folder and file* is responsible for, so you can navigate the repository confidently and answer "where does X live?" without hesitation.

## 3.1 Top-level layout

```
Capstone/
├── src/                    → all pipeline + application code
├── config/                 → LLM provider keys (gitignored)
├── data/                   → raw → final → extracted, in that order
├── models/                 → trained models, reports, benchmark artifacts
├── scripts/                → one-off/ops scripts that sit outside the core pipeline
├── papers/                 → literature PDFs used for the paper's citations
├── paper_ieee/              → the IEEE-format capstone paper (LaTeX source + figures)
├── logs/                   → daemon/validation run logs
├── capstone.db             → read-only SQLite mirror of the data, for human browsing
├── the pipeline spec                → the frozen technical spec / build contract for this track
├── OPERATING_MANUAL.md      → the authoritative day-by-day runbook
├── DATA_PLAYBOOK.md         → data sourcing/cleaning rationale
├── README.md                 → quick setup + execution order
└── requirements.txt / requirements-full.txt
```

## 3.2 `src/` — all code, organized by pipeline stage

| Folder | Responsible for | Depended on by |
|---|---|---|
| `src/data_collection/` | Pulling and cleaning raw Amazon/Google Play/Reddit data into `data/final/` | Everything — it's the root of the dependency graph |
| `src/loading/` | `load_final.py` — the one contract-verification gate | Every script that reads `data/final/` |
| `src/extraction/` | LLM aspect extraction: the provider pool, the prompt, the batch runner, validators | Label engineering, feature building (both consume `aspect_scores.jsonl`) |
| `src/training/` | Label engineering, feature assembly, XGBoost training + SHAP | Category profiling, prediction (both consume trained models / feature manifests) |
| `src/prediction/` | Category profiling, the bridging layer, the predictor, the spec coach | The serving layer (`api.py`, `app.py`) calls `Predictor` and `coach_spec` directly |
| `src/app/` | The two user interfaces: FastAPI + React (`api.py`, `frontend/`), and a Streamlit alternative (`app.py`, `charts.py`, `theme.py`) | Nothing downstream — this is the leaf of the dependency graph, what a user actually touches |

Each `.py` file's specific responsibility is covered in depth in [Chapter 2](02-system-architecture.md) under its matching pipeline stage. Two subfolders deserve extra explanation because they aren't single pipeline stages:

**`src/app/frontend/`** — a full Vite + React 19 single-page app, source-controlled separately from the Python code (`package.json`, `src/App.jsx`, `src/components/{Navbar,SimulatorForm,PredictorResults,SpecCoachPanel,MarketGapsPanel,CustomCharts}.jsx`). It's built (`npm run build`) into `frontend/dist/`, and `api.py` mounts that build directory directly, so in production it's one process serving both the API and the compiled UI.

**`src/app/app.py` + `charts.py` + `theme.py`** — a second, independent UI built in Streamlit. It talks to the same `Predictor`/`coach_spec` functions directly (no HTTP layer), and exists as a fast way to demo or debug the prediction logic without needing the React build step. `theme.py` holds shared CSS injection and reusable UI components (`kpi_card`, `banner`, `trust_badge_html`, etc.); `charts.py` holds the plotting functions.

## 3.3 `config/` — secrets, kept out of version control

| File | Purpose |
|---|---|
| `llm_providers.yaml` | **Gitignored.** Real API keys for Gemini, Groq, and local Ollama config — one or more keys per provider, used by the round-robin pool in `src/extraction/llm_provider.py`. |
| `llm_providers.yaml.template` | The shape of that file without real keys, so a new contributor knows what to fill in. |

## 3.4 `data/` — the three-stage data lifecycle

```
data/raw/        →  data/final/        →  data/extracted/
(scraped, messy)    (cleaned, contract-  (per-review LLM output,
                     verified, frozen)    labels, feature tables,
                                          category profiles)
```

| Folder | Contents | Who writes it | Who reads it |
|---|---|---|---|
| `data/raw/` | Amazon streaming checkpoints (`ckpt_*`), raw candidate JSONL per category, raw scraped reviews | `src/data_collection/*` | Only `clean_and_build.py`, when assembling `data/final/` |
| `data/final/` | `products_{physical,app}.json`, `reviews_{physical,app}.json`, `reddit_context.json`, `manifest.json`, `validation_report.txt` — the **frozen data contract** | `clean_and_build.py` | `src/loading/load_final.py`, and transitively every stage after it |
| `data/extracted/` | `aspect_scores.jsonl` (74,000+ scored reviews — **never delete this**, it represents days of paid API calls), `failed_reviews.jsonl`, `labels.json`, `features_{physical,app}.parquet`, `category_profiles.json` | Stages B, C, D, F | Stages D, E, G |

## 3.5 `models/` — everything the training stage produces

| File/folder | Contents |
|---|---|
| `xgb_{physical,app}.json` / `xgb_{physical,app}_aspects_only.json` | The four trained XGBoost models (full + aspects-only, per product type), saved in XGBoost's native format |
| `xgb_{physical,app}[_aspects_only]_features.json` | The frozen, ordered feature-column manifests — see [Chapter 2 §2.11](02-system-architecture.md#211-how-the-pieces-talk-to-each-other--the-key-architectural-guarantee) for why these are load-bearing |
| `shap_summary_*.png` | Global SHAP feature-importance plots, one per model variant |
| `training_report.json` | The single artifact the FastAPI `/api/analyzer` endpoint renders directly: CV metrics, per-category R², feature importances, acceptance-gate verdicts |
| `bridging_validity.json` | Per-aspect correlation between bridged estimates and review-derived ground truth — powers the trust-badge system |
| `benchmarks/` | Every validation/ablation artifact referenced in the paper: `holdout_validation.json`, `retro_validation_v2.json`, `prompt_comparison.json`, `app_target_experiment.json`, `algorithm_comparison.json`, plus the `.jsonl` files of bridged predictions those numbers were computed from |

## 3.6 `scripts/` — everything that isn't part of the core, always-re-runnable pipeline

These are one-off analyses, validation harnesses, and operational tooling — distinct from `src/`, which is the pipeline itself.

| Group | Scripts | Purpose |
|---|---|---|
| **Data collection orchestration** | `collect_all.py`, `collect_reddit.py` | Drive the full `src/data_collection/` sequence end to end |
| **Validation harnesses (produce the paper's numbers)** | `holdout_validation.py`, `retro_validation.py`, `baseline_check.py`, `compare_prompts.py`, `app_target_experiment.py`, `ab_reddit_priorities.py`, `real_product_stress.py`, `headline_cis.py` | Each one produces exactly one `models/benchmarks/*.json` artifact cited in the paper — see [Chapter 9](09-project-evaluation.md) |
| **Algorithm benchmarking + figures** | `ml_algorithm_comparison.py`, `make_algo_figures.py`, `make_paper_figures.py`, `make_pipeline_diagram*.py` | Produce the six-algorithm comparison and every figure in the paper |
| **Operational / long-running infra** | `extract_daemon.py`, `watchdog.ps1`, `check_progress.py`, `overnight_chain.py` | Keep the multi-day extraction batch running unattended and restart it if it dies |
| **Testing / synthetic** | `run_e2e_smoke.py`, `make_synthetic_data.py`, `stress_test.py` | Regression-test the whole pipeline on fake data without touching real `data/` or `models/` |
| **Misc** | `build_sqlite_view.py`, `capture_ui_screenshots.py`, `reddit_impact_report.py` | Human-browsing DB mirror, UI screenshots for the paper, Reddit-source impact writeup |

## 3.7 `papers/` vs `paper_ieee/` — don't confuse these two

- **`papers/`** — the literature: downloaded PDFs of the ~13 related-work papers cited in the bibliography (ABSA surveys, gradient-boosting papers, e-WOM economics papers, etc.), plus a hand-drawn `work flow block diagram.png` from early planning.
- **`paper_ieee/`** — the capstone deliverable itself: `main.tex` (IEEEtran document class), `refs.bib` (52+ entries), `figures/` (all 12 generated figures, `fig1`–`fig10` plus the three UI screenshots), and the compiled `main.pdf`. This is the file tree covered in [Chapter 8](08-research-paper-mapping.md).

## 3.8 Root-level planning and reference documents

| File | What it's for |
|---|---|
| `the pipeline spec` | The frozen build contract: aspect schema, label formulas, feature column order, acceptance gates — the spec this whole codebase was built against. If you need to know "is this behavior intentional," this file is the answer key. |
| `OPERATING_MANUAL.md` | The authoritative day-by-day runbook and failure decision tree — the doc that wins if it conflicts with anything else. |
| `DATA_PLAYBOOK.md` | Why each data source was chosen, what was excluded and why, cleaning rationale. |
| `README.md` | Fast setup + the exact command sequence to run the pipeline from scratch. |
| `system_architecture.md`, `product_requirements.md`, `technical_requirements.md`, `uiux_design_brief.md`, `implementation_plan.md`, `data_directory_feature_catalog_app_flow.md` | Earlier-stage planning documents — useful for understanding *why* a requirement exists, but `the pipeline spec` and the actual code are the ground truth if they ever disagree. |

## 3.9 Other root files

| File | Purpose |
|---|---|
| `capstone.db` | A **read-only** SQLite mirror of the JSON/parquet pipeline data, rebuilt on demand by `scripts/build_sqlite_view.py`, purely so the data can be browsed with a normal SQL tool (DB Browser, the VS Code SQLite extension) instead of writing throwaway Python every time. The files remain the actual source of truth — this database is a viewing convenience only. |
| `logs/` | Output logs from long-running scripts: the extraction daemon, the watchdog process monitor, and each validation harness run. |
| `.streamlit/`, `secrets_for_streamlit_cloud.toml` | Streamlit Cloud deployment configuration for the `app.py` UI. |
| `.env.template` | Shape of the environment file the FastAPI/React stack expects (filled in locally, never committed). |
| `requirements.txt` / `requirements-full.txt` | Python dependencies — the "full" variant includes everything needed to also regenerate figures and run every validation script, not just the core pipeline. |
