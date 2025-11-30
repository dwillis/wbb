import pandas as pd
import requests
import requests_cache
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Optional

# Install cache to avoid repeated requests
requests_cache.install_cache('fiba_player_cache')

def slugify_competition_name(competition_name: str, year: str) -> str:
    """
    Convert competition name to URL slug format.
    """
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = competition_name.lower()
    # Replace multiple spaces with single space
    slug = re.sub(r'\s+', ' ', slug)
    # Replace spaces with hyphens
    slug = slug.replace(' ', '-')
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    # Add year
    slug = f"{slug}-{year}"
    return slug

def get_game_boxscore_url(game_id: str, competition_name: str, year: str, team_a_code: str, team_b_code: str) -> str:
    """
    Construct the boxscore URL from a game ID, competition information, and team codes.
    Uses the format: /games/{game_id}-{team_a}-{team_b}#boxscore
    """
    competition_slug = slugify_competition_name(competition_name, year)
    base_url = "https://www.fiba.basketball/en/events"
    return f"{base_url}/{competition_slug}/games/{game_id}-{team_a_code}-{team_b_code}#boxscore"

def scrape_player_stats(game_url: str) -> Optional[List[Dict]]:
    """
    Scrape player statistics from a FIBA game boxscore page.
    """
    print(f"Scraping: {game_url}")
    
    try:
        # Remove the #boxscore fragment for the initial request to handle redirects properly
        base_url = game_url.replace('#boxscore', '')
        
        # First, make a GET request without following redirects to capture the redirect
        initial_response = requests.get(base_url, allow_redirects=False)
        
        # Check if we got a redirect
        if initial_response.status_code in [301, 302, 307, 308]:
            redirect_url = initial_response.headers.get('Location')
            if redirect_url:
                print(f"Following redirect to: {redirect_url}")
                # Handle relative redirects
                if redirect_url.startswith('/'):
                    from urllib.parse import urljoin
                    redirect_url = urljoin(base_url, redirect_url)
                final_base_url = redirect_url
            else:
                print(f"Redirect detected but no Location header found")
                final_base_url = base_url
        elif initial_response.status_code == 200:
            # No redirect, use original URL
            final_base_url = base_url
        else:
            print(f"Unexpected status code: {initial_response.status_code}")
            # Try the original URL anyway
            final_base_url = base_url
        
        # Now make the actual request to the final URL
        print(f"Fetching content from: {final_base_url}")
        response = requests.get(final_base_url)
        response.raise_for_status()
        
        # Reconstruct final URL with fragment for display
        final_url = final_base_url + '#boxscore'
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for boxscore data - this will need to be adjusted based on actual HTML structure
        # First, let's try to find the boxscore section
        boxscore_section = soup.find('div', {'id': 'boxscore'}) or soup.find('section', class_='boxscore')
        
        if not boxscore_section:
            print(f"No boxscore section found for {final_url}")
            return None
        
        players_data = []
        
        # Look for player statistics tables
        # This is a generic approach - will need refinement based on actual HTML structure
        stat_tables = boxscore_section.find_all('table', class_='statistics') or boxscore_section.find_all('table')
        
        for table in stat_tables:
            # Try to identify team name
            team_header = table.find_previous(['h2', 'h3', 'div'], class_=['team-name', 'team-title'])
            team_name = team_header.get_text(strip=True) if team_header else "Unknown"
            
            # Find table headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # Find player rows
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= len(headers):
                        player_data = {
                            'team': team_name,
                            'game_url': final_url
                        }
                        
                        # Map cell data to headers
                        for i, cell in enumerate(cells[:len(headers)]):
                            if i < len(headers):
                                player_data[headers[i]] = cell.get_text(strip=True)
                        
                        players_data.append(player_data)
        
        return players_data if players_data else None
        
    except requests.RequestException as e:
        print(f"Error fetching {game_url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing {game_url}: {e}")
        return None

def load_game_data(csv_file: str = "fiba_games.csv") -> List[Dict]:
    """
    Load game data from the CSV file including Game ID, Competition Official Name, and team codes.
    """
    try:
        df = pd.read_csv(csv_file)
        game_data = []
        
        for _, row in df.iterrows():
            if (pd.notna(row['Game ID']) and 
                pd.notna(row['Competition Official Name']) and
                pd.notna(row['Team A Code']) and 
                pd.notna(row['Team B Code'])):
                
                # Extract year from Game Date Time or use 2025 as default
                year = "2025"  # Default year
                if pd.notna(row.get('Game Date Time')):
                    try:
                        # Game Date Time format is typically YYYY-MM-DDTHH:MM:SS
                        year = str(row['Game Date Time'])[:4]
                    except:
                        year = "2025"
                
                game_data.append({
                    'game_id': str(row['Game ID']),
                    'competition_name': row['Competition Official Name'],
                    'team_a_code': row['Team A Code'],
                    'team_b_code': row['Team B Code'],
                    'year': year,
                    'game_date_time': row.get('Game Date Time', '')
                })
        
        # Sort games by Game Date Time in descending order (latest first)
        game_data.sort(key=lambda x: x['game_date_time'], reverse=True)
        
        print(f"Loaded {len(game_data)} games from {csv_file} (sorted by date, latest first)")
        return game_data
    except Exception as e:
        print(f"Error loading game data from {csv_file}: {e}")
        return []

def scrape_all_games(game_data: List[Dict], delay: float = 1.0) -> List[Dict]:
    """
    Scrape player statistics for all games.
    """
    all_player_stats = []
    
    for i, game_info in enumerate(game_data):
        game_id = game_info['game_id']
        competition_name = game_info['competition_name']
        team_a_code = game_info['team_a_code']
        team_b_code = game_info['team_b_code']
        year = game_info['year']
        
        print(f"Processing game {i+1}/{len(game_data)}: {game_id}")
        
        game_url = get_game_boxscore_url(game_id, competition_name, year, team_a_code, team_b_code)
        player_stats = scrape_player_stats(game_url)
        
        if player_stats:
            # Add game ID and competition info to each player record
            for stats in player_stats:
                stats['game_id'] = game_id
                stats['competition_name'] = competition_name
                stats['team_a_code'] = team_a_code
                stats['team_b_code'] = team_b_code
                stats['year'] = year
            all_player_stats.extend(player_stats)
            print(f"Found {len(player_stats)} player records")
        else:
            print(f"No player data found for game {game_id}")
        
        # Add delay to be respectful to the server
        if i < len(game_data) - 1:  # Don't delay after the last request
            time.sleep(delay)
    
    return all_player_stats

def save_player_data(player_data: List[Dict], output_file: str = "fiba_player_stats.csv"):
    """
    Save player statistics to CSV file.
    """
    if not player_data:
        print("No player data to save")
        return
    
    df = pd.DataFrame(player_data)
    df.to_csv(output_file, index=False)
    print(f"Saved {len(player_data)} player records to {output_file}")

def main():
    """
    Main function to run the scraper.
    """
    print("Starting FIBA player statistics scraper...")
    
    # Load game data from CSV
    game_data = load_game_data()
    
    if not game_data:
        print("No game data found. Make sure fiba_games.csv exists and has Game ID and Competition Official Name columns.")
        return
    
    # For testing, you might want to limit to first few games
    # game_data = game_data[:5]  # Uncomment this line to test with first 5 games only
    
    # Scrape all games
    all_player_stats = scrape_all_games(game_data, delay=1.0)
    
    # Save results
    save_player_data(all_player_stats)
    
    print(f"Scraping completed. Total player records: {len(all_player_stats)}")

if __name__ == "__main__":
    main()
