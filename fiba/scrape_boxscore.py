import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlite_utils import Database

BASE_URL = "https://www.fiba.basketball"

def get_game_urls(event_slug):
    page = requests.get(BASE_URL + event_slug).text
    soup = BeautifulSoup(page, "html.parser")
    link_ls = [div.find('a').get("href")
               for div in soup.select("div.game_item")]
    return link_ls

def get_players(link_ls):
    all_tables = []

    for a in link_ls:
        try:
            all_tables.append(get_boxscore(BASE_URL + a))
        except (ValueError, TypeError, AttributeError):
            print("Problem with", BASE_URL + a)
            raise
        time.sleep(3)
    return all_tables

def get_boxscore(game_url):
    print(game_url)
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
    names = game_url.split("/")[-1].split("-")

    all_players = []

    for i in range(len(names)):
        if "Republic" in game_url:
            if names[i].startswith("Republic"):
                names[i] = "Dominican Republic"
            elif names[i].startswith("Dominican"):
                names[i] = "Dominican Republic"
        if "Bosnia" in game_url:
            if names[i].startswith("Bosnia"):
                names[i] = "Bosnia & Herzegovina"
            elif names[i].startswith("Herzegovina"):
                names[i] = "Bosnia & Herzegovina"
            elif names[i].startswith("and"):
                names[i] = "Bosnia & Herzegovina"
        if "Salvador" in game_url:
            if names[i].startswith("Salvador"):
                names[i] = "El Salvador"
            elif names[i].startswith("El"):
                names[i] = "El Salvador"
        if "Rico" in game_url:
            if names[i].startswith("Rico"):
                names[i] = "Puerto Rico"
            elif names[i].startswith("Puerto"):
                names[i] = "Puerto Rico"
        if "Virgin" in game_url:
            if names[i].startswith("Islands"):
                names[i] = "Virgin Islands"
            elif names[i].startswith("Virgin"):
                names[i] = "Virgin Islands"
            elif names[i].startswith("US"):
                names[i] = "Virgin Islands"
        if "Taipei" in game_url:
            if names[i].startswith("Taipei"):
                names[i] = "Chinese Taipei"
            elif names[i].startswith("Chinese"):
                names[i] = "Chinese Taipei"
        if "Zealand" in game_url:
            if names[i].startswith("Zealand"):
                names[i] = "New Zealand"
            elif names[i].startswith("New"):
                names[i] = "New Zealand"
        if "Britain" in game_url:
            if names[i].startswith("Great"):
                names[i] = "Great Britain"
            elif names[i].startswith("Britain"):
                names[i] = "Great Britain"
        if "Macedonia" in game_url:
            if names[i].startswith("North"):
                names[i] = "North Macedonia"
            elif names[i].startswith("Macedonia"):
                names[i] = "North Macedonia"
        if "Cook" in game_url:
            if names[i].startswith("Cook"):
                names[i] = "Cook Islands"
            elif names[i].startswith("Islands"):
                names[i] = "Cook Islands"
        if "Caledonia" in game_url:
            if names[i].startswith("New"):
                names[i] = "New Caledonia"
            elif names[i].startswith("Caledonia"):
                names[i] = "New Caledonia"
        if "Caledonia" in game_url:
            if names[i].startswith("New"):
                names[i] = "New Caledonia"
            elif names[i].startswith("Caledonia"):
                names[i] = "New Caledonia"
        if "Marshall" in game_url:
            if names[i].startswith("Marshall"):
                names[i] = "Marshall Islands"
            elif names[i].startswith("Islands"):
                names[i] = "Marshall Islands"
        if "Papua" in game_url:
            if names[i].startswith("Papua"):
                names[i] = "Papua New Guinea"
            elif names[i].startswith("New"):
                names[i] = "Papua New Guinea"
            elif names[i].startswith("Guinea"):
                names[i] = "Papua New Guinea"

    for i, team in enumerate([loc_box, aw_box]):
        for player in team.find_all("tr"):
            example = [d.text.strip().split("\n")[0] for d in player.find_all("td") if d != "\n"]
            if len(example) < len(colnames):
                example = example[:-1]
                example = example + ["0:0", "0"] + ["0/0"] * 4 + ["0"] * 10
            player_data = {"country": names[i], "vs": names[i-1],
                           "team_score": scores[i], "vs_score": scores[i-1],
                           "date": date}
            for a,b in zip(colnames, example):
                player_data[a] = b

            all_players.append(player_data)

    return pd.DataFrame(all_players)

if __name__ == "__main__":
    event_slug = "/oceania/u17women/2019/games"
    link_ls = get_game_urls(event_slug)
    players = get_players(link_ls)
    df = pd.concat(players)
    df.to_csv("u17oceania_2019_players_game_stats.csv", index = None)
