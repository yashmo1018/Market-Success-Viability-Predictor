"""Splice ice_makers into data/final, drop smartphones+kitchen_appliances, remove apps.

Surgical rebuild that PRESERVES existing keeper products/reviews (and therefore
their ~75k aspect extractions) untouched. Only:
  - removes categories {smartphones, kitchen_appliances} from the physical set
  - appends the isolated ice_makers build (data/staging/icemaker_*.json)
  - empties the app set (products_app.json / reviews_app.json -> [])
  - recomputes manifest.json and re-runs Stage A validation

Run build_icemakers.py first.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "data/final"
STAGING = ROOT / "data/staging"
DROP_CATEGORIES = {"smartphones", "kitchen_appliances"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    prods = load(FINAL / "products_physical.json")
    revs = load(FINAL / "reviews_physical.json")
    ice_prods = load(STAGING / "icemaker_products.json")
    ice_revs = load(STAGING / "icemaker_reviews.json")

    keep_prods = [p for p in prods if p["category"] not in DROP_CATEGORIES]
    keep_puids = {p["product_uid"] for p in keep_prods}
    keep_revs = [r for r in revs if r["product_uid"] in keep_puids]

    # guard: ice_maker product_uids must not collide with an existing keeper
    ice_puids = {p["product_uid"] for p in ice_prods}
    collide = ice_puids & keep_puids
    if collide:
        print(f"WARNING: {len(collide)} ice_maker uids collide with keepers; "
              f"keeping ice_maker version (dropping keeper dupes).")
        keep_prods = [p for p in keep_prods if p["product_uid"] not in collide]
        keep_revs = [r for r in keep_revs if r["product_uid"] not in collide]
        keep_puids = {p["product_uid"] for p in keep_prods}

    new_prods = keep_prods + ice_prods
    new_revs = keep_revs + ice_revs

    (FINAL / "products_physical.json").write_text(
        json.dumps(new_prods, ensure_ascii=False), encoding="utf-8")
    (FINAL / "reviews_physical.json").write_text(
        json.dumps(new_revs, ensure_ascii=False), encoding="utf-8")
    # remove apps entirely
    (FINAL / "products_app.json").write_text("[]", encoding="utf-8")
    (FINAL / "reviews_app.json").write_text("[]", encoding="utf-8")

    # recompute manifest
    cat_stats: dict[str, dict] = defaultdict(lambda: {"products": 0, "reviews": 0})
    for p in new_prods:
        cat_stats[p["category"]]["products"] += 1
    puid_cat = {p["product_uid"]: p["category"] for p in new_prods}
    for r in new_revs:
        cat_stats[puid_cat[r["product_uid"]]]["reviews"] += 1

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pipeline_version": "data-track-1.1-physical-only",
        "categories": dict(cat_stats),
        "totals": {"products_physical": len(new_prods), "products_app": 0,
                   "reviews_physical": len(new_revs), "reviews_app": 0},
        "reddit_available": (FINAL / "reddit_context.json").exists(),
        "validation_passed": True,
        "validation_report": str(FINAL / "validation_report.txt"),
    }
    (FINAL / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Per-category after rebuild:")
    for c, s in sorted(cat_stats.items()):
        print(f"  {c:<22} {s['products']:>4} products  {s['reviews']:>7} reviews")
    print(f"TOTAL: {len(new_prods)} products, {len(new_revs)} reviews (apps removed)")

    # Stage A validation via the ML loader (subprocess; its sys.exit won't kill us)
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'" + str(ROOT) + "'); "
         "from src.loading.load_final import load_contract, print_summary; "
         "print_summary(load_contract(r'" + str(FINAL.resolve()) + "'))"],
        capture_output=True, text=True)
    if result.returncode != 0:
        manifest["validation_passed"] = False
        (FINAL / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("STAGE A VALIDATION FAILED — manifest marked validation_passed=false")
        print(result.stdout or result.stderr)
    else:
        print("Stage A validation: PASSED")
        print(result.stdout[-500:] if result.stdout else "")


if __name__ == "__main__":
    main()
