#!/usr/bin/env python3
"""SMF Swarm — Benchmark dataset fetcher.

Pulls resolved binary questions from public forecasting datasets and writes
a canonical JSONL file for the benchmark harness.

Datasets:
  1. Metaculus — /api2/questions/  (status=resolved, type=binary)
  2. FiveThirtyEight MLB Elo — GitHub raw CSV
  3. (GJOpen requires manual CSV export — documented but not auto-fetched)

Output: ~/.cache/smf-swarm/benchmarks/<dataset>.jsonl
Schema per line: {"id", "question_text", "domain", "outcome", "resolved_at", "source", "url"}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


DEFAULT_OUTDIR = os.path.expanduser("~/.cache/smf-swarm/benchmarks")
METACULUS_API = "https://www.metaculus.com/api2/questions/"
FTE_MLB_URLS = [
    "https://raw.githubusercontent.com/fivethirtyeight/data/master/mlb-elo/mlb_elo.csv",
    "https://raw.githubusercontent.com/fivethirtyeight/data/master/mlb-elo/mlb_elo_latest.csv",
    "https://projects.fivethirtyeight.com/mlb-api/mlb_elo.csv",
]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def fetch_metaculus(limit: int = 200) -> Iterator[dict]:
    """Fetch resolved binary questions from Metaculus.
    
    NOTE: As of April 2025, the Metaculus API requires authentication.
    This function will fail with 403 unless a METACULUS_API_TOKEN env var
    is set. Consider using --dummy or exporting a personal API token.
    """
    token = os.environ.get("METACULUS_API_TOKEN", "")
    headers = {
        "Accept": "application/json",
        "User-Agent": "smf-swarm/1.4.1 (research use)",
    }
    if token:
        headers["Authorization"] = f"Token {token}"
    params = {
        "status": "resolved",
        "type": "binary",
        "order_by": "-resolve_time",
        "limit": min(limit, 100),
    }
    remaining = limit
    offset = 0

    while remaining > 0:
        params["offset"] = offset
        try:
            resp = requests.get(METACULUS_API, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [Metaculus] Request failed: {e}")
            break

        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        for q in results:
            outcome = q.get("resolution")
            if outcome not in (0, 1):
                continue

            yield {
                "id": f"metaculus_{q.get('id', 'unknown')}",
                "question_text": q.get("title", ""),
                "domain": "science_technology",
                "outcome": int(outcome),
                "resolved_at": q.get("resolve_time", ""),
                "source": "metaculus",
                "url": q.get("page_url", ""),
            }

        fetched = len(results)
        remaining -= fetched
        offset += fetched
        if fetched < params["limit"]:
            break
        time.sleep(0.5)

    print(f"  [Metaculus] Fetched {offset} questions")


def fetch_fivethirtyeight_mlb(limit: int = 500) -> Iterator[dict]:
    """Fetch MLB Elo game predictions from FiveThirtyEight."""
    text = ""
    for url in FTE_MLB_URLS:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            text = resp.text
            print(f"  [538 MLB] CSV loaded from {url}")
            break
        except requests.RequestException as e:
            print(f"  [538 MLB] Failed to fetch {url}: {e}")
            continue
    if not text:
        print("  [538 MLB] All URL attempts failed.")
        return

    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    count = 0
    for row in rows:
        if count >= limit:
            break

        try:
            home_score = int(row.get("score1", 0))
            away_score = int(row.get("score2", 0))
            home_prob = float(row.get("elo_prob1", 0.5))
        except (ValueError, TypeError):
            continue

        if home_score == away_score:
            continue

        outcome = 1 if home_score > away_score else 0
        date = row.get("date", "")
        season = row.get("season", "")

        yield {
            "id": f"538mlb_{date}_{row.get('team1','')}_{row.get('team2','')}",
            "question_text": (
                f"In the MLB game on {date}, will {row.get('team1', 'home team')} "
                f"beat {row.get('team2', 'away team')}? "
                f"(FiveThirtyEight Elo predicted {home_prob:.3f} home win probability)"
            ),
            "domain": "sports_baseball",
            "outcome": outcome,
            "resolved_at": date,
            "source": "538_mlb",
            "url": "",
            "home_elo_prob": home_prob,
        }
        count += 1

    print(f"  [538 MLB] Fetched {count} games")


def write_jsonl(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records)} records to {path}")


def generate_dummy_dataset(name: str, count: int) -> list[dict]:
    """Generate a synthetic benchmark dataset for testing."""
    topics = [
        ("Will AI surpass human-level general intelligence by 2030?", "technology"),
        ("Will the Federal Reserve raise interest rates this year?", "finance"),
        ("Will a major hurricane make landfall in the US this season?", "climate"),
        ("Will Ethereum exceed $5000 by year end?", "finance"),
        ("Will COVID-19 be declared no longer a pHEIC by WHO?", "health"),
    ]
    import random
    random.seed(42)
    records = []
    now = time.strftime("%Y-%m-%d")
    for i in range(count):
        text, domain = topics[i % len(topics)]
        records.append({
            "id": f"dummy_{name}_{i:04d}",
            "question_text": f"[{i+1}] {text}",
            "domain": domain,
            "outcome": random.choice([0, 1]),
            "resolved_at": now,
            "source": "dummy",
            "url": "",
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="Fetch benchmark datasets for SMF Swarm")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Output directory")
    parser.add_argument("--datasets", default="metaculus,538mlb", help="Comma-separated dataset names")
    parser.add_argument("--limit", type=int, default=200, help="Max records per dataset")
    parser.add_argument("--dummy", action="store_true", help="Generate synthetic dataset for testing (no network calls)")
    args = parser.parse_args()

    ensure_dir(args.outdir)
    datasets = [d.strip().lower() for d in args.datasets.split(",")]

    print(f"Fetching benchmark data → {args.outdir}")
    print(f"Datasets: {datasets} | Limit: {args.limit}\n")

    n_datasets = len(datasets)

    if args.dummy:
        print("[dummy] Generating synthetic dataset for testing...")
        records = generate_dummy_dataset("test", args.limit)
        write_jsonl(os.path.join(args.outdir, "dummy.jsonl"), records)
        print("\nDone.")
        return

    if "metaculus" in datasets:
        print(f"[1/{n_datasets}] Fetching Metaculus resolved binary questions...")
        records = list(fetch_metaculus(limit=args.limit))
        if records:
            write_jsonl(os.path.join(args.outdir, "metaculus.jsonl"), records)
        else:
            print("  No records found — set METACULUS_API_TOKEN env var for authenticated access.")

    if "538mlb" in datasets:
        print(f"[2/{n_datasets}] Fetching FiveThirtyEight MLB Elo forecasts...")
        records = list(fetch_fivethirtyeight_mlb(limit=args.limit))
        if records:
            write_jsonl(os.path.join(args.outdir, "538_mlb.jsonl"), records)
        else:
            print("  No records found.")

    print("\nDone.")


if __name__ == "__main__":
    main()
