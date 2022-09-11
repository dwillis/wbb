import os
import glob
import json
import time
from datetime import datetime
from sqlite_utils import Database
import tweepy

auth = tweepy.OAuthHandler(os.getenv('TWITTER_KEY'), os.getenv('TWITTER_SECRET_KEY'))
auth.set_access_token(os.getenv('TWITTER_TOKEN'), os.getenv('TWITTER_TOKEN_SECRET'))
api = tweepy.API(auth)

def open_db():
    return Database('ncaa.db')

def load_teams():
    db = open_db()
    teams = db['teams']
    teams_json = json.loads(open('teams.json').read())
    teams.insert_all(teams_json)

def get_coaches_tweets(start):
    db = Database('ncaa.db')
    coaches_tweets_table = db['coaches_tweets']
    coaches_json = json.loads(open('coaches.json').read())
    for account in coaches_json[start:]:
        tweets = []
        print(account)
        try:
            user = api.get_user(screen_name=account)
#            r = db.execute(f"select min(id) from player_tweets where account_name = '{account}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user_id=user.id):
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
        except tweepy.TooManyRequests:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.TweepyException:
            continue
        coaches_tweets_table.upsert_all(tweets, pk="id")

def get_player_tweets(start):
    db = Database('ncaa.db')
    player_tweets_table = db['player_tweets']
    player_json = json.loads(open('players.json').read())
    for account in player_json[start:]:
        tweets = []
        print(account)
        try:
            user = api.get_user(screen_name=account)
#            r = db.execute(f"select min(id) from player_tweets where account_name = '{account}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user_id=user.id):
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
        except tweepy.TooManyRequests:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.TweepyException:
            continue
        player_tweets_table.upsert_all(tweets, pk="id")

def get_commit_tweets(start):
    db = Database('ncaa.db')
    commits_tweets_table = db['commit_tweets']
    commits_json = json.loads(open('commits.json').read())
    for account in commits_json[start:]:
        tweets = []
        print(account)
        try:
            user = api.get_user(screen_name=account)
#            r = db.execute(f"select min(id) from player_tweets where account_name = '{account}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user_id=user.id):
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
        except tweepy.TooManyRequests:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.TweepyException:
            continue
        commits_tweets_table.upsert_all(tweets, pk="id")

def get_team_tweets(start):
    suspended = []
    db = Database('ncaa.db')
    tweets_table = db['tweets']
    teams_json = json.loads(open('teams.json').read())
    for team in teams_json[start:]:
        if 'private' in team:
            if team['private'] == True:
                continue
        tweets = []
        print(team['twitter'])
        try:
            user = api.get_user(screen_name=team['twitter'])
#            r = db.execute(f"select min(id) from tweets where account_name = '{team['twitter']}'")
#            min_id = r.fetchone()
#            for tweet in api.user_timeline(user.id, max_id=min_id[0]):
            for tweet in api.user_timeline(user_id=user.id):
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
        except tweepy.errors.TooManyRequests:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.TweepyException as e:
            if e.api_code == 63:
                suspended.append(team['twitter'])
            else:
                continue
        tweets_table.upsert_all(tweets, pk="id")
    print(suspended)

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
            current_ids = api.friends_ids(team['twitter'])
            r = db.execute(f"select id from following where account_name = '{team['twitter']}'")
            ids = [i[0] for i in r.fetchall()]
            ids_to_load = (list(list(set(current_ids)-set(ids)) + list(set(ids)-set(current_ids))))
            groups = [ids_to_load[i * 100:(i + 1) * 100] for i in range((len(ids_to_load) + 100 - 1) // 100 )]
            if len(groups) > 0:
                for group in groups:
                    try:
                        users = api.lookup_users(group)
                        for user in users:
                            follow = {}
                            follow['team_id'] = team['ncaa_id']
                            follow['account_name'] = team['twitter']
                            follow['join_date'] = user.created_at.strftime("%Y-%m-%d")
                            follow['id'] = user.id
                            follow['username'] = user.screen_name
                            follow['bio'] = user.description
                            follow['name'] = user.name
                            follow['created_at'] = datetime.now().strftime("%Y-%m-%d")
                            following.append(follow)
                    except:
                        continue
        except tweepy.RateLimitError:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.error.TweepError:
            continue
        following_table.upsert_all(following, pk=["id", "account_name"])

def update_player_following(start):
    db = Database('ncaa.db')
    following_table = db['following']
    players_json = json.loads(open('players.json').read())
    for player in players_json[start:]:
        following = []
        print(player)
        try:
            current_ids = api.friends_ids(player)
            r = db.execute(f"select id from following where account_name = '{player}'")
            ids = [i[0] for i in r.fetchall()]
            ids_to_load = (list(list(set(current_ids)-set(ids)) + list(set(ids)-set(current_ids))))
            groups = [ids_to_load[i * 100:(i + 1) * 100] for i in range((len(ids_to_load) + 100 - 1) // 100 )]
            if len(groups) > 0:
                for group in groups:
                    try:
                        users = api.lookup_users(group)
                        for user in users:
                            follow = {}
                            follow['team_id'] = None
                            follow['account_name'] = player
                            follow['join_date'] = user.created_at.strftime("%Y-%m-%d")
                            follow['id'] = user.id
                            follow['username'] = user.screen_name
                            follow['bio'] = user.description
                            follow['name'] = user.name
                            follow['created_at'] = datetime.now().strftime("%Y-%m-%d")
                            following.append(follow)
                    except:
                        continue
        except tweepy.RateLimitError:
            print('waiting...')
            time.sleep(15 * 60)
        except tweepy.error.TweepError:
            continue
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
