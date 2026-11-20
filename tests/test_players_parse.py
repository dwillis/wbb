"""Offline tests for wbb.players parsing (no network)."""

from wbb.players import parse_school_list, parse_school_page, season_label, sr_year

SCHOOL_STATS = """<table id="basic_school_stats"><tbody>
<tr><th data-stat="ranker">1</th><td data-stat="school_name">
<a href="/cbb/schools/abilene-christian/women/2026.html">Abilene Christian</a></td></tr>
<tr class="thead"><th>Rk</th></tr>
</tbody></table>"""

SCHOOL = """<div id="meta"><p><a href="/cbb/conferences/wac/women/2026.html">WAC WBB</a></p></div>
<table id="roster"><thead><tr><th data-stat="player">Player</th><th data-stat="class">Class</th>
<th data-stat="pos">Pos</th></tr></thead><tbody>
<tr><th data-stat="player" data-append-csv="a-1"><a>Ann Smith</a></th><td data-stat="class">JR</td><td data-stat="pos">G</td></tr>
<tr><th data-stat="player" data-append-csv="a-2"><a>Ann Smith</a></th><td data-stat="class">FR</td><td data-stat="pos">F</td></tr>
</tbody></table>
<table id="players_totals"><thead><tr><th data-stat="ranker">Rk</th><th data-stat="name_display">Player</th>
<th data-stat="pos">Pos</th><th data-stat="games">G</th><th data-stat="pts">PTS</th></tr></thead><tbody>
<tr><th data-stat="ranker">1</th><td data-stat="name_display" data-append-csv="a-1">Ann Smith</td>
<td data-stat="pos">G</td><td data-stat="games">30</td><td data-stat="pts">400</td></tr>
</tbody><tfoot><tr><td data-stat="name_display">Team Totals</td></tr></tfoot></table>
<!-- <table id="players_advanced"><thead><tr><th data-stat="name_display">Player</th>
<th data-stat="games">G</th><th data-stat="per">PER</th></tr></thead><tbody>
<tr><td data-stat="name_display" data-append-csv="a-1">Ann Smith</td><td data-stat="games">30</td>
<td data-stat="per">20.1</td></tr></tbody></table> -->"""


def test_season_helpers():
    assert sr_year('2025-26') == 2026
    assert season_label('2025-26') == '2025-2026'


def test_school_list():
    assert parse_school_list(SCHOOL_STATS) == [
        ('Abilene Christian', '/cbb/schools/abilene-christian/women/2026.html')]


def test_school_page_joins_on_player_id_and_reads_commented_table():
    columns, rows = parse_school_page(SCHOOL, 'Abilene Christian', '2025-26')
    assert [label for _k, label in columns] == [
        'Team', 'player_id', 'Player', 'Class', 'Pos', 'G', 'PTS', 'PER',
        'Conference', 'Season']
    first, second = rows
    assert (first['player_id'], first['games'], first['pts'], first['per']) == ('a-1', '30', '400', '20.1')
    assert first['conference'] == 'WAC' and first['season'] == '2025-2026'
    # Same name, different id: no cross-join, roster-only row kept.
    assert second['player_id'] == 'a-2' and 'pts' not in second
