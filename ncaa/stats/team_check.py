import requests
from bs4 import BeautifulSoup
import csv
from typing import Dict, List
import re
import time
from urllib.parse import urlencode

def scrape_division_season(year: int, division: int) -> List[Dict[str, str]]:
    """
    Scrapes NCAA women's basketball teams for a specific season and division.
    
    Args:
        year (int): Academic year to scrape (e.g., 2024 for 2023-24 season)
        division (int): NCAA division (1, 2, or 3)
    
    Returns:
        List[Dict[str, str]]: List of dictionaries containing team information
    """
    base_url = "https://stats.ncaa.org/team/inst_team_list"
    params = {
        'academic_year': year,
        'conf_id': -1,
        'division': division,
        'sport_code': 'WBB'
    }
    url = f"{base_url}?{urlencode(params)}"
    
    # Add headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Make request with error handling
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching data for Division {division}, {year}: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    team_links = soup.find_all('a', href=re.compile(r'/teams/\d+'))
    
    teams = []
    for link in team_links:
        team_name = link.text.strip()
        team_url = f"https://stats.ncaa.org{link['href']}"
        team_id = link['href'].split('/')[-1]
        
        teams.append({
            'season': year,
            'division': division,
            'team_id': team_id,
            'team': team_name,
            'url': team_url
        })
    
    return teams

def scrape_multiple_seasons_divisions(
    start_year: int, 
    end_year: int, 
    divisions: List[int], 
    output_file: str
) -> None:
    """
    Scrapes multiple seasons and divisions, writing results to a CSV file.
    
    Args:
        start_year (int): First season to scrape
        end_year (int): Last season to scrape
        divisions (List[int]): List of divisions to scrape (e.g., [1, 2, 3])
        output_file (str): Path to output CSV file
    """
    # Create/open CSV file
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['season', 'division', 'team_id', 'team', 'url']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Iterate through years and divisions
        for year in range(end_year, start_year - 1, -1):
            for division in divisions:
                print(f"Scraping Division {division}, season {year}-{year+1}")
                teams = scrape_division_season(year, division)
                
                # Write teams to CSV
                for team in teams:
                    writer.writerow(team)
                
                # Add delay between requests to be polite
                if not (year == start_year and division == divisions[-1]):
                    time.sleep(1)
                
                print(f"Found {len(teams)} teams for Division {division}, {year}")

def main():
    # Configure scraping parameters
    start_year = 2010  # Will scrape 2019-20 season
    end_year = 2025    # Will scrape through 2023-24 season
    divisions = [1, 2, 3]  # All NCAA divisions
    output_file = 'ncaa_womens_basketball_teams.csv'
    
    print(f"Starting scrape for Divisions {divisions}")
    print(f"Seasons: {start_year}-{start_year+1} through {end_year}-{end_year+1}")
    scrape_multiple_seasons_divisions(start_year, end_year, divisions, output_file)
    print(f"Scraping complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()