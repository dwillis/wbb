"""Coach biography fetching.

Ports ncaa/coaches/fetch_coach_bios.py (the standalone script) into the wbb
package so `wbb bios` can drive it. Reads coach roster CSVs (columns
team_id,team,name,title,url,season), downloads each coach bio page with
newspaper4k, and writes the rows (original columns + extracted `text`) to a
JSON file.

The standalone script in ncaa/coaches/ is untouched and still works; it
defaults to cwd-relative paths, while this module resolves defaults against
REPO_ROOT. `--skip-existing` merges into an existing output JSON instead of
overwriting it (the original script overwrites with only the current run).
"""

import csv
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from wbb.config import REPO_ROOT

logger = logging.getLogger(__name__)

COACHES_DIR = REPO_ROOT / "ncaa" / "coaches"
DEFAULT_CSV = COACHES_DIR / "coaches.csv"
FETCH_DELAY_SECS = 0.1  # original script's politeness pause between fetches


def _get_article_class():
    try:
        from newspaper import Article  # type: ignore[import]
        from newspaper.article import ArticleException  # type: ignore[import]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "newspaper4k is required. Install it with 'uv add newspaper4k'."
        ) from exc
    return Article, ArticleException


def read_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Rows from a coach CSV, keeping only rows that have a url (script behavior)."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = [dict(row) for row in csv.DictReader(f) if row.get("url")]
    logger.info("Loaded %d rows from %s", len(rows), csv_path)
    return rows


def filter_rows(rows: List[Dict[str, str]], names: Optional[Iterable[str]] = None,
                team_ids: Optional[Iterable[int]] = None, season: Optional[str] = None,
                limit: Optional[int] = None, shuffle: bool = False,
                demo: bool = False) -> List[Dict[str, str]]:
    """Apply the script's filters (names, limit/demo, shuffle) plus CLI filters
    (team_ids, season) that the standalone script lacks."""
    filtered = rows

    if names:
        names_set = set(names)
        filtered = [row for row in filtered if row.get("name") in names_set]
        if not filtered:
            logger.warning("No rows matched the provided names. Nothing to do.")
    if team_ids:
        ids_set = {str(t) for t in team_ids}
        filtered = [row for row in filtered if row.get("team_id") in ids_set]
    if season:
        filtered = [row for row in filtered if row.get("season") == season]

    if shuffle:
        random.shuffle(filtered)

    if demo:
        filtered = filtered[:5]
        logger.info("Demo mode active: restricted to %d rows", len(filtered))
    elif limit is not None:
        filtered = filtered[:limit]

    return filtered


def existing_urls(data: List[Dict[str, Any]]) -> Set[str]:
    """URLs already fetched (non-empty text) in an existing output JSON."""
    return {row["url"] for row in data if row.get("url") and row.get("text")}


def load_existing(output_path: Path) -> List[Dict[str, Any]]:
    """Records from an existing output JSON (for --skip-existing), else []."""
    if not output_path.exists():
        return []
    try:
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (ValueError, OSError) as exc:
        logger.warning("Could not read existing %s (%s); starting fresh", output_path, exc)
        return []


def fetch_article(row: Dict[str, str], language: str = "en") -> Dict[str, Any]:
    """Download and parse one bio page, returning the row plus extracted text."""
    Article, ArticleException = _get_article_class()
    url = row.get("url")
    if not url:
        raise ValueError("Row is missing 'url' value")
    article = Article(url, language=language, fetch_images=False)
    try:
        article.download()
        article.parse()
    except ArticleException as exc:
        raise RuntimeError(f"Failed to download or parse article at {url}: {exc}") from exc
    result: Dict[str, Any] = dict(row)
    result["text"] = article.text
    return result


def fetch_bios(rows: List[Dict[str, str]], language: str = "en",
               skip_urls: Optional[Set[str]] = None,
               on_row: Optional[Callable[[int, int, str, str, Optional[str]], None]] = None
               ) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch bio text for each row.

    skip_urls: URLs to skip (already fetched; each counts as 'skipped').
    on_row: callback(index, total, name, status, error) with status in
    'fetched' | 'failed' | 'skipped'.

    Returns (successful rows with text, count of failures).
    """
    results: List[Dict[str, Any]] = []
    failed = 0
    for idx, row in enumerate(rows, start=1):
        name = row.get("name", "")
        if skip_urls and row.get("url") in skip_urls:
            if on_row is not None:
                on_row(idx, len(rows), name, 'skipped', None)
            continue
        try:
            results.append(fetch_article(row, language))
            if on_row is not None:
                on_row(idx, len(rows), name, 'fetched', None)
        except Exception as exc:  # noqa: BLE001 - log any failure and continue
            failed += 1
            logger.debug("bio fetch failed for %s (%s): %s", name, row.get("url"), exc)
            if on_row is not None:
                on_row(idx, len(rows), name, 'failed', str(exc))
        finally:
            time.sleep(FETCH_DELAY_SECS)
    return results, failed


def merge_results(existing: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge a run's records into an existing list, by url (new text wins)."""
    by_url = {row.get("url"): row for row in existing if row.get("url")}
    for row in results:
        by_url[row["url"]] = row
    return list(by_url.values())


def write_json(data: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d records to %s", len(data), output_path)