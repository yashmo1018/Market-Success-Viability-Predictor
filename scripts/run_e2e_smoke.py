"""End-to-end smoke test: synthetic data -> Stages A-G -> prediction, in a sandbox.

All pipeline paths are relative, so running each stage with cwd=<sandbox> keeps
real data/final/, data/extracted/ and models/ untouched.

Usage: python scripts/run_e2e_smoke.py [--sandbox sandbox_e2e] [--keep]
Exit code 0 = the full pipeline works end to end.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> None:
    print(f"\n>>> ({cwd.name}) {' '.join(cmd)}")
    result = subprocess.run([sys.executable] + cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"SMOKE FAILED at: {' '.join(cmd)} (exit {result.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", default="sandbox_e2e")
    ap.add_argument("--keep", action="store_true", help="keep the sandbox afterwards")
    args = ap.parse_args()

    sandbox = ROOT / args.sandbox
    if sandbox.exists():
        shutil.rmtree(sandbox)
    (sandbox / "data").mkdir(parents=True)

    # 1. synthetic data straight into sandbox/data/final
    run([str(ROOT / "scripts/make_synthetic_data.py"),
         "--out", str(sandbox / "data/final")], cwd=ROOT)

    # 2. Stage A contract check
    run([str(ROOT / "src/loading/load_final.py")], cwd=sandbox)

    # 3. Stage B extraction (mock provider), physical then app; test resume by
    #    running physical twice with a limit first
    run([str(ROOT / "src/extraction/batch_extractor.py"),
         "--type", "physical", "--limit", "50", "--mock"], cwd=sandbox)
    run([str(ROOT / "src/extraction/batch_extractor.py"),
         "--type", "physical", "--mock"], cwd=sandbox)
    run([str(ROOT / "src/extraction/batch_extractor.py"),
         "--type", "app", "--mock"], cwd=sandbox)

    # 3b. hand-validation viewer must run (output is eyeballed in real runs)
    run([str(ROOT / "src/extraction/review_extraction_sample.py"), "--n", "3"],
        cwd=sandbox)

    # 3c. benchmark mode (single provider: mock)
    run([str(ROOT / "src/extraction/batch_extractor.py"),
         "--type", "physical", "--benchmark", "--mock"], cwd=sandbox)

    # 4. Stages C -> D -> E (the single training command)
    run([str(ROOT / "src/training/run_training.py")], cwd=sandbox)

    # 5. Stage F profiles (mock LLM for reddit summary)
    run([str(ROOT / "src/prediction/category_profiler.py"), "--mock"], cwd=sandbox)

    # 6. Stage G prediction (mock bridging)
    run([str(ROOT / "src/prediction/predictor.py"),
         "--category", "wireless_headphones", "--mock",
         "--specs", json.dumps({"name": "AcousticX Pro", "price": 79.0,
                                "description": "ANC over-ear, 40h battery, aluminum frame"})],
        cwd=sandbox)
    run([str(ROOT / "src/prediction/predictor.py"),
         "--category", "finance_apps", "--mock",
         "--specs", json.dumps({"name": "BudgetBee", "price": 0.0,
                                "description": "free budgeting app, bank sync, no ads"})],
        cwd=sandbox)

    # 7. verify all expected artifacts exist
    expected = [
        "data/extracted/aspect_scores.jsonl", "data/extracted/labels.json",
        "data/extracted/features_physical.parquet", "data/extracted/features_app.parquet",
        "data/extracted/category_profiles.json",
        "models/xgb_physical.json", "models/xgb_app.json",
        "models/xgb_physical_aspects_only.json", "models/xgb_app_aspects_only.json",
        "models/xgb_physical_features.json", "models/xgb_app_features.json",
        "models/shap_summary_physical.png", "models/shap_summary_app.png",
        "models/training_report.json", "models/benchmarks/benchmark_results.json",
    ]
    missing = [p for p in expected if not (sandbox / p).exists()]
    if missing:
        sys.exit(f"SMOKE FAILED: missing artifacts {missing}")

    print("\n" + "=" * 60)
    print("E2E SMOKE PASSED — every stage ran and produced its artifacts.")
    print("=" * 60)
    if not args.keep:
        shutil.rmtree(sandbox, ignore_errors=True)
        print(f"(sandbox {sandbox} removed; use --keep to inspect artifacts)")


if __name__ == "__main__":
    main()
