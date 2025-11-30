import os
import json
import pandas as pd
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

def get_tournament_data(start_year: str = "2017", end_year: str = "2025") -> Dict:
    """
    Fetch tournament data by month for the given year range, aggregate and return as a single JSON.
    """
    aggregated_data = []  # This will hold all the game data

    # Iterate over each year in the range
    for year in range(int(start_year), int(end_year) + 1):
        year_str = str(year)
        print(f"Fetching data for year: {year_str}")
        
        # Iterate over each month of the current year
        for month in range(1, 13):
            # Format the month and ensure it's two digits (e.g., "01", "02")
            month_str = f"{month:02d}"

            # Define the start and end dates for the current month
            start_date = f"{year_str}-{month_str}-01T00:00:00.000Z"
            # Use timedelta to get the last day of the month
            next_month = (datetime(year, month, 1) + timedelta(days=32)).replace(day=1)
            end_date = next_month.strftime(f"%Y-%m-01T00:00:00.000Z")

            # Build the curl command
            curl_command = f"""
        curl 'https://digital-api.fiba.basketball/hapi/getgdapgamesbetweentwodates?dateFrom={start_date}&dateTo={end_date}' \
          -H 'Accept: */*' \
          -H 'Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,la;q=0.6,und;q=0.5' \
          -H 'Connection: keep-alive' \
          -H 'DNT: 1' \
          -H 'Origin: https://www.fiba.basketball' \
          -H 'Referer: https://www.fiba.basketball/' \
          -H 'Sec-Fetch-Dest: empty' \
          -H 'Sec-Fetch-Mode: cors' \
          -H 'Sec-Fetch-Site: same-site' \
          -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36' \
          -H 'content-type: application/json' \
          -H 'ocp-apim-subscription-key: c7616771331d48dd9262fa001b4c10be' \
          -H 'sec-ch-ua: "Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"' \
          -H 'sec-ch-ua-mobile: ?0' \
          -H 'sec-ch-ua-platform: "macOS"'
        """

            try:
                print(f"Fetching data for {year_str}-{month_str}")
                result = subprocess.run(
                    curl_command,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode == 0:
                    response_json = json.loads(result.stdout)
                    aggregated_data.extend(response_json)  # Aggregate the data
                else:
                    raise Exception(f"Curl command failed: {result.stderr}")

            except subprocess.CalledProcessError as e:
                raise
            except json.JSONDecodeError as e:
                raise

    return {"results": aggregated_data}

def safe_get(d, keys, default=''):
    """安全地获取嵌套字典中的值，如果不存在返回默认值。"""
    for key in keys:
        d = d.get(key, {})
        if not d:  # 如果字典为空，返回默认值
            return default
    return d if d else default

def flatten_tournament_data(data: Dict) -> List[Dict]:
    """
    Flatten the nested tournament data structure into a list of tournament entries
    """
    flattened_data = []

    try:
        results = data.get('results', {})
        for game in results:
            if isinstance(game, dict):
                if isinstance(game, dict):
                    flattened_game = {
                        'Game ID': game.get('gameId', ''),
                        'Game Name': game.get('gameName', ''),
                        'Game Number': game.get('gameNumber', ''),
                        'Status Code': game.get('statusCode', ''),
                        'Team A ID': safe_get(game, ['teamA', 'teamId']),
                        'Team A Organisation ID': safe_get(game, ['teamA', 'organisationId']),
                        'Team A Code': safe_get(game, ['teamA', 'code']),
                        'Team A Official Name': safe_get(game, ['teamA', 'officialName']),
                        'Team A Short Name': safe_get(game, ['teamA', 'shortName']),
                        'Team B ID': safe_get(game, ['teamB', 'teamId']),
                        'Team B Organisation ID': safe_get(game, ['teamB', 'organisationId']),
                        'Team B Code': safe_get(game, ['teamB', 'code']),
                        'Team B Official Name': safe_get(game, ['teamB', 'officialName']),
                        'Team B Short Name': safe_get(game, ['teamB', 'shortName']),
                        'Team A Score': game.get('teamAScore', ''),
                        'Team B Score': game.get('teamBScore', ''),
                        'Is Live': game.get('isLive', ''),
                        'Current Period': game.get('currentPeriod', ''),
                        'Chrono': game.get('chrono', ''),
                        'Live Game Status': game.get('liveGameStatus', ''),
                        'Current Period Status': game.get('currentPeriodStatus', ''),
                        'Host City': game.get('hostCity', ''),
                        'Host Country': game.get('hostCountry', ''),
                        'Host Country Code': game.get('hostCountryCode', ''),
                        'Venue ID': game.get('venueId', ''),
                        'Venue Name': game.get('venueName', ''),
                        'Game Date Time': game.get('gameDateTime', ''),
                        'Game Date Time UTC': game.get('gameDateTimeUTC', ''),
                        'Has Time Game Date Time': game.get('hasTimeGameDateTime', ''),
                        'IANA Time Zone': game.get('ianaTimeZone', ''),
                        'UTC Offset': game.get('utcOffset', ''),
                        'Is Postponed': game.get('isPostponed', ''),
                        'Is Played Behind Closed Doors': game.get('isPlayedBehindClosedDoors', ''),
                        'Venue Capacity': game.get('venueCapacity', ''),
                        'Spectators': game.get('spectators', ''),
                        'Statistic System': game.get('statisticSystem', ''),
                        'Group ID': game.get('groupId', ''),
                        'Group Pairing Code': game.get('groupPairingCode', ''),
                        'Round ID': safe_get(game, ['round', 'roundId']),
                        'Round Code': safe_get(game, ['round', 'roundCode']),
                        'Round Name': safe_get(game, ['round', 'roundName']),
                        'Round Number': safe_get(game, ['round', 'roundNumber']),
                        'Round Type': safe_get(game, ['round', 'roundType']),
                        'Round Status Code': safe_get(game, ['round', 'roundStatusCode']),
                        'Competition ID': safe_get(game, ['competition', 'competitionId']),
                        'Competition Code': safe_get(game, ['competition', 'competitionCode']),
                        'Competition Official Name': safe_get(game, ['competition', 'officialName']),
                        'Competition Start': safe_get(game, ['competition', 'start']),
                        'Competition End': safe_get(game, ['competition', 'end']),
                        'Competition Status': safe_get(game, ['competition', 'status']),
                        'Competition Age Category': safe_get(game, ['competition', 'ageCategory']),
                        'Competition Gender': safe_get(game, ['competition', 'gender']),
                        'Competition FIBA Zone': safe_get(game, ['competition', 'fibaZone']),
                        'Competition Zone Code': safe_get(game, ['competition', 'zoneInformation', 'zoneCode']),
                        'Competition Type': safe_get(game, ['competition', 'competitionType']),
                        'Competition Category Code': safe_get(game, ['competition', 'competitionCategory', 'code']),
                        'Competition Category Name': safe_get(game, ['competition', 'competitionCategory', 'name'])
                    }
                    if (flattened_game['Status Code'] == 'VALID' and 
                        flattened_game['Competition Gender'] == 'Women'):
                        flattened_data.append(flattened_game)

        return flattened_data
    except Exception as e:
        raise


def save_to_csv(data: List[Dict], csv_path: str) -> None:
    """
    Save the tournament data to a CSV file
    """
    try:
        df = pd.DataFrame(data)

        # Create the directory if it doesn't exist and if there's a directory path
        dir_path = os.path.dirname(csv_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Save to CSV
        df.to_csv(csv_path, index=False)

    except Exception as e:
        raise

def get_csv_name() -> str:
    return "fiba_games.csv"

def main(start_year: str = "2011", end_year: str = "2016"):
    """
    Main function to scrape FIBA games data for a given year range.
    
    Args:
        start_year: Starting year (inclusive)
        end_year: Ending year (inclusive)
    """
    try:
        print(f"Scraping FIBA games data from {start_year} to {end_year}")
        
        # Fetch data using curl
        json_data = get_tournament_data(start_year, end_year)

        # Flatten and process the data
        flattened_data = flatten_tournament_data(json_data)

        # Save to CSV with year range in filename if multiple years
        if start_year == end_year:
            csv_filename = f"fiba_games_{start_year}.csv"
        else:
            csv_filename = f"fiba_games_{start_year}-{end_year}.csv"
        
        save_to_csv(flattened_data, csv_filename)
        print(f"Data saved to {csv_filename}")

    except Exception as e:
        raise


if __name__ == "__main__":
    main()
