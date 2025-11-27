import os
import re
import csv
import json
from urllib.parse import urlparse
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def validate_season(season):
    """
    Validates that a season string follows the expected format (e.g., '2024-25').

    Args:
        season: The season string to validate

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValueError: If the season format is invalid
    """
    if not season or not isinstance(season, str):
        raise ValueError(f"Invalid season: '{season}' - season must be a non-empty string")

    # Check if season matches the expected pattern YYYY-YY
    season_pattern = re.compile(r'^\d{4}-\d{2}$')
    if not season_pattern.match(season):
        raise ValueError(f"Invalid season format: '{season}' - expected format is 'YYYY-YY' (e.g., '2024-25')")

    # Additional validation: check that the years are consecutive
    try:
        start_year = int(season[:4])
        end_year_short = int(season[5:7])
        expected_end = (start_year + 1) % 100

        if end_year_short != expected_end:
            raise ValueError(f"Invalid season: '{season}' - years must be consecutive (e.g., '2024-25', not '2024-26')")
    except (ValueError, IndexError):
        raise ValueError(f"Invalid season format: '{season}' - expected format is 'YYYY-YY' (e.g., '2024-25')")

    return True

def fetch_rosters(id=None, seasons=None):
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    if not seasons:
        seasons = ['2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15']
    elif isinstance(seasons, str):
        seasons = [seasons]
    if id:
        team = [t for t in teams_json if str(id) == str(t['ncaa_id'])][0]
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
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    if not seasons:
        seasons = ['2025-26','2024-25','2023-24','2022-23','2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15', '2013-14', '2012-13', '2011-12', '2010-11', '2009-10', '2008-09', '2007-08', '2006-07', '2005-06', '2004-05', '2003-04', '2002-03', '2001-02']
    elif isinstance(seasons, str):
        seasons = [seasons]
    if id:
        team = [t for t in teams_json if str(id) == str(t['ncaa_id'])][0]
        slug = slugify(team)
        print(id)
        for season in seasons:
            try:
                fetch_season(season, team['url'], slug)
            except:
                try:
                    fetch_season_playwright(season, team['url'], slug)
                except:
                    continue
    else:
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            for season in seasons:
                try:
                    if team['ncaa_id'] == "539":
                        fetch_season_playwright_season(season, team['url'], slug, page_type='sked')
                    else:
                        fetch_season(season, team['url'], slug)
                except:
                    try:
                        fetch_season_playwright(season, team['url'], slug)
                    except:
                        continue

def fetch_season(season, base_url, slug):
    validate_season(season)
    stats_url = base_url+"/stats/"
    game_ids = fetch_game_ids(season, stats_url)
    domain = parse_domain(stats_url)
    parse_games(season, domain, game_ids, slug)


def fetch_season_playwright(season, base_url, slug):
    validate_season(season)
    stats_url = base_url+f"/stats/{season}"
    game_ids = fetch_game_ids_playwright(stats_url)
    domain = parse_domain(stats_url)
    parse_games(season, domain, game_ids, slug)

def fetch_season_playwright_season(season, base_url, slug, page_type='stats'):
    validate_season(season)
    if page_type == 'sked':
        stats_url = base_url+f"/schedule/season/{season}"
    else:
        stats_url = base_url+f"/stats/season/{season}"
    game_ids = fetch_game_ids_playwright(stats_url, page_type)
    domain = parse_domain(stats_url)
    parse_games(season, domain, game_ids, slug)


def build_url(stats_url, season, section):
    return stats_url + season + "#" + section

def fetch_url(url):
    r = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    return r

def fetch_game_ids_playwright(url, page_type='stats'):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Change to True to run headless
        page = browser.new_page()
        page.goto(url)
        
        if page_type == 'stats':
            # Click on the "Game-by-game" tab
            page.click("text=Game-By-Game")
        
        # Wait for the content to load
        page.wait_for_timeout(3000)
        
        # Find game links
        game_links = page.locator("a[href*='boxscore']").all()
        
        # Extract href attributes
        ids = []
        for link in game_links:
            href = link.get_attribute("href")
            if href:
                parts = href.rstrip("/").split("/")
                if parts and parts[-1].isdigit():
                    ids.append(parts[-1])
                elif href.split("=")[1].replace("&path",'').isdigit():
                    ids.append(href.split("=")[1].replace("&path",''))            
        
        browser.close()
        return ids

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
    os.chdir("/Users/dwillis/code/wbb-rosters")
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
    validate_season(season)  # Extra validation layer
    results = []
    os.chdir("/Users/dwillis/code/wbb-game-data")
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
    os.chdir("/Users/dwillis/code/wbb-game-data")
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

def parse_officials(team, slug, season, game_id):
    officials = []
    try:
        game_json = parse_game_json(slug, season, game_id)
    except:
        raise
    try:
        if game_json and game_json['Game'] != '':
            if game_json['Game']['Officials']:
                home_team = game_json['Game']['HomeTeam']['Name']
                visiting_team = game_json['Game']['VisitingTeam']['Name']
                officials.append([team['ncaa_id'], game_id, game_json['Game']['Date'], home_team, game_json['Stats']['HomeTeam']['Totals']['Values']['PersonalFouls'], game_json['Stats']['HomeTeam']['Totals']['Values']['TechnicalFouls'], visiting_team, game_json['Stats']['VisitingTeam']['Totals']['Values']['PersonalFouls'], game_json['Stats']['VisitingTeam']['Totals']['Values']['TechnicalFouls'], game_json['Game']['Officials']])
    except:
        pass
    return officials

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
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    with open(f"turnovers_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/dwillis/code/wbb-game-data/{slug}/{season}")
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
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    with open(f"/Users/dwillis/code/wbb/ncaa/layups_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'action', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/dwillis/code/wbb-game-data/{slug}/{season}")
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

def get_all_officials(season):
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    with open(f"/Users/dwillis/code/wbb/ncaa/officials_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'home', 'home_fouls', 'home_technicals', 'visitor', 'visitor_fouls', 'visitor_technicals', 'officials'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/dwillis/code/wbb-game-data/{slug}/{season}")
            except:
                continue
            for root, dirs, files in os.walk(".", topdown=False):
                for file in files:
                    if file == '.DS_Store':
                        continue
                    game_id = file.split('.')[0]
                    print(game_id)
                    officials = parse_officials(team, slug, season, game_id)
                    for official in officials:
                        csv_file.writerow(official)

def get_all_plays(season):
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    with open(f"/Users/dwillis/code/wbb/ncaa/plays_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'game_id', 'date', 'team', 'opponent', 'type', 'action', 'period', 'seconds', 'player', 'play_id'])
        for team in teams_json:
            print(team['ncaa_id'])
            slug = slugify(team)
            try:
                os.chdir(f"/Users/dwillis/code/wbb-game-data/{slug}/{season}")
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

def count_game_files_all_seasons():
    base_path = "/Users/dwillis/code/wbb-game-data"
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())

    # Regex to match valid season folders like "2024-25"
    season_pattern = re.compile(r'^\d{4}-\d{2}$')

    # Map slug to team info
    slug_to_team = {slugify(team): team for team in teams_json}

    all_seasons = set()
    team_season_counts = {}

    for slug in os.listdir(base_path):
        team_path = os.path.join(base_path, slug)
        if not os.path.isdir(team_path) or slug not in slug_to_team:
            continue

        team_season_counts[slug] = {}

        for season in os.listdir(team_path):
            if not season_pattern.match(season):
                continue  # skip non-season folders

            season_path = os.path.join(team_path, season)
            if not os.path.isdir(season_path):
                continue

            all_seasons.add(season)

            try:
                files = os.listdir(season_path)
                game_files = [f for f in files if f.endswith('.json') and not f.startswith('.')]
                team_season_counts[slug][season] = len(game_files)
            except Exception as e:
                print(f"Error reading {season_path}: {e}")
                team_season_counts[slug][season] = 0

    all_seasons = sorted(all_seasons)

    # Write CSV
    with open("game_file_counts_all_seasons.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        header = ['ncaa_id', 'team_name'] + all_seasons
        csv_file.writerow(header)

        for slug, team in slug_to_team.items():
            ncaa_id = team['ncaa_id']
            team_name = team.get('team', 'Unknown Team')
            season_counts = team_season_counts.get(slug, {})
            row = [ncaa_id, team_name] + [season_counts.get(season, 0) for season in all_seasons]
            csv_file.writerow(row)

def get_teams_with_zero_games(season, file_path="game_file_counts_all_seasons.csv"):
    """
    Load game file count data from CSV and return teams with 0 games in a given season.
    
    :param season: str, like "2023-24"
    :param file_path: str, path to the CSV file
    :return: list of team names
    """
    df = pd.read_csv(file_path)

    if season not in df.columns:
        raise ValueError(f"Season '{season}' not found in the data.")

    return df[df[season] == 0]['team_name'].tolist()
