# NCAA Women's Basketball Coaching Histories

This directory contains scraped coach biographical data, structured coaching history records, and analysis tools for women's basketball coaches. The data pipeline extracts career histories from NCAA coach bio pages, standardizes position titles and institutions, and produces a merged dataset suitable for network analysis and career trajectory research.

## Overview

The coaching histories dataset provides comprehensive career information for NCAA women's basketball coaches, including:
- **Coaching positions**: Institution, title, start/end years
- **Position standardization**: Normalized titles (Head Coach, Assistant Coach, Associate Head Coach, Staff)
- **Institution categorization**: College/university classification (Division I, II, III, Community College, Other)
- **Coach demographics**: Gender identification
- **Network analysis**: Coach-to-coach connections through shared institutions

## Data Pipeline

### 1. Scraping Coach Biographies

**Script**: `fetch_coach_bios.py`

Fetches coach biography pages from NCAA.com team roster pages and extracts plain text content using newspaper4k.

```bash
# Fetch all coach bios from coaches.csv
uv run python fetch_coach_bios.py

# Test with first 5 coaches
uv run python fetch_coach_bios.py --demo

# Fetch specific coaches by name
uv run python fetch_coach_bios.py --names "Dawn Staley" "Geno Auriemma"
```

**Input**: `coaches.csv` (or `coaches_2025-26.csv` for current season)  
**Output**: `coach_bios.json` - Raw biographical text with metadata

### 2. Extracting Structured Coaching Histories

**Script**: `extract_coaching_histories.py`

Uses Claude (via the `llm` library) to parse unstructured biographical text into structured JSON with coaching positions, education, and playing career.

```bash
# Extract all coaching histories
uv run python extract_coaching_histories.py

# Resume from checkpoint (continues from last processed coach)
uv run python extract_coaching_histories.py --resume

# Process specific coaches
uv run python extract_coaching_histories.py --names "Kim Mulkey"
```

**Input**: `coach_bios.json`  
**Output**: `coaching_histories.json` - Structured data with arrays of positions, education, and playing career

**Data structure**:
```json
{
  "team_id": 697,
  "team": "Texas A&M",
  "name": "Joni Taylor",
  "title": "Head Women's Basketball Coach",
  "url": "https://...",
  "season": "2024-25",
  "positions": [
    {
      "college": "Texas A&M",
      "title": "Head Women's Basketball Coach",
      "start": "2022",
      "end": null
    },
    ...
  ],
  "education": [...],
  "playing_career": [...]
}
```

### 3. Position Title Standardization

**Script**: Manual editing of `positions_standardized.csv`

Position titles are standardized into consistent categories to enable analysis:
- **Head Coach**: Head coach roles at any level
- **Assistant Coach**: Entry-level and assistant coaching positions
- **Associate Head Coach**: Senior assistant/associate head coach roles
- **Staff**: Director of operations, graduate assistants, managers, etc.

The standardization process involved:
1. Exporting all unique position titles from raw coaching histories
2. Manual review and categorization of ~12,000+ position records
3. Creating lookup table mapping original titles to standardized categories
4. Handling edge cases (interim positions, multiple titles, etc.)

### 4. Institution Standardization

**Scripts**: `check_and_add_colleges.py`, manual editing of `distinct_colleges.csv`

Institutions are standardized and categorized:

```bash
# Check for colleges missing from standardization file
uv run python check_and_add_colleges.py
```

**Categories**:
- **College**: NCAA colleges/universities with team data
- **Community College**: Two-year colleges
- **Other**: High schools, prep academies, international teams, professional teams

**NCAA ID mapping**: Links colleges to `teams.json` for conference, division, and state information.

### 5. Merging All Data

**Script**: `merge_coaching_data.py`

Combines coaching histories with standardized colleges, teams data, and position titles.

```bash
# Create merged dataset
uv run python merge_coaching_data.py
```

**Inputs**:
- `coaching_histories.json`
- `positions_standardized.csv`
- `distinct_colleges.csv`
- `../teams.json`

**Output**: `coaching_histories_merged.csv` - Final analysis-ready dataset

**Schema**:
```csv
coach,college,title,team_id,start_year,end_year,position_title_standardized,
college_clean,category,team_state,conference,division,gender
```

### 6. Loading to Database

**Script**: `load_coaching_histories.py`

Creates normalized SQLite database from JSON data for SQL-based analysis.

```bash
uv run python load_coaching_histories.py
```

**Output**: `coaching_histories.db` with tables:
- `coaches`: Base coach information (team, name, title, season)
- `positions`: Coaching positions with foreign key to coaches
- `education`: Educational background
- `playing_career`: Playing history

## Biographical Data Work

**Script**: `bios.py`

Collects player biographical data from roster pages using Goose3 article extraction. This complements the coach biography work by extracting player bio pages for broader NCAA women's basketball dataset.

```python
# Fetches player bios from roster URLs
# Uses newspaper/goose3 for text extraction
# Stores in SQLite database (bios.db)
```

**Database**: `bios.db` with tables:
- `bios`: Player biographical text keyed by URL and season
- `not_found`: URLs that failed to fetch

## Gender Analysis

**Script**: `add_gender_to_histories.py`

Adds gender identification to coaching records by analyzing coach names against known patterns and external data sources. Used to produce the `gender` column in `coaching_histories_merged.csv`.

## Network Analysis

**Script**: `coaching_networks_analysis.Rmd`

R Markdown analysis examining:
- **Career pathways**: Common trajectories from assistant to head coach
- **Institutional networks**: Which colleges produce the most future head coaches
- **Conference patterns**: Within-conference coaching mobility
- **Career progression**: Time spent in each position type before promotion
- **Geographic movement**: Cross-conference and cross-division transitions

Key metrics:
- Head coaches by conference and division
- Assistant coaches who became head coaches
- Most common career paths to head coaching positions
- Institutional "feeder" programs

## Key Files

### Primary Data Files
- `coaches_2025-26.csv` - Current season coach roster data (input)
- `coach_bios.json` - Raw biographical text
- `coaching_histories.json` - Structured career data
- `coaching_histories_merged.csv` - Final merged dataset (12,743 records)
- `positions_standardized.csv` - Position title standardization lookup
- `distinct_colleges.csv` - College name standardization (3,553 institutions)

### Databases
- `bios.db` - Player biographical data
- `coaches.db` - Structured coach data
- `coaching_histories.db` - Normalized coaching histories

### Analysis
- `coaching_networks_analysis.Rmd` - Network and career path analysis

### Supporting Scripts
- `build_coach_db.py` - Database building utilities
- `analyze_coach_gender.py` - Gender analysis tools
- `coaching_changes.py` - Track coaching changes across seasons

## Data Quality Notes

1. **Position standardization** required extensive manual review due to inconsistent title formats across institutions
2. **Institution matching** used NCAA team IDs where available; non-NCAA institutions require manual categorization
3. **Date ranges** may have gaps or overlaps due to biographical text ambiguity
4. **Gender data** based on name analysis and may require manual correction
5. **Community college** and **Other** categories capture non-NCAA coaching experience often missing from traditional datasets

## Requirements

```bash
# Core dependencies
uv add newspaper4k llm sqlite-utils goose3

# For analysis
# R with tidyverse, igraph packages
```

## Citation

If using this data, please cite:
- Source: NCAA.com coach biographical pages
- Compiled by: Derek Willis
- Repository: https://github.com/dwillis/wbb-rosters
- Date: 2024-25 season

## Future Work

- Automated position title standardization using LLM classification
- Expanded biographical data extraction (alma maters, playing careers)
- Temporal analysis of coaching market trends
- Integration with team performance metrics
