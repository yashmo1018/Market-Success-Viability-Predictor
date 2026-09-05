"""Full ABS extraction driver: physical then app, restart-on-crash, resumable.

  python scripts/run_extraction.py

Runs for days; the extractor sleeps at provider daily quotas and resumes
automatically. Safe to kill and rerun at any time.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for ptype in ("physical", "app"):
        attempt = 0
        while True:
            attempt += 1
            print(f"\n>>> extraction {ptype} (attempt {attempt})", flush=True)
            rc = subprocess.run(
                [sys.executable, "src/extraction/batch_extractor.py",
                 "--type", ptype, "--per-product-cap", "100"],
                cwd=ROOT).returncode
            if rc == 0:
                break
            if attempt >= 50:
                sys.exit(f"extraction {ptype} kept failing — investigate")
            time.sleep(60)
    print("\nEXTRACTION COMPLETE for both product types.")
    print("Next: python src/extraction/batch_extractor.py --type physical --benchmark")
    print("Then: python src/training/run_training.py")


if __name__ == "__main__":
    main()
