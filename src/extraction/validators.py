"""Pydantic validation of LLM output at the Stage B (extraction) and Stage G (bridging) boundaries."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.extraction.extraction_prompt import APP_ASPECT_KEYS, PHYSICAL_ASPECT_KEYS


class AspectScore(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    evidence: str = Field(min_length=2, max_length=120)


class ExtractionResult(BaseModel):
    scores: dict[str, AspectScore | None]
    confidence: float = Field(ge=0.0, le=1.0)
    n_coerced: int = 0  # malformed aspect entries nulled by the lenient repair pass

    @field_validator("scores")
    @classmethod
    def keys_match_schema(cls, v, info):
        expected = set(info.context["expected_aspects"])
        if set(v.keys()) != expected:
            raise ValueError(f"Aspect keys mismatch: got {set(v.keys())}, expected {expected}")
        return v


class BridgingAspectScore(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str = Field(min_length=5, max_length=200)
    grounded: bool = True  # False = spec gave no concrete evidence (v2 prompt only)


class BridgingResult(BaseModel):
    scores: dict[str, BridgingAspectScore]
    confidence: float = Field(ge=0.0, le=1.0)


def _expected_aspects(product_type: str) -> list[str]:
    if product_type == "physical":
        return PHYSICAL_ASPECT_KEYS
    if product_type == "app":
        return APP_ASPECT_KEYS
    raise ValueError(f"Unknown product_type: {product_type!r} (expected 'physical' or 'app')")


def _coerce_payload(payload: dict, expected: list[str]) -> tuple[dict, int]:
    """Lenient repair for weak-model output. Malformed aspect entries become null
    (we never fabricate evidence), missing keys are added as null, extra keys are
    dropped, score/confidence are clamped. Returns (payload, n_coerced)."""
    n = 0
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        return payload, 0  # hopeless shape — let strict validation reject it
    fixed: dict = {}
    for k in expected:
        v = scores.get(k)
        if isinstance(v, dict) and isinstance(v.get("score"), (int, float)) \
                and isinstance(v.get("evidence"), str) and len(v["evidence"].strip()) >= 2:
            score = float(v["score"])
            clamped = max(0.0, min(10.0, score))
            if clamped != score:
                n += 1
            fixed[k] = {"score": clamped, "evidence": v["evidence"].strip()[:120]}
        elif v is None:
            fixed[k] = None
        else:  # bare number, string, missing key, empty evidence...
            fixed[k] = None
            n += 1
    conf = payload.get("confidence", 0.5)
    try:
        conf = max(0.0, min(1.0, float(conf)))
    except (TypeError, ValueError):
        conf, n = 0.5, n + 1
    return {"scores": fixed, "confidence": conf}, n


def validate_extraction(raw_json: str, product_type: str) -> ExtractionResult:
    expected = _expected_aspects(product_type)
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Extraction output is not valid JSON: {exc}") from exc

    coerced, n_coerced = (_coerce_payload(payload, expected)
                          if isinstance(payload, dict) else (payload, 0))
    # a response that was MOSTLY malformed assertions is untrustworthy — reject
    # so the retry chain can route it to a stronger provider
    if n_coerced > 3:
        raise ValueError(f"Extraction output too malformed: {n_coerced} aspect "
                         "entries had to be discarded")
    coerced["n_coerced"] = n_coerced
    try:
        return ExtractionResult.model_validate(coerced, context={"expected_aspects": expected})
    except ValidationError as exc:
        raise ValueError(f"Extraction output failed schema validation: {exc}") from exc


def validate_bridging(raw_json: str, product_type: str) -> BridgingResult:
    expected = set(_expected_aspects(product_type))
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Bridging output is not valid JSON: {exc}") from exc
    try:
        result = BridgingResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Bridging output failed schema validation: {exc}") from exc
    got = set(result.scores.keys())
    if got != expected:
        missing = expected - got
        unexpected = got - expected
        raise ValueError(
            f"Bridging aspect keys mismatch for {product_type}: "
            f"missing {sorted(missing)}, unexpected {sorted(unexpected)} "
            "(bridging must score every aspect — no nulls, no omissions)"
        )
    return result
