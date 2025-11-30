import json
import csv

def convert_officials_to_csv(json_file_path, csv_file_path):
    """
    Convert officials JSON data to CSV format.
    Each official gets their own row for each game.
    Deduplicates records and removes entries with missing officials or locations.
    
    Args:
        json_file_path (str): Path to the input JSON file
        csv_file_path (str): Path to the output CSV file
    """
    
    # Read the JSON file
    with open(json_file_path, 'r') as json_file:
        games_data = json.load(json_file)
    
    # Use a set to track unique records and avoid duplicates
    unique_records = set()
    
    # Process each game
    for game in games_data:
        date = game.get('date', '')
        start_time = game.get('start_time', '')
        location = game.get('location', '')
        officials = game.get('officials', [])
        
        # Skip if location is missing or empty
        if not location or location.strip() == '':
            continue
            
        # Process each official
        for official in officials:
            # Skip if official is missing, empty, or None
            if not official or (isinstance(official, str) and official.strip() == ''):
                continue
                
            # Create a tuple for the record (tuples are hashable and can be added to sets)
            record = (date, start_time, location, official)
            unique_records.add(record)
    
    # Sort records by date, then start_time for consistent output
    sorted_records = sorted(unique_records, key=lambda x: (x[0], x[1]))
    
    # Write to CSV file
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        
        # Write header
        writer.writerow(['date', 'start_time', 'location', 'official'])
        
        # Write all unique records
        for record in sorted_records:
            writer.writerow(record)

# Run the conversion
if __name__ == "__main__":
    input_file = "officials_202425.json"
    output_file = "officials_202425.csv"
    
    try:
        convert_officials_to_csv(input_file, output_file)
        print(f"Successfully converted {input_file} to {output_file}")
        print("Records deduplicated and entries with missing officials/locations removed")
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {input_file}")
    except Exception as e:
        print(f"Error: {e}")