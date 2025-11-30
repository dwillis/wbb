# NCAA Women's Basketball Data Repository

This repository contains data, scripts, and analysis tools for NCAA women's basketball programs.

## Directory Structure

### `/coaches`
Coach-related data and scripts:
- **Data Files:**
  - `coaching_histories.json` - Complete coaching position histories
  - `coaching_histories_merged.csv` - Merged coaching data with team info and gender
  - `coach_bios.json` - Coach biography text
  - `coach_bios_gender.json` - Coach bios with gender identification
  - `coaches.json` / `coaches.csv` - Current coaches data
  - `coaching_changes.csv` - Historical coaching changes
  - `positions_standardized.csv` - Standardized position titles
  - `distinct_colleges.csv` - College name standardization
  - `coaches.db` / `bios.db` - Coach databases

- **Scripts:**
  - `bios.py` - Coach biography processing
  - `fetch_coach_bios.py` - Scrape coach biographies
  - `extract_coaching_histories.py` - Extract career histories
  - `analyze_coach_gender.py` - Determine gender from pronouns using LLM
  - `add_gender_to_histories.py` - Add gender to merged histories
  - `merge_coaching_data.py` - Merge coaching data with team/college info
  - `build_coach_db.py` - Build coach database
  - `load_coaching_histories.py` - Load coaching histories
  - `check_and_add_colleges.py` - Validate and add missing colleges
  - `coaching_networks_analysis.Rmd` - Network analysis

### `/players`
Player-related data:
- `players.json` / `players.csv` - Player information
- `player404.csv` - Missing player records
- `players_empty.csv` - Players with incomplete data
- `transfers.py` - Transfer portal tracking
- `person20201204.csv` - Historical player data

### `/teams`
Team-related data and scripts:
- `teams.json` / `teams.csv` - Team information with metadata
- `ncaa_teams.csv` - NCAA team listings
- `teams_utils.py` - Team utility functions
- `missing_teams.csv` - Teams not yet in database
- `team_url_checks.csv` - URL validation results
- `team_fouls_location.csv` / `teams_fouls_location_season.csv` - Foul location data
- `following.csv` / `home_teams.csv` / `hhs_twitter.csv` - Social media tracking
- `check_urls.py` - URL validation script
- `convert_teams_to_csv.py` - Format conversion

### `/rosters`
Roster scraping and data:
- **Main Script:**
  - `rosters.py` - Primary roster scraping tool

- **Data Files:**
  - `rosters_YYYY-YY.csv` - Roster data by season
  - `rosters_YYYY-YY_failed_year_check.csv` - Failed validation records
  - `rosters_YYYY-YY_zero_players.csv` - Teams with no players found
  - `rosters.db` - Roster database
  - `compare_rosters.py` - Compare rosters across seasons

### `/games`
Game data and play-by-play:
- `games.json` - Game schedules and results
- `game.py` - Game data processing
- `game_utils.py` - Game utility functions
- `ncaa_games.csv` / `ncaa_games.db` - NCAA game database
- `game_file_counts_all_seasons.csv` - Data coverage statistics
- `game_officials_YYYY-YY.csv` - Officials data by season
- `312-iowa_YYYY-YY_plays.csv` - Play-by-play data (Iowa examples)
- `other_pbp.py` - Alternative play-by-play parsing
- `tourney_games.rb` - Tournament game tracking

### `/officials`
Officials and referees data (maintained as separate subdirectory)

### `/stats`
Statistics and analytics (maintained as separate subdirectory)

### `/scripts`
General utility scripts:
- `utils.py` - Common utility functions
- `matching.py` - Data matching/merging utilities
- `process_json.py` - JSON processing
- `build_db.py` - Database building
- `test.py` - Testing utilities

### `/data`
General data files and databases:
- `ncaa.db` - Main NCAA database
- `ncaa2019.csv` / `ncaa_history.csv` - Historical data
- `geckodriver.log` - Selenium logs

### `/docs`
Documentation:
- `README_rosters_new.md` - Roster scraping documentation
- `COACHES_SCRAPING_PLAN.md` - Coach data collection plan
- `extraction_prompt.md` - LLM extraction prompts
- `free_throw_rate.md` - Analysis notes
- `ncaa_twitter_names_2022.sql` - SQL reference

## Core Files (Root Level)
- `__init__.py` - Python package initialization
- `.ruby-version` - Ruby version specification
- `__pycache__/` - Python cache directory
- `.claude/` - AI assistant configuration

## Usage

Most scripts can be run using `uv run python <script_name.py>`. For example:

```bash
# Scrape rosters for a season
cd rosters
uv run python rosters.py -season 2024-25 -entity player

# Analyze coach gender from bios
cd coaches
uv run python analyze_coach_gender.py -m gpt-4o-mini

# Merge coaching data
cd coaches
uv run python merge_coaching_data.py
```

## Data Sources

Data is collected from:
- NCAA official athletic websites
- Individual school athletic sites (Sidearm Sports, PrestoSports, etc.)
- Various basketball statistics platforms

## Notes

- Always use `uv run` to execute Python scripts
- Check individual documentation files in `/docs` for detailed usage instructions
- Database files (.db) should be backed up before running update scripts
