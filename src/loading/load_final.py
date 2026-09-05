"""Stage A: load and verify the data/final/ contract.

Reads manifest.json first and refuses to proceed unless validation_passed is
true, then loads all contract files into dataclasses and re-checks the
invariants the ML pipeline depends on. Exits naming the exact file and field
on any violation.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PHYSICAL_CATEGORIES = {
    "wireless_headphones",
    "bluetooth_speakers",
    "smartwatches",
    "power_banks",
    "ice_makers",
}
APP_CATEGORIES = {
    "finance_apps",
    "health_fitness_apps",
    "productivity_apps",
    "education_apps",
}

TS_MIN = 946684800   # 2000-01-01
TS_MAX = 1893456000  # 2030-01-01

PHYSICAL_PRODUCT_FIELDS = [
    "product_uid", "source", "source_id", "product_type", "category", "name",
    "brand", "price", "currency", "avg_rating", "rating_count",
    "first_review_ts", "latest_review_ts", "specs", "extra",
]
APP_PRODUCT_FIELDS = PHYSICAL_PRODUCT_FIELDS + [
    "monetization", "install_count", "last_updated_ts", "released_ts",
]
REVIEW_FIELDS = [
    "review_uid", "product_uid", "source", "rating", "title", "text",
    "verified", "helpful_votes", "review_ts", "reviewer_hash", "app_version",
    "word_count",
]


@dataclass
class PhysicalProduct:
    product_uid: str
    source: str
    source_id: str
    product_type: str
    category: str
    name: str
    brand: str
    price: float
    currency: str
    avg_rating: float
    rating_count: int
    first_review_ts: int
    latest_review_ts: int
    specs: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppProduct:
    product_uid: str
    source: str
    source_id: str
    product_type: str
    category: str
    name: str
    brand: str
    price: float
    currency: str
    monetization: str
    avg_rating: float
    rating_count: int
    install_count: int
    last_updated_ts: int
    released_ts: int
    first_review_ts: int
    latest_review_ts: int
    specs: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Review:
    review_uid: str
    product_uid: str
    source: str
    rating: float
    title: str
    text: str
    verified: bool
    helpful_votes: int
    review_ts: int
    reviewer_hash: str
    app_version: str | None
    word_count: int


@dataclass
class ContractData:
    products_physical: list[PhysicalProduct]
    products_app: list[AppProduct]
    reviews_physical: list[Review]
    reviews_app: list[Review]
    reddit_context: dict[str, Any]
    manifest: dict[str, Any]


def _fail(message: str) -> None:
    print(message)
    sys.exit(1)


def _read_json(path: Path) -> Any:
    if not path.exists():
        _fail(f"CONTRACT ERROR: {path.name} not found in {path.parent}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        _fail(f"CONTRACT ERROR: {path.name} is not valid JSON ({exc})")


def _check_required_fields(objs: list[dict], required: list[str], filename: str) -> None:
    for i, obj in enumerate(objs):
        for f_name in required:
            if f_name not in obj:
                uid = obj.get("product_uid") or obj.get("review_uid") or f"index {i}"
                _fail(f"CONTRACT ERROR: {filename}: object {uid} missing required field '{f_name}'")


def _check_unique_uids(objs: list[dict], filename: str) -> None:
    seen: set[str] = set()
    for obj in objs:
        uid = obj["product_uid"]
        if uid in seen:
            _fail(f"CONTRACT ERROR: {filename}: duplicate product_uid '{uid}'")
        seen.add(uid)


def _check_referential(reviews: list[dict], product_uids: set[str],
                       reviews_file: str, products_file: str) -> None:
    for review in reviews:
        if review["product_uid"] not in product_uids:
            _fail(
                f"CONTRACT ERROR: {reviews_file}: review {review['review_uid']} "
                f"references product_uid '{review['product_uid']}' not present in {products_file}"
            )


def _check_categories(objs: list[dict], allowed: set[str], filename: str) -> None:
    for obj in objs:
        if obj["category"] not in allowed:
            _fail(
                f"CONTRACT ERROR: {filename}: product {obj['product_uid']} has "
                f"category '{obj['category']}' not in allowed set {sorted(allowed)}"
            )


def _check_timestamps(objs: list[dict], ts_fields: list[str], filename: str, uid_key: str) -> None:
    for obj in objs:
        for f_name in ts_fields:
            ts = obj[f_name]
            if not isinstance(ts, (int, float)) or not (TS_MIN <= ts <= TS_MAX):
                _fail(
                    f"CONTRACT ERROR: {filename}: {obj[uid_key]} field '{f_name}' = {ts!r} "
                    f"outside sanity bounds [{TS_MIN}, {TS_MAX}] (Unix seconds expected)"
                )


def _check_ratings(objs: list[dict], rating_key: str, filename: str, uid_key: str) -> None:
    for obj in objs:
        rating = obj[rating_key]
        if not isinstance(rating, (int, float)) or not (1.0 <= rating <= 5.0):
            _fail(
                f"CONTRACT ERROR: {filename}: {obj[uid_key]} field '{rating_key}' = {rating!r} "
                f"outside [1.0, 5.0]"
            )


def _check_install_counts(objs: list[dict], filename: str) -> None:
    for obj in objs:
        count = obj["install_count"]
        if not isinstance(count, int) or count <= 0:
            _fail(
                f"CONTRACT ERROR: {filename}: product {obj['product_uid']} field "
                f"'install_count' = {count!r} must be an int > 0"
            )


def load_contract(data_dir: str = "data/final") -> ContractData:
    base = Path(data_dir)

    manifest = _read_json(base / "manifest.json")
    if manifest.get("validation_passed") is not True:
        _fail(
            "VALIDATION FAILED: manifest.json reports validation_passed=false. "
            "Fix data/final/ before proceeding."
        )

    raw_phys = _read_json(base / "products_physical.json")
    raw_apps = _read_json(base / "products_app.json")
    raw_rev_phys = _read_json(base / "reviews_physical.json")
    raw_rev_apps = _read_json(base / "reviews_app.json")
    reddit_context = _read_json(base / "reddit_context.json")

    _check_required_fields(raw_phys, PHYSICAL_PRODUCT_FIELDS, "products_physical.json")
    _check_required_fields(raw_apps, APP_PRODUCT_FIELDS, "products_app.json")
    _check_required_fields(raw_rev_phys, REVIEW_FIELDS, "reviews_physical.json")
    _check_required_fields(raw_rev_apps, REVIEW_FIELDS, "reviews_app.json")

    _check_unique_uids(raw_phys, "products_physical.json")
    _check_unique_uids(raw_apps, "products_app.json")

    _check_referential(raw_rev_phys, {p["product_uid"] for p in raw_phys},
                       "reviews_physical.json", "products_physical.json")
    _check_referential(raw_rev_apps, {p["product_uid"] for p in raw_apps},
                       "reviews_app.json", "products_app.json")

    _check_categories(raw_phys, PHYSICAL_CATEGORIES, "products_physical.json")
    _check_categories(raw_apps, APP_CATEGORIES, "products_app.json")

    _check_timestamps(raw_phys, ["first_review_ts", "latest_review_ts"],
                      "products_physical.json", "product_uid")
    _check_timestamps(raw_apps, ["first_review_ts", "latest_review_ts",
                                 "last_updated_ts", "released_ts"],
                      "products_app.json", "product_uid")
    _check_timestamps(raw_rev_phys, ["review_ts"], "reviews_physical.json", "review_uid")
    _check_timestamps(raw_rev_apps, ["review_ts"], "reviews_app.json", "review_uid")

    _check_ratings(raw_phys, "avg_rating", "products_physical.json", "product_uid")
    _check_ratings(raw_apps, "avg_rating", "products_app.json", "product_uid")
    _check_ratings(raw_rev_phys, "rating", "reviews_physical.json", "review_uid")
    _check_ratings(raw_rev_apps, "rating", "reviews_app.json", "review_uid")

    _check_install_counts(raw_apps, "products_app.json")

    return ContractData(
        products_physical=[PhysicalProduct(**p) for p in raw_phys],
        products_app=[AppProduct(**p) for p in raw_apps],
        reviews_physical=[Review(**r) for r in raw_rev_phys],
        reviews_app=[Review(**r) for r in raw_rev_apps],
        reddit_context=reddit_context,
        manifest=manifest,
    )


def print_summary(data: ContractData) -> None:
    phys_cats = {p.category for p in data.products_physical}
    app_cats = {p.category for p in data.products_app}
    reddit = "present" if data.reddit_context else "absent"
    print("CONTRACT VERIFIED")
    print(f"Physical products: {len(data.products_physical)} across {len(phys_cats)} categories")
    print(f"App products: {len(data.products_app)} across {len(app_cats)} categories")
    print(f"Physical reviews: {len(data.reviews_physical)}")
    print(f"App reviews: {len(data.reviews_app)}")
    print(f"Reddit context: {reddit}")
    print("All checks passed.")


if __name__ == "__main__":
    print_summary(load_contract())
