import os
import re
import csv
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
        seasons = ['2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15', '2013-14', '2012-13', '2011-12', '2010-11', '2009-10', '2008-09', '2007-08', '2006-07', '2005-06', '2004-05', '2003-04', '2002-03', '2001-02']
    if id:
        team = [t for t in teams_json if id == t['ncaa_id']][0]
        slug = slugify(team)
        print(id)
        for season in seasons:
            try:
                fetch_season(season, team['url'], slug)
            except:
                continue
    else:
        for team in teams_json:
            print(team['ncaa_id'])
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
    slug = str(team['ncaa_id'])+'-'+team['team'].lower().replace(" ","-").replace('.','').replace(',','').replace("'","").replace(')','').replace('(','')
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

def parse_game_json(slug, season, game_id):
    os.chdir("/Users/derekwillis/code/wbb-game-data")
    os.chdir(slug)
    os.chdir(season)
    return json.loads(open(game_id+'.json').read())

def parse_turnovers(team, slug, season, game_id):
    turnovers = []
    try:
        game_json = parse_game_json(slug, season, game_id)
    except:
        raise
    if game_json and game_json['Plays'] != '':
        for play in game_json['Plays']:
            if play['Type'] == 'TURNOVER':
                if play['Player'] == None:
                    t = play['Team']
                    team_name = game_json['Game'][t]['Name']
                    uniform = None
                else:
                    t = play['Player']['Team']
                    team_name = game_json['Game'][t]['Name']
                    uniform = play['Player']['UniformNumber']
                if t == 'VisitingTeam':
                    opp = 'HomeTeam'
                else:
                    opp = 'VisitingTeam'
                opponent = game_json['Game'][opp]['Name']
                turnovers.append([team['ncaa_id'], game_id, game_json['Game']['Date'], team_name, opponent, play['Period'], play['ClockSeconds'], uniform, play['Id']])
    return turnovers

def parse_plays(team, slug, season, game_id):
    plays = []
    try:
        game_json = parse_game_json(slug, season, game_id)
    except:
        raise
    if game_json and game_json['Plays'] != '':
        for play in game_json['Plays']:
            if play['Player'] == None:
                t = play['Team']
                team_name = game_json['Game'][t]['Name']
                uniform = None
            else:
                t = play['Player']['Team']
                team_name = game_json['Game'][t]['Name']
                uniform = play['Player']['UniformNumber']
            if t == 'VisitingTeam':
                opp = 'HomeTeam'
            else:
                opp = 'VisitingTeam'
            opponent = game_json['Game'][opp]['Name']
            plays.append([team['ncaa_id'], game_id, game_json['Game']['Date'], team_name, opponent, play['Type'], play['Action'], play['Period'], play['ClockSeconds'], uniform, play['Id']])
    return plays

def parse_layups(team, slug, season, game_id):
    layups = []
    try:
        game_json = parse_game_json(slug, season, game_id)
    except:
        raise
    if game_json and game_json['Plays'] != '':
        for play in game_json['Plays']:
            if play['Type'] == 'LAYUP':
                if play['Player'] == None:
                    t = play['Team']
                    team_name = game_json['Game'][t]['Name']
                    uniform = None
                else:
                    t = play['Player']['Team']
                    team_name = game_json['Game'][t]['Name']
                    uniform = play['Player']['UniformNumber']
                if t == 'VisitingTeam':
                    opp = 'HomeTeam'
                else:
                    opp = 'VisitingTeam'
                opponent = game_json['Game'][opp]['Name']
                if 'stats_name' in team and team_name == team['stats_name']:
                    layups.append([team['ncaa_id'], game_id, game_json['Game']['Date'], team_name, opponent, play['Action'], play['Period'], play['ClockSeconds'], uniform, play['Id']])
    return layups

def get_all_turnovers(season):
    teams_json = json.loads(open('/Users/derekwillis/code/wbb/ncaa/teams.json').read())
    with open(f"turnovers_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/derekwillis/code/wbb-game-data/{slug}/{season}")
            except:
                continue
            for root, dirs, files in os.walk(".", topdown=False):
                for file in files:
                    if file == '.DS_Store':
                        continue
                    game_id = file.split('.')[0]
                    print(game_id)
                    turnovers = parse_turnovers(team, slug, season, game_id)
                    for turnover in turnovers:
                        csv_file.writerow(turnover)

def get_all_layups(season):
    teams_json = json.loads(open('/Users/derekwillis/code/wbb/ncaa/teams.json').read())
    with open(f"/Users/derekwillis/code/wbb/ncaa/layups_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'action', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/derekwillis/code/wbb-game-data/{slug}/{season}")
            except:
                continue
            for root, dirs, files in os.walk(".", topdown=False):
                for file in files:
                    if file == '.DS_Store':
                        continue
                    game_id = file.split('.')[0]
                    print(game_id)
                    layups = parse_layups(team, slug, season, game_id)
                    for layup in layups:
                        csv_file.writerow(layup)

def get_all_plays(season):
    teams_json = json.loads(open('/Users/derekwillis/code/wbb/ncaa/teams.json').read())
    with open(f"/Users/derekwillis/code/wbb/ncaa/plays_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'type', 'action', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/derekwillis/code/wbb-game-data/{slug}/{season}")
            except:
                continue
            for root, dirs, files in os.walk(".", topdown=False):
                for file in files:
                    if file == '.DS_Store':
                        continue
                    game_id = file.split('.')[0]
                    print(game_id)
                    plays = parse_plays(team, slug, season, game_id)
                    for play in plays:
                        csv_file.writerow(play)
