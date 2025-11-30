# Repository Reorganization Summary

**Date:** November 30, 2025

## Changes Made

The NCAA women's basketball data repository has been reorganized from a flat structure into logical folders based on data type and functionality.

## New Directory Structure

### Created Folders:
1. **`/coaches`** - All coach-related data, scripts, and databases
2. **`/players`** - Player information and transfer data
3. **`/teams`** - Team metadata, URLs, and social media tracking
4. **`/games`** - Game schedules, play-by-play, and officials data
5. **`/rosters`** - Roster scraping tools and season data
6. **`/scripts`** - General utility scripts
7. **`/data`** - General databases and historical data files
8. **`/docs`** - All documentation and markdown files

### Existing Folders (Retained):
- **`/officials`** - Officials data (already organized)
- **`/stats`** - Statistics and analytics (already organized)

## File Migrations

### Coaches (25+ files)
- Coaching histories, bios, and gender analysis
- Position standardization and college name mapping
- All coaching-related Python scripts and databases

### Players (5 files)
- Player rosters and transfer tracking
- Historical player records

### Teams (12+ files)
- Team listings with conference/division metadata
- URL validation and social media tracking
- Foul location statistics

### Games (10+ files)
- Game schedules and results
- Play-by-play data
- Officials assignments by season

### Rosters (30+ files)
- Main `rosters.py` scraping script
- Season-specific roster data (2018-2025)
- Failed validation logs

### Scripts (5 files)
- Core utility functions
- Database builders
- JSON processors

### Data (4 files)
- Main NCAA database
- Historical CSV files
- Selenium logs

### Docs (5 files)
- README files
- Scraping documentation
- Analysis notes

## Benefits

1. **Improved Organization** - Related files grouped together
2. **Easier Navigation** - Clear separation of concerns
3. **Better Maintainability** - Logical structure for future development
4. **Clearer Purpose** - Each folder has a specific role

## Root-Level Files

Only essential files remain in root:
- `README.md` - Main repository documentation
- `__init__.py` - Python package marker
- `__pycache__/` - Python cache
- `.claude/` - AI assistant config

## Usage Notes

When running scripts from subdirectories, ensure you're in the correct folder or adjust import paths as needed. Most scripts use relative imports and should work from their new locations.

Example:
```bash
# Run roster scraping
cd rosters
uv run python rosters.py -season 2024-25 -entity player

# Analyze coach gender
cd coaches  
uv run python analyze_coach_gender.py -m gpt-4o-mini
```

## Next Steps

1. Update any hardcoded paths in scripts that reference moved files
2. Update documentation to reflect new structure
3. Test key scripts to ensure they work from new locations
4. Consider adding `.gitkeep` files to empty folders if needed
