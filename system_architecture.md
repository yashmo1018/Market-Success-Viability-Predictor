# System Architecture & Data Flow Document
## Hybrid AI Product Success Predictor

### 1. Architecture Overview

The system is a batch-trained, online-served ML pipeline with an LLM at two boundaries: (1) unstructured text → structured features (training time), (2) product specs → estimated features (inference time). Everything between those boundaries is classical, reproducible ML.

```
┌──────────────────── OFFLINE / TRAINING ────────────────────┐
│                                                             │
│  McAuley Amazon 2023        Google Play (live, country=in)  │
│  (download + filter)        (google-play-scraper)           │
│        │                          │            Reddit       │
│        ▼                          ▼         (Pullpush,      │
│  ┌─────────────────────────────────────┐    optional)      │
│  │ DATA TRACK: clean, sample, validate │◄──────┘            │
│  │ output: data/final/ (THE CONTRACT)  │                    │
│  └───────────────┬─────────────────────┘                    │
│                  ▼                                          │
│  ┌─────────────────────────────────────┐                    │
│  │ STAGE B: LLM aspect extraction      │  multi-provider    │
│  │ null-forcing prompt + Pydantic      │  pool: Gemini /    │
│  │ → aspect_scores.jsonl               │  Groq / Ollama     │
│  └───────────────┬─────────────────────┘                    │
│         ┌────────┴────────┐                                 │
│         ▼                 ▼                                 │
│  STAGE C: labels    STAGE F: category profiles              │
│  (per-category      (stats + pain points + Reddit           │
│   normalized)        synthesis) ──────────────┐             │
│         ▼                                     │             │
│  STAGE D: feature matrices                    │             │
│  (physical.parquet / app.parquet              │             │
│   + feature manifests)                        │             │
│         ▼                                     │             │
│  STAGE E: XGBoost ×2 (+aspects-only ×2)       │             │
│  + SHAP + training report → models/           │             │
└───────────────────────────────────────────────┼─────────────┘
                                                │
┌──────────────────── ONLINE / SERVING ─────────┼─────────────┐
│  Streamlit UI                                 ▼             │
│  ┌──────────┐   specs   ┌──────────────────────────┐        │
│  │Simulator │──────────►│ STAGE G: Bridging LLM    │        │
│  └──────────┘           │ (Gemini Flash, 1 call)   │        │
│  ┌──────────┐           │ specs+profile → aspects  │        │
│  │Explorer  │           └──────────┬───────────────┘        │
│  └──────────┘                      ▼                        │
│  ┌──────────┐           ┌──────────────────────────┐        │
│  │Analyzer  │◄──────────│ Predictor: manifest-     │        │
│  └──────────┘  results  │ ordered vector → XGBoost │        │
│                          │ → SHAP → risks/strengths │        │
│                          └──────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
        Persistence: PostgreSQL (Supabase) mirrors data/final/ +
        aspect scores + predictions; file artifacts are the source
        of truth for models (models/ directory).
```

### 2. Component Responsibilities

| Component | Responsibility | Key invariant |
|---|---|---|
| Data track collectors | Acquire + clean + structure raw data | Output conforms to frozen data contract |
| `load_final.py` | Contract enforcement at ML boundary | Refuses manifest with validation_passed=false |
| `llm_provider.py` | Provider pool, rate limiting, rotation, resume | Every extraction persisted before next call |
| `batch_extractor.py` | Stage B orchestration | Null-forcing prompt; Pydantic gate; failed_reviews.jsonl |
| `label_engineering.py` | Success labels + fake-review robustness flags | Within-category normalization only |
| `feature_builder.py` | Matrices + feature manifests | Manifest on disk = single source of column order |
| `run_training.py` | One-command C→D→E | Seeded; cached stages; acceptance gates |
| `category_profiler.py` | Category intelligence for bridging | Evidence phrases traceable to real reviews |
| `bridging_layer.py` | Specs→aspect estimation | Grounded in category profile; all aspects scored |
| `predictor.py` | Vector assembly + inference + SHAP | Iterates manifest; never hardcodes columns |
| Streamlit app | Presentation | No score without SHAP decomposition |
| Supabase (PostgreSQL) | Shared persistence, prediction log | Schema v2 (see schema_v2.sql) |

### 3. Data Flow Details

**Training-time flow (runs once, re-runnable per stage):**
1. `data/final/reviews_*.json` → batch extractor → per-review `{aspect: score|null, evidence}` rows in `aspect_scores.jsonl` (append-only, resumable)
2. Products + review timestamps → labels.json (`success_score` 0–100, within-category min-max, log1p on volume/installs; suspect-review products flagged and excluded)
3. aspect_scores.jsonl (confidence ≥ 0.3) → per-product aspect means + mention_rates → join labels → `features_{type}.parquet` + `xgb_{type}_features.json` manifests
4. Parquet → 5-fold CV → final models (full + aspects-only per type) → SHAP artifacts → training_report.json

**Inference-time flow (per prediction, <15s):**
1. UI collects category + structured specs + free text
2. Load `category_profiles.json[category]` (precomputed)
3. ONE Gemini Flash call: bridging prompt → 9 or 11 aspect scores + reasoning
4. Vector assembly: aspects from bridge; price from user; neutral priors (category medians) for rating_count_log/velocity/installs; category means for mention_rates; column order from manifest
5. XGBoost predict (full + aspects-only) → TreeExplainer SHAP → top-3 risks/strengths
6. Result dict rendered; prediction row written to Supabase `predictions`

### 4. Failure Modes & Degradation

| Failure | Behavior |
|---|---|
| Gemini down at inference | Fallback bridging via Groq → Ollama (quality note shown in UI) |
| Bridging returns invalid JSON | One retry with error context, then fallback provider |
| Category profile missing | Simulator disabled for that category with clear message; others unaffected |
| Reddit absent | Profiles built without Reddit section (silent, by design) |
| Extraction batch crash | Resume from aspect_scores.jsonl on restart; zero rework |
| Contract violation in data drop | Loader exits naming exact file/field; data track fixes; no partial runs |

### 5. Technology Stack
Python 3.10+ · XGBoost 2.x (hist, enable_categorical) · SHAP · Pydantic v2 · pandas/pyarrow · google-generativeai / groq / ollama · PostgreSQL 15 (Supabase) · Streamlit · matplotlib

### 6. Security & Privacy
- Reviewer names hashed (SHA-256, 8-char) before storage; raw names never persisted
- API keys in gitignored config; no keys in code or logs
- Supabase RLS deferred (no auth in v1); anon key restricted to project tables
- All scraped data is public content; McAuley usage under academic citation terms
