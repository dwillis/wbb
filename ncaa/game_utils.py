import os
import re
import json
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def fetch_rosters(id=None, seasons=None):
    teams_json = json.loads(open('/Users/derekwillis/code/wbb/ncaa/teams.json').read())
    if not seasons:
        seasons = ['2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15']
    if id:
        team = [t for t in teams_json if id == t['ncaa_id']][0]
        slug = slugify(team)
        for season in seasons:
            try:
                fetch_season(season, team['url'], slug)
            except:
                continue
    else:
        for team in teams_json:
            slug = slugify(team)
            for season in seasons:
                try:
                    fetch_season(season, team['url'], slug)
                except:
                    continue

def fetch_game_stats(id=None, seasons=None):
    teams_json = json.loads(open('/Users/derekwillis/code/wbb/ncaa/teams.json').read())
    if not seasons:
        seasons = ['2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15']
    if id:
        team = [t for t in teams_json if id == t['ncaa_id']][0]
        slug = slugify(team)
        for season in seasons:
            try:
                fetch_season(season, team['url'], slug)
            except:
                continue
    else:
        for team in teams_json:
            slug = slugify(team)
            for season in seasons:
                try:
                    fetch_season(season, team['url'], slug)
                except:
                    continue

def fetch_season(season, base_url, slug):
    stats_url = base_url+"/stats/"
    game_ids = fetch_game_ids(season, stats_url)
    domain = parse_domain(stats_url)
    parse_games(season, domain, game_ids, slug)

def build_url(stats_url, season, section):
    return stats_url + season + "#" + section

def fetch_url(url):
    r = requests.get(url)
    return r

def fetch_game_ids(season, stats_url):
    url = build_url(stats_url, season, 'game')
    r = fetch_url(url)
    season_html = BeautifulSoup(r.text, features="html.parser")
    games = season_html.find('section', {'id': 'game-team'}).findAll('a')
    game_ids = [x['href'].split("id=")[1].replace("&path=wbball","") for x in games]
    return game_ids

def slugify(team):
    slug = str(team['ncaa_id'])+'-'+team['team'].lower().replace(" ","-").replace('.','').replace(',','').replace("'","").replace(')','').replace(')','')
    return slug

def parse_roster(season, slug):
    results = []
    os.chdir("/Users/derekwillis/code/wbb-rosters")
    if not os.path.exists(slug):
        os.makedirs(slug)
    os.chdir(slug)
    if not os.path.exists(season):
        os.makedirs(season)
    os.chdir(season)
    for game_id in game_ids:
        game_json = fetch_game_json(domain, game_id)
        write_json(game_id, game_json, season)

def parse_games(season, domain, game_ids, slug):
    results = []
    os.chdir("/Users/derekwillis/code/wbb-game-data")
    if not os.path.exists(slug):
        os.makedirs(slug)
    os.chdir(slug)
    if not os.path.exists(season):
        os.makedirs(season)
    os.chdir(season)
    for game_id in game_ids:
        game_json = fetch_game_json(domain, game_id)
        write_json(game_id, game_json, season)

def parse_domain(url):
    domain = urlparse(url).netloc
    return domain

def fetch_game_json(domain, game_id):
    url = f"https://{domain}/api/livestats?game_id={game_id}&detail=full"
    print(url)
    r = fetch_url(url)
    if r.status_code == 200:
        try:
            pbp = r.json()
        except:
            pbp = None
    else:
        pbp = None
    return pbp

def write_json(game_id, game_json, season):
    game_id = str(game_id).split('&')[0]
    filename = str(game_id) + '.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(game_json, f, ensure_ascii=False, indent=4)
