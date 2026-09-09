# Implementation Plan & Execution Document
## Hybrid AI Product Success Predictor

### 1. Team Structure & Ownership

| Track | Owner | Deliverables |
|---|---|---|
| Data Track | Teammate(s) | `data/final/` contract files + validation report (per the data contract) |
| ML Track | Raj | Extraction pipeline, both XGBoost models, bridging layer, Streamlit app (per the ML pipeline spec) |
| Shared | Both | Supabase setup, report writing, demo prep |

**The interface between tracks is the DATA CONTRACT** (Section 2 of the data contract). It is frozen after Week 1. Changes require both owners' sign-off and edits to both the pipeline spec files.

### 2. Timeline (8 working weeks)

**Week 1 — Foundations (both tracks in parallel)**
- Data: download McAuley metadata, run sub-category filter, hit the decision gate on product counts; begin review-file downloads
- ML: set up repo structure, Supabase project + schema, write llm_provider.py and the extraction prompt; create all API accounts (Gemini + Groq per member)
- Joint: freeze the data contract; agree category list is final
- **Exit criteria:** filter counts verified ≥100/category; provider pool passes a 10-review smoke test

**Week 2 — Collection & Extraction Gate**
- Data: complete Amazon review extraction, Google Play collection, Reddit best-effort; run cleaning; deliver first `data/final/` drop with validation passing
- ML: hand-validation gate on 30 reviews (null-forcing verified); launch full physical batch extraction
- **Exit criteria:** validation_passed=true manifest delivered; extraction batch running with resume capability proven (kill and restart test)

**Week 3 — Extraction Completes, Labels**
- ML: app batch extraction; benchmark run (100 reviews × all providers); label engineering + the label-variance diagnostic
- Data: fix any issues surfaced by ML loading; finalize v1.1 data drop if needed
- **Exit criteria:** aspect_scores.jsonl complete for both types; per-category label std ≥ 8

**Week 4 — Training**
- ML: feature builder, run_training.py, both models + aspects-only variants, SHAP outputs, training report
- **Exit criteria:** CV R² ≥ 0.2 on both full models (target ≥ 0.35); per-category R² reviewed; feature manifests saved

**Week 5 — Prediction Layer**
- ML: category profiler, bridging layer, predictor; test on 10 hand-written prototype specs per category and sanity-check outputs
- **Exit criteria:** end-to-end predict() returns well-formed results for all 10 categories in <15s

**Week 6 — Application**
- ML: Streamlit app (Analyzer + Simulator pages); Data teammate joins on UI polish
- **Exit criteria:** demo path works: pick category → enter specs → see viability + SHAP breakdown

**Week 7 — Evaluation & Report**
- Both: write report (methodology, benchmark table, limitations incl. proxy label, US-data gap, fake-review robustness); error analysis on worst predictions
- **Exit criteria:** report draft complete; benchmark table final

**Week 8 — Buffer & Demo**
- Rehearse demo twice; freeze code; record backup demo video (network-independent)

### 3. Milestone Gates (hard stops — do not proceed past a failed gate)

| Gate | Week | Criterion | If failed |
|---|---|---|---|
| G1 Category volume | 1 | ≥100 products/physical category | Broaden keywords or merge categories |
| G2 Extraction quality | 2 | 30-review hand check: nulls correct, evidence verbatim | Tighten prompt; re-test before batch |
| G3 Label variance | 3 | Per-category std ≥ 8 | Adjust label weights; re-derive |
| G4 Model floor | 4 | CV R² ≥ 0.2 both models | Debug: extraction confidence dist, leakage, per-category breakdown |
| G5 E2E latency | 5 | Prediction < 15s | Cache profiles; single bridging call |

### 4. Risk Register (top items)

| Risk | Prob. | Impact | Mitigation | Owner |
|---|---|---|---|---|
| LLM batch exceeds free quotas | Med | High | Multi-key pool + Ollama overnight; start batch Week 2 not Week 3 | ML |
| Aspect scores vague | Med | Critical | G2 hand gate before any batch | ML |
| Category yields too thin | Low | High | G1 gate before big downloads | Data |
| Label variance flat | Med | High | G3 diagnostic; alternative weightings pre-planned | ML |
| Contract drift between tracks | Med | High | Frozen contract + loader validation that names exact violations | Both |
| Team member unavailable | Med | Med | Both the pipeline spec files are complete enough for either person to run either track via the development workflow | Both |

### 5. Tooling & Ways of Working
- All code written via the development workflow sessions driven by the two the pipeline spec files; keep both files updated as ground truth
- Git: main branch protected; feature branches per stage; PR review by the other track owner for contract-touching changes
- Long batches (extraction) run on local machines, never inside the development workflow sessions
- Weekly 30-min sync: gate status, blockers, contract change requests
- Secrets: `.env` + `config/llm_providers.yaml`, both gitignored, template files committed

### 6. Definition of Done (project level)
1. `python src/training/run_training.py` produces both models from clean data with zero manual edits
2. Streamlit demo: spec → viability + SHAP in <15s across all 10 categories
3. Benchmark table (≥3 LLM providers, 100 reviews) in the report
4. Report documents: proxy-label limitation, aspects-only R² as the honest headline, US-data gap, fake-review robustness measures
5. README allows a stranger to reproduce the pipeline from `data/final/`
