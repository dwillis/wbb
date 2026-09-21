"""SQLite persistence for scraped rosters (sqlite-utils).

Opt-in via `--db` on the wbb CLI. Tables mirror ENTITY_CONFIGS[*]['output_fields']
plus player_id and scraped_at. A legacy `rosters` table (pre-2026 schema without
scraped_at) is renamed to rosters_legacy in place on first open — nothing lost.
"""

import logging
from datetime import datetime, timezone

from sqlite_utils import Database

from wbb.csvio import normalize_row

logger = logging.getLogger(__name__)

# entity_type -> table name (mirrors ENTITY_CONFIGS csv_prefix)
TABLE_FOR_ENTITY = {'player': 'rosters', 'coach': 'coaches'}

# Column order at table creation; output_fields first, DB-only columns last.
TABLE_COLUMNS = {
    'rosters': {
        'team_id': int, 'team': str, 'season': str, 'jersey': str, 'name': str,
        'position': str, 'height': str, 'academic_year': str, 'hometown': str,
        'high_school': str, 'previous_school': str, 'url': str,
        'player_id': str, 'scraped_at': str,
    },
    'coaches': {
        'team_id': int, 'team': str, 'name': str, 'title': str, 'url': str,
        'season': str, 'scraped_at': str,
    },
}

# Compound natural keys, following the wnba.db precedent (upsert_all pk).
TABLE_PKS = {
    'rosters': ['team_id', 'season', 'name'],
    'coaches': ['team_id', 'season', 'name'],
}

_LEGACY_TABLE = 'rosters_legacy'


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _migrate_legacy(db: Database):
    """Rename a legacy `rosters` table (old schema without scraped_at) in place."""
    if 'rosters' not in db.table_names():
        return
    if 'scraped_at' in db['rosters'].columns_dict:
        return  # current schema already

    target = _LEGACY_TABLE
    n = 2
    while target in db.table_names():
        target = f"{_LEGACY_TABLE}_{n}"
        n += 1
    db.execute(f'ALTER TABLE "rosters" RENAME TO "{target}"')
    logger.info(f"Migrated legacy rosters table to {target} ({db[target].count:,} rows preserved)")


def _ensure_schema(db: Database):
    for table, columns in TABLE_COLUMNS.items():
        if table not in db.table_names():
            db[table].create(columns, pk=TABLE_PKS[table])
        db[table].create_index(['season', 'team_id'], if_not_exists=True)


def open_db(path) -> Database:
    """Open (creating/migrating as needed) the roster database."""
    db = Database(str(path))
    _migrate_legacy(db)
    _ensure_schema(db)
    return db


def upsert_entities(db: Database, entity_type: str, players, season: str,
                    team_state_map=None, scraped_at: str = None) -> int:
    """Refresh rows for every (team_id, season) present in this batch.

    Rows are normalized through the same csvio.normalize_row the CSV writer
    uses, so DB and CSV never disagree on a row's shape. Teams that returned
    zero rows are deliberately skipped: a transient scrape failure must not
    delete good data. Returns the number of rows written.
    """
    table = TABLE_FOR_ENTITY[entity_type]
    if not players:
        return 0

    scraped_at = scraped_at or _utc_now()
    columns = TABLE_COLUMNS[table]
    pks = TABLE_PKS[table]
    column_order = list(columns)

    by_team = {}
    for player in players:
        row = normalize_row(player, entity_type, team_state_map)
        row['player_id'] = getattr(player, 'player_id', None) or ''
        row['scraped_at'] = scraped_at
        row['season'] = season
        by_team.setdefault(row.get('team_id'), []).append({k: row.get(k) for k in columns})

    written = 0
    for team_id, rows in by_team.items():
        with db.conn:
            db.execute(f'DELETE FROM "{table}" WHERE "team_id" = ? AND "season" = ?',
                       [team_id, season])
            db[table].insert_all(rows, pk=pks, replace=True, column_order=column_order)
            written += len(rows)
    return written