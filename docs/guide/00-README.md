# Project Leadership Guide

**A complete, project-specific learning path for the Hybrid AI Product Success Predictor capstone** — "Launch-Blind Product Viability Estimation from Specifications via LLM Aspect Bridging" (Raj Jagtap, 2026).

This guide exists to make you the person who can confidently explain, defend, and present every part of this project — to teammates, your mentor, external examiners, and judges — without leaning on the paper or the code in the moment. Everything in it is grounded in the actual codebase and the actual numbers produced by this project, not generic ML theory.

## How to use this guide

- **First pass:** read chapters in order, 1 → 12. Each one builds on the last.
- **Before a viva:** go straight to [Chapter 10](10-viva-prep.md) and [Chapter 12](12-final-revision-guide.md).
- **Before a presentation:** [Chapter 1 §1.6](01-project-overview.md#16-the-three-pitches) has 30-second / 2-minute / 5-minute scripts; [Chapter 12 §12.5–12.6](12-final-revision-guide.md) has full 5-minute and 15-minute speaking scripts.
- **If someone doubts a specific number:** every chapter cites the exact `.json` artifact or script that produced it — trace it back and show them.
- **If you forget which file does what:** [Chapter 3](03-project-structure.md) is the map.

## Chapters

| # | Chapter | What it covers |
|---|---|---|
| 1 | [Project Overview](01-project-overview.md) | The problem, why it matters, existing approaches, why this is different, 30s/2min/5min pitches |
| 2 | [Complete System Architecture](02-system-architecture.md) | Every pipeline stage — purpose, inputs, outputs, why it exists, what breaks if removed |
| 3 | [Project Structure](03-project-structure.md) | Every folder and major file — responsibility, dependents |
| 4 | [Data Pipeline](04-data-pipeline.md) | Sources, collection, cleaning, fraud filtering, label formula, feature engineering |
| 5 | [Model Development](05-model-development.md) | Why XGBoost, how it learns, hyperparameters, metrics, alternatives considered |
| 6 | [Supporting Technologies](06-supporting-technologies.md) | Every library/framework/API used — what, why, what if removed |
| 7 | [Design Decisions](07-design-decisions.md) | Every major decision — alternatives, trade-offs, remaining limitations |
| 8 | [Research Paper Mapping](08-research-paper-mapping.md) | How the paper's C1–C5 contributions and every section map to real code |
| 9 | [Project Evaluation](09-project-evaluation.md) | How it was tested, the real numbers, strengths, limitations, future work |
| 10 | [Viva & Presentation Prep](10-viva-prep.md) | Likely questions with confident answers, plus hard follow-ups |
| 11 | [Plain English Guide](11-plain-english-guide.md) | Every major module explained to 4 different audiences |
| 12 | [Final Revision Guide](12-final-revision-guide.md) | Cheat sheet, key concepts, 5-min and 15-min scripts |

## The five numbers you must never blank on

1. **ρ = 0.317**, 95% CI [0.059, 0.543], AUC = 0.743 — the pre-registered holdout result (n=59), the paper's primary evidence.
2. **R² = 0.567** (physical, aspects-only) — the honest model number; R² = 0.893 is the full model and leaks via `avg_rating`.
3. **R² = 0.101** — the app track's failure against a 0.35 acceptance gate, tested across 5 different target definitions (best: 0.231).
4. **74,000+** reviews extracted; **732 physical / 319 app** products after cleaning and fraud-filtering 71 suspect products.
5. **XGBoost beat 5 alternatives** on identical data — R²=0.564, RMSE=11.4, 8× faster than its closest rival (sklearn Gradient Boosting).

Every one of these traces to a real file on disk: `models/benchmarks/holdout_validation.json`, `models/training_report.json`, `models/benchmarks/app_target_experiment.json`, `data/final/manifest.json`, `models/benchmarks/algorithm_comparison.json`.
