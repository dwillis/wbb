# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Rules

- **Always run Python scripts with `uv run python <script.py>`. Always.**
- **Never change existing working code without express permission.** Explain proposed changes, warn they could break working code, and wait for permission. When debugging, add instrumentation rather than changing logic.
- **When debugging CSV output issues, check field mapping first**: verify dataclass field names match CSV column names, check `to_dict()` transformations (e.g. `Player.year` maps to `academic_year`), and verify `output_fields` in `ENTITY_CONFIGS` — before debugging extraction logic.
- **Before adding a new team URL format, check whether that format already exists** in the scraper.
- Backup `.db` files before running update scripts against them.

## Common Commands

```bash
# Tests (from repo root; tests validate generated roster CSVs in ncaa/rosters/)
uv run pytest tests/
uv run pytest tests/test_ball_state_team_47_roster.py   # single test

# wbb CLI — scrape rosters (entry point installed by uv sync)
uv run wbb scrape -s 2025-26 -entity player             # all teams
uv run wbb scrape -s 2025-26 -teams 193 257 697          # specific team IDs
uv run wbb scrape -s 2025-26 -team 193 -url https://goduke.com  # custom URL
uv run wbb scrape -s 2025-26 -teams 47 433 --db          # also write SQLite
uv run wbb export -s 2025-26                             # season CSV from the DB
uv run wbb query "SELECT team, count(*) n FROM rosters GROUP BY team"
uv run wbb list-teams --type javascript                  # scraper config map (no network)
# Flags: -entity player|coach|all, --use-playwright, --quiet, --verbose, --out-dir, --teams-file

# Legacy shim (deprecated, forwards to the CLI — subcommand required):
uv run python ncaa/rosters/rosters.py scrape -s 2024-25 -team 47

# Coach data pipeline (from ncaa/coaches/)
uv run python fetch_coach_bios.py
uv run python analyze_coach_gender.py -m gpt-4o-mini   # LLM gender ID (needs `llm keys set openai`)
uv run python merge_coaching_data.py

# FIBA scraper (from fiba/) — multi-mode, caches HTTP requests
uv run python scrape_boxscore.py --mode events
uv run python scrape_boxscore.py --mode event-games --event-slug /worldcup/women/2022
uv run python scrape_boxscore.py --mode event-stats --event-slug /worldcup/women/2022
```

Season format is `"YYYY-YY"` (e.g. `"2025-26"`). JavaScript-heavy roster sites need `shot-scraper` (`uv tool install shot-scraper`) or Playwright (`playwright install chromium`); the `uv run shot-scraper` subprocess coupling means scraping should be run from inside the repo.

## Architecture

Data-journalism repo for women's basketball (NCAA, FIBA, WNBA, USWNT, TV ratings) — mostly scraper scripts plus committed CSV/JSON/SQLite data. `ncaa/` is the primary focus.

### wbb/ package — the roster scraper CLI (extracted from the old ncaa/rosters/rosters.py)

- **All scraping logic moved verbatim** from the old 3,858-line monolith; behavior parity is a hard constraint. `ncaa/rosters/rosters.py` is now a deprecated shim that delegates to `wbb.cli`.
- Module map: `models.py` (Player dataclass, `to_dict()` renames `year` → `academic_year`), `parsing.py` (FieldExtractors/HeaderMapper/SeasonVerifier), `templates.py` (JSTemplates — 968 lines of live-site JS, **never reformat**), `config.py` (URLBuilder, TeamConfig per-team dicts, ENTITY_CONFIGS, repo-relative path constants), `scrapers.py` (all 5 scrapers + factory, kept together — they share private helpers), `manager.py` (RosterManager + TeamOutcome/on_team hooks), `csvio.py` (CSV writers + row normalization), `db.py` (sqlite-utils persistence), `cli.py`.
- **CLI** (`wbb scrape|export|query|list-teams`): CSV is the primary output; `--db` additionally upserts into SQLite with replace-per-scope refresh (only rewrites rows for `(team_id, season)` pairs that returned ≥1 rows, so transient failures can't delete good data). Tables `rosters`/`coaches`, pk `(team_id, season, name)`; a legacy table without `scraped_at` is auto-renamed to `rosters_legacy` on first open.
- Output discipline: CSV → files; human status/progress/summary → **stderr**; `query`/`list-teams` results → **stdout**. Progress lines appear only on a TTY. Exit codes: 0 ≥1 row, 1 zero rows, 2 usage error.
- `ENTITY_CONFIGS` dict configures scraping per entity (`player`, `coach`): CSS selectors per field, `output_fields`, CSV prefix. Known quirk: the `get_config` vue_data dict-merge means only teams 72/731 actually use `VueDataScraper` — do not "fix".
- Team list comes from `ncaa/teams/teams.json` (git-ignored, so it is not package data — resolved at runtime, `--teams-file` overrides).
- Outputs land in `ncaa/rosters/`: `rosters_YYYY-YY.csv`, per-team `rosters_YYYY-YY_team_<id>.csv`, plus sidecars `rosters_YYYY-YY_failed_year_check.csv` and `rosters_YYYY-YY_zero_players.csv`. Override dir with `--out-dir` or `$WBB_OUTPUT_DIR`.

### updates/ — automated via GitHub Action (`.github/workflows/`, every 3 hours)

1. `transfers.py` and `coaching_changes.py` scrape WordPress posts from wbbblog.com (WP REST API) → `transfers.json`, `coaching_changes.json`
2. `dashboard.py` regenerates `dashboard.html`
3. `summarize_changes.py` diffs the JSON against HEAD to produce the commit message; the workflow auto-commits changes. Recent commits follow this pattern ("data: transfers added: ...", "chore: refresh data, no new entries [skip ci]").

### Data layout (ncaa/)

- `coaches/` — coaching histories/bios with LLM gender identification pipeline; `merged_schools.py` + `previous_schools.csv` for coach career paths
- `teams/` — team metadata (conferences, divisions, URLs, social); `check_urls.py` validates URLs
- `players/` — player data + `transfers.py` portal tracking
- `games/`, `officials/` — schedules, play-by-play, referee data
- `docs/` — per-subsystem docs worth reading before changes: `README_rosters_new.md` (scraper design), `COACHES_SCRAPING_PLAN.md`
- Databases: `ncaa.db`, `rosters.db`, `coaches.db`, `bios.db` (SQLite, via sqlite-utils)