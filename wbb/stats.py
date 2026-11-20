"""Team-level season stats CSVs (wbbstats{YY}.csv).

Two sources, same columns:

- Sports-Reference (default; port of the stats half of
  ncaa/WBBLogScraperScript.R): one request for the season's
  /cbb/seasons/women/{YYYY}-school-stats.html, whose basic_school_stats table
  is renamed to the model columns. Rank is SR's row number, the NCAA
  tournament marker is stripped from School, percents are fractions (0.457),
  and blank cells (e.g. conference records for independents or before
  conference play) are written as NA, as R's write_csv did. All Division I
  schools on the page are kept; the R script's Le Moyne/Mercyhurst/West
  Georgia exclusion applied only to its game log loop.

- The wbb-game-data archive (--from-games), described below.

The archive path produces one Sports-Reference-style team stats CSV per division and season
(wbbstats{YY}_i|ii|iii.csv): one row per team, with won-lost splits and
season box-score totals summed over the team's completed games.

Built on wbb/logs.py: the game log rows (one per team per game) are the
input, so the same index, manifest, feed parsing and season-window rules
apply. Only games with a result (W_L set) count. Box-score totals sum the
games that have them; a game without a box score still counts toward
Games/wins/points/minutes.

Minutes is team minutes: 40 per game plus 5 per overtime period. Home and
away splits use the game log's HomeAway column; the index has no neutral-site
flag, so neutral games land in whichever side the index lists the team on.
OverallSRS/OverallSOS come from Sports-Reference, not the game JSON, and are
left "NA" for schema parity (as in the game logs).
"""

import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from wbb.logs import DIVISION_KEYS, build_game_logs, season_year

FIELDS = ['Rank', 'School', 'Games', 'OverallWins', 'OverallLosses', 'WinPct',
          'OverallSRS', 'OverallSOS', 'ConferenceWins', 'ConferenceLosses',
          'HomeWins', 'HomeLosses', 'AwayWins', 'AwayLosses', 'ForPoints',
          'OppPoints', 'Minutes', 'FieldGoalsMade', 'FieldGoalsAttempted',
          'FieldGoalPCT', 'ThreePointMade', 'ThreePointAttempts', 'ThreePointPct',
          'FreeThrowsMade', 'FreeThrowsAttempted', 'FreeThrowPCT',
          'OffensiveRebounds', 'TotalRebounds', 'Assists', 'Steals', 'Blocks',
          'Turnovers', 'PersonalFouls', 'Season']

# Output column <- game log column, for the summed box-score totals.
_SUMS = [('FieldGoalsMade', 'TeamFG'), ('FieldGoalsAttempted', 'TeamFGA'),
         ('ThreePointMade', 'Team3P'), ('ThreePointAttempts', 'Team3PA'),
         ('FreeThrowsMade', 'TeamFT'), ('FreeThrowsAttempted', 'TeamFTA'),
         ('OffensiveRebounds', 'TeamOffRebounds'),
         ('TotalRebounds', 'TeamTotalRebounds'), ('Assists', 'TeamAssists'),
         ('Steals', 'TeamSteals'), ('Blocks', 'TeamBlocks'),
         ('Turnovers', 'TeamTurnovers'), ('PersonalFouls', 'TeamPersonalFouls')]

_PCTS = [('FieldGoalPCT', 'FieldGoalsMade', 'FieldGoalsAttempted'),
         ('ThreePointPct', 'ThreePointMade', 'ThreePointAttempts'),
         ('FreeThrowPCT', 'FreeThrowsMade', 'FreeThrowsAttempted')]


def output_name(season, division):
    """Default output filename: wbbstats{year}_i|ii|iii.csv."""
    return f"wbbstats{season_year(season)}_{DIVISION_KEYS[division][1]}.csv"


def _ot_periods(label):
    """'' -> 0, 'OT' -> 1, '2OT' -> 2."""
    if not label:
        return 0
    return int(label[:-2]) if label[:-2].isdigit() else 1


def _ratio(num, den):
    return round(num / den, 3) if den else None


def aggregate(log_rows):
    """Team season rows from game log rows (ordered as the logs: by team name)."""
    teams = {}
    for row in log_rows:
        result = row.get('W_L')
        if result not in ('W', 'L'):
            continue
        name = row['Team']
        t = teams.get(name)
        if t is None:
            t = teams[name] = {f: 0 for f in FIELDS}
            t.update(School=name, Season=row['Season'],
                     OverallSRS='NA', OverallSOS='NA')
        won = result == 'W'
        t['Games'] += 1
        t['OverallWins' if won else 'OverallLosses'] += 1
        if row.get('GameType') == 'REG (Conf)':
            t['ConferenceWins' if won else 'ConferenceLosses'] += 1
        side = 'Away' if row.get('HomeAway') == '@' else 'Home'
        t[f"{side}{'Wins' if won else 'Losses'}"] += 1
        t['ForPoints'] += row.get('TeamScore') or 0
        t['OppPoints'] += row.get('OpponentScore') or 0
        t['Minutes'] += 40 + 5 * _ot_periods(row.get('OT'))
        for out, src in _SUMS:
            t[out] += row.get(src) or 0

    rows = []
    for rank, t in enumerate(teams.values(), start=1):
        t['Rank'] = rank
        t['WinPct'] = _ratio(t['OverallWins'], t['Games'])
        for out, made, att in _PCTS:
            t[out] = _ratio(t[made], t[att])
        rows.append(t)
    return rows


def build_team_stats(season, division, data_dir=None):
    """Team stats rows for one division and season, plus build_game_logs' info
    (with 'teams_with_games' and 'stat_rows' added)."""
    log_rows, info = build_game_logs(season, division, data_dir=data_dir)
    rows = aggregate(log_rows)
    info['teams_with_games'] = len(rows)
    info['stat_rows'] = len(rows)
    return rows, info


def write_team_stats(rows, path):
    """Write the team stats rows as CSV; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return path


# ------------------------------------------------- Sports-Reference source

SR_BASE_URL = "https://www.sports-reference.com"
SR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

# basic_school_stats data-stat -> output column (the R script's X-column renames).
SR_COLUMNS = {
    'ranker': 'Rank', 'school_name': 'School', 'g': 'Games',
    'wins': 'OverallWins', 'losses': 'OverallLosses', 'win_loss_pct': 'WinPct',
    'srs': 'OverallSRS', 'sos': 'OverallSOS',
    'wins_conf': 'ConferenceWins', 'losses_conf': 'ConferenceLosses',
    'wins_home': 'HomeWins', 'losses_home': 'HomeLosses',
    'wins_visitor': 'AwayWins', 'losses_visitor': 'AwayLosses',
    'pts': 'ForPoints', 'opp_pts': 'OppPoints', 'mp': 'Minutes',
    'fg': 'FieldGoalsMade', 'fga': 'FieldGoalsAttempted', 'fg_pct': 'FieldGoalPCT',
    'fg3': 'ThreePointMade', 'fg3a': 'ThreePointAttempts', 'fg3_pct': 'ThreePointPct',
    'ft': 'FreeThrowsMade', 'fta': 'FreeThrowsAttempted', 'ft_pct': 'FreeThrowPCT',
    'orb': 'OffensiveRebounds', 'trb': 'TotalRebounds', 'ast': 'Assists',
    'stl': 'Steals', 'blk': 'Blocks', 'tov': 'Turnovers', 'pf': 'PersonalFouls',
}


def sr_output_name(season):
    """Default Sports-Reference output filename: wbbstats{YY}.csv."""
    return f"wbbstats{season_year(season)}.csv"


def sr_school_stats_url(season):
    return f"{SR_BASE_URL}/cbb/seasons/women/{int(season[:4]) + 1}-school-stats.html"


def _sr_number(text):
    """'.457' -> 0.457, '24' -> 24, '-3.06' -> -3.06, '' -> 'NA' (as R wrote it)."""
    text = text.strip()
    if not text:
        return 'NA'
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_sr_school_stats(html, season):
    """Team rows (keyed by FIELDS) from a school stats page (bytes or str)."""
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find(id='basic_school_stats')
    if table is None:
        raise ValueError("basic_school_stats table not found on the school stats page")
    rows = []
    for tr in table.select('tbody tr'):
        if 'thead' in (tr.get('class') or []):
            continue
        cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
        if 'school_name' not in cells or cells.get('ranker') is None:
            continue
        row = {}
        for stat, col in SR_COLUMNS.items():
            cell = cells.get(stat)
            text = cell.get_text(' ', strip=True) if cell is not None else ''
            if stat == 'school_name':
                row[col] = text.replace('NCAA', '').strip()
            else:
                row[col] = _sr_number(text)
        row['Season'] = f"{season[:4]}-{int(season[:4]) + 1}"
        rows.append(row)
    return rows


def scrape_sr_team_stats(season, session=None):
    """Fetch and parse one season's Sports-Reference school stats; returns (rows, url)."""
    url = sr_school_stats_url(season)
    resp = (session or requests).get(url, headers=SR_HEADERS, timeout=30)
    resp.raise_for_status()
    # Parse the bytes: SR sends no charset header, so resp.text would be
    # decoded as Latin-1 and mangle names like "Arkansas–Pine Bluff".
    return parse_sr_school_stats(resp.content, season), url
