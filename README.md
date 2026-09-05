---
title: Market Success Viability Predictor
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Hybrid AI Product Success Predictor — ML Track

A market-intelligence platform that mines real consumer reviews at the aspect level (build quality, value, stability, ad experience, etc.) using LLM extraction, learns which aspect patterns drive market success per category using XGBoost trained on real products, and lets a founder describe an unlaunched product's specs to receive an explainable Market Viability Assessment grounded in real category data.

## Setup

```bash
pip install -r requirements.txt
cp config/llm_providers.yaml.template config/llm_providers.yaml   # then fill in real keys
cp .env.template .env                                             # then fill in real values
```

## Execution Order

```bash
python src/loading/load_final.py                          # verify contract
python src/extraction/batch_extractor.py --type physical --limit 30
python src/extraction/review_extraction_sample.py         # HAND-VALIDATE, then:
python src/extraction/batch_extractor.py --type physical  # full batch (days, resumable)
python src/extraction/batch_extractor.py --type app
python src/extraction/batch_extractor.py --benchmark      # 100-review model comparison
python src/training/run_training.py                       # C→D→E, both models, report
python src/prediction/category_profiler.py
streamlit run src/app/app.py
```
