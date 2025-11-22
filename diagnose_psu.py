#!/usr/bin/env python3
"""
Diagnostic script for Penn State fetch_game_stats issue.
This will help identify why the fetch fails for 2025-26 season.
"""

import json
import sys
import os

# Add the project to path
sys.path.insert(0, '/home/user/wbb')

print("=" * 80)
print("Penn State 2025-26 Diagnostic")
print("=" * 80)

# Load teams.json with correct path
teams_json = json.loads(open('/home/user/wbb/ncaa/teams.json').read())

# Find Penn State
team = [t for t in teams_json if t['ncaa_id'] == 539][0]
print(f"\nTeam: {team['team']}")
print(f"NCAA ID: {team['ncaa_id']}")
print(f"Base URL: {team['url']}")

season = '2025-26'

# Show what URL would be constructed
# Replicate slugify function inline
def slugify(team):
    slug = str(team['ncaa_id'])+'-'+team['team'].lower().replace(" ","-").replace('.','').replace(',','').replace("'","").replace(')','').replace('(','')
    return slug

slug = slugify(team)
print(f"Slug: {slug}")

# URL that fetch_season_playwright_season would use
stats_url_season = team['url'] + f"/stats/season/{season}"
print(f"\nURL (fetch_season_playwright_season): {stats_url_season}")

# URL that fetch_season_playwright would use (fallback)
stats_url = team['url'] + f"/stats/{season}"
print(f"URL (fetch_season_playwright fallback): {stats_url}")

# URL that regular fetch_season would use
stats_url_regular = team['url'] + "/stats/"
print(f"URL (regular fetch_season): {stats_url_regular}")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

print("""
The fetch_game_stats function fails because it tries to use Playwright to:
1. Navigate to the stats page
2. Click on "Game-By-Game" tab
3. Extract game links

Possible issues:
1. URL might not exist (404)
2. URL pattern might be wrong for 2025-26 season
3. "Game-By-Game" tab might not exist or have a different name
4. Page structure might be different
5. 2025-26 data might not be available yet

To fix this, we need to either:
A. Update the URL pattern for Penn State
B. Handle missing "Game-By-Game" tab gracefully
C. Use a different method to get game IDs for Penn State
""")

print("\n" + "=" * 80)
print("SUGGESTED INVESTIGATION STEPS")
print("=" * 80)
print("""
1. Manually check if these URLs exist in a browser:
   - {0}
   - {1}

2. Check if the page has a "Game-By-Game" tab or button

3. Try the schedule page: {2}/schedule/2025-26

4. Check if Penn State uses a different stats system (e.g., Sidearm, Presto)
""".format(stats_url_season, stats_url, team['url']))

print("\n" + "=" * 80)
print("CODE TRACE")
print("=" * 80)
print("""
When fetch_game_stats(539, '2025-26') is called:

1. Line 75: Finds team 539 (Penn State)
2. Line 76: Creates slug: '{0}'
3. Line 80-81: Calls fetch_season_playwright_season(season='{1}', base_url='{2}', slug='{0}')
4. Line 122: Creates stats_url = '{3}'
5. Line 123: Calls fetch_game_ids_playwright(stats_url)
6. Line 142: Tries to click "text=Game-By-Game"
   - THIS IS WHERE IT LIKELY FAILS

If step 6 fails, the exception is caught at line 84 and:
7. Line 86: Tries fetch_season_playwright(season, team['url'], slug)
8. Line 115: Creates stats_url = '{4}'
9. Line 116: Calls fetch_game_ids_playwright(stats_url) again
10. Line 142: Tries to click "text=Game-By-Game" again
    - IF THIS ALSO FAILS, gives up (line 88: continue)
""".format(slug, season, team['url'], stats_url_season, stats_url))
