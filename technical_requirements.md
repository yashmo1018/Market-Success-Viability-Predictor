# Technical Requirements Document (TRD)
## Hybrid AI Product Success Predictor

### 1. Runtime & Environment

| Item | Requirement |
|---|---|
| Language | Python 3.10+ (3.11 recommended) |
| OS | Linux/macOS/Windows (team laptops); no cloud compute required |
| RAM | ≥8 GB on the machine that streams McAuley review files |
| Disk | ≥25 GB free (raw Amazon files ~12-15 GB compressed) |
| GPU | None required; Ollama Gemma3:4b runs CPU (~3-5 s/review) or 4-6 GB VRAM |
| Network | Required for collection + cloud LLMs; inference needs one API call |

### 2. Dependencies (pinned at project start; freeze in requirements.txt)

```
# Data track
google-play-scraper>=1.2
requests>=2.31

# ML track
xgboost>=2.0            # native categorical + NaN handling required
scikit-learn>=1.4
shap>=0.45
pandas>=2.1
pyarrow>=15
pydantic>=2.5
google-generativeai>=0.5
groq>=0.9
ollama>=0.2
streamlit>=1.33
matplotlib>=3.8
supabase>=2.4           # python client
python-dotenv
```

### 3. External Services & Quotas

| Service | Tier | Limits (per key) | Keys held |
|---|---|---|---|
| Gemini 3 Flash (AI Studio) | Free | 10 RPM / 1,500 RPD / 250K TPM | 1 per team member |
| Groq (Llama 3.3 70B) | Free | 30 RPM / 1,000 RPD / 12K TPM | 1 per team member |
| Ollama (gemma3:4b local) | Local | Unlimited | n/a |
| Supabase | Free | 500 MB DB, 2 projects | 1 shared project |
| Pullpush (Reddit) | Free/public | Undocumented, unstable | none needed |
| McAuley dataset | Public | none | citation required |
| Streamlit Community Cloud | Free | 1 app | 1 shared |

Throughput planning (2 active members): ~5,000 cloud extractions/day + 1-2k/night Ollama → 33k reviews in ~5-6 days.

### 4. Data Requirements

| Requirement | Value |
|---|---|
| Physical products | ≥100/category post-filter (target 200-300), 6 categories |
| Apps | ≥75/category post-filter (target 100-150), 4 categories |
| Reviews per product | 5 (hard floor) – 20 (cap), rating-stratified |
| Review length | 10–400 words post-cleaning, English |
| Product requirements | price present; rating_count ≥ 20 (physical) / ratings ≥ 100 & installs present (apps) |
| Timestamps | Unix seconds everywhere (McAuley ms ÷ 1000) |
| Label variance | per-category success_score std ≥ 8 (gate G3) |

### 5. Model Requirements

| Requirement | Specification |
|---|---|
| Algorithm | XGBRegressor, objective reg:squarederror, tree_method hist |
| Categorical handling | enable_categorical=True; `category` as pandas category dtype |
| Missing values | Native NaN routing; imputation is FORBIDDEN |
| Hyperparameters (baseline) | n_estimators 600, lr 0.05, max_depth 5, min_child_weight 3, subsample 0.8, colsample 0.8, early_stopping 50 |
| Validation | 5-fold CV; report RMSE/MAE/R² overall AND per category |
| Variants | Per type: full model + aspects-only model (drop price, avg_rating, rating_count_log, velocity, installs, days_since_update) |
| Acceptance | full R² ≥ 0.35 pass / 0.2–0.35 warn / <0.2 fail; aspects-only R² is the reported headline |
| Explainability | shap.TreeExplainer; summary plots persisted; per-prediction top-3 risks/strengths |
| Artifacts | xgb native .json save; feature-manifest .json alongside every model; training_report.json |
| Reproducibility | random_state=42 everywhere; identical rerun ⇒ identical metrics |

### 6. LLM Requirements

| Requirement | Specification |
|---|---|
| Extraction output | Strict JSON per Pydantic schema; score∈[0,10] or null; evidence ≤120 chars verbatim |
| Null-forcing | Unmentioned aspect ⇒ null (validated at gate G2 by hand on 30 reviews) |
| Retry policy | invalid → 1 retry same provider (error appended) → switch provider → log to failed_reviews.jsonl |
| Confidence floor | extraction confidence < 0.3 excluded from aggregation |
| Provider abstraction | single `extract_aspects()` entry; per-key RPM/RPD tracking; resume from jsonl |
| Bridging | Gemini Flash only; all aspects scored (no nulls); reasoning per aspect; 1 call/prediction |
| Benchmark | same seeded 100 reviews × ≥3 providers; report agreement (mean |Δscore| pairwise), latency, JSON-valid % |

### 7. Database Requirements
- PostgreSQL 15 (Supabase); schema per `schema_v2.sql` (10 tables, 2 materialized views)
- Materialized views refreshed after every extraction batch (`REFRESH ... CONCURRENTLY`)
- File artifacts (parquet/models) remain source of truth for training; DB is shared persistence + prediction log
- DB size budget: well under 500 MB free tier (33k reviews ≈ 40-60 MB with scores)

### 8. Application Requirements
- Streamlit multipage: Simulator, Explorer, Analyzer, About-the-model
- Prediction latency < 15 s p95 (dominated by one LLM call)
- Every displayed score accompanied by SHAP top-3 and the proxy-label disclaimer
- App reads only: models/, data/extracted/category_profiles.json, feature manifests, Supabase for logging

### 9. Quality & Engineering Standards
- Type hints on all public functions; Pydantic at every LLM boundary
- Seeded randomness (42) in sampling, CV, benchmarks
- Stage caching with `--force` override; append-only logs for long batches
- No hardcoded column orders — manifests only
- Secrets: .env / config/llm_providers.yaml (gitignored, templates committed)
- Tests: contract loader (bad manifest rejected), Pydantic validators (malformed LLM output rejected), feature builder (column order matches manifest), label math (known fixtures)

### 10. Compliance & Ethics
- McAuley citation (Hou et al., 2024) mandatory in report
- Google Play scraping: moderate volume, rate-limited, public data, research use
- Reviewer PII hashed; no names/images stored
- In-product honesty requirements per PRD §6 (disclaimers are a requirement, not copy)
