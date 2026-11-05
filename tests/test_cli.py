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

def test_games_parser():
    args = _parse(['games', '-s', '2026-27', '-teams', '392', '539', '--skip-existing'])
    assert args.command == 'games'
    assert args.teams == [392, 539]
    assert args.skip_existing is True and args.headed is False
    assert args.data_dir is None


def test_games_rejects_bad_season():
    from wbb.cli import main
    assert main(['games', '-s', '2026-28']) == 2


def test_games_slug_and_wmt_routing():
    from wbb.games import slugify, WMT_TEAMS
    assert slugify({'ncaa_id': 539, 'team': 'Penn State'}) == '539-penn-state'
    assert 539 in WMT_TEAMS and 392 not in WMT_TEAMS


def test_bios_parser():
    args = _parse(['bios', '-s', '2025-26', '--teams', '193', '257',
                   '--skip-existing', '--quiet'])
    assert args.command == 'bios'
    assert args.season == '2025-26'
    assert args.teams == [193, 257]
    assert args.skip_existing is True
    assert args.quiet is True
    assert args.csv and args.csv.endswith('coaches.csv')  # default: ncaa/coaches/coaches.csv


def test_bios_output_defaults_next_to_csv(tmp_path):
    from wbb.bios import DEFAULT_CSV
    args = _parse(['bios', '--csv', str(tmp_path / 'custom.csv')])
    assert args.output is None  # resolved at runtime to csv dir's coach_bios.json


def test_bios_filter_rows():
    from wbb.bios import filter_rows
    rows = [
        {'team_id': '193', 'name': 'A', 'season': '2025-26', 'url': 'u1'},
        {'team_id': '257', 'name': 'B', 'season': '2024-25', 'url': 'u2'},
    ]
    assert [r['url'] for r in filter_rows(rows)] == ['u1', 'u2']
    assert [r['url'] for r in filter_rows(rows, season='2025-26')] == ['u1']
    assert [r['url'] for r in filter_rows(rows, team_ids=[257])] == ['u2']
    assert [r['url'] for r in filter_rows(rows, names=['A'])] == ['u1']
    assert filter_rows(rows, names=['nobody']) == []
    assert len(filter_rows(rows, limit=1)) == 1
    assert len(filter_rows(rows, demo=True)) == min(len(rows), 5)


def test_bios_merge_and_existing(tmp_path):
    from wbb.bios import existing_urls, load_existing, merge_results, write_json
    out = tmp_path / 'coach_bios.json'
    assert load_existing(out) == []
    write_json([{'url': 'u1', 'text': 'old', 'name': 'A'},
                {'url': 'u2', 'text': ''}], out)  # empty text doesn't count as existing
    assert existing_urls(load_existing(out)) == {'u1'}
    merged = merge_results(load_existing(out), [{'url': 'u1', 'text': 'new', 'name': 'A'},
                                                {'url': 'u3', 'text': 'x', 'name': 'C'}])
    by_url = {r['url']: r for r in merged}
    assert by_url['u1']['text'] == 'new' and 'u3' in by_url
    assert by_url['u2'] == {'url': 'u2', 'text': ''}  # non-fetched entries are preserved


def test_games_parser_workers():
    args = _parse(['games', '-s', '2026-27', '--workers', '3'])
    assert args.workers == 3


def test_scrape_all_parallel(tmp_path, monkeypatch):
    import json as _json
    import wbb.games as gm
    from wbb.games import GameScraper

    monkeypatch.setattr(gm, 'fetch_game_ids_static', lambda url, season: ['101', '102', '103'])
    monkeypatch.setattr(gm, 'fetch_game_json', lambda domain, gid: {'game': gid})
    teams = [{'ncaa_id': 392, 'team': 'Maryland', 'url': 'https://x.example.com'},
             {'ncaa_id': 257, 'team': 'Georgia', 'url': 'https://y.example.com'}]
    seen = []
    disc = []
    scraper = GameScraper(data_dir=tmp_path, on_team=seen.append)
    results = scraper.scrape_all(teams, '2026-27',
                                 on_discovery=lambda phase, done, total: disc.append((phase, done, total)))
    assert len(results) == 2 and {o.saved for o in results} == {3}
    assert len(seen) == 2  # on_team fired for both teams
    assert disc == [('requests', 1, 2), ('requests', 2, 2)]  # no browser teams in this fixture
    files = sorted((tmp_path / '392-maryland' / '2026-27').glob('*.json'))
    assert [f.name for f in files] == ['101.json', '102.json', '103.json']
    assert _json.load(open(files[0])) == {'game': '101'}
    assert all(o.status == 'ok' for o in results)

    # --skip-existing on a re-run: same discovery, no re-downloads
    scraper2 = GameScraper(data_dir=tmp_path, skip_existing=True)
    results2 = scraper2.scrape_all(teams, '2026-27')
    assert all(o.saved == 0 and o.skipped == 3 for o in results2)


def test_scrape_all_zero_and_failed(tmp_path, monkeypatch):
    import wbb.games as gm
    from wbb.games import GameScraper

    def flaky_static(url, season):
        return [] if 'empty' in url else ['999']  # empty -> playwright fallback
    monkeypatch.setattr(gm, 'fetch_game_ids_static', flaky_static)
    monkeypatch.setattr(gm, 'fetch_game_ids_playwright', lambda browser, url, page_type='stats': [])
    monkeypatch.setattr(gm, 'wmt_boxscore_links', lambda team, season: [f'{team["url"]}/boxscore/1'])
    monkeypatch.setattr(gm, 'wmt_game_id', lambda url: None)  # unparseable boxscore page
    # unified denominator: browser phase continues the requests count over all n
    disc = []
    scraper = GameScraper(data_dir=tmp_path)
    results = scraper.scrape_all(
        [{'ncaa_id': 392, 'team': 'Sidearm', 'url': 'https://empty.example.com'}], '2026-27',
        on_discovery=lambda phase, done, total: disc.append((phase, done, total)))
    assert disc == [('requests', 1, 1), ('playwright', 1, 1)]
    assert results[0].status == 'zero' and results[0].method == 'playwright'
    # boxscore page unparseable -> 1 found, 1 failed; status is 'ok' because
    # games were found (original GameOutcome.status semantics), nothing saved
    results2 = GameScraper(data_dir=tmp_path).scrape_all(
        [{'ncaa_id': 539, 'team': 'Wmt', 'url': 'https://wmt.example.com'}], '2026-27')
    assert results2[0].found == 1 and results2[0].failed == 1 and results2[0].saved == 0
