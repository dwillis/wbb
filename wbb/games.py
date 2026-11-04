"""Game (box score + play-by-play) scraping.

Two sources, both written to <data_dir>/<slug>/<season>/<game_id>.json (the
wbb-game-data layout):

- Sidearm sites, ported from ncaa/games/game_utils.py (fetch_game_stats):
  game ids from the static stats page, falling back to the Playwright stats
  page's Game-By-Game tab; JSON from the site's /api/livestats endpoint.
- WMT sites (WMT_TEAMS), ported from ncaa/games/other_pbp.py: boxscore links
  from the schedule page, each boxscore page yields a WMT game id; JSON from
  api.wmt.games.

Both drop the original hardcoded paths and os.chdir calls.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from wbb.config import REPO_ROOT

logger = logging.getLogger(__name__)

GAME_DATA_DIR = REPO_ROOT.parent / "wbb-game-data"

# Teams whose games come from WMT (other_pbp.pbp_for_season's default list).
WMT_TEAMS = {31, 147, 234, 255, 312, 334, 365, 428, 463, 513, 523, 539, 328, 473, 626,
             674, 736, 742, 519, 746, 415, 648, 697}
# WMT teams whose schedule page needs browser headers and any /boxscore/ link.
WMT_DIRECT_TEAMS = {539, 463, 365, 77, 127, 234, 742, 312, 559}
WMT_HOST_OVERRIDES = {463: "https://huskers.com"}  # Nebraska

HEADERS = {'User-agent': 'Mozilla/5.0'}
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
WMT_API = ("https://api.wmt.games/api/statistics/games/{id}"
           "?with[0]=actions&with[1]=players&with[2]=plays&with[3]=drives&with[4]=penalties")


def resolve_game_data_dir(data_dir=None):
    """Resolve the game JSON directory: --data-dir flag, $WBB_GAME_DATA_DIR, or ../wbb-game-data."""
    return Path(data_dir or os.environ.get("WBB_GAME_DATA_DIR") or GAME_DATA_DIR)


def validate_season(season):
    """Raise ValueError unless season is 'YYYY-YY' with consecutive years (e.g. '2026-27')."""
    if not isinstance(season, str) or not re.fullmatch(r'\d{4}-\d{2}', season) \
            or int(season[5:7]) != (int(season[:4]) + 1) % 100:
        raise ValueError(f"Invalid season: '{season}' - expected format is 'YYYY-YY' (e.g., '2026-27')")


def slugify(team):
    """Directory slug, identical to game_utils.slugify (e.g. '539-penn-state')."""
    return str(team['ncaa_id']) + '-' + team['team'].lower().replace(" ", "-").replace('.', '').replace(
        ',', '').replace("'", "").replace(')', '').replace('(', '')


def _dedupe(ids):
    return list(dict.fromkeys(ids))


def fetch_game_ids_static(base_url, season):
    """Game ids from the static stats page's #game-team section (older Sidearm layout)."""
    r = requests.get(f"{base_url}/stats/{season}#game", headers=HEADERS, timeout=30)
    html = BeautifulSoup(r.text, features="html.parser")
    section = html.find('section', {'id': 'game-team'})
    if section is None:
        return []
    return [a['href'].split("id=")[1].replace("&path=wbball", "") for a in section.find_all('a')
            if 'id=' in a.get('href', '')]


def fetch_game_ids_playwright(browser, url, page_type='stats'):
    """Game ids from boxscore links on a rendered stats or schedule page."""
    page = browser.new_page()
    try:
        page.goto(url)
        if page_type == 'stats':
            page.click("text=Game-By-Game")
        page.wait_for_timeout(3000)
        ids = []
        for link in page.locator("a[href*='boxscore']").all():
            href = link.get_attribute("href")
            if not href:
                continue
            parts = href.rstrip("/").split("/")
            if parts and parts[-1].isdigit():
                ids.append(parts[-1])
            elif '=' in href and href.split("=")[1].replace("&path", '').isdigit():
                ids.append(href.split("=")[1].replace("&path", ''))
        return ids
    finally:
        page.close()


def fetch_game_json(domain, game_id):
    """Full livestats JSON for one game, or None."""
    url = f"https://{domain}/api/livestats?game_id={game_id}&detail=full"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def wmt_boxscore_links(team, season):
    """Boxscore page URLs from a WMT team's schedule page."""
    team_id = int(team['ncaa_id'])
    host = team['url'].split('/sports/')[0]
    url = f"{team['url']}/schedule/season/{season}/"
    if team_id in WMT_DIRECT_TEAMS:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"schedule page returned {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        host = WMT_HOST_OVERRIDES.get(team_id, host)
        links = [host + a['href'] for a in soup.find_all('a', href=True) if '/boxscore/' in a['href']]
    else:
        r = requests.get(url, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [host + a['href'] for a in soup.find_all('a', class_='schedule-event-link--boxscore')]
        if not links:
            # Newer schedule markup drops the class (e.g. New Mexico); take any boxscore link.
            links = [host + a['href'] for a in soup.find_all('a', href=True) if '/boxscore/' in a['href']]
    return _dedupe(links)


def wmt_game_id(boxscore_url):
    """WMT game id from a boxscore page (anchor to wmt.games, else embedded JS), or None."""
    r = requests.get(boxscore_url, headers=BROWSER_HEADERS, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    tag = [a for a in soup.find_all("a", href=True)
           if "wmt.games" in a['href'] and "/stats/match/full/" in a['href']]
    if tag:
        return tag[0]['href'].split('/')[-1]
    matches = re.findall(r'/stats/match/(?:full/)?(\d+)', r.text)
    return matches[0] if matches else None


def fetch_wmt_game_json(game_id):
    """WMT game JSON, or None when it has no play-by-play (e.g. not yet played)."""
    game = requests.get(WMT_API.format(id=game_id), timeout=60).json()
    plays = (game.get('data') or {}).get('plays') or {}
    return game if 'data' in plays else None


@dataclass
class GameOutcome:
    team_id: int
    team: str
    found: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    method: str = ''
    error: Optional[str] = None
    files: List[Path] = field(default_factory=list)

    @property
    def status(self):
        if self.error:
            return 'error'
        return 'ok' if self.found else 'zero'


class GameScraper:
    """Discovers and downloads game JSON for teams/seasons, sharing one browser."""

    def __init__(self, data_dir=None, headed=False, skip_existing=False,
                 on_team: Optional[Callable[[GameOutcome], None]] = None):
        self.data_dir = resolve_game_data_dir(data_dir)
        self.headed = headed
        self.skip_existing = skip_existing
        self.on_team = on_team
        self.results: List[GameOutcome] = []
        self._pw = None
        self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def _get_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=not self.headed)
        return self._browser

    def discover(self, team, season):
        """Return (game_ids, method) for a Sidearm team, static page first then Playwright."""
        base_url = team['url']
        try:
            ids = fetch_game_ids_static(base_url, season)
            if ids:
                return _dedupe(ids), 'static'
        except requests.RequestException as e:
            logger.debug(f"static stats page failed for {team['team']}: {e}")
        ids = fetch_game_ids_playwright(self._get_browser(), f"{base_url}/stats/{season}")
        return _dedupe(ids), 'playwright'

    def scrape_team(self, team, season) -> GameOutcome:
        outcome = GameOutcome(team['ncaa_id'], team['team'])
        is_wmt = int(team['ncaa_id']) in WMT_TEAMS
        try:
            if is_wmt:
                game_refs, outcome.method = wmt_boxscore_links(team, season), 'wmt'
            else:
                game_refs, outcome.method = self.discover(team, season)
        except Exception as e:
            # A missing Game-By-Game tab (no games posted yet) surfaces as a Playwright timeout.
            if type(e).__name__ == 'TimeoutError':
                logger.debug(f"no game list for {team['team']} {season}: {e}")
            else:
                outcome.error = str(e).splitlines()[0] if str(e) else type(e).__name__
            self._record(outcome)
            return outcome

        outcome.found = len(game_refs)
        out_dir = self.data_dir / slugify(team) / season
        domain = urlparse(team['url']).netloc
        for ref in game_refs:
            try:
                game_id = wmt_game_id(ref) if is_wmt else str(ref).split('&')[0]
                if game_id is None:
                    outcome.failed += 1
                    continue
                path = out_dir / f"{game_id}.json"
                if self.skip_existing and path.exists():
                    outcome.skipped += 1
                    continue
                game_json = fetch_wmt_game_json(game_id) if is_wmt else fetch_game_json(domain, game_id)
            except (requests.RequestException, ValueError) as e:
                logger.debug(f"game {ref} fetch failed: {e}")
                game_json = None
            if game_json is None:
                outcome.failed += 1
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(game_json, f, ensure_ascii=False, indent=4)
            outcome.saved += 1
            outcome.files.append(path)
        self._record(outcome)
        return outcome

    def _record(self, outcome):
        self.results.append(outcome)
        if self.on_team is not None:
            self.on_team(outcome)
