"""Full data-collection driver: runs every collection step in the right order.

  python scripts/collect_all.py            # everything (resumable; rerun after any crash)
  python scripts/collect_all.py --skip-amazon / --skip-play / --skip-build

Order matters: all Amazon metadata scans finish BEFORE --finalize (product
selection), and review scans only run after selection. Every step is resumable,
so rerunning this script continues where it left off.

Bandwidth note: the Amazon streams total ~41 GB (Electronics 22.6 + meta 5.2,
Cell_Phones 9.3 + meta 4.0, Appliances 0.9 + meta 0.3). Run on a connection
where that is acceptable; interruptions are fine (checkpointed).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["Appliances", "Cell_Phones_and_Accessories", "Electronics"]


def run(args: list[str], retries: int = 3) -> None:
    cmd = [sys.executable] + args
    for attempt in range(1, retries + 1):
        print(f"\n>>> {' '.join(args)} (attempt {attempt})", flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode == 0:
            return
        time.sleep(30 * attempt)
    sys.exit(f"FAILED after {retries} attempts: {' '.join(args)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-amazon", action="store_true")
    ap.add_argument("--skip-play", action="store_true")
    ap.add_argument("--skip-reddit", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    if not args.skip_play:
        run(["src/data_collection/play_collect.py"], retries=5)

    if not args.skip_amazon:
        for src in SOURCES:
            run(["src/data_collection/amazon_select_products.py", "--source", src])
        run(["src/data_collection/amazon_select_products.py", "--finalize"])
        for src in SOURCES:
            run(["src/data_collection/amazon_collect_reviews.py", "--source", src])

    if not args.skip_reddit:
        # best-effort; 403s are fine (reddit_context may be {})
        subprocess.run([sys.executable, "src/data_collection/reddit_collect.py"], cwd=ROOT)

    if not args.skip_build:
        run(["src/data_collection/clean_and_build.py", "--out", "data/final"])

    print("\nCOLLECTION COMPLETE. Check data/final/validation_report.txt, then follow "
          "OPERATING_MANUAL.md §3 (pilot extraction + hand-validation).")


if __name__ == "__main__":
    main()
