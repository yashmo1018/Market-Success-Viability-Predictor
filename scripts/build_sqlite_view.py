"""Build capstone.db — a read-only SQLite mirror of the pipeline's file data,
for human browsing with DB Browser / VS Code SQLite extensions.

  python scripts/build_sqlite_view.py     # rebuilds capstone.db from current files

The FILES remain the pipeline's source of truth; this DB is a viewing layer.
Regenerate any time to refresh (e.g. as extraction grows).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path("capstone.db")


def main() -> None:
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""CREATE TABLE products (
        product_uid TEXT PRIMARY KEY, product_type TEXT, category TEXT, name TEXT,
        brand TEXT, price REAL, avg_rating REAL, rating_count INTEGER,
        install_count INTEGER, monetization TEXT)""")
    cur.execute("""CREATE TABLE reviews (
        review_uid TEXT PRIMARY KEY, product_uid TEXT, rating REAL, title TEXT,
        text TEXT, verified INTEGER, helpful_votes INTEGER, review_ts INTEGER,
        word_count INTEGER)""")
    cur.execute("""CREATE TABLE aspect_scores (
        review_uid TEXT, product_uid TEXT, product_type TEXT, model_used TEXT,
        aspect TEXT, score REAL, evidence TEXT, confidence REAL, ts INTEGER)""")

    for fname, ptype in (("products_physical.json", "physical"), ("products_app.json", "app")):
        path = Path("data/final") / fname
        if not path.exists():
            continue
        for p in json.load(open(path, encoding="utf-8")):
            cur.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (p["product_uid"], ptype, p["category"], p["name"], p["brand"],
                         p["price"], p["avg_rating"], p["rating_count"],
                         p.get("install_count"), p.get("monetization")))

    for fname in ("reviews_physical.json", "reviews_app.json"):
        path = Path("data/final") / fname
        if not path.exists():
            continue
        for r in json.load(open(path, encoding="utf-8")):
            cur.execute("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",
                        (r["review_uid"], r["product_uid"], r["rating"], r["title"],
                         r["text"], int(r["verified"]), r["helpful_votes"],
                         r["review_ts"], r["word_count"]))

    scores_path = Path("data/extracted/aspect_scores.jsonl")
    n_rows = 0
    if scores_path.exists():
        with open(scores_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                for aspect, val in row["scores"].items():
                    cur.execute("INSERT INTO aspect_scores VALUES (?,?,?,?,?,?,?,?,?)",
                                (row["review_uid"], row["product_uid"], row["product_type"],
                                 row["model_used"], aspect,
                                 val["score"] if val else None,
                                 val["evidence"] if val else None,
                                 row["confidence"], row["ts"]))
                n_rows += 1

    cur.execute("CREATE INDEX idx_rev_prod ON reviews(product_uid)")
    cur.execute("CREATE INDEX idx_asp_prod ON aspect_scores(product_uid)")
    cur.execute("CREATE INDEX idx_asp_aspect ON aspect_scores(aspect)")
    con.commit()
    n_p = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    n_r = cur.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    n_a = cur.execute("SELECT COUNT(*) FROM aspect_scores").fetchone()[0]
    con.close()
    print(f"capstone.db built: {n_p} products, {n_r} reviews, "
          f"{n_a} aspect-score rows (from {n_rows} extractions)")


if __name__ == "__main__":
    main()
