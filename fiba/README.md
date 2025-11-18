# FIBA Women's Basketball Scraper

This scraper collects data from FIBA women's basketball events, including game results, boxscores, and player statistics.

## Installation

Install required dependencies:

```bash
pip install requests requests-cache pandas beautifulsoup4 sqlite-utils
```

## Features

The scraper now supports four main modes:

### 1. Get List of Women's FIBA Events

Retrieve a list of all women's FIBA events:

```bash
python scrape_boxscore.py --mode events
```

Filter by competition type:

```bash
python scrape_boxscore.py --mode events --competition-type worldcup
python scrape_boxscore.py --mode events --competition-type u19
```

### 2. Scrape Game Results from a FIBA Women's Event

Scrape detailed boxscore data (all players, all games) from a specific event:

```bash
python scrape_boxscore.py --mode event-games --event-slug /oceania/u15women/2018
```

This will create a CSV with player-level statistics for all games in the event.

### 3. Scrape Latest FIBA Women's Games

Get the most recent women's games:

```bash
python scrape_boxscore.py --mode latest-games --limit 20
```

### 4. Scrape FIBA Women's Overall Player Stats

Get aggregate player statistics for a specific event:

```bash
python scrape_boxscore.py --mode event-stats --event-slug /oceania/u15women/2018
```

## Functions

The scraper provides the following functions that can be imported and used programmatically:

- `get_womens_events(competition_type=None)` - Get list of women's FIBA events
- `scrape_womens_event_games(event_slug)` - Scrape all game results with boxscores from an event
- `get_latest_womens_games(limit=10)` - Scrape the latest women's games
- `get_event_player_stats(event_slug)` - Scrape overall player statistics from an event
- `get_boxscore(game_url)` - Get detailed boxscore from a specific game
- `get_game_result(game_url)` - Get basic game result without boxscore

## Usage Examples

### As a Command-Line Tool

```bash
# Get all women's events
python scrape_boxscore.py --mode events --output events.csv

# Scrape a specific event's games
python scrape_boxscore.py --mode event-games --event-slug /worldcup/women/2022 --output worldcup_2022.csv

# Get latest games
python scrape_boxscore.py --mode latest-games --limit 50 --output latest.csv

# Get event player stats
python scrape_boxscore.py --mode event-stats --event-slug /worldcup/women/2022 --output stats.csv
```

### As a Python Module

```python
from fiba.scrape_boxscore import (
    get_womens_events,
    scrape_womens_event_games,
    get_latest_womens_games,
    get_event_player_stats
)

# Get list of women's events
events = get_womens_events()
print(f"Found {len(events)} events")

# Scrape games from a specific event
df = scrape_womens_event_games('/oceania/u15women/2018')
print(f"Scraped {len(df)} player records")

# Get latest games
latest = get_latest_womens_games(limit=20)
print(latest)

# Get player stats for an event
stats = get_event_player_stats('/oceania/u15women/2018')
print(stats.head())
```

## Output Format

### Event Games (boxscore data)
- country: Team name
- vs: Opponent team name
- team_score: Team's score
- vs_score: Opponent's score
- date: Game date
- Player statistics columns (points, rebounds, assists, etc.)

### Latest Games
- game_id: Unique game identifier
- game_url: URL to the game
- team_1: First team name
- team_1_score: First team's score
- team_2: Second team name
- team_2_score: Second team's score
- date: Game date

### Player Stats
- Varies by event, typically includes: player name, team, points, rebounds, assists, etc.
- event_slug: The event this data is from

## Caching

The scraper uses `requests_cache` to cache HTTP requests, reducing load on FIBA servers and speeding up subsequent runs. The cache is stored in a local SQLite database (`fiba_cache.sqlite`).

## Notes

- The scraper includes 1-second delays between requests to be respectful to FIBA servers
- Some events may not have complete data available
- Event slugs follow the pattern: `/competition/division/year` (e.g., `/worldcup/women/2022`)
- For a list of available events, run the `events` mode first
