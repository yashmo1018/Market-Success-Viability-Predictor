"""Extraction daemon: alternates physical/app chunks until both batches finish.

  python scripts/extract_daemon.py [--chunk 500] [--per-product-cap 100]

Why chunks: round-robin product coverage inside batch_extractor means that at ANY
stopping point every product has roughly uniform review coverage; alternating
chunks extends that fairness across the two product types, so Stages C-G can run
on partial extraction while the batch keeps growing. Quota exhaustion pauses
inside the extractor (it sleeps until a key resets) rather than failing reviews.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_chunk(ptype: str, chunk: int, cap: int) -> bool:
    """Returns True when this type is fully extracted. Streams output live so
    long chunks are observable (a captured buffer hides worker backoffs)."""
    import re
    todo_re = re.compile(r"(\d+) to do \(cap ")
    proc = subprocess.Popen(
        [sys.executable, "src/extraction/batch_extractor.py",
         "--type", ptype, "--limit", str(chunk), "--per-product-cap", str(cap),
         "--workers", "14"],  # capture reset-time bursts across 7 cloud pools
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saw_marker = False
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"  [{ptype}] {line}", flush=True)
        m = todo_re.search(line)
        if m and int(m.group(1)) == 0:
            saw_marker = True
    proc.wait()
    if proc.returncode != 0:
        print(f"  [{ptype}] chunk failed (exit {proc.returncode}); backing off 120s")
        time.sleep(120)
        return False
    return saw_marker


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=500)
    ap.add_argument("--per-product-cap", type=int, default=100)
    args = ap.parse_args()

    done = {"physical": False, "app": False}
    cycle = 0
    while not all(done.values()):
        cycle += 1
        print(f"=== cycle {cycle} ({time.strftime('%H:%M')}) ===", flush=True)
        for ptype in ("physical", "app"):
            if not done[ptype]:
                done[ptype] = run_chunk(ptype, args.chunk, args.per_product_cap)
                if done[ptype]:
                    print(f"  [{ptype}] EXTRACTION COMPLETE")
    print("BOTH BATCHES COMPLETE.")


if __name__ == "__main__":
    main()
