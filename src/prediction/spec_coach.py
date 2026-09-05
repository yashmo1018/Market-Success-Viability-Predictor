"""Spec-writing coach — helps the user write a spec the bridging step can ground.

One LLM call reviews the user's draft description against the aspect schema and
the category's real pain points, then returns:
  - per-aspect coverage (covered / vague / missing)
  - the few questions whose answers would sharpen the prediction most
  - an improved rewrite that uses ONLY facts the user stated, with
    [ADD: ...] placeholders for missing decisions (never invented specs)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extraction.extraction_prompt import aspects_for
from src.extraction.llm_provider import ProviderPool, strip_json

COACH_PROMPT = """You are a product-spec coach. A founder wrote a draft spec for a new {category} product. Your job: help them write a spec that fully describes their design decisions — WITHOUT inventing anything they did not say.

ASPECTS a good spec should give evidence for:
{aspect_definitions}

WHAT REAL CONSUMERS IN THIS CATEGORY COMPLAIN ABOUT MOST (from {n_products} real products):
{pain_points}

FOUNDER'S DRAFT SPEC (price: {price}):
\"\"\"{description}\"\"\"

TASK:
1. For each aspect, classify the draft's coverage: "covered" (concrete evidence given), "vague" (mentioned but not specific), or "missing" (nothing to go on).
2. Write at most 5 questions, ordered by impact, that would fill the biggest gaps — prioritize aspects that are BOTH missing AND top category pain points.
3. Rewrite the spec: keep every fact the founder stated (sharpened wording is fine), and insert [ADD: <what to specify>] placeholders where decisions are missing. NEVER invent a material, number, or feature the founder did not state.

Respond ONLY with JSON:
{{"coverage": {{"aspect_name": "covered|vague|missing", ...}}, "questions": ["...", ...], "improved_spec": "...", "summary": "one sentence on overall spec quality"}}
"""

VALID_COVERAGE = {"covered", "vague", "missing"}


def coach_spec(user_specs: dict, category: str, profile: dict, product_type: str,
               use_mock: bool = False, max_retries: int = 1) -> dict:
    aspects = aspects_for(product_type)
    if use_mock:
        return _mock_coach(user_specs, aspects)
    prompt = COACH_PROMPT.format(
        category=category,
        aspect_definitions="\n".join(f"- {a}: {d}" for a, d in aspects.items()),
        n_products=profile["n_products"],
        pain_points={a: profile["pain_points"]["evidence"].get(a, [])[:3]
                     for a in profile["pain_points"]["aspects"]},
        price=user_specs.get("price", "unspecified"),
        description=user_specs.get("description", ""),
    )
    pool = ProviderPool()
    last_error = ""
    for attempt in range(max_retries + 1):
        p = prompt if attempt == 0 else (
            prompt + f"\n\nYour previous response was invalid: {last_error}\n"
            "Return ONLY the corrected JSON object.")
        raw, _ = pool.generate(p, provider=None, json_mode=True)
        try:
            return _validate(strip_json(raw), set(aspects))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            last_error = str(exc)[:300]
    raise ValueError(f"Spec coach failed after {max_retries + 1} attempts: {last_error}")


def _validate(raw: str | dict, expected_aspects: set[str]) -> dict:
    data = raw if isinstance(raw, dict) else json.loads(raw)
    cov = data["coverage"]
    if not expected_aspects.issubset(cov):
        raise ValueError(f"coverage missing aspects: {expected_aspects - set(cov)}")
    for a, v in cov.items():
        if v not in VALID_COVERAGE:
            raise ValueError(f"bad coverage value {v!r} for {a}")
    if not isinstance(data.get("improved_spec"), str) or len(data["improved_spec"]) < 20:
        raise ValueError("improved_spec missing or too short")
    data.setdefault("questions", [])
    data.setdefault("summary", "")
    return data


def _mock_coach(user_specs: dict, aspects: dict[str, str]) -> dict:
    """Offline demo: keyword presence check only."""
    text = user_specs.get("description", "").lower()
    keywords = {
        "value_for_money": ["price", "worth", "cheap", "premium", "below"],
        "utility": ["sound", "function", "feature", "quality", "core"],
        "ease_of_use": ["easy", "setup", "control", "comfort", "intuitive"],
        "reliability": ["reliable", "consistent", "connection", "sync"],
        "design_appeal": ["design", "look", "aesthetic", "sleek", "foldable"],
        "after_sales": ["warranty", "support", "service", "replacement"],
        "build_quality": ["aluminum", "metal", "material", "build", "plastic"],
        "durability": ["durable", "last", "rugged", "resistant"],
        "repairability": ["repair", "replaceable", "spare", "modular"],
        "performance": ["fast", "speed", "smooth", "battery"],
        "stability": ["stable", "crash", "bug"],
        "ad_experience": ["ad", "ads", "ad-free"],
        "update_support": ["update", "roadmap"],
        "privacy_trust": ["privacy", "data", "permission"],
    }
    coverage = {a: ("covered" if any(k in text for k in keywords.get(a, [])) else "missing")
                for a in aspects}
    missing = [a for a, c in coverage.items() if c == "missing"]
    return {"coverage": coverage,
            "questions": [f"What is your plan for {a.replace('_', ' ')}?" for a in missing[:5]],
            "improved_spec": user_specs.get("description", "") +
                             "".join(f"\n[ADD: {a.replace('_', ' ')}]" for a in missing[:5]),
            "summary": f"mock review: {len(missing)} aspects lack evidence"}
