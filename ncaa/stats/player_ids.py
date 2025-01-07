import time
import csv
import sys
import requests
from bs4 import BeautifulSoup

# Check if the input and output file arguments are provided
if len(sys.argv) != 4:
    print("Usage: python player_ids.py <input_csv> <output_csv> <error_csv>")
    sys.exit(1)

# Get input, output, and error file paths
input_csv = sys.argv[1]
output_csv = sys.argv[2]
error_csv = sys.argv[3]

# Headers for the output and error CSVs
output_headers = ['season', 'team_id', 'player_name', 'player_id', 'player_url', 'master_id']
error_headers = ['season', 'team_id', 'player_name', 'player_id', 'player_url', 'master_id']

# Initialize the output CSVs
with open(output_csv, 'w', newline='', encoding='utf-8') as outfile, \
     open(error_csv, 'w', newline='', encoding='utf-8') as errfile:
    output_writer = csv.DictWriter(outfile, fieldnames=output_headers)
    error_writer = csv.DictWriter(errfile, fieldnames=error_headers)

    # Write headers
    output_writer.writeheader()
    error_writer.writeheader()

    # Read the input CSV and process each player
    with open(input_csv, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)

        for row in reader:
            time.sleep(1)
            player_url = row['player_url']
            print(f"Fetching data for player: {row['player_name']} ({player_url})...")

            # Fetch the player page
            response = requests.get(player_url, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                print(f"Failed to fetch page for {row['player_name']}. Status code: {response.status_code}")
                error_writer.writerow(row)
                continue

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the form with id "sit_stat_form_id"
            form = soup.find('form', {'id': 'sit_stat_form_id'})
            master_id = None

            if form:
                # Extract the value of the input element with id "stats_player_seq_field_id"
                input_element = form.find('input', {'id': 'stats_player_seq_field_id'})
                if input_element and 'value' in input_element.attrs:
                    master_id = input_element['value']

            # Add master_id to the row
            row['master_id'] = master_id
            output_writer.writerow(row)

print(f"Player data with master IDs saved to {output_csv}")
print(f"Failed URLs saved to {error_csv}")
