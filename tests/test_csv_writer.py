"""Offline tests for wbb.csvio — rows built in memory, no network."""
import csv
import os

from wbb import csvio
from wbb.config import ENTITY_CONFIGS
from wbb.models import Player


def _player(**overrides):
    defaults = dict(team_id=47, team='Ball State', name='Test Player', year='JR',
                    height="6'0\"", position='G', jersey='3', season='2025-26')
    defaults.update(overrides)
    return Player(**defaults)


def test_player_csv_header_matches_output_fields(tmp_path):
    out = tmp_path / 'players.csv'
    players = [_player(name='Alice', year='JR'), _player(name='Bob', year='SO')]
    assert csvio.write_entities(players, 'player', str(out)) is True

    with open(out, newline='') as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ENTITY_CONFIGS['player']['output_fields']
        rows = list(reader)
    assert len(rows) == 2
    assert all(r['academic_year'] for r in rows), "academic_year must be populated"
    assert 'year' not in rows[0], "raw 'year' column must be renamed to academic_year"
    assert rows[0]['name'] == 'Alice'


def test_coach_row_maps_position_to_title(tmp_path):
    out = tmp_path / 'coaches.csv'
    coach = Player(team_id=47, team='Ball State', name='Coach X', position='Head Coach',
                   season='2025-26')
    assert csvio.write_entities([coach], 'coach', str(out)) is True

    with open(out, newline='') as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]['title'] == 'Head Coach'
    assert 'position' not in rows[0]


def test_add_state_to_hometown_appends_state(tmp_path):
    out = tmp_path / 'players.csv'
    # Team 46 (Baldwin Wallace) is in TeamConfig.ADD_STATE_TO_HOMETOWN with state OH
    player = _player(team_id=46, team='Baldwin Wallace', hometown='Berea')
    state_map = {46: 'OH'}
    csvio.write_entities([player], 'player', str(out), state_map)

    with open(out, newline='') as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]['hometown'] == 'Berea, OH'

    # Already has a comma -> untouched
    player2 = _player(team_id=46, team='Baldwin Wallace', hometown='Berea, OH')
    csvio.write_entities([player2], 'player', str(out), state_map)
    with open(out, newline='') as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]['hometown'] == 'Berea, OH'


def test_write_entities_empty_players_writes_nothing(tmp_path):
    out = tmp_path / 'empty.csv'
    assert csvio.write_entities([], 'player', str(out)) is False
    assert not out.exists()


def test_sidecar_writers(tmp_path):
    zero_out = tmp_path / 'rosters_x_zero_players.csv'
    assert csvio.write_zero_players([{'team_id': 1, 'team_name': 'Zero U'}], str(zero_out))
    with open(zero_out, newline='') as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ['team_id', 'team_name']

    fail_out = tmp_path / 'rosters_x_failed_year_check.csv'
    failed = [{'team_id': 2, 'team_name': 'Fail U', 'url': 'https://x.example'}]
    assert csvio.write_failed_year_check(failed, str(fail_out)) is True
    with open(fail_out, newline='') as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ['team_id', 'team_name', 'url']