# NCAA Women's Basketball Roster Scraper - Redesigned

A modern, modular, and flexible scraper for NCAA women's basketball rosters that uses requests/BeautifulSoup where possible and shot-scraper/Playwright where necessary.

## Features

- **Modular Design**: Separate scrapers for different site layouts (standard, table, JavaScript)
- **Flexible Team Selection**: Scrape single teams, arbitrary sets, or all teams
- **Multiple Scraping Methods**: 
  - Standard requests + BeautifulSoup for static content
  - shot-scraper for JavaScript-heavy sites
  - Playwright for complex dynamic content
  - requests-html for rendered content
- **Consistent Output**: Standardized Player dataclass with CSV export
- **Error Handling**: Robust error handling with detailed logging
- **Configuration-Driven**: Team-specific configurations for optimal scraping

## Installation

### Dependencies

```bash
# Core dependencies
pip install requests beautifulsoup4 tldextract

# Optional: For JavaScript-heavy sites
pip install shot-scraper

# Optional: For dynamic content
pip install playwright
playwright install chromium

# Optional: For requests-html
pip install requests-html
```

Or install with uv:
```bash
uv pip install requests beautifulsoup4 tldextract shot-scraper playwright requests-html
```

## Usage

### Command Line Interface

#### Scrape All Teams for a Season
```bash
python rosters_new.py -season 2023-24
```

#### Scrape Specific Teams
```bash
# Single team
python rosters_new.py -season 2023-24 -team 736

# Multiple teams
python rosters_new.py -season 2023-24 -teams 736 415 77

# Single team with custom URL
python rosters_new.py -season 2023-24 -team 736 -url https://vucommodores.com/sports/womens-basketball/
```

#### Custom Output
```bash
python rosters_new.py -season 2023-24 -team 736 -output vanderbilt_2023-24.csv
```

#### Advanced Options
```bash
# Use Playwright instead of shot-scraper
python rosters_new.py -season 2023-24 -team 736 --use-playwright

# Verbose logging
python rosters_new.py -season 2023-24 -team 736 --verbose
```

### Programmatic Usage

```python
from rosters_new import RosterManager, TeamConfig, ScraperFactory

# Initialize manager
manager = RosterManager()

# Scrape single team
team_data = {'ncaa_id': 736, 'team': 'Vanderbilt', 'url': 'https://vucommodores.com/sports/womens-basketball/'}
players = manager.scrape_team_roster(team_data, '2023-24')

# Scrape multiple teams
team_ids = [736, 415, 77]  # Vanderbilt, Miami, BYU
all_players = manager.scrape_multiple_teams('2023-24', team_ids)

# Save to CSV
manager.save_to_csv(all_players, 'rosters_2023-24.csv')
```

## Architecture

### Core Components

1. **Player Dataclass**: Standardized data structure for player information
2. **BaseScraper**: Abstract base class for all scrapers
3. **Specialized Scrapers**:
   - `StandardScraper`: For standard sidearm-roster-player layouts
   - `TableScraper`: For table-based rosters
   - `JavaScriptScraper`: For JavaScript-heavy sites using shot-scraper or Playwright
   - `RequestsHTMLScraper`: For sites requiring JavaScript rendering
4. **ScraperFactory**: Creates appropriate scraper based on site type
5. **TeamConfig**: Manages team-specific configurations
6. **RosterManager**: Orchestrates scraping operations

### Scraper Types

#### StandardScraper
- Uses requests + BeautifulSoup
- Handles sidearm-roster-player layouts
- Most common NCAA roster format
- Fast and reliable

#### TableScraper  
- Uses requests + BeautifulSoup
- Handles HTML table layouts
- Automatically maps headers to standardized fields
- Good for simple table-based rosters

#### JavaScriptScraper
- Uses shot-scraper or Playwright
- Handles JavaScript-rendered content
- Configurable selectors for different site layouts
- More resource-intensive but handles complex sites

#### RequestsHTMLScraper
- Uses requests-html for JavaScript rendering
- Good middle ground for dynamic content
- Faster than full browser automation

### Team Configuration

Teams are automatically configured based on their NCAA ID:

```python
TEAM_CONFIGS = {
    736: {'type': 'javascript', 'selector': 'players_table', 'url_format': 'season_path'},  # Vanderbilt
    415: {'type': 'javascript', 'selector': 'players_table', 'url_format': 'season_path'},  # Miami
    147: {'type': 'table', 'url_format': 'clemson'},  # Clemson
    311: {'type': 'requests_html', 'selector': 'li.sidearm-roster-list-item'},  # Iowa State
}
```

### URL Building

The `URLBuilder` class handles different URL formats:

- `default`: `/roster/{season}`
- `season_path`: `/roster/season/{season}`
- `wbkb`: Special format for wbkb sites
- `baskbl`: Special format for baskbl sites
- `clemson`: Clemson-specific format
- `valpo`: Valparaiso-specific format

## Output Format

All scrapers produce consistent CSV output with these fields:

- `team_id`: NCAA team ID
- `team`: Team name
- `player_id`: Player ID (when available)
- `name`: Player name
- `year`: Academic year/class
- `hometown`: Player hometown
- `high_school`: High school
- `previous_school`: Previous college (transfers)
- `height`: Player height
- `position`: Playing position
- `jersey`: Jersey number
- `url`: Player profile URL
- `season`: Season (e.g., "2023-24")

## Error Handling

The scraper includes comprehensive error handling:

- Individual player parsing errors don't stop team scraping
- Team scraping errors don't stop batch operations
- Detailed logging for debugging
- Graceful fallbacks for missing data

## Performance Considerations

1. **Use Standard Scraper When Possible**: Fastest option for static content
2. **Batch Operations**: More efficient than individual team scraping
3. **Request Rate Limiting**: Built-in delays to avoid overwhelming servers
4. **Caching**: Session reuse for multiple requests to same domain

## Adding New Teams

To add support for a new team with special requirements:

1. **Identify the scraper type needed** (standard, table, javascript, requests_html)
2. **Add configuration to TeamConfig.TEAM_CONFIGS**:
   ```python
   NEW_TEAM_ID: {
       'type': 'javascript',
       'selector': 'custom_selector',
       'url_format': 'custom_format'
   }
   ```
3. **Add custom JavaScript selector if needed** to ScraperFactory.JS_SELECTORS
4. **Add custom URL format if needed** to URLBuilder

## Examples

### Adding a New JavaScript Selector

```python
# In ScraperFactory.JS_SELECTORS
'custom_cards': """
Array.from(document.querySelectorAll('.custom-player-card'), el => {
    const name = el.querySelector('.player-name').innerText;
    const position = el.querySelector('.player-position').innerText;
    // ... extract other fields
    return {name, position, /* other fields */};
})
"""
```

### Custom Team Configuration

```python
# In TeamConfig.TEAM_CONFIGS
999: {
    'type': 'javascript',
    'selector': 'custom_cards',
    'url_format': 'season_path'
}
```

## Migration from Old Script

The new scraper maintains compatibility with the original output format while providing:

- **Better modularity**: Easy to add new site types
- **Improved error handling**: More robust scraping
- **Flexible team selection**: Scrape any combination of teams
- **Modern Python practices**: Type hints, dataclasses, proper logging
- **Reduced duplication**: Shared components across scrapers

## Troubleshooting

### Common Issues

1. **Import Errors**: Install missing dependencies
2. **JavaScript Sites Not Working**: Install shot-scraper or playwright
3. **Rate Limiting**: Add delays between requests
4. **Invalid Team IDs**: Check teams.json file
5. **URL Building Issues**: Verify team URL format in configuration

### Debugging

Use verbose mode for detailed logging:
```bash
python rosters_new.py -season 2023-24 -team 736 --verbose
```

Check logs for:
- HTTP request/response details
- Parser selection logic
- Data extraction results
- Error details

## Contributing

When adding support for new teams:

1. Test with a single team first
2. Add appropriate configuration
3. Document any special requirements
4. Submit pull request with example usage

## License

Same as original project license.
