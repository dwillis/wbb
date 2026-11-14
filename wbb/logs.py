"""Game log CSVs built from the wbb-game-data archive.

Produces one Sports-Reference-style game log CSV per division and season
(wbblogs{YY}_i|ii|iii.csv): every game played by every team in the requested
division, one row per team per game, with team and opponent box-score totals.

Sources, all inside the archive (default ../wbb-game-data):

- data/teams.json — the team manifest (name, ncaa_id, conference, division)
  that defines the division's teams and names opponents.
- index/seasons/{season}/d{1,2,3}.json — the per-division game index
  (date, home/visitor ids, scores, period scores, path to the raw file).
- raw game JSON files ({ncaa_id}-{slug}/{season}/{game_id}.json) for the
  box-score totals. Two feed formats are handled:
  * Sidearm livestats: Game/Stats with Stats.<Team>.Totals.Values
    (shooting as "made-att" strings) — mirrors wbb/games.py.
  * WMT ("data" wrapper): competitors[].teamStats[].statistic with
    s-prefixed keys; period 0 holds game totals (periods summed as fallback).

Rows are ordered by team name, then by date. Percent columns are fractions
rounded to 3 places (0.621), computed from made/attempted totals rather than
the feeds' rounded percentages. The four SRS columns the model file carries
are kept for schema parity but left "NA" — they come from Sports-Reference,
not from the game JSON.
"""

import csv
import json
from pathlib import Path

from wbb.games import resolve_game_data_dir

RAW_URL = "https://raw.githubusercontent.com/dwillis/wbb-game-data/main/"
MANIFEST_PATH = "data/teams.json"
DIVISION_KEYS = {'I': ('d1.json', 'i'), 'II': ('d2.json', 'ii'),
                 'III': ('d3.json', 'iii')}

# One team-side stat block, shared by the Team and Opponent halves of each row.
# The model CSV names the team half's effective-FG column "EFGPCT" (no prefix),
# while the opponent half keeps the prefix (OpponentEFGPCT).
_STAT_BLOCK = ['FG', 'FGA', 'FGPCT', '3P', '3PA', '3PPCT', '2P', '2PA', '2PPCT',
               'EFGPCT', 'FT', 'FTA', 'FTPCT', 'OffRebounds', 'DefRebounds',
               'TotalRebounds', 'Assists', 'Steals', 'Blocks', 'Turnovers',
               'PersonalFouls']

FIELDS = (['Season', 'Game', 'Date', 'GameType', 'TeamFullName', 'Opponent',
           'HomeAway', 'W_L', 'TeamScore', 'OpponentScore', 'OT']
          + ['EFGPCT' if c == 'EFGPCT' else 'Team' + c for c in _STAT_BLOCK]
          + ['Opponent' + c for c in _STAT_BLOCK]
          + ['URL', 'Conference', 'Team',
             'TeamSRS', 'TeamSOS', 'OpponentSRS', 'OpponentSOS'])

STAT_KEYS = ('fg', 'fga', 'pm', 'pa', 'ftm', 'fta', 'orb', 'drb', 'trb',
             'ast', 'stl', 'blk', 'to', 'pf')


def season_year(season):
    """Short year for the output filename: '2025-26' -> '26'."""
    return season[-2:]


def output_name(season, division):
    """Default output filename: wbblogs{year}_i|ii|iii.csv."""
    return f"wbblogs{season_year(season)}_{DIVISION_KEYS[division][1]}.csv"


# ---------------------------------------------------------------- manifest

def load_manifest(data_dir):
    """Team manifest keyed by ncaa_id."""
    with open(Path(data_dir) / MANIFEST_PATH) as f:
        teams = json.load(f)
    return {t['ncaa_id']: t for t in teams if t.get('ncaa_id') is not None}


# ------------------------------------------------------------ stat parsing

def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _split_range(s):
    """'49-110' -> (49, 110); anything else -> (None, None)."""
    if not isinstance(s, str) or '-' not in s:
        return None, None
    made, _, att = s.partition('-')
    try:
        return int(made), int(att)
    except ValueError:
        return None, None


def _blank_stats():
    return {key: None for key in STAT_KEYS}


def _sidearm_team_stats(side):
    """Box-score totals from a Sidearm Stats.<Team>.Totals block."""
    stats = _blank_stats()
    vals = ((side or {}).get('Totals') or {}).get('Values') or {}
    stats['fg'], stats['fga'] = _split_range(vals.get('Fgam'))
    stats['pm'], stats['pa'] = _split_range(vals.get('Tpam'))
    stats['ftm'], stats['fta'] = _split_range(vals.get('Ftma'))
    for key, field in (('OffensiveRebounds', 'orb'), ('DefensiveRebounds', 'drb'),
                       ('TotalRebounds', 'trb'), ('Assists', 'ast'),
                       ('Steals', 'stl'), ('Blocks', 'blk'),
                       ('Turnovers', 'to'), ('PersonalFouls', 'pf')):
        stats[field] = _num(vals.get(key))
    return stats


def _wmt_team_stats(competitor):
    """One WMT competitor's team totals (period-0 row, else periods summed)."""
    entries = competitor.get('teamStats') or []
    totals = None
    for ts in entries:
        if ts.get('period') == 0:
            totals = ts.get('statistic') or {}
            break
    if totals is None:
        # Older or partial payloads: sum the per-period stats instead.
        totals = {}
        for ts in entries:
            for key, value in (ts.get('statistic') or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value

    def g(key):
        return _num(totals.get(key))

    return {
        'fg': g('sFieldGoalsMade'), 'fga': g('sFieldGoalsAttempted'),
        'pm': g('sThreePointFieldGoalsMade'),
        'pa': g('sThreePointFieldGoalsAttempted'),
        'ftm': g('sFreeThrowsMade'), 'fta': g('sFreeThrowsAttempted'),
        'orb': g('sOffensiveRebounds'), 'drb': g('sDefensiveRebounds'),
        'trb': g('sTotalRebounds'), 'ast': g('sAssists'), 'stl': g('sSteals'),
        'blk': g('sBlocks'), 'to': g('sTurnovers'), 'pf': g('sPersonalFouls'),
    }


def _parse_game_json(data):
    """Box scores, feed names, scores and period counts for one raw game file.

    Returns {'home': ..., 'visitor': ...} dicts (each with 'name', 'score',
    'periods', 'stats'), or None when the payload matches neither format.
    """
    if isinstance(data, dict) and isinstance(data.get('Game'), dict) \
            and isinstance(data.get('Stats'), dict):
        game = data['Game']
        sides = {}
        for key, side in (('HomeTeam', 'home'), ('VisitingTeam', 'visitor')):
            info = game.get(key) or {}
            sides[side] = {
                'name': info.get('Name'),
                'score': _num(info.get('Score')),
                'periods': len(info.get('PeriodScores') or []),
                'stats': _sidearm_team_stats(data['Stats'].get(key) or {}),
            }
        return sides
    if isinstance(data, dict) and isinstance(data.get('data'), dict) \
            and isinstance(data['data'].get('competitors'), list):
        sides = {}
        for comp in data['data']['competitors']:
            periods = [ts.get('period') for ts in (comp.get('teamStats') or [])
                       if ts.get('period')]  # drops the period-0 totals row
            sides['home' if comp.get('homeTeam') else 'visitor'] = {
                'name': comp.get('nameTabular'),
                'score': _num(comp.get('score')),
                'periods': max(periods) if periods else 0,
                'stats': _wmt_team_stats(comp),
            }
        return sides if {'home', 'visitor'} <= set(sides) else None
    return None


def _resolve_sides(entry, parsed):
    """Decide which parsed side ('home'/'visitor') belongs to the manifest ids.

    Returns (home_id, visitor_id, home_key, visitor_key): the ids the two
    parsed sides belong to and which parsed side each is. WMT competitors
    carry a schoolId matching the manifest directly; otherwise the parsed
    scores are matched against the index's hs/vs (extracted from the same
    file). Falls back to the index order when neither works, and the index
    ids double as the fallback when the payload is missing or unreadable.
    """
    home_id, visitor_id = entry.get('h'), entry.get('v')
    home_key, visitor_key = 'home', 'visitor'

    home = (parsed or {}).get('home') or {}
    visitor = (parsed or {}).get('visitor') or {}
    home_score, visitor_score = home.get('score'), visitor.get('score')
    hs, vs = entry.get('hs'), entry.get('vs')
    if home_score is not None and visitor_score is not None and hs is not None:
        if (home_score, visitor_score) == (hs, vs):
            return home_id, visitor_id, 'home', 'visitor'
        if (home_score, visitor_score) == (vs, hs):
            return visitor_id, home_id, 'visitor', 'home'
    return home_id, visitor_id, home_key, visitor_key


# --------------------------------------------------------------- row fields

def _pct(made, att):
    if made is None or not att:
        return None
    return round(made / att, 3)


def _stat_block_values(stats):
    """Stat values in _STAT_BLOCK order for one team-side."""
    fg, fga, pm, pa = stats['fg'], stats['fga'], stats['pm'], stats['pa']
    twos_made = twos_att = None
    if None not in (fg, fga, pm, pa):
        twos_made, twos_att = fg - pm, fga - pa
    efg = None
    if fg is not None and fga:
        efg = round((fg + 0.5 * (pm or 0)) / fga, 3)
    return [fg, fga, _pct(fg, fga), pm, pa, _pct(pm, pa),
            twos_made, twos_att, _pct(twos_made, twos_att), efg,
            stats['ftm'], stats['fta'], _pct(stats['ftm'], stats['fta']),
            stats['orb'], stats['drb'], stats['trb'], stats['ast'],
            stats['stl'], stats['blk'], stats['to'], stats['pf']]


def _stat_fields(stats, prefix):
    """One team or opponent stat block, keyed with the model's column names.
    The team half's effective-FG column is named EFGPCT, without the prefix."""
    fields = {}
    for label, value in zip(_STAT_BLOCK, _stat_block_values(stats)):
        if label == 'EFGPCT':
            fields['EFGPCT' if prefix == 'Team' else 'OpponentEFGPCT'] = value
        else:
            fields[f"{prefix}{label}"] = value
    return fields


def _ot_label(periods):
    """'OT', '2OT', ... from total periods played (4 = regulation)."""
    if not periods or periods <= 4:
        return ''
    return 'OT' if periods == 5 else f'{periods - 4}OT'


# -------------------------------------------------------------- log builder

def _season_window(season):
    """(start_date, end_date) a game's d8 must fall in: July 1 through June 30.
    Guards against mis-filed raw payloads (a closed school's folder holding
    old games) leaking stale dates into a season's log."""
    start = int(season[:4])
    return (f"{start}-07-01", f"{start + 1}-06-30")


def build_game_logs(season, division, data_dir=None):
    """Build the game log rows for one division and season.

    Returns (rows, info); rows are dicts keyed by FIELDS, ordered by team
    name then game date, and info carries summary counters for the CLI.
    """
    data_dir = Path(resolve_game_data_dir(data_dir))
    index_file = data_dir / 'index' / 'seasons' / season / DIVISION_KEYS[division][0]
    if not index_file.exists():
        raise FileNotFoundError(f"No division index for {season}: {index_file}")
    with open(index_file) as f:
        entries = json.load(f).get('games', [])
    window_start, window_end = _season_window(season)
    all_entries = len(entries)
    entries = [e for e in entries
               if window_start <= (e.get('d8') or '') <= window_end]
    manifest = load_manifest(data_dir)
    division_ids = {tid for tid, team in manifest.items()
                    if team.get('division') == division}

    # Raw files are shared between a team's row and its opponent's, so each
    # file is read, parsed and id-mapped once per run.
    parsed_cache = {}
    side_map_cache = {}
    unreadable = 0
    for entry in entries:
        src = entry.get('src')
        if not src or src in parsed_cache:
            continue
        parsed_cache[src] = None
        try:
            with open(data_dir / src) as f:
                parsed_cache[src] = _parse_game_json(json.load(f))
        except (OSError, json.JSONDecodeError):
            unreadable += 1
        if parsed_cache[src] is not None:
            side_map_cache[src] = _resolve_sides(entry, parsed_cache[src])

    # Games per division team, in one entry per (team, game).
    team_games = {tid: [] for tid in division_ids}
    for entry in entries:
        for key in ('h', 'v'):
            if entry.get(key) in team_games:
                team_games[entry[key]].append(entry)

    rows = []
    rows_without_box = 0
    for tid in sorted(team_games,
                      key=lambda t: (manifest[t].get('team') or '').lower()):
        games = sorted(team_games[tid],
                       key=lambda entry: (entry.get('d8') or '', str(entry.get('id'))))
        for game_no, entry in enumerate(games, start=1):
            src = entry.get('src') or ''
            if src in side_map_cache:
                home_id, visitor_id, home_key, visitor_key = side_map_cache[src]
            else:
                home_id, visitor_id = entry.get('h'), entry.get('v')
                home_key, visitor_key = 'home', 'visitor'
            parsed = parsed_cache.get(src)
            if parsed is None:
                rows_without_box += 1
            rows.append(_row(entry, tid, parsed, manifest, season, game_no,
                             home_id, visitor_id, home_key, visitor_key))

    info = {
        'season': season,
        'division': division,
        'teams': len(team_games),
        'indexed_games': all_entries,
        'entries_outside_season_window': all_entries - len(entries),
        'rows': len(rows),
        'rows_without_box_score': rows_without_box,
        'files_unreadable': unreadable,
        'data_dir': data_dir,
    }
    return rows, info


def _row(entry, team_id, parsed, manifest, season, game_no,
         home_id, visitor_id, home_key, visitor_key):
    """One team's game-log row for one index entry."""
    team = manifest.get(team_id, {})
    team_name = team.get('team') or ''
    my_conf = team.get('conference') or ''
    is_home = home_id == team_id
    opp_id = visitor_id if is_home else home_id
    opp = manifest.get(opp_id)
    if opp is not None:
        opp_name, opp_conf = opp.get('team') or '', opp.get('conference') or ''
    else:
        opp_name, opp_conf = entry.get('vn') or entry.get('hn') or '', ''

    my_side = (parsed or {}).get('home' if is_home else visitor_key) or {}
    opp_side = (parsed or {}).get(visitor_key if is_home else home_key) or {}

    # The raw feed is authoritative on scores when it carries both sides;
    # otherwise fall back to the index scores for the row's team.
    if my_side.get('score') is not None and opp_side.get('score') is not None:
        team_score = my_side['score']
        opp_score = opp_side['score']
        got_scores = True
    else:
        team_score = entry.get('hs' if is_home else 'vs')
        opp_score = entry.get('vs' if is_home else 'hs')
        got_scores = team_score is not None and opp_score is not None

    my_stats = my_side.get('stats') or _blank_stats()
    opp_stats = opp_side.get('stats') or _blank_stats()

    if my_conf and opp_conf and my_conf == opp_conf:
        game_type = 'REG (Conf)'
    else:
        game_type = 'REG (Non-Conf)'

    my_periods = my_side.get('periods')
    if not my_periods:
        my_periods = len(entry.get('hp' if is_home else 'vp') or [])

    row = {
        'Season': f"{season[:4]}-{int(season[:4]) + 1}",
        'Game': game_no,
        'Date': entry.get('d8') or '',
        'GameType': game_type,
        'TeamFullName': team_name or (my_side.get('name') or ''),
        'Opponent': opp_name or (opp_side.get('name') or ''),
        'HomeAway': '' if is_home else '@',
        'W_L': ('W' if (got_scores and team_score > opp_score)
                else ('L' if got_scores else '')),
        'TeamScore': team_score,
        'OpponentScore': opp_score,
        'OT': _ot_label(my_periods),
        'URL': (RAW_URL + entry['src']) if entry.get('src') else '',
        'Conference': my_conf,
        'Team': team_name or (my_side.get('name') or ''),
        'TeamSRS': 'NA', 'TeamSOS': 'NA', 'OpponentSRS': 'NA', 'OpponentSOS': 'NA',
    }
    row.update(_stat_fields(my_stats, 'Team'))
    row.update(_stat_fields(opp_stats, 'Opponent'))
    return row


# ----------------------------------------------------------------- writing

def write_game_logs(rows, path):
    """Write the game log rows as CSV; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    return path
