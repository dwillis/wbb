import os
import requests
from bs4 import BeautifulSoup
import json

def slugify(team):
    slug = str(team['ncaa_id'])+'-'+team['team'].lower().replace(" ","-").replace('.','').replace(',','').replace("'","").replace(')','').replace('(','')
    return slug

def pbp_for_season(season="2024-25", team_ids=[31, 147, 234, 255, 312, 334, 365, 428, 463, 513, 523, 539, 328, 473, 626, 674, 736, 742, 519, 746, 415, 648, 697]):
    with open("teams.json", "r") as file:
        teams = json.load(file)
    for team_id in team_ids:
        team = [t for t in teams if t['ncaa_id'] == team_id][0]
        print(team['team'])
        if team_id in [463, 513, 365,77,127,234, 742]:
            boxscore_links = boxscore_links_for_season_direct(team, season)
        else:
            boxscore_links = boxscore_links_for_season(team, season)
        for url in boxscore_links:
            id = parse_boxscore_for_id(url)
            get_plays(id, team, season)

def boxscore_links_for_season(team, season):
    url = f"{team['url']}/schedule/season/{season}/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    boxscore_links = [team['url'].split('/sports/')[0] + l['href'] for l in soup.find_all('a', class_='schedule-event-link--boxscore')]
    return boxscore_links

def boxscore_links_for_season_direct(team, season):
    url = f"{team['url']}/schedule/season/{season}/"
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    if team['ncaa_id'] in [463, 513, 742]:
        boxscore_links = [f"https://huskers.com{l['href']}" for l in soup.find_all('a') if '/boxscore/' in l['href']]
    else:
        boxscore_links = [team['url'].split('/sports/')[0] + l['href'] for l in soup.find_all('a') if '/boxscore/' in l['href']]
    return boxscore_links

def parse_boxscore_for_id(url):
    print(url)
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    tag = [x for x in soup.find_all("a", href=True) if "https://wmt.games/huskers/stats/match/full/" in x['href']]
    id = tag[0].split('/')[-1]

    #id = soup.find("wmt-stats-iframe")['path'].split('/')[-1]
    return id

def get_plays(id, team, season):
    print(id)
    json_url = f"https://api.wmt.games/api/statistics/games/{id}?with[0]=actions&with[1]=players&with[2]=plays&with[3]=drives&with[4]=penalties"
    response = requests.get(json_url)
    game = response.json()
    if 'data' in game['data']['plays']:
        os.chdir("/Users/dwillis/code/wbb-game-data")
        slug = slugify(team)
        if not os.path.exists(slug):
            os.makedirs(slug)
        os.chdir(slug)
        if not os.path.exists(season):
            os.makedirs(season)
        os.chdir(season)
        json_file_path = f'{id}.json'
        with open(json_file_path, 'w') as json_file:
            json.dump(game, json_file, indent=4)
