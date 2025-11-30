import csv
import requests
from bs4 import BeautifulSoup
import re
import sys
import time


NCAA_YEAR_DICT = {
    2025: 16720,
    2024: 16500,
    2023: 16061,
    2022: 15866,
    2021: 15500,
    2020: 15002,
    2019: 14320,
    2018: 12911,
    2017: 12500,
    2016: 12280,
    2015: 12021,
    2014: 11560,
    2013: 11240,
    2012: 10760,
    2011: 10420,
    2010: 10261,
    2009: 10140
    # Don't go back past 2010 end year since no game lists but here are mappings
    # 2009: 10140, 2008: 4, 2007: 6, 2006: 8, 2005: 10, 2004: 10173
}

# Check if the input and output file arguments are provided
if len(sys.argv) != 3:
    print("Usage: python get_players.py <input_csv> <output_csv>")
    sys.exit(1)

# Get input and output file paths
input_csv = sys.argv[1]
output_csv = sys.argv[2]

# Base URL for constructing full links
base_url = "https://stats.ncaa.org"

# Headers for the output CSV
output_headers = ['season', 'team_id', 'player_name', 'player_id', 'player_url']

# Initialize the output list
players_data = []

# Read the input CSV and process each team
with open(input_csv, 'r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    
    for row in reader:
        season = row['season']
        team_id = row['ncaa_id']
        roster_url = f"{base_url}/teams/{team_id}/roster"

        print(roster_url)
        time.sleep(1)
        
        # Fetch the roster page
        print(f"Fetching roster for team ID {team_id} ({roster_url})...")
        response = requests.get(roster_url, headers={'User-Agent': 'Mozilla/5.0'})
        print(response.status_code)
        
        if response.status_code != 200:
            print(f"Failed to fetch roster for team ID {team_id}")
            continue
        
        ncaa_code = NCAA_YEAR_DICT[int(season)]

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'id': f'rosters_form_players_{ncaa_code}_data_table'})
        
        if not table:
            print(f"No roster table found for team ID {team_id}")
            continue
        
        # Extract player information from the table
        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            
            link = cells[3].find('a')
            if link:
                player_name = link.text.strip()
                player_relative_url = link['href']
                player_url = base_url + player_relative_url
                
                # Extract player ID from the URL
                match = re.search(r'/(\d+)$', player_relative_url)
                player_id = match.group(1) if match else None
                
                players_data.append({
                    'season': season,
                    'team_id': team_id,
                    'player_name': player_name,
                    'player_id': player_id,
                    'player_url': player_url
                })

# Save the player data to an output CSV file
with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=output_headers)
    writer.writeheader()
    writer.writerows(players_data)

print(f"Player data saved to {output_csv}")
