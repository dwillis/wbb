# Penn State 2025-26 Game Stats Fetch Issue - Investigation & Fix

## Problem

The call `fetch_game_stats(539, '2025-26')` fails for Penn State.

## Root Cause Analysis

### Code Flow

When `fetch_game_stats(539, '2025-26')` is called:

1. **Line 80-81** (`game_utils.py`): Special handling for Penn State (team_id 539)
   - Calls `fetch_season_playwright_season(season, team['url'], slug)`

2. **Line 122**: Constructs URL
   ```python
   stats_url = base_url + f"/stats/season/{season}"
   # Result: https://gopsusports.com/sports/womens-basketball/stats/season/2025-26
   ```

3. **Line 123**: Calls `fetch_game_ids_playwright(stats_url)`

4. **Line 142** (old version): Tries to click "Game-By-Game" tab
   ```python
   page.click("text=Game-By-Game")
   ```
   **THIS IS WHERE IT FAILS**

### Why It Fails

The original `fetch_game_ids_playwright` function had several issues:

1. **No error handling** - If the page doesn't load or returns non-200 status, it fails silently
2. **Exact text match only** - Only tries "Game-By-Game" (case-sensitive), doesn't try variations
3. **No timeout on click** - Could hang indefinitely
4. **Poor error messages** - Hard to diagnose what went wrong
5. **No browser cleanup on error** - Browser process could leak

### Possible Reasons for Penn State Failure

1. **Wrong URL pattern** - The `/stats/season/2025-26` URL might not exist or might return 404
2. **403 Forbidden** - Penn State's site might block automated requests
3. **No "Game-By-Game" tab** - The 2025-26 season might not have this tab yet
4. **Different tab name** - Tab might be named "Game-by-Game" or "game-by-game" (different case)
5. **Season not available** - 2025-26 data might not be published yet

## Fix Applied

Updated `fetch_game_ids_playwright` function in `ncaa/game_utils.py` (lines 135-209):

### Improvements

1. **HTTP Status Checking**
   ```python
   if response and response.status == 404:
       raise Exception(f"Page not found (404): {url}")
   elif response and response.status == 403:
       raise Exception(f"Access forbidden (403): {url}")
   ```

2. **Multiple Tab Selector Variations**
   ```python
   tab_selectors = [
       "text=Game-By-Game",
       "text=Game-by-Game",
       "text=game-by-game",
       "text=/game.by.game/i",  # Case-insensitive regex
   ]
   ```

3. **Informative Error Messages**
   ```python
   if not tab_clicked:
       raise Exception(
           f"Could not find 'Game-By-Game' tab on page: {url}\n"
           f"The page may not have game-by-game data, or the tab name has changed."
       )
   ```

4. **Timeout on Click**
   ```python
   page.click(selector, timeout=5000)
   ```

5. **Proper Cleanup**
   ```python
   try:
       # ... main logic ...
   finally:
       browser.close()
   ```

6. **Better Game ID Extraction**
   - Handles both URL formats: `/boxscore/12345` and `?id=12345`
   - More robust parsing with try/except

## Next Steps for Debugging

If the issue persists after this fix, the error message will now tell you exactly what failed:

1. **If you get "Page not found (404)"**
   - The URL pattern `/stats/season/2025-26` is wrong for Penn State
   - Try checking if `/stats/2025-26` works instead (fallback already implemented)

2. **If you get "Access forbidden (403)"**
   - Penn State is blocking automated access
   - May need to add headers or use different approach

3. **If you get "Could not find 'Game-By-Game' tab"**
   - The page exists but doesn't have the expected tab
   - Need to manually inspect the page to see what tabs are available
   - The debugging script `test_psu_debug.py` will save the HTML for inspection

4. **If you get "No boxscore links found"**
   - The tab exists but there are no games yet for 2025-26
   - This might be expected if the season hasn't started

## Test Commands

To test the fix:

```python
from ncaa.game_utils import fetch_game_stats

# This should now give a clear error message
fetch_game_stats(539, '2025-26')
```

For detailed debugging:

```bash
python test_psu_debug.py
```

This will:
- Show the exact URL being accessed
- Try multiple selectors for the Game-By-Game tab
- Save the HTML to `debug_page_content.html` if the tab isn't found
- Show all game IDs extracted

## Files Created/Modified

1. **Modified**: `ncaa/game_utils.py` - Improved `fetch_game_ids_playwright` function
2. **Created**: `ncaa/game_utils_debug.py` - Enhanced debugging version
3. **Created**: `test_psu_debug.py` - Test script with verbose output
4. **Created**: `diagnose_psu.py` - Diagnostic information script
5. **Created**: `test_urls.py` - URL pattern testing script
6. **Created**: `PENN_STATE_FIX.md` - This documentation
