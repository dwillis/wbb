import csv
import sys
from bs4 import BeautifulSoup
import re

# Check if the season argument is provided
if len(sys.argv) != 3:
    print("Usage: python teams.py <html_file> <season>")
    sys.exit(1)

# Get the arguments
html_file = sys.argv[1]
season = sys.argv[2]

# Load the HTML content
with open(html_file, 'r') as file:
    html_content = file.read()

# Parse the HTML with BeautifulSoup
soup = BeautifulSoup(html_content, 'html.parser')

# Find all rows containing team information
rows = soup.find_all('tr', {'role': 'row'})

# Initialize a list to store team data
teams = []

# Base URL for constructing full links
base_url = "https://stats.ncaa.org"

# Extract team name, URL, season, and NCAA ID
for row in rows:
    link = row.find('a', class_='skipMask')
    if link:
        team_name = link.text.strip()
        team_url = base_url + link['href']
        
        # Extract numeric ID from the URL
        match = re.search(r'/teams/(\d+)', link['href'])
        ncaa_id = match.group(1) if match else None
        
        teams.append({'team_name': team_name, 'url': team_url, 'season': season, 'ncaa_id': ncaa_id})

# Save to a CSV file
output_file = f"teams_{season}.csv"
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['team_name', 'url', 'season', 'ncaa_id']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(teams)

print(f"Data saved to {output_file}")
