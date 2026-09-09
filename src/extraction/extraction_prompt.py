"""Frozen aspect schema and prompt templates for Stage B extraction and Stage G bridging.

The aspect dicts and prompt wording are FROZEN per the ML pipeline spec §3.1 —
changing them invalidates trained models.
"""

from __future__ import annotations

PHYSICAL_ASPECTS = {
    "value_for_money": "Is the product worth its price? Price-to-benefit perception.",
    "utility": "Does the product perform its core function well? (e.g., sound quality for headphones)",
    "ease_of_use": "Setup, controls, comfort, day-to-day usability.",
    "reliability": "Consistent performance over time; no malfunctions or connectivity drops.",
    "design_appeal": "Aesthetics, look and feel, form factor.",
    "after_sales": "Customer service, warranty, replacement experience.",
    "build_quality": "Materials, construction solidity, fit and finish.",
    "durability": "Longevity; resistance to wear, drops, breakage over time.",
    "repairability": "Ease of repair, spare parts, serviceability.",
}

APP_ASPECTS = {
    "value_for_money": "Is the app worth its price / are IAPs and subscription fair?",
    "utility": "Does the app accomplish its core purpose well?",
    "ease_of_use": "UI clarity, navigation, learning curve.",
    "reliability": "Works consistently; sync, data integrity, uptime.",
    "design_appeal": "Visual design, UI aesthetics.",
    "after_sales": "Developer support responsiveness, help resources.",
    "performance": "Speed, smoothness, load times, battery/memory efficiency.",
    "stability": "Crash-free, bug-free operation.",
    "ad_experience": "Ad intrusiveness. HIGH score = ads are minimal/non-intrusive. LOW = ad-riddled.",
    "update_support": "Active development, bug fixes, feature updates.",
    "privacy_trust": "Permissions, data handling, user trust.",
}

PHYSICAL_ASPECT_KEYS = list(PHYSICAL_ASPECTS.keys())  # length 9
APP_ASPECT_KEYS = list(APP_ASPECTS.keys())            # length 11
SHARED_ASPECT_KEYS = [k for k in PHYSICAL_ASPECT_KEYS if k in APP_ASPECT_KEYS]  # length 6

EXTRACTION_PROMPT = """You are an expert product review analyst. Extract aspect-based sentiment scores from this review.

REVIEW (product: {product_name}, rated {rating}/5 by the reviewer):
\"\"\"{review_text}\"\"\"

ASPECTS TO SCORE:
{aspect_definitions}

STRICT RULES:
1. Score an aspect ONLY if the review explicitly discusses it. Score 0.0-10.0 (0=terrible, 5=mixed/neutral, 10=excellent).
2. If the review does NOT mention an aspect, you MUST return null for it. NEVER guess or infer a score for an unmentioned aspect. A review that only discusses sound quality gives you NO information about durability — return null.
3. For every non-null score, include a short verbatim evidence phrase (max 10 words) copied from the review.
4. The reviewer's star rating is context, not an aspect score. Do not convert it into scores.
5. Respond with ONLY the JSON object below. No markdown, no explanation.

OUTPUT FORMAT:
{{"scores": {{"aspect_name": {{"score": 7.5, "evidence": "verbatim phrase"}} OR null, ...}}, "confidence": 0.0-1.0}}
"""

BRIDGING_PROMPT = """You are a market analyst estimating how consumers would perceive a NEW product, based on real category intelligence.

NEW PRODUCT SPECS:
{user_specs}

CATEGORY INTELLIGENCE ({category}, built from {n_products} real products):
- Price: median {median_price}, p25 {p25}, p75 {p75}
- Average consumer aspect scores: {avg_scores}
- Top pain points: {pain_points}
- Top strengths: {strengths}
- Consumer priorities: {priorities}

TASK: Estimate the aspect scores (0-10) consumers would give this product AFTER using it, judged against this category's real expectations. For each aspect, reason from the specs relative to category norms (e.g., price 20% below median with premium features → high value_for_money).

RULES:
1. Every aspect MUST get a numeric score (no nulls here — you are estimating, and the category context is your grounding).
2. Include one-sentence reasoning per aspect referencing a spec and a category fact.
3. Respond ONLY with JSON: {{"scores": {{"aspect": {{"score": X.X, "reasoning": "..."}}}}, "confidence": 0.0-1.0}}
"""


BRIDGING_PROMPT_V2 = """You are a SKEPTICAL market analyst estimating how consumers would perceive a NEW product after months of real use. Marketing copy is adversarially optimistic — flops and hits are marketed with identical enthusiasm. Your value comes from seeing through it.

NEW PRODUCT SPECS:
{user_specs}

CATEGORY INTELLIGENCE ({category}, built from {n_products} real products):
- Price: median {median_price}, p25 {p25}, p75 {p75}
- Average consumer aspect scores (this is what the MEDIAN product actually achieves): {avg_scores}
- Top pain points (where real products in this category FAIL): {pain_points}
- Top strengths: {strengths}
- Consumer priorities: {priorities}

TASK: Estimate the aspect scores (0-10) consumers would give this product AFTER using it, judged against this category's real expectations.

SKEPTIC RULES:
1. IGNORE marketing adjectives ("premium", "amazing", "crystal-clear", "ultimate"). Score ONLY from verifiable, concrete facts: numbers, materials, dimensions, standards (IP rating, Bluetooth version), warranty terms, certifications. "Powerful bass" is noise; "50mm drivers" is evidence.
2. ABSENCE RULE: if the spec gives NO concrete evidence for an aspect, that silence is itself a signal — competent teams state their strengths. Score that aspect 0.5-1.5 points BELOW the category average, and set "grounded": false for it.
3. ANCHOR DISCIPLINE: the category average above is what the median real product achieves — and most new products land near it. Any score more than 2 points above the category average requires a specific, concrete spec fact in the reasoning. When in doubt, score closer to the average.
4. Pain-point check: for each of the category's top pain points, ask whether the spec concretely addresses it. If not, do not score that aspect above the category average.
5. Every aspect MUST get a numeric score. Include one-sentence reasoning per aspect referencing a spec fact (or noting its absence) and a category fact.
6. Respond ONLY with JSON: {{"scores": {{"aspect": {{"score": X.X, "reasoning": "...", "grounded": true/false}}}}, "confidence": 0.0-1.0}}
"""


def aspects_for(product_type: str) -> dict[str, str]:
    if product_type == "physical":
        return PHYSICAL_ASPECTS
    if product_type == "app":
        return APP_ASPECTS
    raise ValueError(f"Unknown product_type: {product_type!r} (expected 'physical' or 'app')")


def build_extraction_prompt(review_text: str, product_name: str, rating: float,
                            product_type: str) -> str:
    aspects = aspects_for(product_type)
    aspect_definitions = "\n".join(f"- {name}: {definition}" for name, definition in aspects.items())
    return EXTRACTION_PROMPT.format(
        product_name=product_name,
        rating=rating,
        review_text=review_text,
        aspect_definitions=aspect_definitions,
    )


def build_bridging_prompt(user_specs: dict, category: str, profile: dict,
                          version: int = 1) -> str:
    template = BRIDGING_PROMPT_V2 if version == 2 else BRIDGING_PROMPT
    return template.format(
        user_specs=user_specs,
        category=category,
        n_products=profile["n_products"],
        median_price=profile["median_price"],
        p25=profile["p25"],
        p75=profile["p75"],
        avg_scores=profile["avg_scores"],
        pain_points=profile["pain_points"],
        strengths=profile["strengths"],
        priorities=profile["priorities"],
    )
