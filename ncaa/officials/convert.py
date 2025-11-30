import csv
import json
import re
from datetime import datetime

def convert_csv_to_json(input_csv_path, output_json_path):
    """
    Convert CSV file to JSON, transforming the officials column from a comma-separated string
    into an array of three names and converting dates to yyyy-mm-dd format.
    Before conversion, deduplicate rows based on specified columns.
    
    Args:
        input_csv_path (str): Path to the input CSV file
        output_json_path (str): Path to save the output JSON file
    """
    data = []
    seen_combinations = set()
    duplicates_count = 0
    
    with open(input_csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            # Convert string numeric fields to integers
            for field in ['ncaa_id', 'game_id', 'home_fouls', 'home_technicals', 
                         'visitor_fouls', 'visitor_technicals']:
                if row[field]:
                    row[field] = int(row[field])
            
            # formatted_date = row['date']
            # Convert date from m/d/yyyy to yyyy-mm-dd format
            if row['date']:
                month, day, year = row['date'].split('/')
                # Pad month and day with leading zeros if needed
                month = month.zfill(2)
                day = day.zfill(2)
                formatted_date = f"{year}-{month}-{day}"
            else:
                formatted_date = row['date']
            
            # Split the officials string into an array of names
            # The officials are separated by commas, but there may be extra spaces
            officials_string = row['officials']
            officials_array = [name.strip().replace('  ',' ').title() for name in officials_string.split(',')]
            
            # Create a tuple of the deduplication columns for comparison
            # Use the original date format for deduplication, then convert after
            dedup_tuple = (
                row['date'],  # original date format
                row['home'],
                row['home_fouls'],
                row['home_technicals'],
                row['visitor'],
                row['visitor_fouls'],
                row['visitor_technicals'],
                officials_string  # original officials string
            )
            
            # Check if this combination has been seen before
            if dedup_tuple in seen_combinations:
                duplicates_count += 1
                continue  # Skip this duplicate row
            else:
                seen_combinations.add(dedup_tuple)
            
            # Now apply the formatting transformations
            row['date'] = formatted_date
            row['officials'] = officials_array
            
            data.append(row)
    
    # Write to JSON file
    with open(output_json_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=2)
    
    print(f"Conversion complete. JSON file saved to {output_json_path}")
    print(f"Processed {len(data)} unique games (removed {duplicates_count} duplicates)")
    if len(data) > 0:
        print(f"Each game has {len(data[0]['officials'])} officials")

if __name__ == "__main__":
    input_csv = "officials_2022-23.csv"
    output_json = "officials_202223.json"
    convert_csv_to_json(input_csv, output_json)