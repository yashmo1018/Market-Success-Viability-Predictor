"""Stage G (part 2): prediction service — bridging scores -> XGBoost -> SHAP explanation.

predict(user_specs, category) returns the single dict the Streamlit app renders.
Input vectors are built by iterating the on-disk feature manifests — never a
hardcoded column list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extraction.extraction_prompt import APP_ASPECT_KEYS, PHYSICAL_ASPECT_KEYS
from src.prediction.bridging_layer import bridge_aspects

MODELS_DIR = Path("models")
PROFILES_PATH = Path("data/extracted/category_profiles.json")
FEATURES_DIR = Path("data/extracted")

PHYSICAL_CATEGORIES = {"wireless_headphones", "bluetooth_speakers", "ice_makers",
                       "smartwatches", "power_banks"}
APP_CATEGORIES: set[str] = set()  # apps removed from the system


class Predictor:
    def __init__(self, use_mock_llm: bool = False):
        self.use_mock_llm = use_mock_llm
        with open(PROFILES_PATH, encoding="utf-8") as f:
            self.profiles = json.load(f)
        self._models: dict[str, xgb.XGBRegressor] = {}
        self._manifests: dict[str, list[str]] = {}
        # category dtype must match training: derive orderings from the parquets
        self._category_dtypes: dict[str, pd.CategoricalDtype] = {}
        for ptype in ("physical",):  # apps removed
            df = pd.read_parquet(FEATURES_DIR / f"features_{ptype}.parquet",
                                 columns=["category"])
            self._category_dtypes[ptype] = df["category"].dtype

    # -- artifact loading ---------------------------------------------------

    def _manifest(self, name: str) -> list[str]:
        if name not in self._manifests:
            with open(MODELS_DIR / f"{name}_features.json", encoding="utf-8") as f:
                self._manifests[name] = json.load(f)
        return self._manifests[name]

    def _model(self, name: str) -> xgb.XGBRegressor:
        if name not in self._models:
            m = xgb.XGBRegressor(enable_categorical=True)
            m.load_model(MODELS_DIR / f"{name}.json")
            self._models[name] = m
        return self._models[name]

    # -- feature vector construction -----------------------------------------

    def _build_row(self, manifest: list[str], bridged: dict[str, float],
                   user_specs: dict, profile: dict, category: str,
                   product_type: str) -> pd.DataFrame:
        values: dict[str, object] = {}
        for col in manifest:  # iterate the manifest — the only source of truth
            if col == "category":
                values[col] = category
            elif col in bridged:
                values[col] = bridged[col]
            elif col.endswith("_mention_rate"):
                aspect = col[: -len("_mention_rate")]
                values[col] = profile["avg_mention_rates"].get(aspect, np.nan)
            elif col == "price":
                values[col] = float(user_specs.get("price", profile["price"]["median"]))
            elif col == "avg_rating":
                values[col] = profile["median_avg_rating"]
            elif col == "rating_count_log":
                values[col] = profile["median_rating_count_log"]
            elif col == "review_velocity":
                values[col] = profile["median_review_velocity"]
            elif col == "install_count_log":
                values[col] = profile["median_install_count_log"]
            elif col == "days_since_update":
                values[col] = profile["median_days_since_update"]
            else:
                values[col] = np.nan
        row = pd.DataFrame([values], columns=manifest)
        row["category"] = row["category"].astype(self._category_dtypes[product_type])
        return row

    # -- SHAP explanation -----------------------------------------------------

    def _shap_top(self, model: xgb.XGBRegressor, row: pd.DataFrame,
                  bridged_reasoning: dict[str, str], k: int = 3) -> tuple[list, list]:
        import shap

        X = row.copy()
        X["category"] = X["category"].cat.codes
        explainer = shap.TreeExplainer(model)
        vals = explainer.shap_values(X)[0]
        shap_by_feature = dict(zip(row.columns, vals))

        # Aggregate SHAP to the ASPECT level: each aspect's total contribution is
        # its score feature + its mention_rate feature. Keep ONLY real aspects
        # (the bridged ones) so non-actionable metadata (category, price,
        # rating_count, velocity, installs) never surfaces as a "risk/strength".
        # The sign is the model's effect on predicted viability (+ raises, - lowers),
        # which can diverge from whether the aspect itself is "good" — that's a real
        # learned relationship, surfaced honestly under direction-based labels.
        aspect_impact: dict[str, float] = {}
        for aspect in bridged_reasoning:
            aspect_impact[aspect] = (
                float(shap_by_feature.get(aspect, 0.0))
                + float(shap_by_feature.get(f"{aspect}_mention_rate", 0.0))
            )
        ordered = sorted(aspect_impact.items(), key=lambda t: t[1])

        def _fmt(aspect: str, impact: float) -> dict:
            return {"feature": aspect, "impact": round(float(impact), 2),
                    "reasoning": bridged_reasoning.get(aspect, "")}

        risks = [_fmt(a, v) for a, v in ordered if v < 0][:k]
        strengths = [_fmt(a, v) for a, v in sorted(ordered, key=lambda t: -t[1])
                     if v > 0][:k]
        return risks, strengths

    # -- public API -------------------------------------------------------------

    def _resolve_type(self, category: str) -> str:
        if category in PHYSICAL_CATEGORIES:
            return "physical"
        if category in APP_CATEGORIES:
            return "app"
        raise ValueError(f"Unknown category {category!r}")

    def predict_from_bridged(self, bridged: dict, category: str,
                             user_specs: dict, confidence: float = 1.0,
                             reasoning: dict | None = None) -> dict:
        """Deterministic prediction from a supplied aspect-score dict (no LLM).
        Used for stress-testing the model layer with controlled inputs."""
        product_type = self._resolve_type(category)
        profile = self.profiles[category]
        reasoning = reasoning or {}
        full_name, aspects_name = f"xgb_{product_type}", f"xgb_{product_type}_aspects_only"
        row_full = self._build_row(self._manifest(full_name), bridged, user_specs,
                                   profile, category, product_type)
        row_aspects = self._build_row(self._manifest(aspects_name), bridged, user_specs,
                                      profile, category, product_type)
        pred_full = float(self._model(full_name).predict(row_full)[0])
        pred_aspects = float(self._model(aspects_name).predict(row_aspects)[0])
        risks, strengths = self._shap_top(self._model(aspects_name), row_aspects, reasoning)
        return {
            "viability_pct": round(float(np.clip(pred_aspects, 0, 100)), 1),
            "full_model_pct": round(float(np.clip(pred_full, 0, 100)), 1),
            "confidence": confidence, "bridged_scores": bridged,
            "top_risks": risks, "top_strengths": strengths, "category": category,
            "success_threshold_p75": profile["success_score"]["p75_threshold"],
            "category_mean_success": profile["success_score"]["mean"],
        }

    # -- honesty layer: measured validity, percentile positioning, gaps ---------

    def _validity(self) -> dict:
        path = MODELS_DIR / "bridging_validity.json"
        if not hasattr(self, "_validity_cache"):
            self._validity_cache = (json.loads(path.read_text(encoding="utf-8"))["aspects"]
                                    if path.exists() else {})
        return self._validity_cache

    def _retro_percentile(self, viability: float) -> float | None:
        """Rank the prediction among specs-only predictions for 90 REAL products
        (retro validation set). Council-approved: rank map only, no fitted params."""
        path = MODELS_DIR / "benchmarks" / "retro_bridged_v2.jsonl"  # production prompt = v2
        if not hasattr(self, "_retro_viab"):
            if not path.exists():
                self._retro_viab = None
            else:
                self._retro_viab = sorted(
                    json.loads(l)["viability"]
                    for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
        if not self._retro_viab:
            return None
        v = self._retro_viab
        return round(100 * sum(1 for x in v if x < viability) / len(v), 1)

    def _market_gaps(self, bridged: dict, profile: dict) -> list[dict]:
        """Category pain points the new design does NOT convincingly solve."""
        gaps = []
        for a in profile.get("pain_points", {}).get("aspects", []):
            cat_avg = profile["avg_aspect_scores"].get(a)
            score = bridged.get(a)
            if cat_avg is None or score is None:
                continue
            if score <= cat_avg + 1.0:  # not clearly better than the market's sore spot
                gaps.append({
                    "aspect": a, "category_avg": round(cat_avg, 2),
                    "your_estimate": round(score, 2),
                    "sample_complaints": profile["pain_points"]["evidence"].get(a, [])[:3],
                })
        return gaps

    def predict(self, user_specs: dict, category: str) -> dict:
        product_type = self._resolve_type(category)
        profile = self.profiles.get(category)
        if profile is None:
            raise ValueError(f"No profile for category {category!r} — run Stage F first.")

        bridging = bridge_aspects(user_specs, category, profile, product_type,
                                  use_mock=self.use_mock_llm)
        bridged = {a: s.score for a, s in bridging.scores.items()}
        reasoning = {a: s.reasoning for a, s in bridging.scores.items()}
        grounded = {a: s.grounded for a, s in bridging.scores.items()}

        full_name = f"xgb_{product_type}"
        aspects_name = f"xgb_{product_type}_aspects_only"
        row_full = self._build_row(self._manifest(full_name), bridged, user_specs,
                                   profile, category, product_type)
        row_aspects = self._build_row(self._manifest(aspects_name), bridged, user_specs,
                                      profile, category, product_type)

        pred_full = float(self._model(full_name).predict(row_full)[0])
        pred_aspects = float(self._model(aspects_name).predict(row_aspects)[0])
        # SHAP from aspects-only model: risks/strengths name design levers
        # (build_quality, durability...) not un-actionable popularity metadata
        # (review_velocity, rating_count) that a pre-launch product can't change.
        risks, strengths = self._shap_top(self._model(aspects_name), row_aspects, reasoning)

        with open(MODELS_DIR / "training_report.json", encoding="utf-8") as f:
            model_version = json.load(f).get("data_hash", "unknown")

        validity = self._validity()
        n_ungrounded = sum(1 for g in grounded.values() if not g)
        n_aspects = max(len(bridged), 1)
        grounded_frac = (n_aspects - n_ungrounded) / n_aspects
        # Grounding-adjusted confidence: the LLM's raw self-confidence is scaled by
        # how many aspects were actually backed by evidence in the spec. A vague or
        # nonsense spec (few grounded aspects) can no longer report high confidence,
        # even though the LLM fills every aspect from category-average priors.
        adj_confidence = round(bridging.confidence * grounded_frac, 2)
        return {
            "price": float(user_specs.get("price", 0.0)),  # input price, for the positioning chart
            "viability_pct": round(np.clip(pred_aspects, 0, 100), 1),
            "full_model_pct": round(np.clip(pred_full, 0, 100), 1),
            "retro_percentile": self._retro_percentile(float(pred_aspects)),
            "confidence": adj_confidence,
            "llm_confidence": bridging.confidence,  # raw LLM self-report (pre-grounding)
            "grounded_frac": round(grounded_frac, 2),
            "bridged_scores": {a: {"score": s.score, "reasoning": s.reasoning,
                                   "grounded": s.grounded,
                                   "trust": validity.get(a, {}).get("badge", "UNMEASURED")}
                               for a, s in bridging.scores.items()},
            "top_risks": risks,
            "top_strengths": strengths,
            "market_gaps": self._market_gaps(bridged, profile),
            "n_ungrounded": n_ungrounded,
            "abstain": n_ungrounded >= len(bridged) // 2,  # half the profile is guesswork
            "category": category,
            "category_products": profile.get("category_products", []),
            "success_threshold_p75": profile["success_score"]["p75_threshold"],
            "category_mean_success": profile["success_score"]["mean"],
            "model_version": model_version,
        }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Stage G prediction smoke test")
    ap.add_argument("--category", required=True)
    ap.add_argument("--specs", required=True, help='JSON, e.g. {"price": 49.9, "description": "..."}')
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    result = Predictor(use_mock_llm=args.mock).predict(json.loads(args.specs), args.category)
    print(json.dumps(result, indent=2))
