"""Autonomous overnight chain: Reddit data -> all stages -> A/B result.

Runs the full pipeline unattended and writes a final verdict. Every step is
idempotent and retried; safe to re-run if interrupted. Progress -> stdout AND
models/benchmarks/overnight_chain.log.

Steps:
  1. Ensure all 10 Reddit categories are collected (runs the sweep if needed)
  2. Install data/staging/reddit_context.json -> data/final (with backup)
  3. Stage F: rebuild category profiles with consumer_priorities (Groq fallback)
  4. E2E smoke test
  5. A/B: Reddit priorities vs none (fair, same-provider, self-contained)

Run: python scripts/overnight_chain.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data/staging/reddit_context.json"
FINAL = ROOT / "data/final/reddit_context.json"
LOG = ROOT / "models/benchmarks/overnight_chain.log"
CATEGORIES = ["wireless_headphones", "bluetooth_speakers", "smartphones", "smartwatches",
              "power_banks", "kitchen_appliances", "finance_apps", "health_fitness_apps",
              "productivity_apps", "education_apps"]


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], tries: int = 1, backoff: int = 60) -> bool:
    for attempt in range(tries):
        log(f"$ {' '.join(cmd)}  (attempt {attempt + 1}/{tries})")
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-8:])
        log(tail)
        if r.returncode == 0:
            return True
        if attempt < tries - 1:
            log(f"  failed, retrying in {backoff}s...")
            time.sleep(backoff)
    return False


def step1_collect() -> None:
    raw = ROOT / "data/staging/reddit_raw"
    for _ in range(30):  # sweep is resumable; loop until all 10 caches exist
        have = {p.stem for p in raw.glob("*.jsonl")} if raw.exists() else set()
        missing = [c for c in CATEGORIES if c not in have]
        if not missing:
            log(f"Step 1 OK: all {len(CATEGORIES)} categories collected")
            return
        log(f"Step 1: {len(have)}/10 collected, missing {missing[:3]}... running sweep")
        run([sys.executable, "scripts/collect_reddit.py", "--all"])
    raise RuntimeError("Step 1 failed: sweep did not complete all categories")


def step2_install() -> None:
    ctx = json.loads(STAGING.read_text(encoding="utf-8"))
    counts = {k: len(v) for k, v in ctx.items()}
    log(f"Step 2: staging has {sum(counts.values())} comments across {len(counts)} cats: {counts}")
    if FINAL.exists():
        backup = FINAL.with_suffix(".json.bak")
        shutil.copy(FINAL, backup)
        log(f"  backed up existing final -> {backup.name}")
    shutil.copy(STAGING, FINAL)
    log(f"Step 2 OK: installed -> {FINAL}")


def step3_profiles() -> None:
    prof_path = ROOT / "data/extracted/category_profiles.json"
    # idempotent: skip the (LLM-heavy) rebuild if priorities are already present
    if prof_path.exists():
        cur = json.loads(prof_path.read_text(encoding="utf-8"))
        have = [c for c, p in cur.items() if p.get("consumer_priorities")]
        if len(have) == len(cur) and cur:
            log(f"Step 3 OK (cached): {len(have)}/{len(cur)} profiles already carry priorities")
            return
    # --force: Stage F otherwise skips rebuild if profiles exist, keeping the
    # pre-Reddit profiles and silently dropping consumer_priorities.
    ok = run([sys.executable, "src/prediction/category_profiler.py", "--force"],
             tries=3, backoff=120)
    if not ok:
        raise RuntimeError("Step 3 failed: category_profiler")
    profiles = json.loads(prof_path.read_text(encoding="utf-8"))
    withp = [c for c, p in profiles.items() if p.get("consumer_priorities")]
    if not withp:
        raise RuntimeError("Step 3 failed: 0 profiles carry priorities after rebuild")
    log(f"Step 3 OK: {len(withp)}/{len(profiles)} profiles carry consumer_priorities")


def step4_smoke() -> None:
    if not run([sys.executable, "scripts/run_e2e_smoke.py"], tries=2, backoff=30):
        raise RuntimeError("Step 4 failed: E2E smoke")
    log("Step 4 OK: E2E SMOKE PASSED")


def step5_ab() -> None:
    # generous retries: bridging leans on LLM providers with daily quotas
    if not run([sys.executable, "scripts/ab_reddit_priorities.py"], tries=8, backoff=1800):
        raise RuntimeError("Step 5 failed: A/B did not complete")
    rep = json.loads((ROOT / "models/benchmarks/ab_reddit_priorities.json").read_text(encoding="utf-8"))
    log(f"Step 5 OK: {rep['verdict']} | delta_rho={rep['delta_rho']:+.3f} "
        f"delta_auc={rep['delta_auc']:+.3f} (n={rep['n']})")


def main() -> None:
    log("=" * 60)
    log("OVERNIGHT CHAIN START")
    steps = [("collect", step1_collect), ("install", step2_install),
             ("profiles", step3_profiles), ("smoke", step4_smoke), ("ab", step5_ab)]
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - record and stop the chain
            log(f"CHAIN HALTED at {name}: {exc}")
            sys.exit(1)
    log("OVERNIGHT CHAIN COMPLETE — project exercised end-to-end with Reddit data")
    log("=" * 60)


if __name__ == "__main__":
    main()
