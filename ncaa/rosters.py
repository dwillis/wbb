import os
import re
import csv
import json
import argparse
import requests
from requests_html import HTMLSession
import tldextract
from bs4 import BeautifulSoup

HEADERS = {'No.': 'jersey', 'Name': 'name', 'Cl.': 'academic_year', 'Pos.': 'position', 'Ht.': 'height', 'Hometown/High School': 'town', 'Hometown/Last School': 'town', 'Num': 'jersey', 'Yr': 'academic_year', 'Ht': 'height', 'Hometown': 'town', 'High School/Previous School': 'high_school', 'Pos': 'position', 'Hometown/Previous School': 'town', 'Exp.': 'academic_year', 'Number': 'jersey', 'Position': 'position', 'HT.': 'height', 'YEAR': 'academic_year', 'HOMETOWN': 'town', 'LAST SCHOOL': 'high_school', 'Yr.': 'academic_year', 'Hometown/High School/Last School': 'town', 'Class': 'academic_year', 'High school': 'high_school', 'Previous College': 'previous_school', 'Cl.-Exp.': 'academic_year', '#': 'jersey', 'High School': 'high_school', 'Hometown / Previous School': 'town', 'No': "jersey", 'Hometown/High School/Previous School': 'town', 'Hometown / High School / Last College': 'town', 'Year': 'academic_year', 'Height': 'height', 'Previous School': 'high_school', 'Cl': 'academic_year', 'Prev. Coll.': 'previous_school', 'Hgt.': 'height', 'Hometown/ High School': 'town', 'Hometown/High School (Last School)': 'town', 'Hometown/High School (Former School)': 'town', 'Hometown / High School': 'town', 'YR': 'academic_year', 'POS': 'position', 'HT': 'height', 'Player': 'name', 'Hometown/High School/Previous College': 'town', 'Last School/Hometown': 'town', 'NO.': 'jersey', 'NAME': 'name', 'YR.': 'academic_year', 'POS.': 'position', 'HIGH SCHOOL': 'high_school', 'NO': 'jersey', 'HOMETOWN/HIGH SCHOOL': 'town', 'Academic Yr.': 'academic_year', 'Full Name': 'name', 'POSITION': 'position'}

SEASONS = ['2022-23', '2021-22', '2020-21', '2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15', '2013-14',
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

def fetch_wbkb_roster(base_url, season):
    url = base_url.replace('index',season+'/roster?view=list')
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        html = None
    else:
        html = BeautifulSoup(r.text, features="html.parser")
    return html

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
    cols = [x.text.strip() for x in html.find('thead').find_all('th') if x.text.strip() if x.text.strip() != '']
    if team['ncaa_id'] == 255:
        cols = [x.text.strip() for x in html.find('thead').find_all('th') if x.text.strip() != 'Social']
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
    if team['ncaa_id'] == 30164:
        headers = html.find_all('table')[1].find_all('tr')[0]
    elif team['ncaa_id'] == 326:
        headers = html.find_all('table')[12].find_all('tr')[0]
    else:
        headers = html.find('table').find_all('tr')[0]
    cols = [x.text.strip() for x in headers if x.text.strip() != '']
    if 'Pronounciation' in cols:
        cols.remove('Pronounciation')
    if 'Major' in cols:
        cols.remove('Major')
    if 'MAJOR' in cols:
        cols.remove('MAJOR')
    if 'Major/Minor' in cols:
        cols.remove('Major/Minor')
    if 'College' in cols:
        cols.remove('College')
    if 'Wt.' in cols:
        cols.remove('Wt.')
    if 'Ltrs.' in cols:
        cols.remove('Ltrs.')
    if 'Pronouns' in cols:
        cols.remove('Pronouns')
    new_cols = [HEADERS[c] for c in cols]
    raw_players = [x for x in html.find('tbody').find_all('tr')]
    for raw_player in raw_players:
        [x.span.decompose() for x in raw_player.find_all('td') if x.find('span')]
        raw_player_list = [x.text.strip() for x in raw_player.find_all('td') if x.text.replace('*','').replace('(she/her/hers)','').replace('she/her/hers','').strip() != '']
        if team['ncaa_id'] == 73 and raw_player_list[0] == '43':
            continue
        if team['ncaa_id'] == 114 or team['ncaa_id'] == 1199 or team['ncaa_id'] == 22626 or team['ncaa_id'] == 24317 or team['ncaa_id'] == 30037 or team['ncaa_id'] == 341 or team['ncaa_id'] == 1315 or team['ncaa_id'] == 46 or team['ncaa_id'] == 510 or team['ncaa_id'] == 641 or team['ncaa_id'] == 730 or team['ncaa_id'] == 75 or team['ncaa_id'] == 806 or team['ncaa_id'] == 817 or team['ncaa_id'] == 89 or team['ncaa_id'] == 145 or team['ncaa_id'] == 217 or team['ncaa_id'] == 247 or team['ncaa_id'] == 2713 or team['ncaa_id'] == 2798 or team['ncaa_id'] == 28594 or team['ncaa_id'] == 30002 or team['ncaa_id'] == 30225 or team['ncaa_id'] == 467 or team['ncaa_id'] == 567 or team['ncaa_id'] == 569 or team['ncaa_id'] == 137 or team['ncaa_id'] == 715 or team['ncaa_id'] == 760 or team['ncaa_id'] == 779 or team['ncaa_id'] == 808 or team['ncaa_id'] == 8688 or team['ncaa_id'] == 379:
            raw_player_list = [x.text.strip() for x in raw_player.find_all('td')]
        raw_player_list[4] = " ".join([x for x in raw_player_list[4].split()])
        if team['ncaa_id'] == 1036:
            if len(raw_player_list) == len(new_cols):
                raw_player_list.pop()
        if team['ncaa_id'] == 1096:
            if len(raw_player_list) >= len(new_cols):
                raw_player_list.pop()
        if team['ncaa_id'] == 142:
            del raw_player_list[2]
        if any(major in raw_player_list for major in ['Nursing', 'Biology', 'Public Health', 'Exercise Science', 'Pre-Nursing', 'Economics', 'Physical Therapy', 'Psychology','Business Administration','Criminal Justice/Psychology', 'Forensic Science', 'Undecided', 'Management', 'Psychology / Management', 'Political Science', 'Psychology / Pre-Medicine', 'Undeclared', 'Biomedical Engineering', 'Business Marketing', 'Chemistry', 'Business', 'Computer Science', 'Business Management', 'AS', 'BIOE', 'CM', 'AE', 'ME', 'BM', 'CVE', 'BME', 'Information Technology', 'Criminal Justice', 'Elementary Education', 'Special Education', 'Criminal Justice/Sociology', 'Exercise and Sports Science', 'Political Science', 'Exercise Sports Science', 'Accounting', 'Psychology', 'Pre-Physical Therapy', 'MS-Counseling Psychology', 'Business Admin.', 'Pre-Medicine', 'MBA', 'Occupational Therapy', 'Pharmacy', 'Biomedical Sciences/Medical Laboratory Sciences', 'Pharm. & Healthcare Business', 'Biomedical Sciences', 'Exercise Science: Pre-Athletic Training', 'Business Administration: Sport Management', 'Exercise Science: Individual Program of Study', 'Applied Psychology & Human Services', 'Outdoor Education, Leadership, & Tourism: Adventure Education', 'Natural Science', 'Exercise Science: Pre-Physical Therapy', 'Childhood Education', 'Global Studies', 'Healthcare Mgmt.', 'Computer Info. Systems', 'Veterinary Science', 'Psychology & Business', 'Business & Psychology', 'Biology & Spanish', 'History & Spanish', 'Politics/Computer Science', 'Geology', 'Politics/Sociology', 'Economics', 'English/Psychology', 'Education', 'Communication Sciences and Disorders', 'Sociology', 'Social Work', 'Psychology / Criminal Justice', 'Undeclared / -', 'Dental Hygiene', 'Early Education/Psychology', 'Elementary Education/Psychology', 'Sports Management', 'Exploratory', 'Creative Writing and Publishing', 'Administration of Justice', 'Emergency Medical Services Management', 'Sport Psychology', 'Physical Education', 'Athletic Training', 'Physician Assistant', 'Sports and Exercise Psychology', 'Athletic Training', 'Sports Managment', 'Sport Management', 'Film and Interactive Media', 'Biochemistry', 'HSSP', 'Business/HSSP', 'Business/Psychology', 'Business/International and Global Studies', 'Industrial Design', 'Mechanical Engineering', 'Architecture', 'Applied Mathematics', 'Business Analytics and Information Management', 'General Business', 'Forensic Biology', 'Pharmaceutical Business', 'Health Sciences', 'Business Undecided', 'Civil Engineering', 'Health Science', 'Education & Studio Art', 'Political Science & Philosophy', 'Biochemistry & Molecular Biology', 'Education & English', 'Business Economics', 'Global & International Studies & French & Francophone Studies', 'Marketing & Sales', 'Math', 'Sports Broadcasting', 'General Studies', 'Occupational Studies', 'Elementary Education/Mathematics', 'Liberal Studies', 'Communication', 'Elementary Education/Sociology', 'Public Health', 'Elementary Education/History', 'Accounting & Marketing', 'Biology/Biotechnology', 'Liberal Studies/Education', 'Entrepreneurship & Marketing', 'Engineering', 'Finance', 'English', 'Music', 'UX', 'NU', 'BE', 'Pre-Veterinary', 'Forensic Psychology', 'Exercise Physiology', 'Outdoor Education, Leadership, & Tourism', 'Recreation & Sports Mgmt.', 'Liberal Arts', 'French', 'Marketing & Communication', 'Dental Hygiene', 'Early Education/Psychology', 'Mathematics and Computer Technology', 'Pre-Physician Assistant', 'Applied Sciences', 'Computer Information Systems', 'Forensic Chemistry', 'Elementary Education and Psychology',"Pre- Physician's Assistant", 'Professional Communications (Graduate)', 'Environmental Science', 'Welding', 'Business Management & Marketing']):
            if team['ncaa_id'] == 186:
                del raw_player_list[4]
            else:
                raw_player_list.pop()
        if len(raw_player_list) < len(new_cols):
            name = " ".join([x.strip() for x in raw_player.find('a').text.replace("  ","").strip().split()])
            raw_player_list.insert(1, name)
        player_dict = dict(zip(new_cols, raw_player_list))
        print(player_dict)
        if 'high_school' not in player_dict:
            if team['ncaa_id'] == 2713:
                player_dict['high_school'] = None
            else:
                player_dict['town'], player_dict['high_school'] = [x.strip() for x in player_dict['town'].split('/', maxsplit=1)]
        if 'previous_school' not in player_dict:
            player_dict['previous_school'] = None
        #print(player_dict)
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

def fetch_and_parse_clemson(team, season):
    roster = []
    er = tldextract.extract(team['url'])
    url = team['url'] + "/roster/season/" + season[0:4]
    r = fetch_url(url)
    html = BeautifulSoup(r.text, features="html.parser")
    cols = [x.text for x in html.find_all('th')]
    cols = cols[0:-2]
    new_cols = [HEADERS[c] for c in cols]
    players = html.find('table').find_all('tr')[1:]
    for player in players:
        raw_player_list = [x.text.strip() for x in player.find_all('td')]
        player_dict = dict(zip(new_cols, raw_player_list))
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': None,
            'name': player_dict['name'],
            'year': player_dict['academic_year'],
            'hometown': player_dict['town'],
            'high_school': None,
            'previous_school': None,
            'height': player_dict['height'],
            'position': player_dict['position'],
            'jersey': player_dict['jersey'],
            'url': "https://www."+er.domain+"."+er.suffix+player.find('a')['href'],
            'season': season
        })
    return roster

def fetch_and_parse_miami(team, season):
    roster = []
    er = tldextract.extract(team['url'])
    url = team['url'] + "/roster/season/" + season
    session = HTMLSession()
    r = session.get(url)
    r.html.render(timeout=30)
    cols = [x.text for x in r.html.find('th') if x.text not in ['Experience','Twitter', 'Instagram', 'TikTok']]
    cols = cols[0:-2]
    new_cols = [HEADERS[c] for c in cols]
    new_cols[7] = 'previous_school'
    players = r.html.find('table tr.odd') + r.html.find('table tr.even')
    for player in players:
        raw_player_list = [x.text.strip() for x in player.find('td')]
        player_dict = dict(zip(new_cols, raw_player_list))
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
            'url': player.find('a', first=True).attrs['href'],
            'season': season
        })
    return roster

def fetch_and_parse_iowa_state(team, season):
    roster = []
    er = tldextract.extract(team['url'])
    url = team['url'] + "/roster/" + season
    session = HTMLSession()
    r = session.get(url)
    r.html.render(timeout=30)
    players = r.html.find('li.sidearm-roster-list-item')
    new_cols = ['number', 'name', ]
    for player in players:
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': None,
            'name': player.find('a', first=True).text,
            'year': player.find('span.sidearm-roster-list-item-year', first=True).text,
            'hometown': player.find('div.sidearm-roster-list-item-hometown', first=True).text,
            'high_school': player.find('span.sidearm-roster-list-item-highschool', first=True).text,
            'previous_school': None,
            'height': player.find('span.sidearm-roster-list-item-height', first=True).text,
            'position': player.find('span.sidearm-roster-list-item-position', first=True).text,
            'jersey': player.find('span')[0].text,
            'url': "https://www."+er.domain+"."+er.suffix+player.find('a', first=True).attrs['href'],
            'season': season
        })
    return roster

def fetch_and_parse_iowa(team, season):
    roster = []
    er = tldextract.extract(team['url'])
    url = team['url'] + "/roster/" + "season/" + season
    r = requests.get(url)
    html = BeautifulSoup(r.text, features="html.parser")
    players = html.find_all('div', class_="rosters__table")[0].find('table').find_all('tr')[1:]
    for player in players:
        roster.append({
            'team_id': team['ncaa_id'],
            'team': team['team'],
            'id': None,
            'name': player.find_all('td')[1].text.strip(),
            'year': player.find_all('td')[4].text,
            'hometown': player.find_all('td')[5].text.strip(),
            'high_school': player.find_all('td')[6].text.strip(),
            'previous_school': None,
            'height': player.find_all('td')[3].text,
            'position': player.find_all('td')[2].text,
            'jersey': player.find_all('td')[0].text,
            'url': player.find('a')['href'],
            'season': season
        })
    return roster

def fetch_and_parse_baylor(team, season):
    roster = []
    er = tldextract.extract(team['url'])
    url = team['url'] + "/roster/" + season
    session = HTMLSession()
    r = session.get(url, timeout=30)
    r.html.render()
    rows = r.html.find('tr.sidearm-roster-table-row')
    headers = rows[0]
    cols = [x.text for x in headers.find('th') if x.text not in ['Experience','Twitter']]
    new_cols = [HEADERS[c] for c in cols]
    players = rows[1:-1]
    for player in players:
        raw_player_list = player.text.split('\n')
        del raw_player_list[5]
        player_dict = dict(zip(new_cols, raw_player_list))
        if 'high_school' in player_dict:
            player_dict['previous_school'] = player_dict['high_school']
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
            'url': "https://www."+er.domain+"."+er.suffix+player.find('a', first=True).attrs['href'],
            'season': season
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
        if 'Instagram' in name:
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
        idx = [i for i,_ in enumerate(teams_json) if _['ncaa_id'] == team][0]
        teams_json = teams_json[idx:-1]
    teams_with_urls = [x for x in teams_json if "url" in x]
    with open(f"/Users/dwillis/code/wbb/ncaa/rosters_{season}.csv", 'w') as output_file:
        csv_file = csv.writer(output_file)
        csv_file.writerow(['ncaa_id', 'team', 'player_id', 'name', 'year', 'hometown', 'high_school', 'previous_school', 'height', 'position', 'jersey', 'url', 'season'])
        for team in teams_with_urls:
            if team['ncaa_id'] == 26107 and season == '2021-22':
                continue
            if 'roster' in team:
                continue
            print(team['ncaa_id'])
            if team['ncaa_id'] == 51:
                roster = fetch_and_parse_baylor(team, season)
            elif team['ncaa_id'] == 415:
                roster = fetch_and_parse_miami(team, season)
            elif team['ncaa_id'] == 147:
                roster = fetch_and_parse_clemson(team, season)
            elif team['ncaa_id'] == 311 or team['ncaa_id'] == 742:
                roster = fetch_and_parse_iowa_state(team, season)
            elif team['ncaa_id'] == 312:
                roster = fetch_and_parse_iowa(team, season)
            elif team['ncaa_id'] == 532:
                continue
            elif 'wbkb' in team['url']:
                html = fetch_wbkb_roster(team['url'], season)
                roster = None
                if html:
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
