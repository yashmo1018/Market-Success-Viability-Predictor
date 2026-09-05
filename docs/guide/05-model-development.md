# Chapter 5 — Model Development

## 5.1 Why XGBoost was chosen — not assumed

This is the single most defensible claim you can make in a viva: **the algorithm was not picked first and justified after.** Six algorithms were benchmarked on the *identical* aspects-only feature matrix, same 5-fold cross-validation, same seed (42), same 732 physical products, and XGBoost won on the primary metric before any of its other advantages were even considered.

| Algorithm | R² (primary) | RMSE | Training time |
|---|---|---|---|
| **XGBoost** | **0.564** | **11.4** | **0.29 s** |
| Gradient Boosting (sklearn) | 0.549 | 11.6 | 2.43 s (8× slower) |
| Random Forest | 0.532 | 11.8 | 0.70 s |
| MLP (neural network) | 0.490 | 12.3 | 0.78 s |
| SVR (RBF kernel) | 0.421 | 13.1 | 0.01 s |
| Ridge Regression | 0.368 | 13.7 | 0.00 s |

Full classification-derived metrics (accuracy, precision, recall, specificity, F1, AUC-ROC, MCC — explained in §5.6) are in `models/benchmarks/algorithm_comparison.json` and Table I of the paper.

**Honest caveat, and know this before anyone asks:** sklearn's Gradient Boosting narrowly *beats* XGBoost on the derived classification metrics (F1 = 0.934 vs 0.917, MCC = 0.870 vs 0.838). The paper does not hide this. It argues, correctly, that (a) regression is the actual task — the model predicts a continuous success score, not a category — so R²/RMSE are the primary metrics and XGBoost wins those outright; (b) the classification gap is within cross-validation fold noise (the two models' per-fold accuracy ranges overlap almost completely: XGBoost 0.88–0.97 vs GB 0.92–0.98); and (c) Gradient Boosting costs 8× the training time and cannot handle the aspect data's structural missingness natively.

## 5.2 How it learns

XGBoost is a **gradient-boosted tree ensemble.** In plain English: it builds many small decision trees, one after another, where each new tree's only job is to correct the errors the trees before it made. It doesn't build one big tree that tries to get everything right at once — it builds hundreds of small, weak trees that each fix a little bit of what's still wrong, and adds their corrections together.

Concretely, the model here builds 600 such trees (each at most 5 levels deep), and each new tree is fit to the *residual error* of the ensemble so far, scaled down by a learning rate of 0.05 so no single tree can overcorrect. Cross-validation with early stopping picks the actual number of trees used (in the physical-products aspects-only model, the best iteration was found well before 600, avoiding overfitting).

## 5.3 How predictions are generated

At prediction time, a row of features (aspect means, mention rates, price, rating, category, etc.) is passed down every one of the ~600 trees. Each tree outputs a small adjustment; all adjustments are summed to produce the final predicted success score (0–100). For a **new, unlaunched product**, that row doesn't come from real reviews — it comes from the bridging layer's LLM-estimated aspect profile (see [Chapter 2, Stage G](02-system-architecture.md#29-stage-g--bridging--prediction)).

## 5.4 Important hyperparameters

| Hyperparameter | Value | What it controls, in plain English |
|---|---|---|
| `n_estimators` | 600 | How many correction-trees to build (upper bound; early stopping can use fewer) |
| `learning_rate` | 0.05 | How large a correction each tree is allowed to make — small values need more trees but generalize better |
| `max_depth` | 5 | How many yes/no questions deep each tree can go — limits how complex a single tree's logic can get, which fights overfitting |
| `min_child_weight` | 3 | Refuses to split a tree branch unless it covers enough data — another overfitting guard |
| `subsample` / `colsample_bytree` | 0.8 / 0.8 | Each tree sees only 80% of the rows and 80% of the columns, at random — this is the same idea as Random Forest's randomness, injected into boosting to reduce overfitting |
| `enable_categorical` | true | Lets the `category` column be used directly as a category, with no manual one-hot encoding |
| `tree_method` | `hist` | A faster, histogram-based way of finding tree splits — this is a big part of why XGBoost trains 8× faster than sklearn's Gradient Boosting here |
| `early_stopping_rounds` | 50 | Stop adding trees if validation performance hasn't improved in 50 rounds |
| `random_state` | 42 | Fixes randomness so results are reproducible |

## 5.5 Training process

5-fold cross-validation: the 732 physical products are split into 5 groups; the model trains on 4 and validates on the 5th, five times, rotating which group is held out. This produces 5 independent R²/RMSE/MAE estimates, which are then averaged — a much more trustworthy number than training once on all the data and reporting how well it fits itself. **Per-category R²** is also reported separately (headphones, speakers, phones, watches, power banks, kitchen appliances), specifically to catch the failure mode where a model looks good overall but is actually only good at one category. After cross-validation, a final model is trained on all the data, using the best iteration count found during CV.

## 5.6 Validation process and evaluation metrics

Two variants are trained and evaluated **separately**, and this split is the paper's most important modeling decision:

- **Full model** — uses all features, including price, average rating, and rating count. Reaches **R² = 0.893** on physical products. But `avg_rating` alone correlates with the target at r ≈ 0.56, because it's literally 35% of how the target was constructed. This isn't a discovery — it's the model partially "cheating" by seeing a piece of its own answer. The paper explicitly discloses this as an upper bound on fit, not evidence of insight.
- **Aspects-only model** — metadata stripped, only LLM-derived aspect features remain. Reaches **R² = 0.567** on physical products, and **R² = 0.101 on apps** (a FAIL against the pre-registered 0.35 acceptance gate). This is the honest number, and it's the variant behind every claim in the paper.

Metrics used, and what each one means in plain English:

| Metric | Meaning |
|---|---|
| **R²** | What fraction of the variation in success scores the model explains — the primary metric, since this is a regression task |
| **RMSE / MAE** | Average prediction error, in the same units as the score (0–100) |
| **Accuracy** *(derived)* | Of all top-vs-bottom quintile predictions, what fraction were correct |
| **Precision** *(derived)* | Of everything the model called a "hit," what fraction really were hits |
| **Recall / Sensitivity** *(derived)* | Of everything that really was a hit, what fraction the model caught |
| **Specificity** *(derived)* | Same idea as recall, but for flops — of real flops, what fraction were correctly identified |
| **F1** *(derived)* | The balance point between precision and recall |
| **AUC-ROC** *(derived)* | How well the model ranks products, across every possible cutoff — not just one threshold |
| **MCC** *(derived)* | A single number that accounts for all four confusion-matrix outcomes at once; a good summary metric when hits and flops are roughly balanced |

The "(derived)" metrics only exist because the continuous success score was **binarized** into top-quintile ("hit") vs. bottom-quintile ("flop") after the fact, purely to let those standard classification metrics be reported for completeness — the model itself never does classification.

## 5.7 Strengths

- Best R² and RMSE of any algorithm tested, on the exact task the model is actually asked to do (regression)
- Handles the aspect data's structural missingness natively — no imputation, no injected noise
- Trains 8× faster than its closest competitor, which matters for a 5-fold-CV development loop iterated many times
- SHAP `TreeExplainer` gives *exact* (not approximate) explanations in polynomial time, which is what powers every risk/strength explanation the app shows a user
- Native categorical support for the `category` column, keeping structure a tree learner can exploit instead of exploding it into one-hot columns

## 5.8 Weaknesses

- R² = 0.567 (aspects-only, physical) means roughly 43% of the variance in success is still unexplained — a real, disclosed limitation, not a flaw hidden from the reader
- Complete failure on the app track (R² = 0.101) — covered honestly as a negative finding, not smoothed over
- Like any gradient-boosted tree model, it can't extrapolate outside the range of prices/categories it was trained on
- Six hyperparameters were fixed by convention/prior experience rather than exhaustively tuned per category — a reasonable trade-off for a capstone timeline, worth naming if asked

## 5.9 Alternatives considered, and why they were rejected

| Alternative | Why not chosen |
|---|---|
| **Random Forest** | Solid (R² = 0.532) but consistently behind XGBoost on every regression metric, and no meaningful advantage to offset that |
| **sklearn Gradient Boosting** | Nearly matches XGBoost's regression score (0.549 vs 0.564) and even edges ahead on derived classification metrics, but costs 8× the training time and lacks native missing-value handling — a real cost against a narrow, fold-noise-sized benefit |
| **MLP (neural network)** | Falls behind (R² = 0.490); this matches a broader, well-documented pattern in the literature where tree ensembles beat deep learning on small-to-medium tabular data, which is exactly this dataset's shape (732 rows, ~30 columns) |
| **SVR (RBF kernel)** | Falls further behind (R² = 0.421); kernel SHAP explanations on an SVR are also approximate and much slower, which matters because SHAP explanations are a user-facing feature of the app |
| **Ridge Regression** | Weakest of all six (R² = 0.368); the large gap down from the tree ensembles is itself evidence that the aspect-to-success relationship is meaningfully **nonlinear** — a purely linear model can't capture it |

## 5.10 Why this approach was ultimately selected

Three properties of *this specific problem* — not accuracy alone — favor XGBoost:

1. **Native missing-value handling.** An aspect a review never mentions is structurally missing, by design (see the null-forcing prompt, [Chapter 7](07-design-decisions.md)). XGBoost learns which direction to send missing values during a split; Ridge and SVR would need an imputation strategy that injects fabricated information into a system whose entire premise is "don't fabricate."
2. **Native categorical support.** The `category` feature is used directly via `enable_categorical`, with no one-hot encoding needed.
3. **SHAP compatibility.** `TreeExplainer` gives exact Shapley values in polynomial time for tree ensembles — this is what powers the per-prediction "top risks / top strengths" explanations a founder actually sees in the app. The same explanation on an MLP or SVR would be approximate and dramatically slower.

Accuracy, efficiency, and explainability all pointed the same direction, and XGBoost was the only algorithm that won on all three simultaneously.
