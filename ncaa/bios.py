import time
import csv
import requests
from sqlite_utils import Database
from goose3 import Goose

g = Goose()
db = Database("bios.db")
season = "2022_23"

bios = []
not_found = []

url = f"https://raw.githubusercontent.com/Sports-Roster-Data/womens-college-basketball/main/wbb_rosters_{season}.csv"
response = requests.get(url)
reader = csv.DictReader(response.text.splitlines())

for row in reader:
    print(row['url'])
    try:
        bio = g.extract(url=row['url'])
        bios.append({ 'season': season, 'url': row['url'], 'text': bio.cleaned_text })
    except:
        not_found.append({'url': row['url']})
    time.sleep(0.5)

db["bios"].insert_all(bios)
db["not_found"].insert_all(not_found)
