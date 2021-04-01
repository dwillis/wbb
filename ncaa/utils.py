import os
import glob
import json
import time
from datetime import datetime
from sqlite_utils import Database
import tweepy

auth = tweepy.OAuthHandler('j8gO12xQHIu9Ukx6ofQfdNdeC', 'F0wQmBCs89doG73XVzpkJU22zryk8sQ2rYCP5dVDvZQZSijqyG')
auth.set_access_token('14517538-17ddx0zvhvPTeQcVAgzfjstFKRnc4wXLOjLkgpiBr', 'FljJEiS7wS2vIoT6RosFZj1GgVqRUXsJgSOu8EN0lcJ0z')
api = tweepy.API(auth)

def open_db():
    return Database('ncaa.db')

def load_teams():
    db = open_db()
    teams = db['teams']
    teams_json = json.loads(open('teams.json').read())
    teams.insert_all(teams_json)


def get_player_tweets(start):
    db = Database('ncaa.db')
    player_tweets_table = db['player_tweets']
    player_json = json.loads(open('players.json').read())
    for account in player_json[start:]:
        tweets = []
        print(account)
        try:
            user = api.get_user(account)
#            r = db.execute(f"select min(id) from player_tweets where account_name = '{account}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user.id):
                tw = {}
                tw['account_name'] = account
                tw['id'] = tweet.id
                tw['url'] = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id_str}"
                tw['text'] = tweet.text
                if 'retweeted_status' in tweet._json:
                    tw['is_rt'] = True
                    tw['rt_url'] = f"https://twitter.com/{tweet.retweeted_status.user.screen_name}/status/{tweet.retweeted_status.id}"
                else:
                    tw['is_rt'] = False
                    tw['rt_url'] = None
                tw['created_at'] = tweet.created_at
                tw['in_reply_to'] = tweet.in_reply_to_status_id
                tw['in_reply_to_name'] = tweet.in_reply_to_screen_name
                tw['is_quote_status'] = tweet.is_quote_status
                tw['retweet_count'] = tweet.retweet_count
                tw['favorite_count'] = tweet.favorite_count
                tweets.append(tw)
        except tweepy.error.TweepError:
            continue
        except tweepy.RateLimitError:
            print('waiting...')
            time.sleep(15 * 60)
        player_tweets_table.upsert_all(tweets, pk="id")

def get_team_tweets(start):
    db = Database('ncaa.db')
    tweets_table = db['tweets']
    teams_json = json.loads(open('teams.json').read())
    for team in teams_json[start:]:
        if 'private' in team:
            continue
        tweets = []
        print(team['twitter'])
        try:
            user = api.get_user(team['twitter'])
#            r = db.execute(f"select min(id) from tweets where account_name = '{team['twitter']}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user.id):
                tw = {}
                tw['team_id'] = team['ncaa_id']
                tw['account_name'] = team['twitter']
                tw['id'] = tweet.id
                tw['url'] = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id_str}"
                tw['text'] = tweet.text
                tw['created_at'] = tweet.created_at
                tw['in_reply_to'] = tweet.in_reply_to_status_id
                tw['in_reply_to_name'] = tweet.in_reply_to_screen_name
                tw['is_quote_status'] = tweet.is_quote_status
                tw['retweet_count'] = tweet.retweet_count
                tw['favorite_count'] = tweet.favorite_count
                tweets.append(tw)
        except tweepy.RateLimitError:
            print('waiting...')
            time.sleep(15 * 60)
        tweets_table.upsert_all(tweets, pk="id")

def update_following(start):
    db = Database('ncaa.db')
    following_table = db['following']
    teams_json = json.loads(open('teams.json').read())
    for team in teams_json[start:]:
        if 'private' in team:
            continue
        following = []
        print(team['twitter'])
        try:
            user = api.get_user(team['twitter'])
            for friend in user.friends():
                follow = {}
                follow['team_id'] = team['ncaa_id']
                follow['account_name'] = team['twitter']
                follow['join_date'] = friend.created_at.strftime("%Y-%m-%d")
                follow['id'] = friend.id
                follow['username'] = friend.screen_name
                follow['bio'] = friend.description
                follow['name'] = friend.name
                following.append(follow)
        except tweepy.RateLimitError:
            print('waiting...')
            time.sleep(15 * 60)
        following_table.upsert_all(following, pk=["id", "account_name"])

def load_following_json(account, db):
    print(account)
    following = []
    following_table = db['following']
    teams_file = 'teams.json'
    teams = json.loads(open(teams_file).read())
    team = next((t for t in teams if account.split('.json')[0] == t['twitter']), None)
    lines = open('/Users/derekwillis/code/wbb/ncaa/teams/'+account).readlines()
    for row in lines:
        new_row = json.loads(row)
        new_row['team_id'] = team['ncaa_id']
        new_row['account_name'] = team['twitter']
        new_row['join_date'] = datetime.strptime(new_row['join_date'], "%d %b %Y").strftime("%Y-%m-%d")
        new_row['update_date'] = datetime.today()
        following.append(new_row)
    following_table.upsert_all(following, pk=["id", "account_name"])

def limit_handled(cursor):
    while True:
        try:
            yield next(cursor)
        except tweepy.RateLimitError:
            time.sleep(15 * 60)

def load_all():
    db = open_db()
    os.chdir('teams')
    teams = glob.glob('*.json')
    os.chdir('..')
    for team in teams:
        load_following_json(team, db)
