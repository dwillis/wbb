#!/usr/bin/env python3
"""
Merge coaching histories with standardized college data.

This script combines coaching_histories.json with distinct_colleges.csv and teams.json
to produce a comprehensive dataset with standardized college names, categories, and 
team information.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional


def load_coaching_histories(file_path: str) -> List[Dict]:
    """Load coaching histories from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_distinct_colleges(file_path: str) -> Dict[int, Dict]:
    """Load distinct colleges and create lookup by ncaa_id."""
    colleges_by_id = {}
    colleges_by_name = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle ncaa_id (may be empty)
            ncaa_id = row['ncaa_id'].strip()
            if ncaa_id:
                ncaa_id = int(ncaa_id)
                if ncaa_id not in colleges_by_id:
                    colleges_by_id[ncaa_id] = {
                        'college_clean': row['college_clean'],
                        'category': row['category']
                    }
            
            # Also store by original college name for fallback lookup
            college_name = row['college'].strip()
            if college_name not in colleges_by_name:
                colleges_by_name[college_name] = {
                    'college_clean': row['college_clean'],
                    'category': row['category'],
                    'ncaa_id': ncaa_id if ncaa_id else None
                }
    
    return colleges_by_id, colleges_by_name


def load_teams(file_path: str) -> Dict[int, Dict]:
    """Load teams data and create lookup by ncaa_id."""
    teams_by_id = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        teams = json.load(f)
        for team in teams:
            ncaa_id = team['ncaa_id']
            teams_by_id[ncaa_id] = {
                'team': team['team'],
                'team_state': team.get('team_state', ''),
                'conference': team.get('conference', ''),
                'division': team.get('division', '')
            }
    
    return teams_by_id


def load_position_standardization(file_path: str) -> Dict[tuple, str]:
    """Load position title standardization mapping."""
    # Create a lookup by (coach_name, position_college, position_title, start_year, end_year)
    standardization = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Create key from identifying fields
            start = row['position_start'] if row['position_start'] != 'NA' else None
            end = row['position_end'] if row['position_end'] != 'NA' else None
            
            key = (
                row['name'],
                row['position_college'],
                row['position_title'],
                start,
                end
            )
            standardization[key] = row['position_title_standardized']
    
    return standardization


def merge_coaching_data(histories: List[Dict], colleges_by_id: Dict, colleges_by_name: Dict, teams: Dict, standardization: Dict) -> List[Dict]:
    """Merge coaching histories with college and team data."""
    merged_data = []
    
    for coach_record in histories:
        coach_name = coach_record.get('name', '')
        current_team_id = coach_record.get('team_id')
        if current_team_id:
            current_team_id = int(current_team_id)
        
        # Process positions (coaching history)
        positions = coach_record.get('positions', [])
        
        for position in positions:
            college = position.get('college', '')
            start_year = position.get('start_year', '')
            end_year = position.get('end_year', '')
            title = position.get('title', '')
            
            # Try to find team_id for this position's college
            team_id = None
            if college in colleges_by_name and colleges_by_name[college]['ncaa_id']:
                team_id = colleges_by_name[college]['ncaa_id']
            
            # Look up standardized title
            start_str = str(start_year) if start_year else None
            end_str = str(end_year) if end_year else None
            lookup_key = (coach_name, college, title, start_str, end_str)
            position_title_standardized = standardization.get(lookup_key, '')
            
            # Initialize merged entry
            merged_entry = {
                'coach': coach_name,
                'college': college,
                'title': title,
                'team_id': team_id if team_id else '',
                'start_year': start_year if start_year else '',
                'end_year': end_year if end_year else '',
                'position_title_standardized': position_title_standardized,
                'college_clean': '',
                'category': '',
                'team_state': '',
                'conference': '',
                'division': ''
            }
            
            # Try to get data from ncaa_id first
            if team_id:
                # Get college info from distinct_colleges
                if team_id in colleges_by_id:
                    college_info = colleges_by_id[team_id]
                    merged_entry['category'] = college_info['category']
                
                # Get team info from teams.json (including team name for college_clean)
                if team_id in teams:
                    team_info = teams[team_id]
                    merged_entry['college_clean'] = team_info['team']
                    merged_entry['team_state'] = team_info['team_state']
                    merged_entry['conference'] = team_info['conference']
                    merged_entry['division'] = team_info['division']
            
            # If no team_id or data not found, try lookup by college name
            if not merged_entry['college_clean'] and college in colleges_by_name:
                college_info = colleges_by_name[college]
                merged_entry['college_clean'] = college_info['college_clean']
                merged_entry['category'] = college_info['category']
                # If we found an ncaa_id through name lookup, try to get team data
                if college_info['ncaa_id'] and college_info['ncaa_id'] in teams:
                    team_info = teams[college_info['ncaa_id']]
                    merged_entry['team_state'] = team_info['team_state']
                    merged_entry['conference'] = team_info['conference']
                    merged_entry['division'] = team_info['division']
            
            # If still no college_clean, use the original college name
            if not merged_entry['college_clean']:
                merged_entry['college_clean'] = college
            
            merged_data.append(merged_entry)
    
    return merged_data


def save_to_csv(data: List[Dict], output_path: str):
    """Save merged data to CSV file."""
    if not data:
        print("No data to save")
        return
    
    fieldnames = [
        'coach', 'college', 'title', 'team_id', 'start_year', 'end_year',
        'position_title_standardized', 'college_clean', 'category', 'team_state', 'conference', 'division'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"Saved {len(data)} records to {output_path}")


def main():
    """Main execution function."""
    # Define file paths
    base_dir = Path(__file__).parent
    histories_file = base_dir / 'coaching_histories.json'
    colleges_file = base_dir / 'distinct_colleges.csv'
    teams_file = base_dir / 'teams.json'
    standardization_file = base_dir / 'positions_standardized.csv'
    output_file = base_dir / 'coaching_histories_merged.csv'
    
    print("Loading coaching histories...")
    histories = load_coaching_histories(histories_file)
    print(f"Loaded {len(histories)} coaches")
    
    print("Loading distinct colleges...")
    colleges_by_id, colleges_by_name = load_distinct_colleges(colleges_file)
    print(f"Loaded {len(colleges_by_id)} colleges with ncaa_id")
    print(f"Loaded {len(colleges_by_name)} unique college names")
    
    print("Loading teams data...")
    teams = load_teams(teams_file)
    print(f"Loaded {len(teams)} teams")
    
    print("Loading position title standardization...")
    standardization = load_position_standardization(standardization_file)
    print(f"Loaded {len(standardization)} standardized position titles")
    
    print("Merging data...")
    merged_data = merge_coaching_data(histories, colleges_by_id, colleges_by_name, teams, standardization)
    
    print("Saving merged data...")
    save_to_csv(merged_data, output_file)
    
    # Print some statistics
    with_team_id = sum(1 for entry in merged_data if entry['team_id'])
    with_state = sum(1 for entry in merged_data if entry['team_state'])
    with_division = sum(1 for entry in merged_data if entry['division'])
    
    print(f"\nStatistics:")
    print(f"  Total entries: {len(merged_data)}")
    print(f"  Entries with team_id: {with_team_id}")
    print(f"  Entries with team_state: {with_state}")
    print(f"  Entries with division: {with_division}")


if __name__ == '__main__':
    main()
