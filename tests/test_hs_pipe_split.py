"""Offline tests for pipe-packed high_school values: everything after the
first '|' moves to previous_school (wbb.parsing.FieldExtractors.split_school_pipe,
applied in wbb.csvio.normalize_row for CSV and DB output alike)."""

import csv

from wbb import csvio
from wbb.models import Player
from wbb.parsing import FieldExtractors


def _player(**overrides):
    defaults = dict(team_id=5, team='Akron', name='Jessie Joaquim', year='Senior',
                    position='F', jersey='3', season='2026-27')
    defaults.update(overrides)
    return Player(**defaults)


# --- FieldExtractors.split_school_pipe -----------------------------------------

def test_moves_tail_after_first_pipe():
    hs, prev = FieldExtractors.split_school_pipe(
        'Escola Secundária de Francisco Franco | Cochise College | New Mexico')
    assert hs == 'Escola Secundária de Francisco Franco'
    assert prev == 'Cochise College | New Mexico'   # internal separators kept


def test_two_parts_and_unspaced_pipes():
    assert FieldExtractors.split_school_pipe('Standish-Sterling | Toledo') == \
        ('Standish-Sterling', 'Toledo')
    assert FieldExtractors.split_school_pipe('Mayfair HS|Cypress College') == \
        ('Mayfair HS', 'Cypress College')


def test_no_pipe_is_unchanged():
    assert FieldExtractors.split_school_pipe('Rutgers Prep') == ('Rutgers Prep', '')
    assert FieldExtractors.split_school_pipe('', 'Old School') == ('', 'Old School')
    assert FieldExtractors.split_school_pipe(None) == ('', '')


def test_never_overwrites_existing_previous_school():
    assert FieldExtractors.split_school_pipe('A | B', 'Existing School') == \
        ('A | B', 'Existing School')


def test_edge_whitespace_and_trailing_pipe():
    assert FieldExtractors.split_school_pipe('  Veritas Christian Academy | Bluegrass United  ') == \
        ('Veritas Christian Academy', 'Bluegrass United')
    hs, prev = FieldExtractors.split_school_pipe('Delaware Hayes |')
    assert (hs, prev) == ('Delaware Hayes', '')
    assert FieldExtractors.split_school_pipe('| Leading Pipe') == ('| Leading Pipe', '')


# --- applied in normalize_row (CSV + DB path) ----------------------------------

def test_normalize_row_splits_pipes():
    row = csvio.normalize_row(_player(
        high_school='Sapulpa HS | Oral Roberts | Oklahoma State'), 'player')
    assert row['high_school'] == 'Sapulpa HS'
    assert row['previous_school'] == 'Oral Roberts | Oklahoma State'


def test_normalize_row_leaves_clean_rows_alone():
    row = csvio.normalize_row(_player(high_school='Pickerington Central'), 'player')
    assert row['high_school'] == 'Pickerington Central'
    assert row['previous_school'] == ''


def test_normalize_row_respects_existing_previous_school():
    row = csvio.normalize_row(_player(high_school='A | B', previous_school='Kept'), 'player')
    assert row['high_school'] == 'A | B'
    assert row['previous_school'] == 'Kept'


def test_write_entities_csv_reflects_split(tmp_path):
    out = tmp_path / 'players.csv'
    assert csvio.write_entities([_player(
        high_school='Escola Secundária de Francisco Franco | Cochise College | New Mexico',
        hometown='Maputo, Mozambique')], 'player', str(out)) is True
    with open(out, newline='') as f:
        row = list(csv.DictReader(f))[0]
    assert row['high_school'] == 'Escola Secundária de Francisco Franco'
    assert row['previous_school'] == 'Cochise College | New Mexico'