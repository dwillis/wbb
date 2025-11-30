# Women's Basketball Data Repository

A comprehensive data collection and analysis toolkit for women's basketball at multiple levels: NCAA, FIBA, WNBA, and US Women's National Team.

## Repository Structure

### 📊 `/ncaa` - NCAA Women's Basketball
The primary focus of this repository, containing extensive data, scraping tools, and analysis for NCAA Division I, II, and III women's basketball programs.

**[Full NCAA Documentation →](ncaa/README.md)**

#### Quick Start - NCAA
```bash
cd ncaa

# Scrape rosters for current season
cd rosters
uv run python rosters.py -season 2024-25 -entity player

# Analyze coaching data
cd ../coaches
uv run python analyze_coach_gender.py -m gpt-4o-mini
uv run python merge_coaching_data.py
```

#### NCAA Directory Structure
- **`/coaches`** - Coaching histories, biographies, career paths, and gender analysis
- **`/rosters`** - Roster scraping tools and seasonal player data (2018-2026)
- **`/teams`** - Team metadata, URLs, conferences, divisions, and social media
- **`/players`** - Player information and transfer tracking
- **`/games`** - Game schedules, play-by-play, and officials data
- **`/officials`** - Officials and referees information
- **`/stats`** - Statistical analysis and metrics
- **`/scripts`** - Utility scripts and helpers
- **`/data`** - General databases and historical data
- **`/docs`** - Documentation and guides

#### Key NCAA Features
- **Comprehensive Roster Scraping**: Automated scraping for 350+ NCAA programs with support for multiple platform types (Sidearm, Nuxt.js, Vue.js, custom JavaScript)
- **Coaching Database**: 3,100+ coaches with career histories, 12,700+ position records, standardized titles, and LLM-powered gender identification
- **Team Tracking**: Complete team metadata including conferences, divisions, URLs, and social media
- **Play-by-Play Data**: Game-level data with officials, locations, and detailed play information
- **Transfer Portal**: Tracking player transfers across programs

---

### 🌍 `/fiba` - FIBA Women's Basketball
International women's basketball data from FIBA competitions including World Cups, Olympic qualifiers, and youth tournaments.

**[Full FIBA Documentation →](fiba/README.md)**

#### Features
- Game results and boxscores from FIBA events
- Player statistics across multiple tournaments
- Support for World Cup, U19, U17, U15 competitions
- Event-level and game-level data collection
- Automated caching to reduce server load

#### Usage
```bash
cd fiba

# Get list of all women's FIBA events
python scrape_boxscore.py --mode events

# Scrape specific event
python scrape_boxscore.py --mode event-games --event-slug /worldcup/women/2022

# Get latest games
python scrape_boxscore.py --mode latest-games --limit 20

# Get player stats for an event
python scrape_boxscore.py --mode event-stats --event-slug /worldcup/women/2022
```

#### Data Files
- `fiba_games.csv` - Complete game results
- `fiba_player_stats.csv` - Player statistics across tournaments
- `fiba_women.db` - SQLite database with all FIBA data
- `shot_chart.csv` - Shot location data
- `fiba_cache.sqlite` - HTTP request cache

---

### 🏀 `/wnba` - WNBA Data
Professional women's basketball data and utilities for WNBA teams and players.

#### Contents
- `teams.json` - WNBA team information
- `wnba.db` - WNBA database
- `wnba_utils.py` - Utility functions for WNBA data processing

---

### 🇺🇸 `/uswnt` - US Women's National Team
Data for the US Women's National Basketball Team.

#### Structure
- `/box_scores` - Game box scores
- `/rosters` - Team rosters
- `games.csv` - Game schedule and results
- `parse_box_score.py` - Box score parsing utility

---

### 📺 `/showbuzz` - Tournament Television Data
Television ratings and viewership data for women's basketball tournaments.

#### Contents
- Daily CSV files for 2019 and 2021 NCAA tournaments
- `showbuzz.py` - Data collection script
- Dates covered: March-April 2019 and 2021

---

## Installation & Setup

### Prerequisites
- Python 3.8+
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)
- OR pip with virtual environment

### Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/dwillis/wbb.git
cd wbb

# Install dependencies (handled automatically by uv)
uv sync
```

### Using pip
```bash
# Clone repository
git clone https://github.com/dwillis/wbb.git
cd wbb

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Additional Dependencies

For NCAA roster scraping with JavaScript support:
```bash
# Install shot-scraper for JavaScript rendering
uv tool install shot-scraper

# OR for Playwright support
pip install playwright
playwright install chromium
```

For LLM-powered analysis (coach gender identification):
```bash
pip install llm
# Configure with your API key
llm keys set openai
```

## Common Usage Patterns

### NCAA Roster Scraping
```bash
cd ncaa/rosters

# Scrape all teams for a season
uv run python rosters.py -season 2024-25

# Scrape specific teams
uv run python rosters.py -season 2024-25 -teams 193 257 697

# Scrape single team with custom URL
uv run python rosters.py -season 2024-25 -team 193 -url https://goduke.com
```

### Coach Data Analysis
```bash
cd ncaa/coaches

# Fetch coach biographies
uv run python fetch_coach_bios.py

# Analyze gender from bios using LLM
uv run python analyze_coach_gender.py -m gpt-4o-mini

# Merge coaching data with team info
uv run python merge_coaching_data.py

# Add gender to merged histories
uv run python add_gender_to_histories.py
```

### FIBA Data Collection
```bash
cd fiba

# List all women's events
python scrape_boxscore.py --mode events --output events.csv

# Scrape World Cup data
python scrape_boxscore.py --mode event-games \
  --event-slug /worldcup/women/2022 \
  --output worldcup_2022.csv
```

## Data Files & Formats

### NCAA
- **CSV**: Rosters, coaches, teams, games
- **JSON**: Teams, coaches, players, coaching histories
- **SQLite**: ncaa.db (main database), rosters.db, coaches.db, bios.db

### FIBA
- **CSV**: Game results, player stats, shot charts
- **SQLite**: fiba_women.db, fiba_cache.sqlite (HTTP cache)

### WNBA/USWNT
- **JSON**: Team information
- **CSV**: Games, rosters, box scores
- **SQLite**: wnba.db

## Key Scripts

### NCAA
- `rosters/rosters.py` - Main roster scraping engine (165KB, handles 350+ teams)
- `coaches/fetch_coach_bios.py` - Scrape coach biographies
- `coaches/extract_coaching_histories.py` - Extract career histories
- `coaches/analyze_coach_gender.py` - LLM-powered gender identification
- `coaches/merge_coaching_data.py` - Merge coaching data with team metadata
- `teams/check_urls.py` - Validate team website URLs

### FIBA
- `scrape_boxscore.py` - Multi-mode FIBA data scraper
- `player_game.py` - Player game statistics
- `shot_chart.py` - Shot chart data processing

### WNBA/USWNT
- `wnba/wnba_utils.py` - WNBA data utilities
- `uswnt/parse_box_score.py` - Box score parser

## Data Coverage

### NCAA
- **Seasons**: 2018-19 through 2025-26
- **Teams**: 350+ Division I programs
- **Coaches**: 3,100+ coaches with 12,700+ position records
- **Players**: Comprehensive roster data per season

### FIBA
- **Competitions**: World Cup, Olympic qualifiers, youth tournaments (U15-U19)
- **Years**: 2011-2025
- **Events**: 100+ women's basketball events

### WNBA
- Current WNBA teams and player data

### USWNT
- US Women's National Team games and rosters

## Contributing

This repository is primarily maintained for data journalism and research purposes. Issues and pull requests are welcome for bug fixes and data improvements.

## Notes

- **NCAA scraping**: Always use `uv run` to execute Python scripts
- **Rate limiting**: Scrapers include delays to be respectful to source servers
- **Caching**: FIBA scraper caches HTTP requests to reduce load
- **Databases**: Backup .db files before running update scripts
- **Season format**: Use "YYYY-YY" format (e.g., "2024-25")

## License

Data collected from public sources. Please respect source website terms of service and rate limits.

## Acknowledgments

Data sources:
- NCAA official athletic websites
- FIBA.basketball official website
- Individual school athletic sites (Sidearm Sports, PrestoSports, etc.)
- ShowBuzz Daily television ratings

## Contact

Repository maintained by [@dwillis](https://github.com/dwillis)
