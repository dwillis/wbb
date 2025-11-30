# NCAA Women's Basketball Coaches Scraping Plan

## Executive Summary

This document provides step-by-step instructions for adding coach scraping capabilities to the existing NCAA roster scraper (`rosters.py`) while maximizing code reuse and maintaining simplicity. The approach uses an **Entity-Aware Unified Scraper** with entity-specific configuration, allowing a single file to handle both players and coaches with minimal complexity increase.

## Current Architecture Analysis

### Strengths to Preserve
- **Modular design**: Separate classes for URL building, field extraction, season verification
- **Multiple scraper strategies**: Standard (Sidearm), Table, JavaScript-based
- **Configuration-driven**: Team-specific configs handle special cases
- **Robust error handling**: Verification steps, fallbacks, detailed logging

### Key Components for Reuse
1. **URLBuilder**: Already handles different URL formats - can be used for both players and coaches
2. **SeasonVerifier**: Works for both entity types
3. **FieldExtractors**: Normalization logic applies to both
4. **HeaderMapper**: Field mapping useful for both
5. **RosterManager**: CSV saving logic reusable

---

## Chosen Architecture: Entity-Aware Unified Scraper

**Philosophy**: Single scraper with entity type parameter

### Rationale
1. **Minimal complexity increase**: Adding entity_type parameter is simpler than refactoring into library
2. **Maximum code reuse**: All infrastructure classes remain shared
3. **Single source of truth**: One file contains all scraping logic
4. **Easy debugging**: All code in one place makes troubleshooting easier
5. **Consistent behavior**: Both entities guaranteed to use same URL building, verification, error handling

### Architecture Overview
```
rosters.py (enhanced)
├── Shared Infrastructure (unchanged)
│   ├── URLBuilder
│   ├── SeasonVerifier  
│   ├── FieldExtractors
│   └── HeaderMapper
├── Entity Configurations (NEW)
│   ├── ENTITY_CONFIGS dictionary
│   │   ├── 'player' config
│   │   └── 'coach' config
└── Enhanced Scrapers (entity-aware)
    ├── StandardScraper(entity_type)
    ├── TableScraper(entity_type)
    └── JavaScriptScraper(entity_type)
```

### Command-Line Interface
```bash
# Scrape players (default)
python rosters.py -season 2025-26 -team 746

# Scrape coaches
python rosters.py -season 2025-26 -team 746 -entity coach

# Scrape both
python rosters.py -season 2025-26 -team 746 -entity all
```

### Advantages
- ✅ Minimal code duplication
- ✅ Single file to maintain
- ✅ Shared bug fixes benefit both entities
- ✅ Consistent error handling and logging
- ✅ Easy to add new entity types (staff, trainers)
- ✅ Backward compatible (defaults to 'player')

---

## Step-by-Step Implementation Guide

### Phase 1: Add Entity Configuration (2-3 hours)

#### Step 1.1: Define Entity Configuration Dictionary

Add this near the top of `rosters.py`, after the existing configuration constants:
├── Shared Infrastructure (unchanged)
│   ├── URLBuilder
│   ├── SeasonVerifier  
│   ├── FieldExtractors
│   └── HeaderMapper
├── Entity Configurations
│   ├── PLAYER_SELECTORS
│   ├── COACH_SELECTORS
│   ├── PLAYER_FIELD_MAP
│   └── COACH_FIELD_MAP
└── Enhanced Scrapers (entity-aware)
    ├── StandardScraper(entity_type)
    ├── TableScraper(entity_type)
    └── JavaScriptScraper(entity_type)
```

#### Step 1.1: Define Entity Configuration Dictionary

Add this near the top of `rosters.py`, after the existing configuration constants:

```python
# Entity-specific configurations for players and coaches
ENTITY_CONFIGS = {
    'player': {
        'sidearm_selectors': [
            '.sidearm-roster-player',
            '.sidearm-roster-list-item',
            '.s-person-card'  # Used by some teams
        ],
        'sidearm_container': '.sidearm-roster-players',
        'field_selectors': {
            'name': ['.sidearm-roster-player-name', 'h3 a', '.sidearm-roster-player-name-link'],
            'jersey': ['.sidearm-roster-player-jersey-number', '.sidearm-roster-player-jersey'],
            'position': ['.sidearm-roster-player-position'],
            'height': ['.sidearm-roster-player-height'],
            'academic_year': ['.sidearm-roster-player-academic-year', '.sidearm-roster-player-academic-year-long'],
            'hometown': ['.sidearm-roster-player-hometown'],
            'high_school': ['.sidearm-roster-player-highschool', '.sidearm-roster-player-high-school']
        },
        'output_fields': ['team', 'team_id', 'season', 'jersey', 'name', 'position', 
                         'height', 'academic_year', 'hometown', 'high_school', 'previous_school', 'url'],
        'csv_prefix': 'rosters',
        'entity_label': 'players'
    },
    'coach': {
        'sidearm_selectors': [
            '.sidearm-roster-coach',
            '.sidearm-roster-coaches-card'
        ],
        'sidearm_container': '.sidearm-roster-coaches',
        'field_selectors': {
            'name': ['.sidearm-roster-coach-name', 'h3', 'h4', 'strong a', 'a'],
            'title': ['.sidearm-roster-coach-title', '.sidearm-roster-coach-position', '.title'],
            'experience': ['.sidearm-roster-coach-seasons', '.sidearm-roster-coach-experience'],
            'alma_mater': ['.sidearm-roster-coach-college', '.sidearm-roster-coach-alma-mater']
        },
        'output_fields': ['team', 'team_id', 'season', 'name', 'title', 
                         'experience', 'alma_mater', 'url'],
        'csv_prefix': 'coaches',
        'entity_label': 'coaches'
    }
}
```

**Location**: Place this after the `TeamConfig` class definition, before the `BaseScraper` class.

#### Step 1.2: Add Entity Type to Command-Line Arguments

Find the argument parser section in the `main()` function and add:

```python
parser.add_argument('-entity', '--entity-type', 
                   choices=['player', 'coach', 'all'], 
                   default='player',
                   help='Type of entity to scrape: player, coach, or all (default: player)')
```

**Location**: Add this after the existing arguments, around line 1450.

#### Step 1.3: Update BaseScraper to Accept Entity Type

Modify the `BaseScraper.__init__()` method:

```python
class BaseScraper:
    def __init__(self, team_name: str, team_id: int, season: str, 
                 base_url: str, entity_type: str = 'player'):
        self.team_name = team_name
        self.team_id = team_id
        self.season = season
        self.base_url = base_url
        self.entity_type = entity_type
        self.entity_config = ENTITY_CONFIGS[entity_type]
```

**Location**: Update the `BaseScraper` class around line 740.

#### Step 1.4: Update Scraper Subclass Signatures

Update `StandardScraper`, `TableScraper`, and `JavaScriptScraper` to accept and pass through `entity_type`:

```python
class StandardScraper(BaseScraper):
    def __init__(self, team_name: str, team_id: int, season: str, 
                 base_url: str, entity_type: str = 'player'):
        super().__init__(team_name, team_id, season, base_url, entity_type)
```

**Location**: Update each scraper class (StandardScraper ~line 770, TableScraper ~line 896, JavaScriptScraper ~line 1030).

#### Step 1.5: Test Backward Compatibility

Run existing scraper to ensure it still works with default 'player' entity type:

```bash
cd /Users/dwillis/code/wbb
uv run python ncaa/rosters.py -season 2025-26 -team 746
```

Expected: Should scrape players normally with no changes to output.

---

### Phase 2: Implement Coach Extraction (3-4 hours)

#### Step 2.1: Update StandardScraper Selector Logic

Modify `StandardScraper.scrape_roster()` to use entity-specific selectors:

```python
def scrape_roster(self) -> List[Player]:
    """Scrape roster using standard Sidearm structure"""
    try:
        response = requests.get(self.roster_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        # ... existing verification code ...
        
        # Use entity-specific selectors
        selectors = self.entity_config['sidearm_selectors']
        player_elements = []
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                player_elements = elements
                logger.info(f"Found {len(player_elements)} {self.entity_config['entity_label']} using selector: {selector}")
                break
        
        if not player_elements:
            logger.warning(f"No {self.entity_config['entity_label']} found for {self.team_name}")
            return []
        
        # Extract entities (players or coaches)
        entities = []
        for element in player_elements:
            if self.entity_type == 'player':
                entity_data = self._extract_player_data(element)
            else:  # coach
                entity_data = self._extract_coach_data(element)
            
            if entity_data:
                entities.append(entity_data)
        
        return entities
```

**Location**: Modify `StandardScraper.scrape_roster()` around line 780-850.

#### Step 2.2: Create Coach Data Extraction Method

Add a new method to `StandardScraper`:

```python
def _extract_coach_data(self, coach_element) -> Optional[Player]:
    """Extract coach information from a coach element"""
    try:
        # Extract name
        name = None
        for selector in self.entity_config['field_selectors']['name']:
            name_elem = coach_element.select_one(selector)
            if name_elem:
                name = name_elem.get_text(strip=True)
                break
        
        if not name:
            return None
        
        # Extract title
        title = None
        for selector in self.entity_config['field_selectors']['title']:
            title_elem = coach_element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break
        
        # Extract experience
        experience = None
        for selector in self.entity_config['field_selectors']['experience']:
            exp_elem = coach_element.select_one(selector)
            if exp_elem:
                experience = exp_elem.get_text(strip=True)
                break
        
        # Extract alma mater
        alma_mater = None
        for selector in self.entity_config['field_selectors']['alma_mater']:
            alma_elem = coach_element.select_one(selector)
            if alma_elem:
                alma_mater = alma_elem.get_text(strip=True)
                break
        
        # Create Player object (reusing same dataclass)
        return Player(
            team=self.team_name,
            team_id=str(self.team_id),
            season=self.season,
            name=name,
            jersey='',  # Coaches don't have jersey numbers
            position=title or '',  # Use title as position for coaches
            height='',
            academic_year=experience or '',  # Use experience as year
            hometown=alma_mater or '',  # Use alma_mater as hometown
            high_school='',
            previous_school='',
            url=self.roster_url
        )
    
    except Exception as e:
        logger.warning(f"Error extracting coach data: {e}")
        return None
```

**Location**: Add this method to `StandardScraper` class around line 880.

#### Step 2.3: Update TableScraper for Coaches

Coaches in table-based sites may appear in separate tables or sections. Update `TableScraper.scrape_roster()`:

```python
def scrape_roster(self) -> List[Player]:
    """Scrape roster from table-based format"""
    try:
        response = requests.get(self.roster_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ... existing code ...
        
        # For coaches, look for coach-specific tables or sections
        if self.entity_type == 'coach':
            # Try to find coach-specific table
            coach_headers = soup.find_all(['h2', 'h3', 'h4'], 
                                         string=lambda s: s and 'coach' in s.lower())
            if coach_headers:
                # Find table after coach header
                for header in coach_headers:
                    table = header.find_next('table')
                    if table:
                        return self._parse_table(table, soup)
        
        # Standard table parsing
        tables = soup.find_all('table')
        # ... rest of existing logic ...
```

**Location**: Modify `TableScraper.scrape_roster()` around line 920-950.

#### Step 2.4: Update JavaScriptScraper for Coaches

Add coach support to JavaScript-based scraping:

```python
def scrape_roster(self) -> List[Player]:
    """Scrape roster using shot-scraper for JavaScript-rendered content"""
    try:
        # ... existing code ...
        
        if self.entity_type == 'coach':
            # Use coach-specific selectors
            js_code = f"""
            {{
                coaches: Array.from(document.querySelectorAll('{self.entity_config['sidearm_selectors'][0]}')).map(coach => ({{
                    name: coach.querySelector('.sidearm-roster-coach-name')?.textContent?.trim() || '',
                    title: coach.querySelector('.sidearm-roster-coach-title')?.textContent?.trim() || '',
                    experience: coach.querySelector('.sidearm-roster-coach-seasons')?.textContent?.trim() || '',
                    alma_mater: coach.querySelector('.sidearm-roster-coach-college')?.textContent?.trim() || ''
                }}))
            }}
            """
        else:
            # Existing player JS code
            js_code = JSTemplates.get_standard_selector(self.js_selector)
        
        # ... rest of method ...
```

**Location**: Modify `JavaScriptScraper.scrape_roster()` around line 1050-1070.

#### Step 2.5: Test Coach Scraping on Sample Team

Test with Maryland (team 120), which has a well-structured coach section:

```bash
cd /Users/dwillis/code/wbb
uv run python ncaa/rosters.py -season 2025-26 -team 120 -entity coach
```

Expected output: CSV file with coach names, titles, and other available information.

---

### Phase 3: Update Data Management (1-2 hours)

#### Step 3.1: Update RosterManager to Handle Entity Types

Modify `RosterManager.save_to_csv()` to create entity-specific output files:

```python
def save_to_csv(self, players: List[Player], output_file: Optional[str] = None, 
                entity_type: str = 'player') -> str:
    """Save players/coaches to CSV with entity-specific fields"""
    if not players:
        logger.warning(f"No {entity_type}s to save")
        return ""
    
    # Get entity-specific configuration
    entity_config = ENTITY_CONFIGS[entity_type]
    
    # Generate default filename if not provided
    if not output_file:
        entity_prefix = entity_config['csv_prefix']
        output_file = f"{entity_prefix}_{self.season}.csv"
    
    # ... rest of existing save logic ...
    
    # Use entity-specific output fields
    fieldnames = entity_config['output_fields']
```

**Location**: Modify `RosterManager.save_to_csv()` around line 1270-1300.

#### Step 3.2: Update Team-Specific Output Files

Modify `RosterManager` to create team-specific files when scraping individual teams:

```python
def save_to_csv(self, players: List[Player], output_file: Optional[str] = None, 
                entity_type: str = 'player', team_id: Optional[int] = None) -> str:
    """Save players/coaches to CSV"""
    if not players:
        return ""
    
    entity_config = ENTITY_CONFIGS[entity_type]
    entity_prefix = entity_config['csv_prefix']
    
    # Generate filename
    if not output_file:
        if team_id:
            output_file = f"{entity_prefix}_{self.season}_team_{team_id}.csv"
        else:
            output_file = f"{entity_prefix}_{self.season}.csv"
    
    # ... rest of method ...
```

**Location**: Update around line 1270.

#### Step 3.3: Update Main Function to Handle Entity Type

Modify the `main()` function to pass entity_type through the scraping workflow:

```python
def main():
    args = parser.parse_args()
    entity_type = args.entity_type
    
    # ... existing code ...
    
    if entity_type == 'all':
        # Scrape both players and coaches
        logger.info(f"Scraping both players and coaches for team {team_id}")
        
        # Scrape players
        players = scrape_team(team_id, args.season, entity_type='player')
        if players:
            manager_player = RosterManager(args.season)
            manager_player.save_to_csv(players, entity_type='player', team_id=team_id)
        
        # Scrape coaches  
        coaches = scrape_team(team_id, args.season, entity_type='coach')
        if coaches:
            manager_coach = RosterManager(args.season)
            manager_coach.save_to_csv(coaches, entity_type='coach', team_id=team_id)
    else:
        # Scrape single entity type
        entities = scrape_team(team_id, args.season, entity_type=entity_type)
        if entities:
            manager = RosterManager(args.season)
            manager.save_to_csv(entities, entity_type=entity_type, team_id=team_id)
```

**Location**: Update `main()` function around line 1450-1480.

#### Step 3.4: Add Entity-Specific Logging

Update log messages to distinguish between players and coaches:

```python
logger.info(f"Scraping {entity_config['entity_label']} for {team_name} (ID: {team_id})")
logger.info(f"Found {len(entities)} {entity_config['entity_label']} for {team_name}")
logger.info(f"Scraped {len(entities)} {entity_config['entity_label']} from {team_name}")
```

**Location**: Update throughout scraper methods.

---

### Phase 4: Testing & Validation (2-3 hours)

#### Step 4.1: Test Individual Entity Types

```bash
# Test player scraping (should work as before)
uv run python ncaa/rosters.py -season 2025-26 -team 746

# Test coach scraping
uv run python ncaa/rosters.py -season 2025-26 -team 120 -entity coach

# Test scraping both
uv run python ncaa/rosters.py -season 2025-26 -team 120 -entity all
```

#### Step 4.2: Test Different Site Types

Test across different scraper types:

```bash
# Sidearm site (Standard scraper)
uv run python ncaa/rosters.py -season 2025-26 -team 120 -entity coach

# Table-based site
uv run python ncaa/rosters.py -season 2025-26 -team 29 -entity coach

# JavaScript site (if applicable)
uv run python ncaa/rosters.py -season 2025-26 -team 71 -entity coach
```

#### Step 4.3: Validate Output Format

Check that CSV files have correct structure:

```bash
# Check player CSV
head -5 rosters_2025-26_team_746.csv

# Check coach CSV
head -5 coaches_2025-26_team_120.csv
```

Expected fields:
- **Players**: team, team_id, season, jersey, name, position, height, academic_year, hometown, high_school, previous_school, url
- **Coaches**: team, team_id, season, name, title, experience, alma_mater, url

#### Step 4.4: Test Edge Cases

```bash
# Team with no coaches listed
uv run python ncaa/rosters.py -season 2025-26 -team XXXX -entity coach

# Team with minimal coach information
uv run python ncaa/rosters.py -season 2025-26 -team YYYY -entity coach
```

Expected: Graceful handling with appropriate warnings.

#### Step 4.5: Run Batch Test

Test 10-15 teams to ensure consistency:

```bash
# Create a test script
for team_id in 120 746 257 164 387 458 521 718; do
    echo "Testing team $team_id"
    uv run python ncaa/rosters.py -season 2025-26 -team $team_id -entity all
done
```

---

## Site Type Analysis

### Sidearm Sites (Majority)
**Player Structure:**
```html
<ul class="sidearm-roster-players">
  <li class="sidearm-roster-player">
    <div class="sidearm-roster-player-name">Name</div>
    <div class="sidearm-roster-player-position">Position</div>
  </li>
</ul>
```

**Coach Structure:**
```html
<ul class="sidearm-roster-coaches">
  <li class="sidearm-roster-coach">
    <div class="sidearm-roster-coach-name">Name</div>
    <div class="sidearm-roster-coach-title">Title</div>
  </li>
</ul>
```

**Key Insight**: Same structural pattern, different class names

### Table Sites
- Some sites have separate coach tables
- Others mix coaches and players in one table (less common)
- May need table inspection to determine entity type

### JavaScript Sites
- Similar to Sidearm but different selectors
- Coach info often in separate section
- May require additional JavaScript selectors

---

## Data Schema

### Players CSV Output
```csv
team,team_id,season,jersey,name,position,height,academic_year,hometown,high_school,previous_school,url
Virginia,746,2025-26,1,Player Name,Guard,5-9,Sophomore,City ST,High School,,https://...
```

### Coaches CSV Output
```csv
team,team_id,season,name,title,experience,alma_mater,url
Maryland,120,2025-26,Brenda Frese,Head Coach,23rd Season,Arizona,https://umterps.com/...
```

### Required Fields
**Coaches:**
- **name**: Coach full name
- **title**: Position (Head Coach, Assistant Coach, etc.)
- **experience**: Years/season information (if available)
- **alma_mater**: Undergraduate institution (if available)

### Optional Fields
- **phone**: Contact information
- **email**: Contact email  
- **bio_url**: Link to full bio page

---

## Edge Cases to Handle

### 1. Missing Coach Information
- Some sites may not list coaches on roster page
- **Solution**: Log warning, continue scraping, output empty coach CSV

### 2. Interim Coaches
- Title may include "Interim" or "Acting"
- **Solution**: Preserve full title string

### 3. Non-Coaching Staff
- Trainers, managers may be listed
- **Solution**: Include all listed staff, filter in post-processing if needed

### 4. Multiple Title Lines
- "Associate Head Coach / Recruiting Coordinator"
- **Solution**: Keep full multi-line title

### 5. Coach vs Player Detection
- Some sites use similar markup
- **Solution**: Check for specific coach indicators (title field, "coach" in class name)

---

## Code Changes Summary

### Additions (Estimated)
- Entity configuration: ~80 lines (ENTITY_CONFIGS dictionary)
- Coach extraction methods: ~120 lines (_extract_coach_data, coach-specific logic)
- Command-line argument: ~3 lines
- Entity type handling in main: ~30 lines
- Documentation/comments: ~20 lines
- **Total: ~250 new lines**

### Modifications
- Scraper class signatures: ~20 lines
- Selector retrieval logic: ~40 lines
- CSV output methods: ~30 lines
- Logging statements: ~15 lines
- **Total: ~105 modified lines**

### Deletions
- None (backward compatible)

**Net Addition: ~355 lines to existing ~1,500 line file = ~24% increase**

---

## Future Enhancements

### Phase 5: Enhanced Coach Data
- Scrape coach bio pages for detailed information
- Extract career history
- Capture phone/email if available

### Phase 6: Staff Members
- Add support for non-coaching staff
- Trainers, managers, support staff

### Phase 7: Historical Tracking
- Track coaching changes over seasons
- Build coaching history database

### Phase 8: Cross-Reference
- Link coaches to player rosters they coached
- Analyze coaching tenure and team performance

---

## Risk Assessment

### Low Risk ✅
- Breaking existing player scraping (entity_type defaults to 'player')
- Performance impact (same number of HTTP requests)

### Medium Risk ⚠️
- Site structure variations (mitigated by multi-selector approach)
- Missing coach data (handle gracefully with warnings)

### High Risk ❌
- None identified

---

## Success Metrics

### Quantitative
- Coach scraping success rate: >85% of teams
- Field completion rate: >70% for name/title
- Performance: No significant slowdown vs player-only scraping
- Backward compatibility: 100% of existing player scraping continues to work

### Qualitative
- Code remains maintainable
- Easy to add new entity types in future
- Clear separation between entity configs
- Logging clearly distinguishes entity types

---

## Implementation Checklist

### Phase 1: Entity Configuration ☐
- [ ] Add ENTITY_CONFIGS dictionary
- [ ] Add -entity command-line argument
- [ ] Update BaseScraper to accept entity_type
- [ ] Update all scraper subclass signatures
- [ ] Test backward compatibility with player scraping

### Phase 2: Coach Extraction ☐
- [ ] Update StandardScraper selector logic
- [ ] Create _extract_coach_data() method
- [ ] Update TableScraper for coaches
- [ ] Update JavaScriptScraper for coaches
- [ ] Test coach scraping on sample team (Maryland 120)

### Phase 3: Data Management ☐
- [ ] Update RosterManager.save_to_csv() for entity types
- [ ] Implement entity-specific output files
- [ ] Update main() to handle 'all' entity type
- [ ] Add entity-specific logging throughout
- [ ] Test CSV output format

### Phase 4: Testing & Validation ☐
- [ ] Test individual entity types
- [ ] Test different site types (Sidearm, Table, JS)
- [ ] Validate output format
- [ ] Test edge cases
- [ ] Run batch test on 10-15 teams
- [ ] Verify no regression in player scraping

### Documentation ☐
- [ ] Update inline comments
- [ ] Update README with coach scraping instructions
- [ ] Document known limitations
- [ ] Add examples for each entity type

---

## Conclusion

This implementation plan provides a clear path to add coach scraping capabilities to `rosters.py` with minimal complexity increase. The Entity-Aware Unified Scraper approach:

- **Maximizes code reuse**: All infrastructure classes remain shared
- **Maintains simplicity**: Single file, clear entity configurations
- **Ensures maintainability**: Single source of truth, consistent patterns
- **Enables extensibility**: Easy to add more entity types in future

**Estimated implementation time: 8-12 hours** across four phases with built-in testing and validation at each step.

The implementation maintains full backward compatibility - existing player scraping continues to work without any changes, while new coach scraping capabilities are added through an optional command-line argument.
