import csv
import glob
import json
from datetime import datetime
import requests
from sqlite_utils import Database

def open_db():
    return Database('wnba.db')

def load_teams():
    db = open_db()
    teams = db['teams']
    teams_json = json.loads(open('teams.json').read())
    teams.insert_all(teams_json, pk='id')

def fetch_players():
    url = "https://data.wnba.com/data/5s/v2015/json/mobile_teams/wnba/2019/players/10_player_info.json"
    r = requests.get(url)
    with open('wnba_players.json', 'w', encoding='utf-8') as file:
        json.dump(r.json(), file, ensure_ascii=False, indent=4)

def load_roster_data(season):
    db = open_db()
    rosters = db['rosters']
    teams = ['dream', 'mystics', 'sky', 'sun', 'fever', 'liberty', 'wings', 'aces', 'sparks', 'lynx', 'mercury', 'storm']
    for team in teams:
        url = f"https://data.wnba.com/data/5s/v2015/json/mobile_teams/wnba/{season}/teams/{team}_roster.json"
        r = requests.get(url)
        team_json = r.json()
        team_id = team_json['t']['tid']
        players = team_json['t']['pl']
        for player in players:
            player['team_id'] = team_id
            season = season
        rosters.upsert_all(players, pk="pid", foreign_keys=["team_id"])

def load_following_csv(account):
    following = []
    db = open_db()
    following_table = db['following']
    with open(f"{account}.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            row['account_name'] = account
            row['join_date'] = datetime.strptime(row['join_date'], "%d %b %Y").strftime("%Y-%m-%d")
            new_row = json.dumps(row)
            following.append(json.loads(new_row))
    following_table.upsert_all(following, pk=["id", "account_name"])

def load_following_json(account):
    following = []
    db = open_db()
    following_table = db['following']
    lines = open(f"{account}.json").readlines()
    for row in lines:
        new_row = json.loads(row)
        new_row['account_name'] = account
        new_row['join_date'] = datetime.strptime(new_row['join_date'], "%d %b %Y").strftime("%Y-%m-%d")
        following.append(new_row)
    following_table.upsert_all(following, pk=["id", "account_name"])

def load_tweets():
    tweets = []
    db = open_db()
    tweets_table = db['tweets']
    accounts = glob.glob('*.json')
    for account in accounts:
        if account == 'teams.json':
            continue
        print(account)
        lines = open(account).readlines()
        if len(lines) == 0:
            continue
        for row in lines:
            new_row = json.loads(row)
            new_row['account_name'] = account.split('.json')[0]
            tweets.append(new_row)
    tweets_table.upsert_all(tweets, pk=['id'])
