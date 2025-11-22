#!/usr/bin/env python3
"""
Test script to run the debugging version for Penn State 2025-26.
"""

import sys
import json

sys.path.insert(0, '/home/user/wbb')

# Load teams
teams_json = json.loads(open('/home/user/wbb/ncaa/teams.json').read())
team = [t for t in teams_json if t['ncaa_id'] == 539][0]

# Create slug
slug = str(team['ncaa_id']) + '-' + team['team'].lower().replace(" ", "-").replace('.', '').replace(',', '').replace("'", "").replace(')', '').replace('(', '')

print(f"Team: {team['team']}")
print(f"URL: {team['url']}")
print(f"Slug: {slug}")
print(f"Season: 2025-26")
print()

try:
    from ncaa.game_utils_debug import fetch_season_playwright_season_debug
    fetch_season_playwright_season_debug('2025-26', team['url'], slug)
    print("\n✓ SUCCESS!")
except Exception as e:
    print(f"\n✗ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
