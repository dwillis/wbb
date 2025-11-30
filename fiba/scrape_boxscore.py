import time
import requests
import requests_cache
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlite_utils import Database
import re

BASE_URL = "https://www.fiba.basketball"

requests_cache.install_cache('fiba_cache')

def get_womens_events(competition_type=None):
    """
    Get a list of women's FIBA events.

    Args:
        competition_type: Optional filter for specific competition types
                         (e.g., 'worldcup', 'olympic', 'u19', 'u17', '3x3')

    Returns:
        List of dictionaries containing event information (name, slug, year)
    """
    # Try multiple entry points for women's events
    urls_to_try = [
        "/competitions",
        "/",
    ]

    events = []

    for url in urls_to_try:
        try:
            page = requests.get(BASE_URL + url, timeout=10).text
            soup = BeautifulSoup(page, "html.parser")

            # Look for links that contain 'women' in the URL
            links = soup.find_all('a', href=True)

            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # Filter for women's events
                if 'women' in href.lower() and '/games' not in href:
                    # Extract event information
                    match = re.search(r'/([^/]+/[^/]*women[^/]*/\d{4})', href)
                    if match:
                        event_slug = '/' + match.group(1)
                        event_info = {
                            'name': text if text else event_slug.replace('/', ' ').strip(),
                            'slug': event_slug,
                            'games_url': event_slug + '/games'
                        }

                        # Extract year
                        year_match = re.search(r'/(\d{4})', event_slug)
                        if year_match:
                            event_info['year'] = year_match.group(1)

                        # Apply competition type filter if specified
                        if competition_type is None or competition_type.lower() in event_slug.lower():
                            if event_info not in events:
                                events.append(event_info)

        except Exception as e:
            print(f"Error fetching events from {url}: {e}")
            continue

    return events

def get_latest_womens_games(limit=10):
    """
    Scrape the latest FIBA women's games.

    Args:
        limit: Maximum number of recent games to fetch

    Returns:
        DataFrame of recent game results
    """
    recent_games = []

    # Try to find recent games from the women's page or results page
    urls_to_try = [
        "/women",
        "/competitions/women",
    ]

    for url in urls_to_try:
        try:
            page = requests.get(BASE_URL + url, timeout=10).text
            soup = BeautifulSoup(page, "html.parser")

            # Look for game items
            game_items = soup.select("div.game_item, div.game-item, article.game")[:limit]

            for game_item in game_items:
                game_link = game_item.find('a')
                if game_link and game_link.get('href'):
                    game_url = game_link.get('href')
                    if not game_url.startswith('http'):
                        game_url = BASE_URL + game_url

                    try:
                        game_data = get_game_result(game_url)
                        if game_data:
                            recent_games.append(game_data)
                    except Exception as e:
                        print(f"Error fetching game {game_url}: {e}")
                        continue

                    time.sleep(1)

            if recent_games:
                break

        except Exception as e:
            print(f"Error fetching latest games from {url}: {e}")
            continue

    if recent_games:
        return pd.DataFrame(recent_games)
    else:
        return pd.DataFrame()

def get_game_result(game_url):
    """
    Get basic game result information without full boxscore.

    Args:
        game_url: URL of the game

    Returns:
        Dictionary with game result information
    """
    try:
        page = requests.get(game_url, timeout=10).text
        soup = BeautifulSoup(page, "html.parser")

        # Extract teams
        teams = [s.text for s in soup.find_all('span', class_='team-name')[:2]]

        # Extract scores
        final_score = soup.find("div", class_="final-score")
        if final_score:
            scores = [s.strip() for s in final_score.text.split("\n") if s.strip()]
        else:
            return None

        # Extract date from URL or page
        date_match = re.search(r'/game/(\d+)/', game_url)
        game_id = date_match.group(1) if date_match else None

        if len(teams) >= 2 and len(scores) >= 2:
            return {
                'game_id': game_id,
                'game_url': game_url,
                'team_1': teams[0],
                'team_1_score': scores[0],
                'team_2': teams[1],
                'team_2_score': scores[1],
                'date': datetime.now().strftime('%Y-%m-%d')
            }
    except Exception as e:
        print(f"Error getting game result: {e}")
        return None

def get_event_player_stats(event_slug):
    """
    Scrape overall player statistics from a FIBA women's event.

    Args:
        event_slug: The event slug (e.g., '/oceania/u15women/2018')

    Returns:
        DataFrame of player statistics
    """
    stats_url = BASE_URL + event_slug + '/statistics'

    try:
        page = requests.get(stats_url, timeout=10).text
        soup = BeautifulSoup(page, "html.parser")

        # Try to find the statistics table
        stats_tables = soup.find_all('table', class_=['table', 'stats-table', 'player-stats'])

        if not stats_tables:
            # Try to find stats through data tabs
            stats_tab = soup.find('li', {'data-tab-content': 'statistics'})
            if stats_tab:
                data_url = stats_tab.get('data-ajax-url')
                if data_url:
                    page = requests.get(BASE_URL + data_url, timeout=10).text
                    soup = BeautifulSoup(page, "html.parser")
                    stats_tables = soup.find_all('table')

        all_stats = []

        for table in stats_tables:
            # Extract headers
            headers = []
            thead = table.find('thead')
            if thead:
                headers = [th.text.strip() for th in thead.find_all('th')]

            # Extract player rows
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > 0:
                        player_data = {}
                        for i, cell in enumerate(cells):
                            header = headers[i] if i < len(headers) else f'col_{i}'
                            player_data[header] = cell.text.strip()

                        player_data['event_slug'] = event_slug
                        all_stats.append(player_data)

        if all_stats:
            return pd.DataFrame(all_stats)
        else:
            print(f"No statistics tables found for event: {event_slug}")
            return pd.DataFrame()

    except Exception as e:
        print(f"Error fetching player stats from {stats_url}: {e}")
        return pd.DataFrame()

def scrape_womens_event_games(event_slug):
    """
    Scrape all game results (with boxscores) from a women's FIBA event.

    Args:
        event_slug: The event slug (e.g., '/oceania/u15women/2018/games')

    Returns:
        DataFrame containing all player statistics from all games in the event
    """
    if not event_slug.endswith('/games'):
        event_slug = event_slug + '/games'

    print(f"Scraping games from: {event_slug}")
    link_ls = get_game_urls(event_slug)
    print(f"Found {len(link_ls)} games")

    players = get_players(link_ls)
    if players:
        df = pd.concat(players, ignore_index=True)
        return df
    else:
        return pd.DataFrame()

def get_game_urls(event_slug):
    """
    Get URLs for all games in an event.

    Args:
        event_slug: The event games URL (e.g., '/oceania/u15women/2018/games')

    Returns:
        List of game URLs
    """
    page = requests.get(BASE_URL + event_slug).text
    soup = BeautifulSoup(page, "html.parser")
    link_ls = [div.find('a').get("href")
               for div in soup.select("div.game_item")]
    return link_ls

def get_players(link_ls):
    all_tables = []
    for a in link_ls:
        if a == None:
            continue
        try:
            all_tables.append(get_boxscore(BASE_URL + a))
        except (ValueError, TypeError, AttributeError):
            print("Problem with", BASE_URL + a)
            raise
        time.sleep(1)
    return all_tables

def get_boxscore(game_url):
    print(game_url)
#    if game_url == 'https://www.fiba.basketballhttps://www.fiba.basketball/u16americas/women/2021/game/2908/Canada-USA':
#        game_url = 'https://www.fiba.basketball/u16americas/women/2021/game/2908/Canada-USA'
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
    teams = [s.text for s in box_sc.find_all('span', class_='team-name')[:2]]

    all_players = []

    for i, team in enumerate([loc_box, aw_box]):
        for player in team.find_all("tr"):
            example = [d.text.strip().split("\n")[0] for d in player.find_all("td") if d != "\n"]
            if len(example) < len(colnames):
                example = example[:-1]
                example = example + ["0:0", "0"] + ["0/0"] * 4 + ["0"] * 10
            player_data = {"country": teams[i], "vs": teams[i-1],
                           "team_score": scores[i], "vs_score": scores[i-1],
                           "date": date}
            for a,b in zip(colnames, example):
                player_data[a] = b

            all_players.append(player_data)

    return pd.DataFrame(all_players)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Scrape FIBA women\'s basketball data')
    parser.add_argument('--mode', type=str, required=True,
                        choices=['events', 'event-games', 'latest-games', 'event-stats'],
                        help='Scraping mode')
    parser.add_argument('--event-slug', type=str, help='Event slug (e.g., /oceania/u15women/2018)')
    parser.add_argument('--competition-type', type=str, help='Filter events by competition type')
    parser.add_argument('--limit', type=int, default=10, help='Limit for latest games')
    parser.add_argument('--output', type=str, help='Output CSV filename')

    args = parser.parse_args()

    if args.mode == 'events':
        # Get list of women's FIBA events
        print("Fetching women's FIBA events...")
        events = get_womens_events(competition_type=args.competition_type)
        if events:
            df = pd.DataFrame(events)
            output_file = args.output or 'fiba_womens_events.csv'
            df.to_csv(output_file, index=False)
            print(f"Found {len(events)} events. Saved to {output_file}")
            print("\nSample events:")
            print(df.head())
        else:
            print("No events found")

    elif args.mode == 'event-games':
        # Scrape game results from a specific event
        if not args.event_slug:
            print("Error: --event-slug required for event-games mode")
            exit(1)

        print(f"Scraping games from event: {args.event_slug}")
        df = scrape_womens_event_games(args.event_slug)

        if not df.empty:
            output_file = args.output or f"fiba_womens_{args.event_slug.replace('/', '_')}_games.csv"
            df.to_csv(output_file, index=False)
            print(f"Scraped {len(df)} player records. Saved to {output_file}")
        else:
            print("No game data found")

    elif args.mode == 'latest-games':
        # Scrape latest women's games
        print(f"Fetching latest {args.limit} women's games...")
        df = get_latest_womens_games(limit=args.limit)

        if not df.empty:
            output_file = args.output or 'fiba_latest_womens_games.csv'
            df.to_csv(output_file, index=False)
            print(f"Found {len(df)} games. Saved to {output_file}")
            print("\nLatest games:")
            print(df)
        else:
            print("No recent games found")

    elif args.mode == 'event-stats':
        # Scrape overall player stats from an event
        if not args.event_slug:
            print("Error: --event-slug required for event-stats mode")
            exit(1)

        print(f"Fetching player statistics for event: {args.event_slug}")
        df = get_event_player_stats(args.event_slug)

        if not df.empty:
            output_file = args.output or f"fiba_womens_{args.event_slug.replace('/', '_')}_stats.csv"
            df.to_csv(output_file, index=False)
            print(f"Scraped {len(df)} player stat records. Saved to {output_file}")
            print("\nTop players:")
            print(df.head())
        else:
            print("No player statistics found")

    # Example usage (commented out):
    # python scrape_boxscore.py --mode events --competition-type worldcup
    # python scrape_boxscore.py --mode event-games --event-slug /oceania/u15women/2018
    # python scrape_boxscore.py --mode latest-games --limit 20
    # python scrape_boxscore.py --mode event-stats --event-slug /oceania/u15women/2018
