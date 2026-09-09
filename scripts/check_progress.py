"""Progress progress check: python scripts/check_progress.py"""

import json
import time
from collections import Counter
from pathlib import Path

TARGET = 74933
rows = [json.loads(l) for l in open("data/extracted/aspect_scores.jsonl", encoding="utf-8")
        if l.strip()]
recent = [r for r in rows if r["ts"] > time.time() - 1800]
rate = len(recent) / 1800 * 86400
print(f"extracted: {len(rows)}/{TARGET} ({len(rows)/TARGET*100:.1f}%)")
print(f"last 30 min: {len(recent)} -> {rate:,.0f}/day"
      + (f"; ~{(TARGET-len(rows))/rate:.1f} days left" if rate else " (daemon idle/paused?)"))
print("mix (recent):", dict(Counter(r["model_used"] for r in recent)))
fails = Path("data/extracted/failed_reviews.jsonl")
n_fail = sum(1 for l in open(fails, encoding="utf-8") if l.strip()) if fails.exists() else 0
print(f"failures total: {n_fail}")
daemon_log = Path("logs/extract_daemon.log")
if daemon_log.exists():
    lines = daemon_log.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    print("daemon log tail:", *lines[-3:], sep="\n  ")
