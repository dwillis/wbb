"""Player season stats CSVs scraped from Sports-Reference (women's college basketball).

Python port of ncaa/ScrapingBasketballPlayers.Rmd. For one season:

1. Read the season's school stats page
   (/cbb/seasons/women/{YYYY}-school-stats.html) for every school's link.
2. For each school page (/cbb/schools/{slug}/women/{YYYY}.html), take the
   roster table, the players_totals table and the players_advanced table
   (served inside an HTML comment), and left-join them onto the roster.
3. Add Team, Conference and Season and write one CSV for all schools.

Differences from the Rmd, all deliberate:

- The season drives both the URL year and the Season column (the Rmd had a
  2022 URL hardcoded against a "2025-2026" label).
- Tables are joined on Sports-Reference's player id (data-append-csv), not
  on the display name, so two players with the same name can't cross-join.
- Columns use the page's header labels (Player, Class, G, FG%, PER, ...)
  with each stat kept once: the duplicated Pos/G/GS/MP columns from the
  totals and advanced tables and the Rk/Awards columns are dropped, so there
  are no Pos.x/Pos.y suffixes. A player_id column is added.
- Team is the school name from the school stats table ("Abilene Christian"),
  which matches the School column of `wbb stats`; Conference is the
  conference link text without the trailing " WBB".

Sports-Reference allows about 20 requests a minute and blocks clients that
go faster, so requests are spaced by `delay` seconds (default 3.5) and a 429
stops the run rather than retrying into a longer block.
"""

import csv
import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Comment

from wbb.config import REPO_ROOT

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sports-reference.com"
PLAYERS_DIR = REPO_ROOT / "ncaa" / "players"
DEFAULT_DELAY = 3.5
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

# Stats repeated across tables (kept from the first table that has them) and
# per-table bookkeeping columns that aren't carried into the output.
_SKIP = {'ranker', 'name_display', 'player', 'awards'}


class RateLimited(Exception):
    """Sports-Reference answered 429; continuing would extend the block."""


def sr_year(season):
    """'2025-26' -> 2026 (Sports-Reference names seasons by their end year)."""
    return int(season[:4]) + 1


def season_label(season):
    """'2025-26' -> '2025-2026', the Rmd's Season column format."""
    return f"{season[:4]}-{sr_year(season)}"


def output_name(season):
    """Default output filename: players{YY}.csv, as the Rmd wrote players22.csv."""
    return f"players{season[-2:]}.csv"


class Fetcher:
    """requests session that spaces requests at least `delay` seconds apart."""

    def __init__(self, delay=DEFAULT_DELAY, session=None):
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self._last = 0.0

    def get(self, url):
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(url, timeout=30)
        finally:
            self._last = time.monotonic()
        if resp.status_code == 429:
            raise RateLimited(f"429 from {url} (Retry-After: "
                              f"{resp.headers.get('Retry-After', 'unknown')})")
        resp.raise_for_status()
        return resp.text


# ------------------------------------------------------------------ parsing

def parse_school_list(html):
    """[(school name, path)] from the season school stats page."""
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find(id='basic_school_stats')
    if table is None:
        raise ValueError("basic_school_stats table not found on the school stats page")
    schools = []
    for cell in table.select('tbody td[data-stat="school_name"]'):
        a = cell.find('a')
        if a and a.get('href'):
            schools.append((a.get_text(strip=True), a['href']))
    return schools


def _find_table(soup, table_id):
    """A table by id, including ones Sports-Reference ships inside comments."""
    table = soup.find(id=table_id)
    if table is not None:
        return table
    marker = f'id="{table_id}"'
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if marker in comment:
            return BeautifulSoup(comment, 'lxml').find(id=table_id)
    return None


def _table_rows(table):
    """(columns, rows) for one stats table.

    columns is [(data_stat, header label)] in page order; rows is a list of
    (player_id, {data_stat: text}). Only tbody rows with a player are kept,
    so header repeats and the Team Totals footer drop out.
    """
    if table is None:
        return [], []
    head = table.select('thead tr')
    labels = {}
    columns = []
    if head:
        for th in head[-1].find_all('th'):
            stat = th.get('data-stat')
            if stat:
                columns.append((stat, th.get_text(strip=True)))
                labels[stat] = th.get_text(strip=True)
    rows = []
    for tr in table.select('tbody tr'):
        if 'thead' in (tr.get('class') or []):
            continue
        cells = {c.get('data-stat'): c.get_text(strip=True)
                 for c in tr.find_all(['th', 'td']) if c.get('data-stat')}
        id_cell = tr.find(attrs={'data-append-csv': True})
        player_id = id_cell['data-append-csv'] if id_cell else None
        name = cells.get('player') or cells.get('name_display')
        if not name:
            continue
        rows.append((player_id or name, cells))
    return columns, rows


def _conference(soup):
    meta = soup.find(id='meta')
    if meta is None:
        return ''
    a = meta.find('a', href=re.compile(r'/cbb/conferences/'))
    if a is None:
        return ''
    return re.sub(r'\s+WBB$', '', a.get_text(strip=True))


def parse_school_page(html, team, season):
    """(columns, rows) for one school: the roster left-joined with totals and
    advanced. columns is [(key, label)]; rows are dicts keyed by key."""
    soup = BeautifulSoup(html, 'lxml')
    conference = _conference(soup)
    tables = [_table_rows(_find_table(soup, tid))
              for tid in ('roster', 'players_totals', 'players_advanced')]

    columns = [('team', 'Team'), ('player_id', 'player_id'), ('player', 'Player')]
    seen = {'team', 'player_id', 'player'}
    for cols, _rows in tables:
        for stat, label in cols:
            if stat in _SKIP or stat in seen:
                continue
            seen.add(stat)
            columns.append((stat, label))
    columns += [('conference', 'Conference'), ('season', 'Season')]

    roster_cols, roster = tables[0]
    by_id = [dict(rows) for _cols, rows in tables[1:]]
    out = []
    for player_id, cells in roster:
        row = {'team': team, 'player_id': player_id, 'player': cells.get('player', ''),
               'conference': conference, 'season': season_label(season)}
        for stat, value in cells.items():
            if stat not in _SKIP:
                row.setdefault(stat, value)
        for lookup in by_id:
            for stat, value in (lookup.get(player_id) or {}).items():
                if stat not in _SKIP:
                    row.setdefault(stat, value)
        out.append(row)
    return columns, out


# ------------------------------------------------------------------ scraping

def school_stats_url(season):
    return f"{BASE_URL}/cbb/seasons/women/{sr_year(season)}-school-stats.html"


def scrape_players(season, schools=None, limit=None, delay=DEFAULT_DELAY,
                   fetcher=None, on_school=None):
    """Scrape every school's players for one season.

    schools: optional iterable of URL slugs ('abilene-christian') or school
    names to restrict the run. on_school(idx, total, team, n_rows, error) is
    called after each school. Returns (columns, rows, info); a 429 stops the
    run early with info['rate_limited'] set and the rows scraped so far.
    """
    fetcher = fetcher or Fetcher(delay=delay)
    school_list = parse_school_list(fetcher.get(school_stats_url(season)))
    if schools:
        wanted = {s.lower() for s in schools}
        school_list = [(name, path) for name, path in school_list
                       if name.lower() in wanted
                       or path.split('/')[3].lower() in wanted]
    if limit:
        school_list = school_list[:limit]

    columns, seen, rows = [], set(), []
    info = {'schools': len(school_list), 'schools_ok': 0, 'schools_failed': [],
            'schools_empty': [], 'rate_limited': None}
    for idx, (team, path) in enumerate(school_list, start=1):
        try:
            cols, team_rows = parse_school_page(fetcher.get(BASE_URL + path), team, season)
        except RateLimited as e:
            info['rate_limited'] = str(e)
            if on_school:
                on_school(idx, len(school_list), team, 0, str(e))
            break
        except (requests.RequestException, ValueError) as e:
            info['schools_failed'].append((team, str(e)))
            if on_school:
                on_school(idx, len(school_list), team, 0, str(e))
            continue
        for col in cols:
            if col[0] not in seen:
                seen.add(col[0])
                columns.append(col)
        rows.extend(team_rows)
        if team_rows:
            info['schools_ok'] += 1
        else:
            info['schools_empty'].append(team)
        if on_school:
            on_school(idx, len(school_list), team, len(team_rows), None)

    # Keep Conference and Season last, as the Rmd's mutate() put them.
    tail = [c for c in columns if c[0] in ('conference', 'season')]
    columns = [c for c in columns if c[0] not in ('conference', 'season')] + tail
    info['rows'] = len(rows)
    return columns, rows, info


def write_players(columns, rows, path):
    """Write the player rows as CSV with the page's header labels; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([label for _key, label in columns])
        for row in rows:
            writer.writerow([row.get(key, '') for key, _label in columns])
    return path
