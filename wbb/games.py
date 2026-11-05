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
from typing import Callable, List, Optional, Tuple
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
        """Game ids from boxscore links on a rendered stats or schedule page.

        Waits for the boxscore links to appear (event-based) instead of a fixed
        sleep; falls back to the old 3s wait when no link appears by timeout
        (sites with different link markup)."""
        page = browser.new_page()
        try:
            page.goto(url)
            if page_type == 'stats':
                page.click("text=Game-By-Game")
            try:
                page.wait_for_selector("a[href*='boxscore']", timeout=10000, state='attached')
            except Exception:
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


class _NeedsBrowser(Exception):
    """Internal: the static stats page had nothing; Playwright fallback needed."""


class GameScraper:
    """Discovers and downloads game JSON for teams/seasons.

    scrape_all() runs three phases so the shared browser stays single-threaded
    (sync Playwright is not): (1) requests-only discovery in a thread pool,
    (2) Playwright discovery for teams whose static page had nothing,
    (3) game JSON fetches in the thread pool. scrape_team() remains as the
    single-team form; file writes land on unique paths, so workers share
    nothing else mutable — outcomes are assembled in the main thread.
    """

    def __init__(self, data_dir=None, headed=False, skip_existing=False, workers=6,
                 on_team: Optional[Callable[[GameOutcome], None]] = None):
        self.data_dir = resolve_game_data_dir(data_dir)
        self.headed = headed
        self.skip_existing = skip_existing
        self.workers = workers
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

    def _requests_discovery(self, team, season):
        """Phase 1 discovery: requests only. Raises _NeedsBrowser for the Playwright path."""
        if int(team['ncaa_id']) in WMT_TEAMS:
            return _dedupe(wmt_boxscore_links(team, season)), 'wmt'
        try:
            ids = fetch_game_ids_static(team['url'], season)
        except requests.RequestException as e:
            logger.debug(f"request discovery for {team['team']}: {e} -> trying browser")
            raise _NeedsBrowser(team['team']) from e
        if not ids:
            raise _NeedsBrowser(team['team'])
        return _dedupe(ids), 'static'

    def _fetch_one(self, team, season, ref, out_dir, domain) -> Tuple[str, Optional[Path]]:
        """One game's JSON fetch: returns ('saved'|'skipped'|'failed', path)."""
        is_wmt = int(team['ncaa_id']) in WMT_TEAMS
        try:
            if is_wmt:
                game_id = wmt_game_id(ref)
                game_json = fetch_wmt_game_json(game_id) if game_id is not None else None
            else:
                game_id = str(ref).split('&')[0]
                game_json = fetch_game_json(domain, game_id) if game_id else None
        except (requests.RequestException, ValueError) as e:
            logger.debug(f"game {ref} fetch failed: {e}")
            return 'failed', None
        if not game_id or game_json is None:
            return 'failed', None
        path = out_dir / f"{game_id}.json"
        if self.skip_existing and path.exists():
            return 'skipped', None
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(game_json, f, ensure_ascii=False, indent=4)
        return 'saved', path

    def scrape_all(self, teams, season, on_discovery=None) -> List[GameOutcome]:
        """Pipelined run over all teams; returns outcomes in completion order.

        Phases: (1) requests-only discovery in a thread pool, (2) sequential
        Playwright discovery for teams the static page couldn't serve — with
        each team's game fetches queued into the same pool as its discovery
        finishes so downloads overlap the browser work, (3) a final blocking
        drain of any fetches still queued. Outcomes are finalized in the main
        thread (workers share nothing mutable), so on_team/on_discovery
        callbacks are safe.

        on_discovery(phase, done, total) fires per completed discovery for CLI
        progress; phase is 'requests' or 'playwright'.
        """
        outcomes = [GameOutcome(t['ncaa_id'], t['team']) for t in teams]
        discovered: List[Optional[Tuple[List[str], str]]] = [None] * len(teams)
        n = len(teams)

        def discover_job(i):
            try:
                return i, self._requests_discovery(teams[i], season), None
            except _NeedsBrowser as e:
                return i, None, ('browser', e)
            except Exception as e:
                return i, None, ('error', e)

        def fetch_job(i):
            refs = discovered[i][0] if discovered[i] else []
            if not refs:
                return i, []
            out_dir = self.data_dir / slugify(teams[i]) / season
            domain = urlparse(teams[i]['url']).netloc
            return i, [(self._fetch_one(teams[i], season, ref, out_dir, domain), ref)
                       for ref in refs]

        def finalize(i, per):
            outcome = outcomes[i]
            if discovered[i]:
                outcome.method = discovered[i][1]
                outcome.found = len(per)
            for (status, path), _ref in per:
                if status == 'saved':
                    outcome.saved += 1
                    outcome.files.append(path)
                elif status == 'skipped':
                    outcome.skipped += 1
                else:
                    outcome.failed += 1
            self.results.append(outcome)
            if self.on_team is not None:
                self.on_team(outcome)

        from concurrent.futures import (ThreadPoolExecutor, as_completed, wait,
                                        FIRST_COMPLETED)
        with ThreadPoolExecutor(max_workers=max(1, self.workers)) as pool:
            # Phase 1: requests-only discovery for every team.
            logger.info(f"discovering (static/wmt requests): {n} teams, {self.workers} workers")
            pending: dict = {}
            need_browser: List[int] = []
            done1 = 0
            for fut in as_completed([pool.submit(discover_job, i) for i in range(n)]):
                i, refs, err = fut.result()
                if err is None:
                    game_ids, method = refs
                    discovered[i] = (game_ids, method)
                elif err[0] == 'browser':
                    need_browser.append(i)
                else:
                    e = err[1]
                    outcomes[i].error = str(e).splitlines()[0] if str(e) else type(e).__name__
                done1 += 1
                if on_discovery is not None:
                    on_discovery('requests', done1, n)

            # Queue fetches for everything requests discovered, then overlap
            # the Playwright teams' discovery with those downloads.
            for i, di in enumerate(discovered):
                if di is not None and di[0]:
                    pending[pool.submit(fetch_job, i)] = i

            # Phase 2: Playwright discovery, sequential (one shared browser).
            if need_browser:
                logger.info(f"discovering (browser): {len(need_browser)} teams, sequential")
            for j, i in enumerate(need_browser, 1):
                team = teams[i]
                try:
                    refs, method = self.discover(team, season)
                    discovered[i] = (refs, method)
                except Exception as e:
                    # A missing Game-By-Game tab (no games posted yet) surfaces as a timeout.
                    if type(e).__name__ == 'TimeoutError':
                        logger.debug(f"no game list for {team['team']} {season}: {e}")
                        discovered[i] = ([], 'playwright')
                    else:
                        outcomes[i].error = str(e).splitlines()[0] if str(e) else type(e).__name__
                if discovered[i]:
                    pending[pool.submit(fetch_job, i)] = i
                    # Stream any fetches that finished while the browser worked.
                    if pending:
                        done, _ = wait(set(pending), timeout=0, return_when=FIRST_COMPLETED)
                        for f in done:
                            (i_done, per) = f.result()
                            finalize(i_done, per)
                            del pending[f]
                if on_discovery is not None:
                    # Same denominator as phase 1 / the team lines: phases so
                    # far = requests-only teams (done1 minus browser teams) + browser done.
                    on_discovery('playwright', done1 - len(need_browser) + j, n)

            # Phase 3: block until all queued fetches finish, then finalize
            # the rest (teams whose discovery errored never enter the pool).
            if pending:
                done, _ = wait(set(pending))
                for f in done:
                    i, per = f.result()
                    finalize(i, per)
            for i in range(n):
                if discovered[i] is None:
                    finalize(i, [])
        return self.results

    def scrape_team(self, team, season) -> GameOutcome:
        """Sequential single-team convenience path."""
        return self.scrape_all([team], season)[0]

    def _record(self, outcome):
        self.results.append(outcome)
        if self.on_team is not None:
            self.on_team(outcome)
