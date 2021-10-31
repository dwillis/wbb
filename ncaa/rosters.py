import os
import re
import json
import argparse
import requests
from bs4 import BeautifulSoup

SEASONS = ['2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15', '2013-14',
'2012-13', '2011-12', '2010-11', '2009-10', '2008-09', '2007-08', '2006-07', '2005-06', '2004-05', '2003-04',
'2002-03', '2001-02', '2000-01', '1999-00', '1998-99', '1997-98', '1996-97', '1995-96', '1994-95', '1993-94', '1992-93', '1991-92', '1990-91']

def fetch_url(url):
    r = requests.get(url)
    return r

def fetch_roster(base_url, season):
    url = base_url + "/roster/" + season
    r = fetch_url(url)
    if r.history:
        return None
    return BeautifulSoup(r.text, features="html.parser")

def fetch_roster_datatables(url, season):
    r = fetch_url(url)
    return BeautifulSoup(r.text, features="html.parser")

def parse_roster_datatables(html):
    roster = []
    players = html.find('table').find_all('tr')[1:]
    for player in players:
        jersey, first, last, height, position, year, hometown, high_school, season = [x.text.strip() for x in player.find_all('td')]
        name = first + ' ' + last
        roster.append({
            'name': name,
            'year': year,
            'hometown': hometown,
            'high_school': high_school,
            'previous_school': None,
            'height': height,
            'position': position,
            'jersey': jersey
        })
    return roster

def parse_roster(html):
    roster = []
    players = html.find_all('li', {'class': 'sidearm-roster-player'})
    for player in players:
        position = None
        if player.find('span', {'class': 'sidearm-roster-player-previous-school'}):
            previous_school = player.find('span', {'class': 'sidearm-roster-player-previous-school'}).text
        else:
            previous_school = None
        if player.find('span', {'class': 'sidearm-roster-player-highschool'}):
            high_school_text = player.find('span', {'class': 'sidearm-roster-player-highschool'}).text.strip()
            high_school = " ".join([x.strip() for x in high_school_text.split(' ') if x != ''])
        else:
            high_school = None
        if player.find('span', {'class': 'sidearm-roster-player-height'}):
            height = player.find('span', {'class': 'sidearm-roster-player-height'}).text
        else:
            height = None
        try:
            hometown = player.find('span', {'class': 'sidearm-roster-player-hometown'}).text
        except:
            hometown = None
        if player.find('div', {'class': 'sidearm-roster-player-position'}).text.strip() == '':
            position = 'N/A'
        if not position and '"' in player.find('div', {'class': 'sidearm-roster-player-position'}).text.strip():
            position = 'N/A'
        if not position and player.find('div', {'class': 'sidearm-roster-player-position'}).find('span', {'class': 'text-bold'}).find('span', {'class': 'sidearm-roster-player-position-long-short hide-on-small-down'}):
            try:
                position = player.find('div', {'class': 'sidearm-roster-player-position'}).find('span', {'class': 'text-bold'}).find('span', {'class': 'sidearm-roster-player-position-long-short hide-on-small-down'}).text.strip()
            except AttributeError:
                position = None
        if not position and player.find('div', {'class': 'sidearm-roster-player-position'}).find('span', {'class': 'text-bold'}):
            try:
                position = player.find('div', {'class': 'sidearm-roster-player-position'}).find('span', {'class': 'text-bold'}).text.strip()
            except AttributeError:
                position = None
        try:
            jersey = player.find('span', {'class': 'sidearm-roster-player-jersey-number'}).text.strip()
        except:
            jersey = None
        try:
            academic_year = player.find_all('span', {'class': 'sidearm-roster-player-academic-year'})[1].text
        except:
            academic_year = None
        try:
            name = player.find('a')['aria-label'].split(' - ')[0]
        except:
            name = player.find('h3').text.strip()
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': player['data-player-id'],
            'name': name,
            'year': academic_year,
            'hometown': hometown,
            'high_school': high_school,
            'previous_school': previous_school,
            'height': height,
            'position': position,
            'jersey': jersey,
            'url': player.find('a')['href'],
            'season': season
        })
    return roster

# Example usage: python rosters.py -season 2021-22 -url https://baylorbears.com/sports/womens-basketball/

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NCAA team information')
    parser.add_argument('-season', action='store', dest='season', help='a string season such as "2020-21"')
    parser.add_argument('-url', action='store', dest='url', help='base url for a team')
    results = parser.parse_args()
    roster_html = fetch_roster(results.url, results.season)
    roster = parse_roster(roster_html, results.season)
    print(roster)
