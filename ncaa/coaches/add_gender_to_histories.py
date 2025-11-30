#!/usr/bin/env python3
"""
Add gender information from coach_bios_gender.json to coaching_histories_merged.csv
"""

import json
import csv
from pathlib import Path
from typing import Dict, Optional


def load_coach_gender_mapping(file_path: str) -> Dict[str, Optional[str]]:
    """
    Load gender information from coach_bios_gender.json.
    
    Returns:
        Dictionary mapping coach names to gender (F, M, N, or None)
    """
    gender_map = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        coaches = json.load(f)
        
        for coach in coaches:
            name = coach.get('name', '')
            gender = coach.get('gender')
            if name:
                gender_map[name] = gender
    
    return gender_map


def add_gender_to_histories(histories_file: str, gender_map: Dict[str, Optional[str]], output_file: str):
    """
    Add gender column to coaching_histories_merged.csv
    """
    rows = []
    
    # Read existing CSV
    with open(histories_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            coach_name = row['coach']
            # Look up gender, default to None if not found
            row['gender'] = gender_map.get(coach_name)
            rows.append(row)
    
    # Add 'gender' to fieldnames if not already present
    if 'gender' not in fieldnames:
        fieldnames = list(fieldnames) + ['gender']
    
    # Write updated CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return len(rows)


def main():
    """Main execution function."""
    base_dir = Path(__file__).parent
    gender_file = base_dir / 'coach_bios_gender.json'
    histories_file = base_dir / 'coaching_histories_merged.csv'
    output_file = base_dir / 'coaching_histories_merged.csv'
    
    print("Loading gender information from coach_bios_gender.json...")
    gender_map = load_coach_gender_mapping(gender_file)
    print(f"Loaded gender information for {len(gender_map)} coaches")
    
    print("\nAdding gender to coaching_histories_merged.csv...")
    total_rows = add_gender_to_histories(histories_file, gender_map, output_file)
    
    print(f"Updated {total_rows} records")
    
    # Print statistics
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        gender_counts = {}
        matched = 0
        unmatched = 0
        
        for row in reader:
            gender = row.get('gender')
            if gender and gender != '':
                gender_counts[gender] = gender_counts.get(gender, 0) + 1
                matched += 1
            else:
                unmatched += 1
    
    print("\nGender Distribution in Merged File:")
    print(f"  Female (F): {gender_counts.get('F', 0)}")
    print(f"  Male (M): {gender_counts.get('M', 0)}")
    print(f"  Non-binary (N): {gender_counts.get('N', 0)}")
    print(f"  Unknown/Unmatched: {unmatched}")
    print(f"\nTotal records: {total_rows}")
    print(f"Matched coaches: {matched} ({matched/total_rows*100:.1f}%)")
    print(f"Unmatched coaches: {unmatched} ({unmatched/total_rows*100:.1f}%)")
    print("\nDone!")


if __name__ == '__main__':
    main()
