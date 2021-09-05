import time
import requests
import requests_cache
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlite_utils import Database

BASE_URL = "https://www.fiba.basketball"

requests_cache.install_cache('fiba_cache')

def get_game_urls(event_slug):
    page = requests.get(BASE_URL + event_slug).text
    soup = BeautifulSoup(page, "html.parser")
    link_ls = [div.find('a').get("href")
               for div in soup.select("div.game_item")]
    return link_ls

def get_players(link_ls):
    all_tables = []
    for a in link_ls:
        if a == None:
            continue
        try:
            all_tables.append(get_boxscore(BASE_URL + a))
        except (ValueError, TypeError, AttributeError):
            print("Problem with", BASE_URL + a)
            raise
        time.sleep(1)
    return all_tables

def get_boxscore(game_url):
    print(game_url)
#    if game_url == 'https://www.fiba.basketballhttps://www.fiba.basketball/u16americas/women/2021/game/2908/Canada-USA':
#        game_url = 'https://www.fiba.basketball/u16americas/women/2021/game/2908/Canada-USA'
    try:
        box_sc_p = requests.get(game_url).text
    except:
        box_sc_p = requests.get(game_url).text
    box_sc = BeautifulSoup(box_sc_p, "html.parser")

    data_dir = box_sc.find("li", {"data-tab-content": "boxscore"}).get("data-ajax-url")
    boxsc_p = requests.get(BASE_URL + data_dir).text
    boxsc = BeautifulSoup(boxsc_p, "html.parser")

    # check to see if game completed
    if len(boxsc.find_all("tbody")) == 0:
        return None

    scores = [s for s in box_sc.find("div", class_= "final-score").text.split("\n") if s]
    date = game_url.split("/")[-2]

    loc_box, aw_box = boxsc.find_all("tbody")
    colnames = [d.text for d in boxsc.find("thead").find_all("th")]
    teams = [s.text for s in box_sc.find_all('span', class_='team-name')[:2]]

    all_players = []

    for i, team in enumerate([loc_box, aw_box]):
        for player in team.find_all("tr"):
            example = [d.text.strip().split("\n")[0] for d in player.find_all("td") if d != "\n"]
            if len(example) < len(colnames):
                example = example[:-1]
                example = example + ["0:0", "0"] + ["0/0"] * 4 + ["0"] * 10
            player_data = {"country": teams[i], "vs": teams[i-1],
                           "team_score": scores[i], "vs_score": scores[i-1],
                           "date": date}
            for a,b in zip(colnames, example):
                player_data[a] = b

            all_players.append(player_data)

    return pd.DataFrame(all_players)

if __name__ == "__main__":
    event_slug = "/oceania/u15women/2018/games"
    link_ls = get_game_urls(event_slug)
    players = get_players(link_ls)
    df = pd.concat(players)
    df.to_csv("u15oceania_2018_players_game_stats.csv", index = None)
