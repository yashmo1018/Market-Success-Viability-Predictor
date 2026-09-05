"""Stage G (part 1): bridging — estimate aspect scores for a NEW product from
user specs + category intelligence. Uses gemini_flash ONLY (JSON mode), with the
mock provider available for tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extraction.extraction_prompt import build_bridging_prompt
from src.extraction.llm_provider import ProviderPool, strip_json
from src.extraction.validators import BridgingResult, validate_bridging


def profile_to_prompt_fields(profile: dict) -> dict:
    """Adapt a category_profiles.json entry to the BRIDGING_PROMPT placeholders."""
    return {
        "n_products": profile["n_products"],
        "median_price": profile["price"]["median"],
        "p25": profile["price"]["p25"],
        "p75": profile["price"]["p75"],
        "avg_scores": profile["avg_aspect_scores"],
        "pain_points": {a: profile["pain_points"]["evidence"].get(a, [])[:5]
                        for a in profile["pain_points"]["aspects"]},
        "strengths": {a: profile["strengths"]["evidence"].get(a, [])[:5]
                      for a in profile["strengths"]["aspects"]},
        "priorities": profile.get("consumer_priorities") or "not available",
    }


def bridge_aspects(user_specs: dict, category: str, profile: dict,
                   product_type: str, use_mock: bool = False,
                   max_retries: int = 2, prompt_version: int = 2) -> BridgingResult:
    """One LLM call estimating every aspect score for the new product.

    prompt_version=2 (default) is the skeptic prompt: ignores marketing
    adjectives, penalizes absence, anchors to category averages, and labels
    each score grounded/ungrounded. Validated on 90 real products
    (models/benchmarks/) — v1 kept only for comparison runs."""
    prompt = build_bridging_prompt(user_specs, category, profile_to_prompt_fields(profile),
                                   version=prompt_version)
    if use_mock:
        return _mock_bridge(user_specs, profile, product_type)
    # Cascade through the whole fleet (gemini-first per PROVIDER_ORDER), so one
    # prediction never hard-fails just because one pool's daily quota is drained.
    pool = ProviderPool()

    last_error = ""
    for attempt in range(max_retries + 1):
        p = prompt if attempt == 0 else (
            prompt + f"\n\nYour previous response was invalid: {last_error}\n"
            "Return ONLY the corrected JSON object with EVERY aspect scored."
        )
        raw, _ = pool.generate(p, provider=None, json_mode=True)
        try:
            return validate_bridging(strip_json(raw), product_type)
        except ValueError as exc:
            last_error = str(exc)[:300]
    raise ValueError(f"Bridging failed after {max_retries + 1} attempts: {last_error}")


def _mock_bridge(user_specs: dict, profile: dict, product_type: str) -> BridgingResult:
    """Deterministic bridging for tests: category mean nudged by price position."""
    from src.extraction.extraction_prompt import APP_ASPECT_KEYS, PHYSICAL_ASPECT_KEYS

    aspects = PHYSICAL_ASPECT_KEYS if product_type == "physical" else APP_ASPECT_KEYS
    median = profile["price"]["median"] or 1.0
    price = float(user_specs.get("price", median))
    nudge = max(-1.5, min(1.5, (median - price) / max(median, 1.0) * 2.0))
    scores = {}
    for a in aspects:
        base = profile["avg_aspect_scores"].get(a) or 5.0
        val = max(0.0, min(10.0, base + (nudge if a == "value_for_money" else nudge * 0.3)))
        scores[a] = {"score": round(val, 1),
                     "reasoning": f"mock: category mean {base} adjusted for price {price} "
                                  f"vs median {median}"}
    return BridgingResult(scores=scores, confidence=0.5)
