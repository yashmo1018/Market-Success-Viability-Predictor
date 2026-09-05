"""Stage B: batch LLM aspect extraction with crash-safe resume.

CLI:
  python src/extraction/batch_extractor.py --input data/final/reviews_physical.json --type physical
  [--category X] [--limit N] [--benchmark] [--provider mock|gemini_flash|...] [--force]

Every result is appended to data/extracted/aspect_scores.jsonl immediately.
On start, already-extracted review_uids are skipped (resume). Failures after the
full retry chain go to data/extracted/failed_reviews.jsonl and the batch continues.

Retry policy per review: same provider once with the validation error appended ->
switch to next provider -> log failure and continue.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extraction.extraction_prompt import build_extraction_prompt
from src.extraction.llm_provider import ProviderError, ProviderPool, strip_json
from src.extraction.validators import ExtractionResult, validate_extraction

OUT_DIR = Path("data/extracted")
SCORES_PATH = OUT_DIR / "aspect_scores.jsonl"
FAILED_PATH = OUT_DIR / "failed_reviews.jsonl"
BENCHMARK_PATH = Path("models/benchmarks/benchmark_results.json")
BENCHMARK_SEED = 42
BENCHMARK_N = 100


def extract_aspects(review_text: str, product_name: str, rating: float,
                    product_type: str, pool: ProviderPool,
                    provider: str | None = None) -> tuple[ExtractionResult, str]:
    """Single entry point. Returns (result, model_used). Raises on total failure.

    provider=None runs in chain mode: each attempt the pool picks the first
    instantly-available provider (cloud when a key is free, ollama in the gaps).
    Validation failures retry with the error appended, up to 4 attempts.
    """
    prompt = build_extraction_prompt(review_text, product_name, rating, product_type)
    last_error = ""
    for _ in range(6):
        p = prompt if not last_error else (
            prompt + f"\n\nYour previous response was invalid: {last_error}\n"
            "Return ONLY the corrected JSON object."
        )
        raw, used = pool.generate(p, provider=provider)  # ProviderError propagates
        try:
            return validate_extraction(strip_json(raw), product_type), used
        except ValueError as exc:
            last_error = str(exc)[:300]
    raise ProviderError(f"Extraction failed after retries: {last_error}")


def _extract_with_quota_wait(r: dict, product_type: str, pool: ProviderPool,
                             provider: str | None,
                             max_waits: int = 10) -> tuple[ExtractionResult, str]:
    """extract_aspects, but when ALL providers fail because cloud quotas are
    exhausted, sleep until a key frees up instead of failing the review.
    A multi-day batch must pause at the daily caps, not burn the queue."""
    for attempt in range(max_waits):
        try:
            return extract_aspects(r["text"], r["_product_name"], r["rating"],
                                   product_type, pool, provider=provider)
        except ProviderError:
            wake = pool.earliest_available()
            wait = wake - time.time()
            if wait == float("inf") and attempt >= 2:
                raise  # no cloud keys at all and retries didn't help
            # transient turbulence (benched keys, busy ollama, bad JSON streaks):
            # back off until a key frees, minimum 60s, instead of failing the review
            wait = min(max(wait + 5, 30), 3900)
            print(f"  providers unavailable (attempt {attempt+1}); backing off "
                  f"{wait:.0f}s...", flush=True)
            time.sleep(wait)
    raise ProviderError("quota-wait retries exhausted")


def _load_done_uids() -> tuple[set[str], dict[str, int]]:
    """Returns (extracted review_uids, per-product extracted counts)."""
    done: set[str] = set()
    per_product: dict[str, int] = {}
    if SCORES_PATH.exists():
        with open(SCORES_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    done.add(row["review_uid"])
                    per_product[row["product_uid"]] = per_product.get(row["product_uid"], 0) + 1
                except (json.JSONDecodeError, KeyError):
                    continue
    return done, per_product


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()


def _load_reviews(input_path: Path, product_type: str, category: str | None) -> list[dict]:
    with open(input_path, encoding="utf-8") as f:
        reviews = json.load(f)
    products_file = input_path.parent / f"products_{product_type}.json"
    with open(products_file, encoding="utf-8") as f:
        products = {p["product_uid"]: p for p in json.load(f)}
    enriched = []
    for r in reviews:
        prod = products.get(r["product_uid"])
        if prod is None:
            continue
        if category and prod["category"] != category:
            continue
        enriched.append({**r, "_product_name": prod["name"], "_category": prod["category"]})
    return enriched


def run_batch(input_path: Path, product_type: str, category: str | None,
              limit: int | None, provider: str | None, pool: ProviderPool,
              per_product_cap: int = 100, workers: int = 6) -> None:
    reviews = _load_reviews(input_path, product_type, category)
    done, done_per_product = _load_done_uids()

    # Per-product cap (seeded sample) + round-robin interleave across products,
    # so coverage is uniform no matter where a multi-day batch is interrupted.
    rng = random.Random(42)
    by_product: dict[str, list[dict]] = {}
    for r in reviews:
        by_product.setdefault(r["product_uid"], []).append(r)
    queues = []
    for uid, revs in sorted(by_product.items()):
        room = per_product_cap - done_per_product.get(uid, 0)
        if room <= 0:
            continue
        pending = [r for r in revs if r["review_uid"] not in done]
        rng.shuffle(pending)
        queues.append(pending[:room])
    todo = []
    while queues:
        queues = [q for q in queues if q]
        for q in queues:
            if q:
                todo.append(q.pop(0))
    if limit:
        todo = todo[:limit]
    print(f"{len(reviews)} reviews loaded, {len(done)} already extracted, "
          f"{len(todo)} to do (cap {per_product_cap}/product, round-robin, "
          f"{workers} workers).")

    counters = {"ok": 0, "fail": 0, "i": 0}
    io_lock = threading.Lock()
    t_batch = time.time()

    def work(r: dict) -> None:
        t0 = time.time()
        try:
            result, used = _extract_with_quota_wait(r, product_type, pool, provider)
            row = {
                "review_uid": r["review_uid"],
                "product_uid": r["product_uid"],
                "product_type": product_type,
                "model_used": used,
                "scores": {k: (v.model_dump() if v else None)
                           for k, v in result.scores.items()},
                "confidence": result.confidence,
                "n_coerced": result.n_coerced,
                "latency_ms": int((time.time() - t0) * 1000),
                "ts": int(time.time()),
            }
            with io_lock:
                _append_jsonl(SCORES_PATH, row)
                counters["ok"] += 1
        except ProviderError as exc:
            with io_lock:
                _append_jsonl(FAILED_PATH, {
                    "review_uid": r["review_uid"], "product_uid": r["product_uid"],
                    "product_type": product_type, "error": str(exc)[:500],
                    "ts": int(time.time()),
                })
                counters["fail"] += 1
        with io_lock:
            counters["i"] += 1
            i = counters["i"]
        if i % 25 == 0 or i == len(todo):
            rate = i / max(time.time() - t_batch, 1e-9)
            eta_min = (len(todo) - i) / max(rate, 1e-9) / 60
            print(f"  [{i}/{len(todo)}] ok={counters['ok']} fail={counters['fail']} "
                  f"rate={rate:.2f}/s eta={eta_min:.0f}min", flush=True)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, todo))
    print(f"DONE: {counters['ok']} extracted, {counters['fail']} failed "
          f"(see {FAILED_PATH if counters['fail'] else 'no failures'}).")


def run_benchmark(input_path: Path, product_type: str, pool: ProviderPool) -> None:
    """Run the SAME fixed-seed 100 reviews through ALL providers; write agreement stats."""
    reviews = _load_reviews(input_path, product_type, None)
    rng = random.Random(BENCHMARK_SEED)
    sample = rng.sample(reviews, min(BENCHMARK_N, len(reviews)))
    providers = list(pool.providers)
    print(f"Benchmarking providers {providers} on {len(sample)} reviews (seed {BENCHMARK_SEED})")

    per_provider: dict[str, dict] = {}
    all_scores: dict[str, dict[str, dict]] = {p: {} for p in providers}
    for prov in providers:
        valid = 0
        latencies: list[float] = []
        for r in sample:
            t0 = time.time()
            try:
                result, _ = extract_aspects(r["text"], r["_product_name"], r["rating"],
                                            product_type, pool, provider=prov)
                valid += 1
                all_scores[prov][r["review_uid"]] = {
                    k: (v.score if v else None) for k, v in result.scores.items()
                }
            except ProviderError:
                pass
            latencies.append(time.time() - t0)
        per_provider[prov] = {
            "json_validity_rate": round(valid / len(sample), 3),
            "mean_latency_s": round(sum(latencies) / len(latencies), 2),
            "n": len(sample),
        }
        print(f"  {prov}: validity={per_provider[prov]['json_validity_rate']} "
              f"latency={per_provider[prov]['mean_latency_s']}s")

    # pairwise agreement: mean |score diff| on aspects both scored non-null,
    # plus null-agreement rate (both null or both non-null)
    agreement = {}
    for i, a in enumerate(providers):
        for b in providers[i + 1:]:
            diffs, null_agree, total = [], 0, 0
            for uid in set(all_scores[a]) & set(all_scores[b]):
                for k in all_scores[a][uid]:
                    sa, sb = all_scores[a][uid][k], all_scores[b][uid].get(k)
                    total += 1
                    if (sa is None) == (sb is None):
                        null_agree += 1
                    if sa is not None and sb is not None:
                        diffs.append(abs(sa - sb))
            agreement[f"{a}_vs_{b}"] = {
                "mean_abs_score_diff": round(sum(diffs) / len(diffs), 2) if diffs else None,
                "null_agreement_rate": round(null_agree / total, 3) if total else None,
            }

    BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
        json.dump({"seed": BENCHMARK_SEED, "n_reviews": len(sample),
                   "product_type": product_type, "per_provider": per_provider,
                   "pairwise_agreement": agreement, "ts": int(time.time())}, f, indent=2)
    print(f"Benchmark written to {BENCHMARK_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage B batch aspect extraction")
    ap.add_argument("--input", default=None, help="reviews json (default: data/final/reviews_{type}.json)")
    ap.add_argument("--type", required=True, choices=["physical", "app"], dest="product_type")
    ap.add_argument("--category", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--provider", default=None,
                    help="pin one provider (gemini_flash|groq_llama70b|ollama_gemma|mock)")
    ap.add_argument("--mock", action="store_true", help="use the mock provider (no API keys needed)")
    ap.add_argument("--per-product-cap", type=int, default=100,
                    help="max reviews extracted per product (seeded sample)")
    ap.add_argument("--workers", type=int, default=6,
                    help="concurrent extraction workers")
    args = ap.parse_args()

    input_path = Path(args.input) if args.input else Path(f"data/final/reviews_{args.product_type}.json")

    # Stage A gate: refuse to run on unvalidated data
    from src.loading.load_final import load_contract
    load_contract(str(input_path.parent))

    if args.mock or args.provider == "mock":
        pool = ProviderPool(config={}, providers=["mock"])
        provider = "mock"
    else:
        pool = ProviderPool()
        provider = args.provider

    if args.benchmark:
        run_benchmark(input_path, args.product_type, pool)
    else:
        run_batch(input_path, args.product_type, args.category, args.limit, provider, pool,
                  per_product_cap=args.per_product_cap, workers=args.workers)


if __name__ == "__main__":
    main()
