"""Unit tests for wbb.stats.aggregate (no game data needed)."""

from wbb.stats import FIELDS, aggregate

BOX = dict(Season='2023-2024', Team='A', TeamFG=30, TeamFGA=60, Team3P=5, Team3PA=20,
           TeamFT=10, TeamFTA=12, TeamOffRebounds=8, TeamTotalRebounds=35,
           TeamAssists=15, TeamSteals=7, TeamBlocks=3, TeamTurnovers=12,
           TeamPersonalFouls=18)


def test_aggregate_records_minutes_and_totals():
    rows = [
        dict(BOX, W_L='W', GameType='REG (Conf)', HomeAway='', TeamScore=75,
             OpponentScore=60, OT=''),
        dict(BOX, W_L='L', GameType='REG (Non-Conf)', HomeAway='@', TeamScore=70,
             OpponentScore=72, OT='2OT'),
        dict(BOX, W_L='', HomeAway='', TeamScore=None, OpponentScore=None, OT=''),
    ]
    [t] = aggregate(rows)
    assert list(t) == FIELDS
    assert (t['Rank'], t['School'], t['Games']) == (1, 'A', 2)
    assert (t['OverallWins'], t['OverallLosses'], t['WinPct']) == (1, 1, 0.5)
    assert (t['ConferenceWins'], t['ConferenceLosses']) == (1, 0)
    assert (t['HomeWins'], t['HomeLosses'], t['AwayWins'], t['AwayLosses']) == (1, 0, 0, 1)
    assert (t['ForPoints'], t['OppPoints']) == (145, 132)
    assert t['Minutes'] == 40 + 40 + 2 * 5
    assert (t['FieldGoalsMade'], t['FieldGoalsAttempted'], t['FieldGoalPCT']) == (60, 120, 0.5)
    assert t['FreeThrowPCT'] == 0.833
    assert t['OverallSRS'] == 'NA' and t['Season'] == '2023-2024'


SR_PAGE = """<table id="basic_school_stats"><thead><tr class="over_header"><th>x</th></tr></thead><tbody>
<tr><th data-stat="ranker">1</th><td data-stat="school_name"><a href="/a">Alabama</a> <sup><small>NCAA</small></sup></td>
<td data-stat="g">34</td><td data-stat="wins">24</td><td data-stat="losses">10</td>
<td data-stat="win_loss_pct">.706</td><td data-stat="srs">21.78</td><td data-stat="sos">-3.10</td>
<td data-stat="DUMMY"></td><td data-stat="wins_conf"></td><td data-stat="losses_conf"></td>
<td data-stat="fg_pct">.434</td></tr>
<tr class="thead"><th data-stat="ranker">Rk</th></tr>
</tbody></table>"""


def test_parse_sr_school_stats():
    from wbb.stats import parse_sr_school_stats
    [row] = parse_sr_school_stats(SR_PAGE, '2023-24')
    assert list(row) == FIELDS
    assert (row['Rank'], row['School'], row['Games']) == (1, 'Alabama', 34)
    assert (row['WinPct'], row['OverallSRS'], row['OverallSOS']) == (0.706, 21.78, -3.1)
    assert (row['ConferenceWins'], row['ConferenceLosses']) == ('NA', 'NA')
    assert row['FieldGoalPCT'] == 0.434 and row['Season'] == '2023-2024'
