#!/usr/bin/env python3
"""
Check if all college values from coaching_histories.json are present in distinct_colleges.csv.
Add missing colleges with empty ncaa_id and category fields.
"""

import json
import csv
from pathlib import Path
from typing import Set, List, Dict


def load_coaching_colleges(file_path: str) -> Set[str]:
    """Extract all unique college names from coaching_histories.json."""
    colleges = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        histories = json.load(f)
        
        for coach_record in histories:
            # Get colleges from positions
            positions = coach_record.get('positions', [])
            for position in positions:
                college = position.get('college', '')
                if college:
                    college = college.strip()
                    if college:
                        colleges.add(college)
    
    return colleges


def load_distinct_colleges(file_path: str) -> tuple[Set[str], List[Dict]]:
    """Load distinct_colleges.csv and return set of college names and all rows."""
    colleges = set()
    rows = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            college = row['college'].strip()
            if college:
                colleges.add(college)
            rows.append(row)
    
    return colleges, rows


def add_missing_colleges(file_path: str, missing_colleges: Set[str], existing_rows: List[Dict]):
    """Add missing colleges to distinct_colleges.csv."""
    # Sort missing colleges for consistent output
    sorted_missing = sorted(missing_colleges)
    
    # Create new rows for missing colleges
    new_rows = []
    for college in sorted_missing:
        new_rows.append({
            'college': college,
            'ncaa_id': '',
            'college_clean': college,  # Use the original name as clean name
            'category': ''
        })
    
    # Combine existing and new rows
    all_rows = existing_rows + new_rows
    
    # Write back to file
    fieldnames = ['college', 'ncaa_id', 'college_clean', 'category']
    
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    
    print(f"Added {len(new_rows)} missing colleges to {file_path}")
    for college in sorted_missing:
        print(f"  + {college}")


def main():
    """Main execution function."""
    base_dir = Path(__file__).parent
    histories_file = base_dir / 'coaching_histories.json'
    colleges_file = base_dir / 'distinct_colleges.csv'
    
    print("Loading colleges from coaching_histories.json...")
    coaching_colleges = load_coaching_colleges(histories_file)
    print(f"Found {len(coaching_colleges)} unique colleges in coaching histories")
    
    print("\nLoading distinct_colleges.csv...")
    distinct_colleges, existing_rows = load_distinct_colleges(colleges_file)
    print(f"Found {len(distinct_colleges)} colleges in distinct_colleges.csv")
    
    # Find missing colleges
    missing = coaching_colleges - distinct_colleges
    
    if missing:
        print(f"\nFound {len(missing)} missing colleges:")
        for college in sorted(missing):
            print(f"  - {college}")
        
        print("\nAdding missing colleges to distinct_colleges.csv...")
        add_missing_colleges(colleges_file, missing, existing_rows)
        print("\nDone!")
    else:
        print("\n✓ All colleges from coaching_histories.json are present in distinct_colleges.csv")


if __name__ == '__main__':
    main()
