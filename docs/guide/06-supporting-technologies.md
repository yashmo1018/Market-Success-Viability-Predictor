# Chapter 6 — Supporting Technologies

Every entry below is something actually imported and used in this codebase — nothing generic or aspirational.

## 6.1 XGBoost

**What it does:** trains the gradient-boosted tree models that turn an aspect profile into a success score.
**Why used:** it won a head-to-head benchmark against 5 alternatives on this exact data ([Chapter 5](05-model-development.md)) — not chosen by default.
**Why suitable:** native missing-value handling (critical, since "aspect never mentioned" is a structural, meaningful gap, not noise to be filled in), native categorical support for the `category` column, and it's fast enough to retrain 5-fold CV repeatedly during development.
**If replaced:** with Ridge or SVR, missing aspect values would need imputation — injecting fabricated numbers into a system whose entire selling point is refusing to fabricate. With an MLP, SHAP explanations would become approximate and much slower to compute.

## 6.2 SHAP (SHapley Additive exPlanations)

**What it does:** explains *why* a specific prediction came out the way it did, by attributing the prediction to individual feature contributions.
**Why used:** every prediction the app shows a user comes with "top risks" and "top strengths" — SHAP is what computes those, tied to design levers the user actually controls (e.g., "durability is pulling your score down").
**Why suitable:** `TreeExplainer` gives *exact* (not approximate) Shapley values for tree ensembles like XGBoost, in polynomial time — fast enough to run per-prediction in a live web request.
**If replaced:** with a model type SHAP can't explain exactly (like an SVR), explanations would be approximate, slower, and less trustworthy for the specific claim "this exact number is why your score is X."

## 6.3 Pydantic

**What it does:** validates that data has the exact shape/types it's supposed to, and raises a clear error immediately if not.
**Why used:** every LLM response — both from the extraction stage and the bridging stage — is untrusted, free-text-generated JSON until proven otherwise. Pydantic models (`AspectScore`, `ExtractionResult`) enforce that scores are floats in [0, 10], evidence phrases exist and aren't empty, and the returned aspect keys exactly match the frozen schema.
**Why suitable:** it fails loudly and specifically ("keys mismatch: got X, expected Y") instead of silently accepting malformed data that would corrupt a `.jsonl` file 40,000 rows deep.
**If removed:** a single malformed LLM response could silently write bad data into `aspect_scores.jsonl`, and nothing downstream would catch it until a very confusing bug appeared much later in training.

## 6.4 The multi-provider LLM pool (Gemini Flash, Groq Llama-3.3-70B, Ollama)

**What it does:** runs the two LLM-dependent stages of the pipeline — aspect extraction and bridging — across three interchangeable providers.
**Why used:** free-tier API limits (10 RPM / 1,500 requests-per-day per Gemini key, 30 RPM / 1,000 RPD for Groq) make a single provider unworkable for a 74,000-review batch that has to finish this decade. The pool round-robins across multiple keys per provider, tracks rate limits per key, and falls through to a local Ollama model when every cloud key is exhausted for the day.
**Why suitable:** this is the only way to run a multi-day extraction batch on free-tier quotas without babysitting it — it's what makes the crash-safe, resumable batch extractor (`extract_daemon.py`, `watchdog.ps1`) practical.
**If removed (single provider only):** the extraction batch would either need paid, higher-quota API access, or would take proportionally longer and be far more fragile to any single provider's rate limits or outages.

## 6.5 FastAPI

**What it does:** serves the prediction, spec-coach, category-profile, and analyzer endpoints over HTTP.
**Why used:** it's the backend for the primary user-facing interface — the React app calls `/api/predict`, `/api/coach`, `/api/profile/{category}`, `/api/analyzer` directly.
**Why suitable:** built-in request validation via Pydantic models (`PredictRequest`, `CoachRequest`), automatic docs, and it can mount the compiled React build directly (`StaticFiles`), so one process serves both the API and the UI in production.
**If replaced:** with Flask or Django, you'd lose the automatic Pydantic-based request validation that currently rejects malformed requests (e.g., negative prices) before they ever reach the prediction logic.

## 6.6 React 19 + Vite

**What it does:** the primary user interface — `SimulatorForm`, `PredictorResults`, `SpecCoachPanel`, `MarketGapsPanel`, `CustomCharts`, `Navbar`.
**Why used:** a founder needs an interactive form (enter a product spec, see a live viability breakdown), not a static report — React's component model fits that naturally.
**Why suitable:** Vite gives fast dev-server rebuilds during UI iteration; the built output is a static bundle FastAPI can serve directly with no separate frontend server needed in production.
**If replaced:** with the Streamlit-only interface (§6.7), the same predictions would still work, but the UI would be far more constrained — Streamlit is excellent for fast internal tooling, less suited to a polished, custom-interaction product demo.

## 6.7 Streamlit

**What it does:** a second, independent UI (`src/app/app.py`) over the exact same `Predictor`/`coach_spec` functions, with no HTTP layer in between.
**Why used:** it's dramatically faster to stand up and iterate on than a full React app, which makes it useful for quickly demoing or debugging the prediction logic itself, decoupled from frontend build tooling. It's also what's deployed to Streamlit Cloud (`.streamlit/`, `secrets_for_streamlit_cloud.toml`).
**Why suitable:** pure Python, no separate build step, renders charts and KPI cards (`theme.py`, `charts.py`) with very little code.
**If removed:** the React/FastAPI stack alone would still fully cover the product, but there'd be no lightweight, zero-build way to sanity-check the prediction pipeline or deploy a quick public demo.

## 6.8 pandas + PyArrow (parquet)

**What it does:** the feature tables (`features_{physical,app}.parquet`) are built, joined, and read with pandas; PyArrow is the parquet engine underneath.
**Why used:** the natural format for "one row per product, many numeric/categorical columns" — exactly what XGBoost training needs.
**Why suitable:** parquet is compact, fast to read/write, and preserves the pandas `category` dtype exactly, which matters because that dtype is what feeds XGBoost's `enable_categorical` flag directly.
**If replaced:** with plain CSV, the categorical dtype would need to be re-declared every time the file is loaded, adding a place for training/serving to silently drift out of sync.

## 6.9 scikit-learn

**What it does:** supplies `KFold` for the 5-fold cross-validation splits, plus the four non-XGBoost algorithms benchmarked in [Chapter 5](05-model-development.md) (Random Forest, Gradient Boosting, SVR, Ridge, MLP).
**Why used:** it's the standard, well-tested implementation of every classical ML baseline — using it for the comparison algorithms keeps the benchmark fair (nobody can claim XGBoost only won because of a home-grown, weaker baseline implementation).
**If removed:** the algorithm comparison in Chapter 5/the paper would have no credible baselines to benchmark against, undermining the "we didn't just assume XGBoost" claim.

## 6.10 Matplotlib

**What it does:** generates every static figure — SHAP summaries, the algorithm comparison charts, the pipeline architecture diagram, the holdout validation scatter plot.
**Why used:** full manual control over layout, a house color/style system was built (`INK`, `MUTED`, `BLUE`, etc. — shared `rcParams` across figure scripts) so every figure in the paper reads as one consistent visual system rather than default-styled, mismatched plots.
**If replaced:** with a higher-level plotting library (e.g., default seaborn styling), less manual control over exact caption placement, direct value labels, and the specific "house style" the paper's figures use.

## 6.11 PyYAML

**What it does:** reads `config/llm_providers.yaml`, the (gitignored) file holding real API keys for the LLM pool.
**Why used:** YAML is a natural fit for "list of providers, each with a list of keys and rate limits" — more readable than the equivalent JSON for a hand-edited config file.
