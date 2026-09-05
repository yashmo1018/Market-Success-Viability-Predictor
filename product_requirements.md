# Product Requirements Document (PRD)
## Hybrid AI Product Success Predictor

### 1. Problem Statement
Indian SME founders, D2C brands, and indie app developers make launch decisions worth ₹5–25 lakh with either no market research or tools that reduce consumer opinion to star ratings and binary sentiment. They cannot see WHY products in their target category succeed or fail, and have no affordable way to estimate how their specific product concept would be received before building it.

### 2. Solution Summary
A market-intelligence platform that (a) mines real consumer reviews at the aspect level (build quality, value, stability, ad experience, etc.) using LLM extraction, (b) learns which aspect patterns drive market success per category using XGBoost trained on 2,000+ real products, and (c) lets a founder describe an unlaunched product's specs and receive an explainable Market Viability Assessment grounded in real category data.

### 3. Target Users
| Persona | Need | Primary feature |
|---|---|---|
| Hardware founder (e.g., planning TWS earbuds) | Validate spec/price choices pre-manufacturing | Prototype Simulator (physical) |
| Indie app developer | Understand what drives success in their app category before/after launch | Prototype Simulator (app) + Category Explorer |
| Product manager at D2C brand | Understand competitor weaknesses, category pain points | Category Explorer / Analyzer |
| Academic evaluator / grad-school reviewer | Assess methodology rigor | Benchmark study, SHAP explainability, documented limitations |

### 4. Product Scope

**In scope (v1 — capstone):**
- 10 categories: 6 physical (wireless_headphones, bluetooth_speakers, smartphones, smartwatches, power_banks, kitchen_appliances), 4 app (finance, health_fitness, productivity, education)
- Two data sources: McAuley Amazon 2023 (physical), Google Play India (apps); Reddit as optional category context
- Aspect-level extraction with null-forcing and evidence phrases
- Two XGBoost regressors (+ aspects-only variants) with SHAP
- Prototype Simulator: specs → bridged aspect estimates → viability % + top risks/strengths
- Category Explorer: profile view of any category (averages, pain points, strengths)
- LLM benchmark study across ≥3 providers

**Out of scope (v1):**
- Live scraping of Amazon/Flipkart at runtime; real sales data; user accounts/auth; payment; non-English reviews; fake-review *classification* (robustness heuristics only); mobile app; more categories

### 5. Functional Requirements

**FR1 — Prototype Simulator**
- FR1.1 User selects category (determines physical vs app routing)
- FR1.2 User enters specs via structured form (price required; category-specific fields e.g. battery, build material / has_ads, monetization) plus free-text description
- FR1.3 System returns within 15s: viability % (full model), aspect-driven viability % (aspects-only model), bridged aspect scores with per-aspect reasoning, top 3 risks and top 3 strengths from SHAP
- FR1.4 Every result displays the disclaimer: proxy-based estimate, not a sales forecast

**FR2 — Category Explorer**
- FR2.1 For any of the 10 categories: price stats, average aspect scores with mention rates, top pain points and strengths with real evidence phrases, success-score distribution
- FR2.2 Aspect "white-space" view: aspects with low mention rates (potential unmet/undiscussed needs)

**FR3 — Existing Product Analyzer**
- FR3.1 Select any product in the training set; view its aspect profile vs category average and its success score components

**FR4 — Transparency**
- FR4.1 Every prediction shows model version + n_products behind the category
- FR4.2 Benchmark table and training metrics accessible from an "About the model" page

### 6. Non-Functional Requirements
| NFR | Requirement |
|---|---|
| Performance | Prediction end-to-end < 15s (one LLM call + model inference) |
| Cost | ₹0 infrastructure: free LLM tiers, Supabase free tier, Streamlit Community Cloud |
| Reproducibility | Fixed seeds; feature manifests; one-command training |
| Explainability | No score shown without its SHAP decomposition |
| Honesty | Proxy label, US-data gap, and robustness limits stated in-product, not only in the report |
| Privacy | Reviewer identities hashed; no PII stored |

### 7. Success Metrics (capstone)
- Model: aspects-only CV R² ≥ 0.2 (stretch 0.35); per-category R² reported for all 10
- Extraction: ≥95% JSON-valid rate on primary provider; hand-validation gate passed
- Product: demo completes spec→result across all 10 categories without error
- Academic: benchmark study with ≥3 providers; all four limitation classes documented

### 8. Key Risks to Product Promise
The system estimates *perceived reception relative to category norms*, not revenue. Naming ("Market Viability Assessment"), UI disclaimers, and the aspects-only model reporting exist specifically to keep the promise honest.
