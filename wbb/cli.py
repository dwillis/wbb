"""wbb command-line interface.

Subcommands: scrape (full parity with the old rosters.py main()), export,
query, list-teams, games (game JSON downloads; see wbb/games.py), logs (game
log CSVs from the wbb-game-data archive; see wbb/logs.py), bios
(coach bio text fetching; see wbb/bios.py). All human
status goes to stderr; query/list-teams results
and the single-team JSON dump go to stdout; CSVs go to files.
"""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

from sqlite_utils import Database

from wbb import __version__, bios as wbb_bios, csvio, db as wbb_db, games as wbb_games
from wbb import logs as wbb_logs
from wbb.config import DB_PATH, ENTITY_CONFIGS, GAMES_DIR, TeamConfig, TEAMS_FILE, resolve_output_dir
from wbb.manager import RosterManager, TeamOutcome

logger = logging.getLogger(__name__)

SUMMARY_WIDTH = 64


def setup_logging(quiet: bool = False, verbose: bool = False):
    """Configure logging: --quiet -> WARNING (wins), --verbose -> DEBUG, else INFO."""
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')


def _fmt_path(p) -> str:
    """Path relative to cwd when possible, else absolute."""
    path = Path(p)
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


class _Progress:
    """Per-team progress on stderr: ephemeral 'ok' lines, persistent failure lines.

    Thread-safe: outcomes can arrive from parallel workers, so the counter
    increment and the stderr write happen under one lock (each line emitted
    atomically).
    """

    def __init__(self, total: int, entity_label: str):
        import threading
        self.total = total
        self.entity_label = entity_label
        self.count = 0
        self.enabled = sys.stderr.isatty()
        self._lock = threading.Lock()

    def _line(self, outcome) -> str:
        return f"[{outcome.n_players:3d} {self.entity_label}] {outcome.team} ({outcome.team_id})"

    def __call__(self, outcome):
        if not self.enabled:
            return
        with self._lock:
            self.count += 1
            if outcome.status == 'ok':
                sys.stderr.write(f"\r[{self.count:5d}/{self.total}] {self._line(outcome)}   ")
                sys.stderr.flush()
            else:
                if self.count > 1:
                    sys.stderr.write("\n")
                detail = {
                    'zero': f"no {self.entity_label} found",
                    'failed_verification': "failed season check",
                    'error': f"ERROR: {outcome.error}",
                }.get(outcome.status, outcome.status)
                sys.stderr.write(f"[{self.count:5d}/{self.total}] {outcome.team} ({outcome.team_id}) — {detail}\n")
                sys.stderr.flush()

    def finish(self):
        if self.enabled and self.count:
            sys.stderr.write("\n")
            sys.stderr.flush()


def _print_summary(title: str, managers, elapsed: float, output_files, db_info=None):
    """End-of-run summary; always printed (even with --quiet), to stderr.

    db_info: (Database, display_path) or None.
    """
    total_players = sum(o.n_players for m in managers for o in m.team_results)
    attempted = sum(len(m.team_results) for m in managers)
    lines = ["-" * SUMMARY_WIDTH, title,
             f"  teams attempted     {attempted}",
             f"  players scraped     {total_players:,}"]
    for m in managers:
        zero = len(m.zero_player_teams)
        failed = len(m.failed_year_check_teams)
        entity_label = ENTITY_CONFIGS[m.entity_type]['entity_label']
        if zero:
            sidecar = next((f for f, e in output_files if e == m.entity_type), None)
            lines.append(f"  zero-{entity_label} teams    {zero}"
                         + (f"      -> {str(sidecar).replace('.csv', f'_zero_{entity_label}.csv')}" if sidecar else ""))
        if failed:
            sidecar = next((f for f, e in output_files if e == m.entity_type), None)
            lines.append(f"  failed season check {failed}"
                         + (f"      -> {str(sidecar).replace('.csv', '_failed_year_check.csv')}" if sidecar else ""))
    mins, secs = divmod(int(elapsed), 60)
    lines.append(f"  elapsed             {mins}m {secs:02d}s")
    for f, e in output_files:
        lines.append(f"  csv ({ENTITY_CONFIGS[e]['entity_label']})".ljust(21) + str(f))
    if db_info is not None:
        database, db_display = db_info
        for table in wbb_db.TABLE_FOR_ENTITY.values():
            if table in database.table_names():
                lines.append(f"  db ({table})".ljust(21) + f"{db_display} ({database[table].count:,} rows)")
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()


def _resolve_output(args, entity_type, team_ids):
    """Default output path logic (old main() defaults, rooted at out_dir)."""
    out_dir = resolve_output_dir(args.out_dir)
    prefix = ENTITY_CONFIGS[entity_type]['csv_prefix']
    if args.output:
        return Path(args.output)
    if team_ids and len(team_ids) == 1:
        return out_dir / f"{prefix}_{args.season}_team_{team_ids[0]}.csv"
    return out_dir / f"{prefix}_{args.season}.csv"


def cmd_scrape(args) -> int:
    entity_types = ['player', 'coach'] if args.entity_type == 'all' else [args.entity_type]
    start = time.monotonic()

    # Single team with URL override (old main() early-return path)
    if args.url and args.team:
        first = entity_types[0]
        manager = RosterManager(entity_type=first, use_playwright=args.use_playwright,
                                teams_file=args.teams_file)
        teams = manager.get_teams([args.team])
        if teams:
            team_data = teams[0].copy()
            team_data['url'] = args.url
        else:
            team_data = {'ncaa_id': args.team, 'team': f'Team_{args.team}', 'url': args.url}

        players = manager.scrape_team_roster(team_data, args.season)
        year_check_failed = not manager._verify_team_season(team_data, args.season)
        if year_check_failed:
            manager.failed_year_check_teams.append({
                'team_id': team_data['ncaa_id'],
                'team_name': team_data.get('team', f'Team_{team_data["ncaa_id"]}'),
                'url': team_data['url']
            })
        if len(players) == 0 and not year_check_failed:
            manager.zero_player_teams.append({
                'team_id': team_data['ncaa_id'],
                'team_name': team_data.get('team', f'Team_{team_data["ncaa_id"]}')
            })
        manager._record_outcome(
            TeamOutcome(team_data['ncaa_id'], team_data.get('team', f'Team_{team_data["ncaa_id"]}'),
                        len(players), 'failed_verification' if year_check_failed
                        else ('zero' if not players else 'ok'), None))

        if args.db:
            wbb_db.upsert_entities(wbb_db.open_db(args.db), first, players, args.season,
                                   csvio.build_team_state_map(manager.teams_data))
        if args.output:
            output_file = Path(args.output)
            manager.save_to_csv(players, str(output_file))
            if manager.zero_player_teams:
                manager.save_zero_player_teams_to_csv(str(output_file).replace('.csv', '_zero_players.csv'))
            if manager.failed_year_check_teams:
                manager.save_failed_year_check_teams_to_csv(
                    str(output_file).replace('.csv', '_failed_year_check.csv'))
        else:
            for player in players:
                print(json.dumps(player.to_dict(), indent=2))
        return 1 if not players else 0

    # Multiple-teams path
    team_ids = args.teams or ([args.team] if args.team else None)
    is_all = args.entity_type == 'all'
    managers, output_files, total = [], [], 0

    for entity_type in entity_types:
        if is_all:
            logger.info(f"=== Scraping {ENTITY_CONFIGS[entity_type]['entity_label']} ===")
        manager = RosterManager(entity_type=entity_type, use_playwright=args.use_playwright,
                                teams_file=args.teams_file)
        progress = _Progress(len(manager.get_teams(team_ids, division=args.division)),
                             ENTITY_CONFIGS[entity_type]['entity_label'])
        manager.on_team = progress
        players = manager.scrape_multiple_teams(args.season, team_ids, workers=args.workers,
                                                division=args.division)
        progress.finish()
        manager.last_scraped = players
        managers.append(manager)

        output_file = _resolve_output(args, entity_type, team_ids)
        manager.save_to_csv(players, str(output_file))
        output_files.append((output_file, entity_type))

        # Sidecars (byte-identical naming to the old CLI)
        if manager.zero_player_teams:
            suffix = '_zero_coaches.csv' if (is_all and entity_type == 'coach') else '_zero_players.csv'
            manager.save_zero_player_teams_to_csv(str(output_file).replace('.csv', suffix))
        if manager.failed_year_check_teams and not (is_all and entity_type == 'coach'):
            manager.save_failed_year_check_teams_to_csv(
                str(output_file).replace('.csv', '_failed_year_check.csv'))
        total += len(players)

    database = wbb_db.open_db(args.db) if args.db else None
    if database is not None:
        for m in managers:
            if m.last_scraped:
                wbb_db.upsert_entities(database, m.entity_type, m.last_scraped, args.season,
                                       csvio.build_team_state_map(m.teams_data))

    _print_summary(f"Scrape complete: {args.season} {args.entity_type}", managers,
                   time.monotonic() - start, output_files,
                   (database, str(args.db)) if database is not None else None)

    return 0 if total >= 1 else 1


def cmd_export(args) -> int:
    db_path = args.db or DB_PATH
    if not Path(db_path).exists():
        sys.stderr.write(f"Database not found: {db_path} (scrape with --db first)\n")
        return 1

    database = wbb_db.open_db(db_path)
    entity_types = ['player', 'coach'] if args.entity_type == 'all' else [args.entity_type]
    wrote_any = False
    for entity_type in entity_types:
        table = wbb_db.TABLE_FOR_ENTITY[entity_type]
        if table not in database.table_names():
            sys.stderr.write(f"No '{table}' table in {db_path}\n")
            continue
        rows = list(database.query(f'SELECT * FROM "{table}" WHERE "season" = ?', [args.season]))
        output_file = _resolve_output(args, entity_type, None)
        fieldnames = ENTITY_CONFIGS[entity_type]['output_fields']
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        sys.stderr.write(f"Exported {len(rows)} rows to {output_file}\n")
        wrote_any = wrote_any or bool(rows)
    return 0 if wrote_any else 1


def cmd_query(args) -> int:
    db_path = args.db or DB_PATH
    if not Path(db_path).exists():
        sys.stderr.write(f"Database not found: {db_path}\n")
        return 1
    sql = args.sql.strip().rstrip(';')
    if not sql.lower().startswith(('select', 'with')):
        sys.stderr.write("Only SELECT/WITH statements are allowed.\n")
        return 2
    database = Database(str(db_path))
    rows = list(database.query(sql))
    if not rows:
        sys.stderr.write("No results.\n")
        return 0
    if args.format == 'json':
        json.dump(rows, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return 0


def cmd_list_teams(args) -> int:
    teams_file = args.teams_file or TEAMS_FILE
    if not Path(teams_file).exists():
        sys.stderr.write(f"Teams file not found: {teams_file}\n")
        return 1
    with open(teams_file) as f:
        teams = json.load(f)

    rows = []
    for t in teams:
        cfg = TeamConfig.get_config(t['ncaa_id'])
        rows.append({
            'ncaa_id': t['ncaa_id'], 'team': t['team'], 'conference': t.get('conference', ''),
            'division': t.get('division', ''), 'team_state': t.get('team_state', ''),
            'scraper_type': cfg['type'], 'url_format': cfg.get('url_format', 'default'),
            'url': t.get('url', ''),
        })
    if args.division:
        rows = [r for r in rows if r['division'] == args.division]
    if args.conference:
        rows = [r for r in rows if r['conference'].lower() == args.conference.lower()]
    if args.scraper_type:
        rows = [r for r in rows if r['scraper_type'] == args.scraper_type]

    if args.format == 'json':
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        fieldnames = ['ncaa_id', 'team', 'conference', 'division', 'team_state',
                      'scraper_type', 'url_format', 'url']
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return 0


def cmd_games(args) -> int:
    try:
        wbb_games.validate_season(args.season)
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2
    teams_file = args.teams_file or TEAMS_FILE
    if not Path(teams_file).exists():
        sys.stderr.write(f"Teams file not found: {teams_file}\n")
        return 1
    with open(teams_file) as f:
        teams = json.load(f)
    team_ids = args.teams or ([args.team] if args.team else None)
    if team_ids:
        teams = [t for t in teams if int(t['ncaa_id']) in team_ids]
    if args.division:
        teams = [t for t in teams if t.get('division') == args.division]
    if not teams:
        sys.stderr.write("No matching teams.\n")
        return 1

    start = time.monotonic()
    enabled = sys.stderr.isatty()
    state = {'count': 0}

    state = {'count': 0}
    last_len = [0]

    def ephemeral(text):
        """Overwrite the current stderr line, clearing any leftovers."""
        pad = ' ' * max(last_len[0] - len(text), 0)
        last_len[0] = len(text) + len(pad)
        sys.stderr.write("\r" + text + pad)
        sys.stderr.flush()

    def progress(o):
        if not enabled:
            return
        state['count'] += 1
        prefix = f"[{state['count']:5d}/{len(teams)}]"
        if o.status == 'ok':
            ephemeral(f"{prefix} [{o.saved:3d} games] {o.team} ({o.team_id})")
        else:
            detail = f"ERROR: {o.error}" if o.error else "no games found"
            sys.stderr.write("\n" if state['count'] > 1 else "")
            sys.stderr.write(f"{prefix} {o.team} ({o.team_id}) — {detail}\n")
            last_len[0] = 0
        sys.stderr.flush()

    def discovery_progress(phase, done, total):
        if not enabled:
            return
        ephemeral(f"[discovery {phase}] {done:5d}/{total}")

    with wbb_games.GameScraper(data_dir=args.data_dir, headed=args.headed,
                               skip_existing=args.skip_existing, workers=args.workers,
                               on_team=progress) as scraper:
        scraper.scrape_all(teams, args.season, on_discovery=discovery_progress)
    if enabled:
        sys.stderr.write("\n")

    results = scraper.results
    saved = sum(o.saved for o in results)
    mins, secs = divmod(int(time.monotonic() - start), 60)
    lines = ["-" * SUMMARY_WIDTH, f"Games complete: {args.season}",
             f"  teams attempted     {len(results)}",
             f"  teams with games    {sum(1 for o in results if o.found)}",
             f"  games saved         {saved:,}"]
    if args.skip_existing:
        lines.append(f"  games skipped       {sum(o.skipped for o in results):,}")
    failed = sum(o.failed for o in results)
    if failed:
        lines.append(f"  games failed        {failed:,}")
    errors = [o for o in results if o.error]
    if errors:
        lines.append(f"  team errors         {len(errors)}")
    lines.append(f"  elapsed             {mins}m {secs:02d}s")
    lines.append(f"  data dir            {scraper.data_dir}")
    sys.stderr.write("\n".join(lines) + "\n")
    return 0 if saved >= 1 else 1


def cmd_bios(args) -> int:
    # Fail fast with the install hint before any row work.
    wbb_bios._get_article_class()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.stderr.write(f"CSV file not found: {csv_path} (use --csv)\n")
        return 1
    output_path = Path(args.output) if args.output else csv_path.parent / "coach_bios.json"

    start = time.monotonic()
    enabled = sys.stderr.isatty()
    counts = {'fetched': 0, 'failed': 0, 'skipped': 0}

    # Newline handling for failed/skipped rows needs the counter; wrap it here.
    state = {'count': 0}

    def on_row_cb(idx, total, name, status, error):
        counts[status] += 1
        if not enabled:
            if status == 'failed':
                logger.warning("bio fetch failed for %s: %s", name, error)
            return
        state['count'] += 1
        if status == 'fetched':
            sys.stderr.write(f"\r[fetching {idx:5d}/{total}] {name}   ")
        else:
            detail = ('ERROR: ' + (error or '')) if status == 'failed' else 'already fetched'
            sys.stderr.write("\n" if state['count'] > 1 else "")
            sys.stderr.write(f"[{idx:5d}/{total}] {name} — {detail}\n")
        sys.stderr.flush()

    rows = wbb_bios.read_rows(csv_path)
    rows = wbb_bios.filter_rows(rows, names=args.names, team_ids=args.teams,
                                season=args.season, limit=args.limit,
                                shuffle=args.shuffle, demo=args.demo)
    if not rows:
        sys.stderr.write("No rows selected for processing. Nothing to do.\n")
        return 1

    skip_urls = set()
    existing = []
    if args.skip_existing:
        existing = wbb_bios.load_existing(output_path)
        skip_urls = wbb_bios.existing_urls(existing)

    results, _unused_failed = wbb_bios.fetch_bios(
        rows, language=args.language, skip_urls=skip_urls, on_row=on_row_cb)
    if enabled and state['count']:
        sys.stderr.write("\n")

    if results:
        data = wbb_bios.merge_results(existing, results) if args.skip_existing else results
        wbb_bios.write_json(data, output_path)
    else:
        # Unlike the standalone script, don't overwrite the JSON with an empty run.
        sys.stderr.write("No bios were successfully fetched; output not written.\n")

    mins, secs = divmod(int(time.monotonic() - start), 60)
    lines = ["-" * SUMMARY_WIDTH, "Coach bios complete",
             f"  rows selected       {len(rows)}",
             f"  bios fetched        {counts['fetched']:,}"]
    if counts['skipped']:
        lines.append(f"  bios skipped        {counts['skipped']:,}")
    if counts['failed']:
        lines.append(f"  bios failed         {counts['failed']:,}")
    if results:
        lines.append(f"  output json         {output_path} ({len(data):,} total records)"
                     if args.skip_existing else f"  output json         {output_path}")
    lines.append(f"  elapsed             {mins}m {secs:02d}s")
    sys.stderr.write("\n".join(lines) + "\n")
    return 0 if counts['fetched'] >= 1 else 1


def cmd_logs(args) -> int:
    division = args.division.upper()
    start = time.monotonic()
    try:
        rows, info = wbb_logs.build_game_logs(args.season, division,
                                              data_dir=args.data_dir)
    except (ValueError, FileNotFoundError) as e:
        sys.stderr.write(f"{e}\n")
        return 2

    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path(args.out_dir) / wbb_logs.output_name(args.season, division)
    wbb_logs.write_game_logs(rows, output_file)

    mins, secs = divmod(int(time.monotonic() - start), 60)
    lines = ["-" * SUMMARY_WIDTH, f"Game logs complete: {args.season} {division}",
             f"  teams with games    {info['teams']}",
             f"  games indexed       {info['indexed_games']:,}",
             f"  rows written        {info['rows']:,}"]
    if info['files_unreadable']:
        lines.append(f"  files unreadable    {info['files_unreadable']}")
    if info['rows_without_box_score']:
        lines.append(f"  rows w/o box score  {info['rows_without_box_score']:,} "
                     "(scores from the index only)")
    lines.append(f"  elapsed             {mins}m {secs:02d}s")
    lines.append(f"  csv                 {output_file}")
    lines.append(f"  data dir            {info['data_dir']}")
    sys.stderr.write("\n".join(lines) + "\n")
    return 0 if info['rows'] >= 1 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='wbb',
        description=f"NCAA women's basketball roster toolkit v{__version__} "
                    "(scrape | export | query | list-teams | games | logs | bios)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--db', nargs='?', const=str(DB_PATH), default=None, metavar='PATH',
                        help='Write/read the roster database (bare --db uses ncaa/rosters/rosters.db)')
    common.add_argument('--out-dir', default=None, metavar='DIR',
                        help='CSV output directory (default: ncaa/rosters, $WBB_OUTPUT_DIR)')
    common.add_argument('--verbose', action='store_true', help='Verbose (DEBUG) logging')
    common.add_argument('--quiet', action='store_true', help='Only warnings and the summary')

    sub = parser.add_subparsers(dest='command', required=True)

    p_scrape = sub.add_parser('scrape', parents=[common],
                              help='Scrape rosters to CSV (and optionally SQLite)')
    p_scrape.add_argument('-season', '-s', required=True, help='Season (e.g., "2025-26")')
    p_scrape.add_argument('-teams', nargs='*', type=int, help='Specific team IDs to scrape')
    p_scrape.add_argument('-team', type=int, help='Single team ID to scrape')
    p_scrape.add_argument('-output', '--out', dest='output', help='Output CSV file path')
    p_scrape.add_argument('-url', help='Base URL for single team scraping')
    p_scrape.add_argument('-entity', '--entity-type', choices=['player', 'coach', 'all'],
                          default='player', help='Entity to scrape (default: player)')
    p_scrape.add_argument('--division', choices=['I', 'II', 'III'],
                          help='Limit the run to teams in this division '
                               '(multiple-teams mode; ignored with -url)')
    p_scrape.add_argument('--use-playwright', action='store_true',
                          help='Use Playwright instead of shot-scraper for JS teams')
    p_scrape.add_argument('--workers', type=int, default=4, metavar='N',
                          help='Scrape N teams concurrently (default: 4; use 1 for the '
                               'old sequential behavior). Each JavaScript-registry team '
                               'runs its own browser, so high values multiply RAM use.')
    p_scrape.add_argument('--teams-file', default=None, help='Path to teams.json (default: ncaa/teams/teams.json)')
    p_scrape.set_defaults(func=cmd_scrape)

    p_export = sub.add_parser('export', parents=[common],
                              help='Export a season from the DB back to CSV')
    p_export.add_argument('-season', '-s', required=True, help='Season (e.g., "2025-26")')
    p_export.add_argument('-entity', '--entity-type', choices=['player', 'coach', 'all'],
                          default='player')
    p_export.add_argument('-output', '--out', dest='output', help='Output CSV file path')
    p_export.set_defaults(func=cmd_export)

    p_query = sub.add_parser('query', parents=[common], help='Run a read-only SQL query')
    p_query.add_argument('sql', help='SELECT/WITH statement')
    p_query.add_argument('--format', choices=['csv', 'json'], default='csv')
    p_query.set_defaults(func=cmd_query)

    p_list = sub.add_parser('list-teams', parents=[common],
                            help='List teams with their scraper configuration (no network)')
    p_list.add_argument('--division', choices=['I', 'II', 'III'])
    p_list.add_argument('--conference')
    p_list.add_argument('--type', dest='scraper_type',
                        choices=['standard', 'table', 'javascript', 'vue_data'])
    p_list.add_argument('--format', choices=['csv', 'json'], default='csv')
    p_list.add_argument('--teams-file', default=None, help='Path to teams.json')
    p_list.set_defaults(func=cmd_list_teams)

    p_games = sub.add_parser('games', help='Download game box score/play-by-play JSON')
    p_games.add_argument('--verbose', action='store_true', help='Verbose (DEBUG) logging')
    p_games.add_argument('--quiet', action='store_true', help='Only warnings and the summary')
    p_games.add_argument('-season', '-s', required=True, help='Season (e.g., "2026-27")')
    p_games.add_argument('-teams', nargs='*', type=int, help='Specific team IDs')
    p_games.add_argument('-team', type=int, help='Single team ID')
    p_games.add_argument('--division', choices=['I', 'II', 'III'])
    p_games.add_argument('--data-dir', default=None, metavar='DIR',
                         help='Game JSON directory (default: ../wbb-game-data, $WBB_GAME_DATA_DIR)')
    p_games.add_argument('--skip-existing', action='store_true',
                         help="Don't re-download games that already have a JSON file")
    p_games.add_argument('--headed', action='store_true', help='Show the Playwright browser window')
    p_games.add_argument('--workers', type=int, default=6,
                         help='Parallel request workers for discovery and game fetches (default: 6)')
    p_games.add_argument('--teams-file', default=None, help='Path to teams.json')
    p_games.set_defaults(func=cmd_games)

    p_logs = sub.add_parser('logs',
                            help='Build a game log CSV (wbblogs{YY}_{div}.csv) '
                                 'from the wbb-game-data archive')
    p_logs.add_argument('--verbose', action='store_true', help='Verbose (DEBUG) logging')
    p_logs.add_argument('--quiet', action='store_true', help='Only warnings and the summary')
    p_logs.add_argument('-s', '--season', required=True, help='Season (e.g., "2025-26")')
    p_logs.add_argument('-d', '--division', required=True, choices=['I', 'II', 'III'],
                        help='Division of the teams whose logs to build')
    p_logs.add_argument('-output', '--out', dest='output', default=None,
                        help='Output CSV file path (default: wbblogs{YY}_{i|ii|iii}.csv '
                             'in the output dir)')
    p_logs.add_argument('--out-dir', default=GAMES_DIR, metavar='DIR',
                        help='CSV output directory (default: ncaa/games)')
    p_logs.add_argument('--data-dir', default=None, metavar='DIR',
                        help='Game JSON directory (default: ../wbb-game-data, $WBB_GAME_DATA_DIR)')
    p_logs.set_defaults(func=cmd_logs)

    p_bios = sub.add_parser(
        'bios', help='Fetch coach bio page text from a coach roster CSV to JSON')
    p_bios.add_argument('--verbose', action='store_true', help='Verbose (DEBUG) logging')
    p_bios.add_argument('--quiet', action='store_true', help='Only warnings and the summary')
    p_bios.add_argument('-s', '--season', default=None,
                        help='Only fetch rows with this season column value (e.g., "2025-26")')
    p_bios.add_argument('--csv', default=str(wbb_bios.DEFAULT_CSV),
                        help='Input coach CSV (default: ncaa/coaches/coaches.csv)')
    p_bios.add_argument('--output', '--out', dest='output', default=None,
                        help='Output JSON file (default: coach_bios.json next to the input CSV)')
    p_bios.add_argument('--teams', nargs='*', type=int, help='Only these team IDs')
    p_bios.add_argument('--names', nargs='*', help='Only these coach names (exact match)')
    p_bios.add_argument('--limit', type=int, help='Process only the first N rows after filtering')
    p_bios.add_argument('--demo', action='store_true', help='Process only five rows')
    p_bios.add_argument('--shuffle', action='store_true', help='Shuffle rows before applying limit/demo')
    p_bios.add_argument('--skip-existing', action='store_true',
                        help='Skip urls already in the output JSON and merge new results into it')
    p_bios.add_argument('--language', default='en', help='Language hint for newspaper4k (default: en)')
    p_bios.set_defaults(func=cmd_bios)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(quiet=args.quiet, verbose=args.verbose)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        return 130
    except Exception as e:
        logger.error(f"Fatal: {e}")
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())