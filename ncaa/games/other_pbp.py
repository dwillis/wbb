import os
import requests
from bs4 import BeautifulSoup
import json

def slugify(team):
    slug = str(team['ncaa_id'])+'-'+team['team'].lower().replace(" ","-").replace('.','').replace(',','').replace("'","").replace(')','').replace('(','')
    return slug

def pbp_for_season(season="2025-26", team_ids=[31, 147, 234, 255, 312, 334, 365, 428, 463, 513, 523, 539, 328, 473, 626, 674, 736, 742, 519, 746, 415, 648, 697]):
    try:
        with open("teams.json", "r") as file:
            teams = json.load(file)
    except FileNotFoundError:
        print("Error: teams.json not found in current directory")
        return

    for team_id in team_ids:
        team_matches = [t for t in teams if t['ncaa_id'] == team_id]
        if not team_matches:
            print(f"Warning: Team ID {team_id} not found in teams.json")
            continue

        team = team_matches[0]
        print(f"Processing: {team['team']}")

        try:
            if team_id in [539, 463, 365, 77, 127, 234, 742, 312, 559]:
                boxscore_links = boxscore_links_for_season_direct(team, season)
            else:
                boxscore_links = boxscore_links_for_season(team, season)

            print(f"Found {len(boxscore_links)} games for {team['team']}")

            for url in boxscore_links:
                try:
                    id = parse_boxscore_for_id(url)
                    get_plays(id, team, season)
                except Exception as e:
                    print(f"Error processing {url}: {e}")
                    continue
        except Exception as e:
            print(f"Error processing team {team['team']}: {e}")
            continue

def boxscore_links_for_season(team, season):
    url = f"{team['url']}/schedule/season/{season}/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    boxscore_links = [team['url'].split('/sports/')[0] + l['href'] for l in soup.find_all('a', class_='schedule-event-link--boxscore')]
    return boxscore_links

def boxscore_links_for_season_direct(team, season):
    url = f"{team['url']}/schedule/season/{season}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"Warning: Got status code {r.status_code} for {url}")
        if r.status_code == 403:
            print("  Site may be blocking automated requests. Try accessing from a different network/IP.")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    if team['ncaa_id'] in [463]:
        boxscore_links = [f"https://huskers.com{l['href']}" for l in soup.find_all('a') if '/boxscore/' in l['href']]
    else:
        boxscore_links = [team['url'].split('/sports/')[0] + l['href'] for l in soup.find_all('a') if '/boxscore/' in l['href']]
    return boxscore_links

def parse_boxscore_for_id(url):
    print(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Try to find WMT game ID in anchor tags (works for some teams)
    tag = [x for x in soup.find_all("a", href=True) if "wmt.games" in x['href'] and "/stats/match/full/" in x['href']]
    if tag:
        id = tag[0]['href'].split('/')[-1]
        return id
    
    # If not found in anchor tags, search for it in JavaScript data
    # Pattern: /stats/match/full/XXXXXXX or /stats/match/XXXXXXX
    import re
    pattern = r'/stats/match/(?:full/)?(\d+)'
    matches = re.findall(pattern, r.text)
    if matches:
        # Return the first unique match
        return matches[0]
    
    print(f"Warning: No game ID found for {url}")
    return None

def get_plays(id, team, season):
    if id is None:
        print("Skipping game - no ID found")
        return
    print(id)
    json_url = f"https://api.wmt.games/api/statistics/games/{id}?with[0]=actions&with[1]=players&with[2]=plays&with[3]=drives&with[4]=penalties"
    response = requests.get(json_url)
    game = response.json()
    if 'data' in game['data']['plays']:
        slug = slugify(team)
        # Base directory for JSON files
        base_dir = os.path.expanduser("~/code/wbb-game-data")
        # Create directory structure: base_dir/slug/season/
        season_dir = os.path.join(base_dir, slug, season)
        os.makedirs(season_dir, exist_ok=True)

        json_file_path = os.path.join(season_dir, f'{id}.json')
        with open(json_file_path, 'w') as json_file:
            json.dump(game, json_file, indent=4)
        print(f"Saved: {json_file_path}")
