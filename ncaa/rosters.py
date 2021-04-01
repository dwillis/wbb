import os
import re
import json
import argparse
import requests
from bs4 import BeautifulSoup

def fetch_url(url):
    r = requests.get(url)
    return r

def fetch_roster(base_url, season):
    url = base_url + "roster/" + season
    r = fetch_url(url)
    return BeautifulSoup(r.text, features="html.parser")

def parse_roster(html):
    roster = []
    players = html.find_all('li', {'class': 'sidearm-roster-player'})
    for player in players:
        if player.find('span', {'class': 'sidearm-roster-player-previous-school'}):
            previous_school = player.find('span', {'class': 'sidearm-roster-player-previous-school'}).text
        else:
            previous_school = None
        if player.find('span', {'class': 'sidearm-roster-player-highschool'}):
            high_school = player.find('span', {'class': 'sidearm-roster-player-highschool'}).text
        else:
            high_school = None
        roster.append({
            'name': player.find('a')['aria-label'].split(' - ')[0],
            'year': player.find_all('span', {'class': 'sidearm-roster-player-academic-year'})[1].text,
            'hometown': player.find('span', {'class': 'sidearm-roster-player-hometown'}).text,
            'high_school': high_school,
            'previous_school': previous_school,
            'height': player.find('span', {'class': 'sidearm-roster-player-height'}).text,
            'position': player.find('span', {'class': 'sidearm-roster-player-position-long-short'}).text.strip(),
            'jersey': player.find('span', {'class': 'sidearm-roster-player-jersey-number'}).text.strip()
        })
    return roster

# Example usage: python rosters.py -season 2020-21 -url https://baylorbears.com/sports/womens-basketball/

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NCAA team information')
    parser.add_argument('-season', action='store', dest='season', help='a string season such as "2020-21"')
    parser.add_argument('-url', action='store', dest='url', help='base url for a team')
    results = parser.parse_args()
    roster_html = fetch_roster(results.url, results.season)
    roster = parse_roster(roster_html)
    print(roster)
