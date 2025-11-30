import os
import csv
import requests
from bs4 import BeautifulSoup
import glob
from time import sleep

def process_team_files(directory='teams'):
    # Headers for requests to mimic Mozilla browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Find all matching CSV files
    pattern = os.path.join(directory, 'teams_*_d*.csv')
    csv_files = glob.glob(pattern)
    
    for input_file in csv_files:
        # Extract year and division from filename
        filename = os.path.basename(input_file)
        parts = filename.replace('.csv', '').split('_')
        year = parts[1]
        div = parts[2].replace('d', '')
        
        # Create output filename
        output_file = os.path.join(directory, f'teams_{year}_d{div}_with_id.csv')
        
        # Process the file
        print(f"Processing {input_file}...")
        
        rows_to_write = []
        with open(input_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames + ['master_team_id', 'div']
            
            for row in reader:
                try:
                    # Make request to URL
                    response = requests.get(row['url'], headers=headers)
                    response.raise_for_status()
                    
                    # Parse HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find history link
                    history_link = soup.find('a', href=lambda href: href and '/history/' in href)
                    
                    if history_link:
                        # Extract master_team_id
                        master_team_id = history_link['href'].split('/')[4]
                    else:
                        master_team_id = ''
                    
                    # Add new fields to row
                    row_copy = row.copy()
                    row_copy['master_team_id'] = master_team_id
                    row_copy['div'] = div
                    rows_to_write.append(row_copy)
                    
                    # Be nice to the server
                    sleep(1)
                    
                except Exception as e:
                    print(f"Error processing {row['url']}: {str(e)}")
                    row_copy = row.copy()
                    row_copy['master_team_id'] = ''
                    row_copy['div'] = div
                    rows_to_write.append(row_copy)
        
        # Write processed data to new file
        with open(output_file, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_to_write)
        
        print(f"Completed processing {input_file}")

if __name__ == "__main__":
    process_team_files()