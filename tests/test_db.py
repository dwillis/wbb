"""Offline tests for wbb.db — schema, legacy migration, refresh semantics."""
import sqlite_utils

from wbb.db import open_db, upsert_entities, TABLE_FOR_ENTITY
from wbb.models import Player


def _player(name='Alice', team_id=47, **overrides):
    defaults = dict(team_id=team_id, team='Ball State', name=name, year='JR',
                    height="6'0\"", position='G', jersey='3', season='2025-26')
    defaults.update(overrides)
    return Player(**defaults)


def _seed_legacy_schema(path):
    """Create a pre-2026 `rosters` table (old column names, no scraped_at)."""
    d = sqlite_utils.Database(str(path))
    d['rosters'].insert_all([{
        'team_id': 47, 'team': 'Ball State', 'id': 'x1', 'name': 'Old Player', 'year': 'SR',
        'hometown': '', 'high_school': '', 'previous_school': '', 'height': '6-0',
        'position': 'G', 'jersey': '1', 'url': '', 'season': '2021-22'}], pk='id')
    d.close()


def test_legacy_table_renamed_not_lost(tmp_path):
    db_path = tmp_path / 'rosters.db'
    _seed_legacy_schema(db_path)

    db = open_db(db_path)
    assert 'rosters_legacy' in db.table_names()
    assert db['rosters_legacy'].count == 1
    # New schema has scraped_at
    assert 'scraped_at' in db['rosters'].columns_dict
    # Legacy rows survive untouched
    assert list(db['rosters_legacy'].rows)[0]['name'] == 'Old Player'


def test_current_schema_not_renamed(tmp_path):
    db_path = tmp_path / 'rosters.db'
    db = open_db(db_path)
    upsert_entities(db, 'player', [_player()], '2025-26')

    db2 = open_db(db_path)
    assert 'rosters_legacy' not in db2.table_names()
    assert db2['rosters'].count == 1


def test_replace_per_scope_removes_stale_rows(tmp_path):
    db = open_db(tmp_path / 'rosters.db')
    upsert_entities(db, 'player', [_player('Alice'), _player('Bob')], '2025-26')
    assert db['rosters'].count == 2

    # Second run: Bob left, Carol joined -> only Alice + Carol remain
    upsert_entities(db, 'player', [_player('Alice'), _player('Carol')], '2025-26')
    names = sorted(r['name'] for r in db['rosters'].rows)
    assert names == ['Alice', 'Carol']


def test_zero_row_team_is_skipped(tmp_path):
    db = open_db(tmp_path / 'rosters.db')
    upsert_entities(db, 'player', [_player('Alice')], '2025-26')
    upsert_entities(db, 'player', [], '2025-26')  # transient failure must not delete
    assert db['rosters'].count == 1


def test_duplicate_names_collapse(tmp_path):
    db = open_db(tmp_path / 'rosters.db')
    p = _player('Alice')
    written = upsert_entities(db, 'player', [p, _player('Alice')], '2025-26')
    assert db['rosters'].count == 1
    assert written == 2  # rows processed; table holds collapsed unique rows


def test_other_team_and_season_untouched(tmp_path):
    db = open_db(tmp_path / 'rosters.db')
    upsert_entities(db, 'player', [_player('Alice', team_id=47), _player('Zoe', team_id=999)], '2025-26')
    upsert_entities(db, 'player', [_player('Bob', team_id=47)], '2025-26')

    # replace-per-scope: team 47's refresh removes departed Alice (she's no
    # longer on the scraped roster), while team 999's Zoe is untouched
    names = sorted(r['name'] for r in db['rosters'].rows)
    assert names == ['Bob', 'Zoe']

    upsert_entities(db, 'player', [_player('Alice', team_id=47, season='2024-25')], '2024-25')
    assert db['rosters'].count == 3  # 2024-25 row is separate from the two 2025-26 rows


def test_coach_table_shape(tmp_path):
    db = open_db(tmp_path / 'rosters.db')
    coach = Player(team_id=47, team='Ball State', name='Coach A', position='Head Coach',
                   season='2025-26')
    upsert_entities(db, 'coach', [coach], '2025-26')
    row = list(db['coaches'].rows)[0]
    assert row['title'] == 'Head Coach'
    assert 'scraped_at' in row
    assert TABLE_FOR_ENTITY['coach'] == 'coaches'