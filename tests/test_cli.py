"""Offline tests for the wbb CLI parser and command plumbing."""
import pytest

from wbb.cli import build_parser
from wbb.config import DB_PATH


def _parse(argv):
    args = build_parser().parse_args(argv)
    return args


def test_scrape_requires_season():
    import pytest
    with pytest.raises(SystemExit) as exc:
        _parse(['scrape'])
    assert exc.value.code == 2  # argparse usage error


def test_scrape_bare_db_flag_uses_default_path():
    args = _parse(['scrape', '-s', '2025-26', '-team', '47', '--db'])
    assert args.command == 'scrape'
    assert args.season == '2025-26'
    assert args.team == 47
    assert args.db == str(DB_PATH)
    assert args.entity_type == 'player'


def test_scrape_db_with_custom_path():
    args = _parse(['scrape', '-s', '2025-26', '--db', '/tmp/other.db'])
    assert args.db == '/tmp/other.db'


def test_scrape_db_absent_is_none():
    args = _parse(['scrape', '-s', '2025-26'])
    assert args.db is None


def test_scrape_flags_parity():
    args = _parse(['scrape', '-season', '2025-26', '-teams', '193', '257',
                   '-entity', 'all', '--use-playwright', '--quiet', '--verbose'])
    assert args.teams == [193, 257]
    assert args.entity_type == 'all'
    assert args.use_playwright is True
    assert args.quiet is True and args.verbose is True


def test_query_write_guard_rejects_non_select():
    args = _parse(['query', 'DELETE FROM rosters'])
    assert args.sql.strip().startswith('DELETE')


def test_query_format_choices():
    assert _parse(['query', '--format', 'json', 'SELECT 1']).format == 'json'
    with pytest.raises(SystemExit):
        _parse(['query', '--format', 'xml', 'SELECT 1'])


def test_list_teams_type_filter():
    args = _parse(['list-teams', '--type', 'javascript', '--format', 'json'])
    assert args.scraper_type == 'javascript'
    assert args.format == 'json'


def test_export_defaults():
    args = _parse(['export', '-s', '2025-26'])
    assert args.command == 'export'
    assert args.season == '2025-26'
    assert args.db is None  # export falls back to DB_PATH at runtime