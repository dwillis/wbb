"""Tests for wbb/logs.py — game log CSVs from the wbb-game-data archive."""

import csv
import json

import pytest

from wbb import logs


# ------------------------------------------------------------ stat parsing

def sidearm_totals(fg, tpa, ft, points, reb=50, ast=10, stl=6, blk=3, to=12, pf=15):
    """A Sidearm Stats.<Team>.Totals.Values dict."""
    return {'Points': str(points), 'Fgam': f"{fg['m']}-{fg['a']}",
            'ShootingPercentage': '50.0%', 'Tpam': f"{tpa['m']}-{tpa['a']}",
            'Tppercentage': '33.3%', 'Ftma': f"{ft['m']}-{ft['a']}", 'Ftp': '70.0%',
            'TotalRebounds': str(reb), 'OffensiveRebounds': str(reb // 2),
            'DefensiveRebounds': str(reb - reb // 2), 'Ties': '0', 'Leads': '2',
            'TimeWithLead': '1:00', 'PercentLead': '10%', 'LastLeadScore': '',
            'LastLeadTime': '', 'LargestLead': '5', 'LargestLeadScores': '',
            'LargestLeadTime': '', 'Assists': str(ast), 'Turnovers': str(to),
            'PointsFromBench': '0', 'Blocks': str(blk), 'PointsOnCourt': '0',
            'PointsOffFastBreak': '0', 'Steals': str(stl),
            'PointsOffTurnovers': '0', 'PointsInPaint': '0',
            'PointsOffSecondChance': '0', 'PersonalFouls': str(pf),
            'TechnicalFouls': '0', 'Possession': '0',
            'AverageScoringPossession': '-'}


def sidearm_player_row(**overrides):
    row = {'Uni': '00', 'Name': 'A. PLAYER', 'Position': 'G', 'CurrentlyInGame': '',
           'Minutes': '10', 'Fgam': '1-2', 'ShootingPercentage': '50.0%',
           'Tpam': '0-1', 'Tppercentage': '0.0%', 'Ftma': '0-0', 'Ftp': '0.0%',
           'TotalRebounds': '1', 'OffensiveRebounds': '0', 'DefensiveRebounds': '1',
           'Assists': '1', 'Turnovers': '1', 'Blocks': '0', 'Steals': '1',
           'PersonalFouls': '1', 'TechnicalFouls': '0', 'Efficiency': '1.0',
           'UsagePercentage': '10', 'PointsPerMinute': '.1', 'Points': '2',
           'PersonId': ''}
    row.update(overrides)
    return row


def sidearm_game(home=('Home U', 60, [10, 15, 15, 20]), visitor=('Vis U', 50)):
    home = (home + (None,))[:3] if len(home) < 3 else home
    if home[2] is None:
        home = (home[0], home[1], [10, 15, 15, 20])
    return {
        'Game': {
            'IsComplete': True,
            'HomeTeam': {'Id': 'HU', 'Name': home[0], 'Score': home[1],
                         'PeriodScores': home[2]},
            'VisitingTeam': {'Id': 'VU', 'Name': visitor[0], 'Score': visitor[1],
                             'PeriodScores': [p // 2 for p in home[2]]},
        },
        'Stats': {
            'HomeTeam': {'TopPerformer': {}, 'Players': [],
                         'PlayerGroups': {'Players': {'Title': 'Players', 'Key': {},
                                                      'Values': []}},
                         'Totals': {'Key': {}, 'FullKey': {},
                                    'Values': sidearm_totals({'m': 20, 'a': 50},
                                                             {'m': 5, 'a': 15},
                                                             {'m': 3, 'a': 5},
                                                             points=home[1])},
                         'PeriodStats': []},
            'VisitingTeam': {'TopPerformer': {}, 'Players': [],
                             'PlayerGroups': {'Players': {'Title': 'Players',
                                                          'Key': {}, 'Values': []}},
                             'Totals': {'Key': {}, 'FullKey': {},
                                        'Values': sidearm_totals({'m': 15, 'a': 45},
                                                                 {'m': 3, 'a': 12},
                                                                 {'m': 2, 'a': 4},
                                                                 points=visitor[1])},
                             'PeriodStats': []},
        },
    }


def wmt_stat(fgm=20, fga=50, tpm=5, tpa=15, ftm=3, fta=5, orb=10, drb=20,
             trb=30, ast=10, stl=6, blk=3, to=12, pf=15, pts=None):
    return {'sFieldGoalsMade': fgm, 'sFieldGoalsAttempted': fga,
            'sThreePointFieldGoalsMade': tpm, 'sThreePointFieldGoalsAttempted': tpa,
            'sFreeThrowsMade': ftm, 'sFreeThrowsAttempted': fta,
            'sOffensiveRebounds': orb, 'sDefensiveRebounds': drb,
            'sTotalRebounds': trb, 'sAssists': ast, 'sSteals': stl, 'sBlocks': blk,
            'sTurnovers': to, 'sPersonalFouls': pf, 'sPoints': pts}


def wmt_competitor(side, name, score, stats_rows):
    return {'homeTeam': side == 'home', 'nameTabular': name, 'score': score,
            'teamStats': [{'period': p, 'statistic': dict(s)}
                          for p, s in stats_rows]}


def test_wmt_stats_use_period_zero_row():
    comp = wmt_competitor('home', 'Temple', 71,
                          [(1, wmt_stat(fgm=7, fga=18)), (2, wmt_stat(fgm=6, fga=15)),
                           (2, wmt_stat(fgm=6, fga=15)),
                           (0, wmt_stat(fgm=27, fga=62, tpm=4, tpa=12, ftm=13, fta=18,
                                        orb=12, drb=25, trb=37, ast=12, stl=13,
                                        blk=None, to=11, pf=13, pts=71))])
    stats = logs._wmt_team_stats(comp)
    assert stats['fg'] == 27 and stats['fga'] == 62
    assert stats['pm'] == 4 and stats['pa'] == 12
    assert stats['ftm'] == 13
    assert stats['trb'] == 37 and stats['ast'] == 12
    assert stats['blk'] is None  # absent key stays blank, not zero


def test_wmt_stats_sum_periods_without_totals_row():
    comp = wmt_competitor('home', 'Temple', 71,
                          [(1, wmt_stat(fgm=7, fga=18, pf=3)),
                           (2, wmt_stat(fgm=6, fga=15, pf=4)),
                           (3, wmt_stat(fgm=6, fga=15, pf=4))])
    stats = logs._wmt_team_stats(comp)
    assert stats['fg'] == 19 and stats['fga'] == 48
    assert stats['pf'] == 11


def test_sidearm_stats_read_made_attended_strings():
    data = sidearm_game()
    parsed = logs._parse_game_json(data)
    home = parsed['home']['stats']
    assert home['fg'] == 20 and home['fga'] == 50
    assert home['pm'] == 5 and home['pa'] == 15
    assert home['ftm'] == 3 and home['fta'] == 5
    assert home['orb'] == 25 and home['drb'] == 25


def test_parse_game_json_rejects_unknown_payload():
    assert logs._parse_game_json({'unexpected': True}) is None
    assert logs._parse_game_json(None) is None


# --------------------------------------------------------------- stat math

def test_stat_block_values_derives_twos_and_efg():
    values = logs._stat_block_values({'fg': 20, 'fga': 50, 'pm': 5, 'pa': 15,
                                      'ftm': 3, 'fta': 5, 'orb': 10, 'drb': 20,
                                      'trb': 30, 'ast': 10, 'stl': 6, 'blk': 3,
                                      'to': 12, 'pf': 15})
    by_key = dict(zip(logs._STAT_BLOCK, values))
    assert by_key['2P'] == 15 and by_key['2PA'] == 35
    assert by_key['2PPCT'] == round(15 / 35, 3)
    assert by_key['FGPCT'] == 0.4
    assert by_key['EFGPCT'] == round((20 + 0.5 * 5) / 50, 3)
    assert by_key['PersonalFouls'] == 15


def test_stat_block_values_blank_without_attempts():
    values = logs._stat_block_values({'fg': None, 'fga': None, 'pm': None,
                                      'pa': None, 'ftm': None, 'fta': None,
                                      'orb': None, 'drb': None, 'trb': None,
                                      'ast': None, 'stl': None, 'blk': None,
                                      'to': None, 'pf': None})
    assert all(v is None for v in values)


def test_team_efg_column_has_no_prefix_opponent_keeps_it():
    stats = {'fg': 20, 'fga': 50, 'pm': 5, 'pa': 15, 'ftm': 3, 'fta': 5,
             'orb': 10, 'drb': 20, 'trb': 30, 'ast': 10, 'stl': 6, 'blk': 3,
             'to': 12, 'pf': 15}
    team = logs._stat_fields(stats, 'Team')
    assert 'EFGPCT' in team and 'TeamEFGPCT' not in team
    opp = logs._stat_fields(stats, 'Opponent')
    assert 'OpponentEFGPCT' in opp


def test_ot_label():
    assert logs._ot_label(4) == ''
    assert logs._ot_label(5) == 'OT'
    assert logs._ot_label(6) == '2OT'
    assert logs._ot_label(0) == ''
    assert logs._ot_label(None) == ''


# ------------------------------------------------------------ row building

def test_side_resolution_score_match_swaps_index_order():
    entry = {'h': 901, 'v': 902, 'hs': 70, 'vs': 60}
    parsed = {'home': {'name': 'A', 'score': 70, 'periods': 4, 'stats': {}},
              'visitor': {'name': 'B', 'score': 60, 'periods': 4, 'stats': {}}}
    assert logs._resolve_sides(entry, parsed) == (901, 902, 'home', 'visitor')
    parsed['home']['score'], parsed['visitor']['score'] = 60, 70
    assert logs._resolve_sides(entry, parsed) == (902, 901, 'visitor', 'home')


def test_side_resolution_falls_back_to_index_order():
    entry = {'h': 901, 'v': 902, 'hs': 70, 'vs': 60}
    parsed = None
    assert logs._resolve_sides(entry, parsed) == (901, 902, 'home', 'visitor')


def test_field_names_match_model_csv():
    expected = ('Season,Game,Date,GameType,TeamFullName,Opponent,HomeAway,W_L,'
                'TeamScore,OpponentScore,OT,TeamFG,TeamFGA,TeamFGPCT,Team3P,'
                'Team3PA,Team3PPCT,Team2P,Team2PA,Team2PPCT,EFGPCT,TeamFT,'
                'TeamFTA,TeamFTPCT,TeamOffRebounds,TeamDefRebounds,'
                'TeamTotalRebounds,TeamAssists,TeamSteals,TeamBlocks,'
                'TeamTurnovers,TeamPersonalFouls,OpponentFG,OpponentFGA,'
                'OpponentFGPCT,Opponent3P,Opponent3PA,Opponent3PPCT,Opponent2P,'
                'Opponent2PA,Opponent2PPCT,OpponentEFGPCT,OpponentFT,OpponentFTA,'
                'OpponentFTPCT,OpponentOffRebounds,OpponentDefRebounds,'
                'OpponentTotalRebounds,OpponentAssists,OpponentSteals,'
                'OpponentBlocks,OpponentTurnovers,OpponentPersonalFouls,URL,'
                'Conference,Team,TeamSRS,TeamSOS,OpponentSRS,OpponentSOS').split(',')
    assert logs.FIELDS == expected
    assert len(logs.FIELDS) == 60


# -------------------------------------------------- end-to-end tiny archive

@pytest.fixture
def tiny_archive(tmp_path):
    """A miniature wbb-game-data archive: manifest, division index, one raw
    file (sidearm), plus one index-only game (no raw file) and one OT game."""
    manifest = [
        {'team': 'Alpha U', 'ncaa_id': 101, 'conference': 'Alpha Conf',
         'division': 'I'},
        {'team': 'Beta U', 'ncaa_id': 102, 'conference': 'Alpha Conf',
         'division': 'I'},
        {'team': 'Gamma U', 'ncaa_id': 103, 'conference': 'Other Conf',
         'division': 'I'},
        {'team': 'Delta U', 'ncaa_id': 104, 'conference': '',
         'division': 'II'},  # other division; opponent only
        {'team': 'Wmt U', 'ncaa_id': 105, 'conference': 'Wmt Conf',
         'division': 'I'},
    ]
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data' / 'teams.json').write_text(json.dumps(manifest))

    index = []
    # Alpha (h) vs Beta (v): a sidearm game with the raw file present
    index.append({'id': 9001, 'd8': '2024-11-09', 'h': 101, 'v': 102,
                  'hs': 60, 'vs': 50,
                  'hp': [10, 15, 15, 20], 'vp': [8, 12, 14, 16],
                  'src': '101-alpha-u/2024-25/9001.json'})
    # WMT OT game: Wmt U (h) vs Gamma in double OT plus one extra period row
    wmt_game = {'data': {
        'competitors': [
            wmt_competitor('home', 'WMT', 88, [
                (1, wmt_stat(fgm=15, fga=40, pf=10, pts=60)),
                (2, wmt_stat(fgm=15, fga=40, pf=10, pts=60)),
                (4, wmt_stat(fgm=2, fga=4, pf=2, pts=8)),
                (5, wmt_stat(fgm=2, fga=4, pf=2, pts=8)),
                (6, wmt_stat(fgm=2, fga=4, pf=2, pts=8)),
                (7, wmt_stat(fgm=2, fga=4, pf=2, pts=8)),
                (0, wmt_stat(fgm=38, fga=96, tpm=4, tpa=12, ftm=6, fta=10,
                             orb=14, drb=30, trb=44, ast=20, stl=10, to=14,
                             pf=28, pts=88)),
            ]),
            wmt_competitor('visitor', 'Other U', 82, [
                (0, wmt_stat(fgm=35, fga=90, tpm=3, tpa=10, ftm=9, fta=14,
                             orb=12, drb=28, trb=40, ast=18, stl=8, to=16,
                             pf=24, pts=82)),
            ]),
        ],
    }}
    (tmp_path / '105-wmt-u').mkdir()
    (tmp_path / '105-wmt-u' / '2024-25').mkdir()
    (tmp_path / '105-wmt-u' / '2024-25' / '9002.json').write_text(
        json.dumps(wmt_game))
    index.append({'id': 9002, 'd8': '2024-12-01', 'h': 105, 'v': 103,
                  'hs': 88, 'vs': 82,
                  'hp': [20, 20, 20, 20, 5, 3], 'vp': [18, 20, 22, 20, 2, 0],
                  'src': '105-wmt-u/2024-25/9002.json'})
    # Index-only game (no raw file): Beta at Gamma
    index.append({'id': 9003, 'd8': '2025-01-10', 'h': 103, 'v': 102,
                  'hs': 70, 'vs': 66, 'hp': [18, 18, 17, 17],
                  'vp': [16, 16, 17, 17]})
    # Stale entry outside the season window (mis-filed payload)
    index.append({'id': 9004, 'd8': '2022-11-09', 'h': 103, 'v': 102,
                  'hs': 60, 'vs': 50})

    (tmp_path / 'index' / 'seasons' / '2024-25').mkdir(parents=True)
    (tmp_path / 'index' / 'seasons' / '2024-25' / 'd1.json').write_text(
        json.dumps({'season': '2024-25', 'division': 'd1', 'games': index}))

    (tmp_path / '101-alpha-u' / '2024-25').mkdir(parents=True)
    (tmp_path / '101-alpha-u' / '2024-25' / '9001.json').write_text(
        json.dumps(sidearm_game(home=('Alpha U', 60), visitor=('Beta U', 50))))
    return tmp_path


def test_build_game_logs_end_to_end(tiny_archive):
    rows, info = logs.build_game_logs('2024-25', 'I', data_dir=tiny_archive)
    by_team = {}
    for row in rows:
        by_team.setdefault(row['Team'], []).append(row)

    assert info['teams'] == 4
    assert info['entries_outside_season_window'] == 1
    # the index-only game yields two rows (one per team) without box scores
    assert info['rows_without_box_score'] == 2

    alpha = by_team['Alpha U'][0]
    assert alpha['Opponent'] == 'Beta U'
    assert alpha['HomeAway'] == '' and alpha['W_L'] == 'W'
    assert alpha['TeamScore'] == 60 and alpha['OpponentScore'] == 50
    assert alpha['GameType'] == 'REG (Conf)'  # same conference in the manifest
    assert alpha['TeamFG'] == 20 and alpha['OpponentFG'] == 15
    assert alpha['EFGPCT'] == 0.45
    assert alpha['Season'] == '2024-2025'

    beta_home = by_team['Beta U'][0]
    assert beta_home['HomeAway'] == '@' and beta_home['W_L'] == 'L'
    assert beta_home['Opponent'] == 'Alpha U'

    wmt = by_team['Wmt U'][0]
    assert wmt['GameType'] == 'REG (Non-Conf)'
    assert wmt['OT'] == '3OT'  # periods parsed from the WMT per-period rows
    assert wmt['TeamFG'] == 38 and wmt['TeamScore'] == 88
    assert wmt['OpponentScore'] == 82

    gamma = by_team['Gamma U']
    assert len(gamma) == 2  # OT game plus the index-only game
    gamma_only = [r for r in gamma if r['URL'] == '']
    assert len(gamma_only) == 1
    assert gamma_only[0]['TeamScore'] == 70
    assert gamma_only[0]['TeamFG'] is None  # no raw file, no box score
    assert gamma_only[0]['W_L'] == 'W'


def test_output_name_and_year():
    assert logs.season_year('2025-26') == '26'
    assert logs.output_name('2025-26', 'I') == 'wbblogs26_i.csv'
    assert logs.output_name('2024-25', 'II') == 'wbblogs25_ii.csv'
    assert logs.output_name('2023-24', 'III') == 'wbblogs24_iii.csv'


def test_write_game_logs_roundtrip(tiny_archive):
    rows, _info = logs.build_game_logs('2024-25', 'I', data_dir=tiny_archive)
    path = tiny_archive / 'out' / 'wbblogs25_i.csv'
    logs.write_game_logs(rows, path)
    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        body = [row for row in reader]
    assert header == logs.FIELDS
    assert len(body) == len(rows)
