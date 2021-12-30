import os
import re
import csv
import json
import argparse
import requests
import tldextract
from bs4 import BeautifulSoup

HEADERS = {'No.': 'jersey', 'Name': 'name', 'Cl.': 'academic_year', 'Pos.': 'position', 'Ht.': 'height', 'Hometown/High School': 'town', 'Hometown/Last School': 'town', 'Num': 'jersey', 'Yr': 'academic_year', 'Ht': 'height', 'Hometown': 'town', 'High School/Previous School': 'high_school', 'Pos': 'position', 'Hometown/Previous School': 'town', 'Exp.': 'academic_year', 'Number': 'jersey', 'Position': 'position', 'HT.': 'height', 'YEAR': 'academic_year', 'HOMETOWN': 'town', 'LAST SCHOOL': 'high_school', 'Yr.': 'academic_year', 'Hometown/High School/Last School': 'town', 'Class': 'academic_year', 'High school': 'high_school', 'Previous College': 'previous_school', 'Cl.-Exp.': 'academic_year', '#': 'jersey', 'High School': 'high_school', 'Hometown / Previous School': 'town', 'No': "jersey", 'Hometown/High School/Previous School': 'town'}

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

def fetch_wbkb_roster(base_url, season):
    url = base_url.replace('index',season+'/roster')
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    return BeautifulSoup(r.text, features="html.parser")

def fetch_baskbl_roster(base_url, season):
    if 'index' in base_url:
        url = base_url.replace('index','roster/?season='+season)
    elif base_url.endswith('w-baskbl'):
        url = base_url+"/"+season+"/roster"
    else:
        url = base_url + 'roster/?season='+season
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        url = base_url.replace('index', "/"+season+"/roster")
        r = requests.get(url, headers=headers)
    return BeautifulSoup(r.text, features="html.parser")

def parse_roster_baskbl(team, html, season):
    roster = []
    er = tldextract.extract(team['url'])
    cols = [x.text.strip() for x in html.find('thead').find_all('th') if x.text.strip() != '']
    new_cols = [HEADERS[c] for c in cols]
    raw_players = [x for x in html.find('tbody').find_all('tr')]
    for raw_player in raw_players:
        [x.span.decompose() for x in raw_player.find_all('td') if x.find('span')]
        raw_player_list = [x.text.strip() for x in raw_player.find_all('td')]
        raw_player_list[4] = " ".join([x for x in raw_player_list[4].split()])
        if len(raw_player_list) < len(new_cols):
            name = " ".join([x.strip() for x in raw_player.find('a').text.replace("  ","").strip().split()])
            raw_player_list.insert(1, name)
        player_dict = dict(zip(new_cols, raw_player_list))
        if 'high_school' not in player_dict:
            player_dict['town'], player_dict['high_school'] = [x.strip() for x in player_dict['town'].split('/', maxsplit=1)]
        if 'previous_school' not in player_dict:
            player_dict['previous_school'] = None
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': None,
            'name': player_dict['name'],
            'year': player_dict['academic_year'],
            'hometown': player_dict['town'],
            'high_school': player_dict['high_school'],
            'previous_school': player_dict['previous_school'],
            'height': player_dict['height'],
            'position': player_dict['position'],
            'jersey': player_dict['jersey'],
            'url': "https://www."+er.domain+"."+er.suffix+raw_player.find('a')['href'],
            'season': season
        })
    return roster

def parse_roster_wbkb(team, html, season):
    roster = []
    er = tldextract.extract(team['url'])
    headers = html.find('table').find_all('tr')[0]
    cols = [x.text.strip() for x in headers if x.text.strip() != '']
    if 'Pronounciation' in cols:
        cols.remove('Pronounciation')
    if 'Major' in cols:
        cols.remove('Major')
    new_cols = [HEADERS[c] for c in cols]
    raw_players = [x for x in html.find('tbody').find_all('tr')]
    for raw_player in raw_players:
        [x.span.decompose() for x in raw_player.find_all('td') if x.find('span')]
        raw_player_list = [x.text.strip() for x in raw_player.find_all('td') if x.text.strip() != '']
        raw_player_list[4] = " ".join([x for x in raw_player_list[4].split()])
        if team['ncaa_id'] == 1036:
            if len(raw_player_list) == len(new_cols):
                raw_player_list.pop()
        if team['ncaa_id'] == 1096:
            if len(raw_player_list) >= len(new_cols):
                raw_player_list.pop()
            if any(major in raw_player_list for major in ['Nursing', 'Biology', 'Public Health', 'Exercise Science', 'Pre-Nursing', 'Economics']):
                raw_player_list.pop()
        if len(raw_player_list) < len(new_cols):
            name = " ".join([x.strip() for x in raw_player.find('a').text.replace("  ","").strip().split()])
            raw_player_list.insert(1, name)
        player_dict = dict(zip(new_cols, raw_player_list))
        print(player_dict)
        if 'high_school' not in player_dict:
            player_dict['town'], player_dict['high_school'] = [x.strip() for x in player_dict['town'].split('/', maxsplit=1)]
        if 'previous_school' not in player_dict:
            player_dict['previous_school'] = None
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': None,
            'name': player_dict['name'],
            'year': player_dict['academic_year'],
            'hometown': player_dict['town'],
            'high_school': player_dict['high_school'],
            'previous_school': player_dict['previous_school'],
            'height': player_dict['height'],
            'position': player_dict['position'],
            'jersey': player_dict['jersey'],
            'url': "https://www."+er.domain+"."+er.suffix+raw_player.find('a')['href'],
            'season': season
        })
    return roster

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

def parse_roster(team, html, season):
    roster = []
    er = tldextract.extract(team['url'])
    try:
        players = html.find_all('li', {'class': 'sidearm-roster-player'})
    except:
        return None
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
            hometown = player.find('span', {'class': 'sidearm-roster-player-hometown'}).text.strip()
        except:
            hometown = None
        if player.find('div', {'class': 'sidearm-roster-player-position'}).text.strip() == '':
            position = 'N/A'
        if not position and '"' in player.find('div', {'class': 'sidearm-roster-player-position'}).text.strip():
            position = player.find('div', {'class': 'sidearm-roster-player-position'}).text.strip().split()[0]
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
            name = player.find('a')['aria-label'].split(' - ')[0].strip()
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
            'url': "https://www."+er.domain+"."+er.suffix+player.find('a')['href'],
            'season': season
        })
    return roster

def get_all_rosters(season, team = None):
    unparsed = []
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    if team:
        teams_json = [x for x in teams_json if x['ncaa_id'] == team]
    teams_with_urls = [x for x in teams_json if "url" in x]
    with open(f"/Users/dwillis/code/wbb/ncaa/rosters_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'team', 'player_id', 'name', 'year', 'hometown', 'high_school', 'previous_school', 'height', 'position', 'jersey', 'url', 'season'])
        for team in teams_with_urls:
            print(team['ncaa_id'])
            if 'wbkb' in team['url']:
                html = fetch_wbkb_roster(team['url'], season)
                roster = parse_roster_wbkb(team, html, season)
            elif 'w-baskbl' in team['url']:
                html = fetch_baskbl_roster(team['url'], season)
                roster = parse_roster_baskbl(team, html, season)
            else:
                html = fetch_roster(team['url'], season)
                roster = parse_roster(team, html, season)
            if roster:
                for player in roster:
                    csv_file.writerow(list(player.values()))
            else:
                unparsed.append(team['ncaa_id'])
    return unparsed

def get_all_rosters_baskbl(season):
    teams_json = json.loads(open('/Users/dwillis/code/wbb/ncaa/teams.json').read())
    teams_with_urls = [x for x in teams_json if "url" in x]
    teams_with_baskbl = [x for x in teams_with_urls if 'w-baskbl' in x['url']]
    with open(f"/Users/dwillis/code/wbb/ncaa/rosters_{season}_baskbl.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'team', 'player_id', 'name', 'year', 'hometown', 'high_school', 'previous_school', 'height', 'position', 'jersey', 'url', 'season'])
        for team in teams_with_baskbl:
            print(team['ncaa_id'])
            html = fetch_baskbl_roster(team['url'], season)
            roster = parse_roster_baskbl(team, html, season)
            if roster:
                for player in roster:
                    csv_file.writerow(list(player.values()))

# Example usage: python rosters.py -season 2021-22 -url https://baylorbears.com/sports/womens-basketball/

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NCAA team information')
    parser.add_argument('-season', action='store', dest='season', help='a string season such as "2020-21"')
    parser.add_argument('-url', action='store', dest='url', help='base url for a team')
    results = parser.parse_args()
    roster_html = fetch_roster(results.url, results.season)
    roster = parse_roster(roster_html, results.season)
    print(roster)
