# OPERATING MANUAL — ML Track Runbook
## Hybrid AI Product Success Predictor

> **Audience:** Raj + any AI assistant (including cheaper/smaller models) continuing this work.
> **Status:** ALL CODE IS BUILT AND VERIFIED end-to-end against synthetic data (2026-07-07).
> **What's blocking:** real data from the data team (`data/final/` is currently placeholder, `validation_passed: false`).
> **Read this file top-to-bottom before touching anything. Follow it literally.**

---

## 0. Prime directives (for any AI assistant working on this repo)

1. **Do not modify** the frozen aspect schema ([extraction_prompt.py](src/extraction/extraction_prompt.py)), the feature column order ([feature_builder.py](src/training/feature_builder.py) `feature_columns()`), or the label formulas ([label_engineering.py](src/training/label_engineering.py)) after real extraction/training has started. Changing them invalidates everything downstream.
2. **Never write into `data/final/`.** It belongs to the data team. Synthetic data goes to `data/synthetic_final/` or a sandbox.
3. **Never delete `data/extracted/aspect_scores.jsonl`** once real extraction has started — it represents days of API calls. Back it up before any risky operation.
4. **After ANY code change, run the smoke test** and require "E2E SMOKE PASSED":
   ```
   python scripts/run_e2e_smoke.py
   ```
   This runs the entire pipeline (Stages A–G) on synthetic data in `sandbox_e2e/` without touching real artifacts. It is the project's regression test.
5. **Seeds are 42 everywhere.** Don't introduce nondeterminism.
6. If a stage refuses to run because its output exists, that is the cache working. Use `--force` only when you *intend* to recompute.

## 0.5 Data track (added 2026-07-07 — we now own data collection too)

The data team's role is absorbed: `python scripts/collect_all.py` acquires, cleans, and
builds `data/final/` end-to-end (Amazon Reviews 2023 streaming + Google Play scraping +
optional Reddit). It is fully resumable — rerun after any crash and it continues from
checkpoints in `data/raw/ckpt_*.json`. Sources, keep/exclude rules, cleaning rationale,
and acceptance criteria: **`DATA_PLAYBOOK.md`**. When it finishes with
`Stage A validation: PASSED`, continue at §3 Step 2 below (the contract check in
Step 1 is already done by the builder).

## 1. System map (what exists, where)

| Stage | Script | Reads | Writes |
|---|---|---|---|
| A: Contract check | `src/loading/load_final.py` | `data/final/*` | (validates only) |
| B: LLM extraction | `src/extraction/batch_extractor.py` | `data/final/reviews_*.json` | `data/extracted/aspect_scores.jsonl`, `failed_reviews.jsonl` |
| B-val: Hand check | `src/extraction/review_extraction_sample.py` | aspect_scores.jsonl | (prints) |
| C: Labels | `src/training/label_engineering.py` | `data/final/*` | `data/extracted/labels.json` |
| D: Features | `src/training/feature_builder.py` | labels + aspect_scores | `features_{physical,app}.parquet`, `models/xgb_*_features.json` |
| E: Training | `src/training/run_training.py` (**runs C→D→E**) | parquets | `models/xgb_*.json`, `shap_*.png`, `training_report.json` |
| F: Profiles | `src/prediction/category_profiler.py` | parquets + aspect_scores + reddit | `data/extracted/category_profiles.json` |
| G: Prediction | `src/prediction/predictor.py` (+ `bridging_layer.py`) | models + profiles | (returns dict) |
| UI | `src/app/app.py` | models + profiles | (Streamlit) |
| Test data | `scripts/make_synthetic_data.py` | — | `data/synthetic_final/` or sandbox |
| Regression test | `scripts/run_e2e_smoke.py` | — | `sandbox_e2e/` (auto-cleaned) |

Support modules: `src/extraction/llm_provider.py` (provider pool: gemini_flash → groq_llama70b → ollama_gemma → mock; key rotation, RPM/RPD limits, fallthrough), `src/extraction/validators.py` (pydantic gates on all LLM output).

**The mock provider** (`--mock`) is a deterministic keyword scorer. Use it for: smoke tests, resume-logic tests, UI demos without keys. **NEVER for real extraction** — its scores are junk science.

## 2. One-time setup (per machine)

```bash
pip install -r requirements.txt
copy config\llm_providers.yaml.template config\llm_providers.yaml
# then edit config/llm_providers.yaml: paste EVERY teammate's Gemini + Groq keys.
# More keys = faster batch. The file is gitignored — never commit it.
python scripts/run_e2e_smoke.py     # must end with "E2E SMOKE PASSED"
```

Optional local fallback (recommended before the big batch): install Ollama, then `ollama pull gemma3:4b`.

## 3. THE DAY REAL DATA ARRIVES — exact sequence

### Step 1 — Verify the contract (5 min)
```bash
python src/loading/load_final.py
```
- Prints `CONTRACT VERIFIED` → continue.
- Prints `CONTRACT ERROR: <file>: <exact field>` → **send that exact message to the data team. Do not work around it. Do not edit their data.** Stop here.

### Step 2 — Pilot extraction + HAND-VALIDATION GATE (30–60 min, human required)
```bash
python src/extraction/batch_extractor.py --type physical --limit 30
python src/extraction/review_extraction_sample.py --n 30
```
A human (Raj) must verify, for each printed review:
- (a) aspects the review doesn't mention are `null` (no hallucinated scores);
- (b) every evidence phrase appears verbatim (the tool flags `EVIDENCE NOT FOUND` automatically).

**Pass criteria:** 0 hallucinated scores you can spot, ≤2 evidence mismatches out of 30.
**If it fails:** the extraction prompt is underperforming on real reviews. Diagnose which rule is broken, adjust ONLY the STRICT RULES wording in `extraction_prompt.py` (never the aspect keys), delete `data/extracted/aspect_scores.jsonl` (it only has ≤30 pilot rows), rerun this step.

### Step 3 — Launch the full batch (days; resumable, crash-safe)
```bash
python src/extraction/batch_extractor.py --type physical
python src/extraction/batch_extractor.py --type app
```
- Progress prints every 25 reviews with ETA.
- **Interrupted? Just rerun the same command.** Already-extracted reviews are skipped automatically.
- Rate limits: pool sleeps and rotates keys automatically; when all cloud keys are exhausted for the day it falls to Ollama (if running). More API keys in the yaml = faster.
- Watch `data/extracted/failed_reviews.jsonl`: <1% failures is normal; >5% means a provider is misbehaving — check the `error` field.
- Throughput math: N keys ≈ N×1500 (Gemini) + N×1000 (Groq) reviews/day. With 4 teammates' keys ≈ 10k/day → 33k reviews ≈ 3–4 days.

### Step 4 — Benchmark (2–3 hours, run once, needed for the report)
```bash
python src/extraction/batch_extractor.py --type physical --benchmark
```
Writes `models/benchmarks/benchmark_results.json` (per-provider JSON-validity, latency, pairwise score agreement). This is your paper's "model selection" evidence.

### Step 5 — Train (one command, ~minutes)
```bash
python src/training/run_training.py
```
Read the console output carefully:
- **Label diagnostics:** any category `FLAT!` (std < 8) → STOP; adjust label weights in `label_engineering.py` (see §5 decision tree), rerun with `--force`.
- **Leakage check:** `corr(avg_rating, success_score)` will be ~0.8–0.9. Expected — that's why the aspects-only variant exists.
- **Acceptance gates:** aspects-only R² is the headline number for the paper.
  - `PASS` (≥0.35): done.
  - `WARN` (0.2–0.35): usable; document as limitation.
  - `FAIL` (<0.2): see §5.

### Step 6 — Profiles + app (10 min)
```bash
python src/prediction/category_profiler.py
streamlit run src/app/app.py
```
Sanity-check in the UI: predict a headphone at the category median price with an average description → expect a mid-range score (~40–60). Predict an absurdly cheap premium product → value_for_money should rise. If predictions don't move with inputs at all, see §5.

## 4. Timeline template (2–3 weeks from data delivery)

| Days | Work | Human gate |
|---|---|---|
| 1 | Steps 1–2 (contract + pilot + hand-validation) | YES — hand-validation |
| 2–5 | Step 3 full batch (runs unattended; check failed_reviews daily) | daily 5-min check |
| 5 | Step 4 benchmark (parallel with batch tail) | — |
| 6 | Steps 5–6 (train, profiles, app) | read gates |
| 7–9 | Iterate if gates WARN/FAIL (§5); freeze models | YES — sign off on R² |
| 10–14 | Paper/report: use `training_report.json`, `benchmark_results.json`, SHAP PNGs; demo polish | — |
| 15–21 | Buffer: data-team slippage, re-extraction, presentation | — |

**Compression option if data is late:** Steps 1–2 on day 1, launch batch, and write the paper's methods section from this manual + CLAUDE.md while the batch runs — nothing in the methods depends on results.

## 5. Failure decision trees

**Contract fails (Step 1)** → message data team with the exact error. Only exception: if `validation_passed` is false but their validation report says data is fine, they forgot to flip the flag — ask them to regenerate the manifest, don't edit it yourself.

**Extraction JSON validity < 90% for a provider** → check `failed_reviews.jsonl` errors. Auth/quota errors: fix keys. Schema errors from one provider: pin the good providers via `--provider gemini_flash`, or demote the bad one in `PROVIDER_ORDER` (llm_provider.py).

**Flat labels (`FLAT!`, std < 8)** — means every product in that category scores the same. In order:
1. Check the histogram — one giant bin at 0.5? The category may have ~identical review counts (min-max degenerates). Confirm with raw data.
2. If volume dominates (all mass from one component), shift weight toward rating/velocity in `PHYSICAL_WEIGHTS`/`APP_WEIGHTS` (keep weights summing to 1, document the change).
3. Rerun `python src/training/label_engineering.py --force`, then training. Never proceed with `--allow-flat` without written justification in the report.

**Aspects-only R² < 0.2 (FAIL)** — in order of likelihood:
1. Label variance: revisit flat-label check per category.
2. Extraction quality: rerun the hand-validation viewer on 30 *random* rows (`review_extraction_sample.py`). Hallucinated/garbage scores → the batch is bad; fix prompt, re-extract (expensive — escalate to Raj first).
3. Coverage: in the parquet, check mention rates — if most aspects have mention_rate < 0.05, aspect means are noise from 1–2 reviews. Consider requiring ≥3 mentions per aspect (edit `load_aspect_aggregates`, document it).
4. Per-category R²: if one category works and others don't, the model is fine and specific categories lack signal — report per-category and move on.

**Prediction looks constant regardless of inputs** → bridging is probably returning category means (check `bridged_scores` reasoning strings in the raw JSON). If reasoning strings say "mock", you left mock mode on. If real Gemini returns near-identical scores for wildly different specs, strengthen user descriptions (bridging quality is input-bound) — this is a known limitation, not a bug.

**`ModuleNotFoundError` / import errors** → `pip install -r requirements.txt`; scripts must be run from the repo root (all paths are cwd-relative).

## 6. Rules for the AI assistant continuing this (cheap-model edition)

- **Always start** by reading this file + `CLAUDE.md`. Then run `python scripts/run_e2e_smoke.py` to confirm the repo is healthy before changing anything.
- **Small diffs only.** One stage per change. Rerun the smoke test after every change.
- **Don't refactor.** The structure is intentional (cached stages, manifest-driven columns, relative paths). "Cleanups" have broken pipelines like this before.
- **Don't invent columns or aspects.** The feature space is defined ONLY by `feature_columns()` + the on-disk manifests.
- **When the human asks for a metric**, read it from `models/training_report.json` — never re-derive by hand.
- **When something fails**, quote the exact console error to the human and use §5. Do not guess-and-patch provider SDK code without reproducing the error.
- Anything touching real API quota (full batch, benchmark) or deleting files under `data/extracted/` or `models/`: **ask the human first.**

## 7. Artifact inventory for the final report/paper

| Claim in paper | Evidence file |
|---|---|
| Extraction methodology & null-forcing | `src/extraction/extraction_prompt.py` (quote the prompt) |
| Multi-LLM comparison | `models/benchmarks/benchmark_results.json` |
| Extraction scale & reliability | line count of `aspect_scores.jsonl` vs `failed_reviews.jsonl` |
| Label construction & robustness | `data/extracted/labels.json` + suspect counts in training report |
| Model performance (headline = aspects-only R²) | `models/training_report.json` |
| Explainability | `models/shap_summary_*.png` + per-prediction SHAP in app |
| End-to-end reproducibility | `scripts/run_e2e_smoke.py` output |
