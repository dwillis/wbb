#!/usr/bin/env python3
"""
Fetch coach biography pages listed in a CSV and store their textual content in JSON.

Usage examples
--------------
Fetch every coach listed in the default `coaches.csv` file and write `coach_articles.json`::

    python fetch_coach_bios.py

Test the pipeline quickly by downloading only the first five coaches::

    python fetch_coach_bios.py --demo

The JSON output preserves every column from the CSV and adds a ``text`` field containing
plain-text content extracted with newspaper4k.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from newspaper import Article  # type: ignore[import]
    from newspaper.article import ArticleException  # type: ignore[import]
except ModuleNotFoundError as exc:  # pragma: no cover - executed if dependency missing
    raise RuntimeError(
        "newspaper4k is required. Install it with 'uv add newspaper4k' or 'pip install newspaper4k'."
    ) from exc

logger = logging.getLogger("fetch_coach_bios")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch coach bio pages and serialize text content")
    parser.add_argument(
        "--csv",
        default="coaches.csv",
        help="Path to the input CSV file (default: coaches.csv in the current directory)",
    )
    parser.add_argument(
        "--output",
        default="coach_bios.json",
        help="Path to the output JSON file (default: coach_bios.json)",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        help="Optional list of coach names to fetch. Matching is case-sensitive.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N records after other filters are applied.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Process only five coaches. Useful for a quick validation run. "
            "Applied after any --names filter."
        ),
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle the selected rows before applying limit/demo. Helpful when sampling.",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language hint passed to newspaper4k Article (default: en).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO).",
    )
    return parser.parse_args()


def read_rows(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(row) for row in reader if row.get("url")]
    logger.info("Loaded %d rows from %s", len(rows), csv_path)
    return rows


def filter_rows(rows: List[Dict[str, str]], names: Iterable[str] | None, limit: int | None, demo: bool, shuffle: bool) -> List[Dict[str, str]]:
    filtered = rows

    if names:
        names_set = set(names)
        filtered = [row for row in filtered if row.get("name") in names_set]
        logger.info("Filtered to %d rows matching provided names", len(filtered))
        if not filtered:
            logger.warning("No rows matched the provided names. Nothing to do.")
            return []

    if shuffle:
        random.shuffle(filtered)

    if demo:
        filtered = filtered[:5]
        logger.info("Demo mode active: restricted to %d rows", len(filtered))
    elif limit is not None:
        filtered = filtered[:limit]
        logger.info("Limit applied: restricted to %d rows", len(filtered))

    return filtered


def fetch_article(row: Dict[str, str], language: str) -> Dict[str, Any]:
    url = row.get("url")
    if not url:
        raise ValueError("Row is missing 'url' value")

    logger.debug("Fetching %s", url)
    article = Article(url, language=language, fetch_images=False)

    try:
        article.download()
        article.parse()
    except ArticleException as exc:
        raise RuntimeError(f"Failed to download or parse article at {url}: {exc}") from exc

    result: Dict[str, Any] = dict(row)
    result["text"] = article.text

    return result

def process_rows(rows: Iterable[Dict[str, str]], language: str) -> List[Dict[str, Any]]:
    processed: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        try:
            processed_row = fetch_article(row, language)
            processed.append(processed_row)
            logger.info("%d/%d - Fetched %s", idx, len(rows), row.get("name"))
        except Exception as exc:  # noqa: BLE001 - log any failure and continue
            logger.error("%d/%d - Failed for %s (%s)", idx, len(rows), row.get("name"), exc)
        finally:
            time.sleep(0.1)
    return processed


def write_json(data: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d records to %s", len(data), output_path)


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    csv_path = Path(args.csv)
    output_path = Path(args.output)

    try:
        rows = read_rows(csv_path)
    except Exception as exc:
        logger.error("Failed to read CSV: %s", exc)
        return 1

    rows = filter_rows(rows, args.names, args.limit, args.demo, args.shuffle)
    if not rows:
        logger.warning("No rows selected for processing. Exiting.")
        return 0

    results = process_rows(rows, args.language)

    if not results:
        logger.warning("No bios were successfully fetched.")
    write_json(results, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
