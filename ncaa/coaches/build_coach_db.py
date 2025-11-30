#!/usr/bin/env python3
"""
Insert coaching data from JSON into SQLite database with proper relationships.
Creates four tables: coaches, positions, education, and playing_career.
"""

import sqlite_utils
import json
import sys


def load_json_file(filename):
    """
    Load JSON data from a file.
    
    Args:
        filename: Path to the JSON file
    
    Returns:
        Parsed JSON data
    """
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filename}': {e}")
        sys.exit(1)


def insert_coaching_data(json_data, db_path="coaches.db"):
    """
    Insert coaching data into SQLite database with proper table structure.
    
    Args:
        json_data: List of coach dictionaries with nested positions, education, and playing_career
        db_path: Path to the SQLite database file
    """
    db = sqlite_utils.Database(db_path)
    
    for coach_data in json_data:
        # Extract coach-level data
        coach = {
            "team_id": coach_data["team_id"],
            "team": coach_data["team"],
            "name": coach_data["name"],
            "title": coach_data["title"],
            "url": coach_data["url"],
            "season": coach_data["season"]
        }
        
        # Insert coach and get the primary key
        coaches_table = db["coaches"]
        coaches_table.insert(coach, pk="name", replace=True)
        coach_name = coach["name"]
        
        # Insert positions with foreign key to coach
        if coach_data.get("positions"):
            positions_data = []
            for position in coach_data["positions"]:
                position_record = {
                    "coach_name": coach_name,
                    "college": position["college"],
                    "title": position["title"],
                    "start_year": position["start_year"],
                    "end_year": position["end_year"]
                }
                positions_data.append(position_record)
            
            db["positions"].insert_all(positions_data)
        
        # Insert education with foreign key to coach
        if coach_data.get("education"):
            education_data = []
            for edu in coach_data["education"]:
                edu_record = {
                    "coach_name": coach_name,
                    "college": edu["college"],
                    "degree": edu["degree"],
                    "year": edu["year"]
                }
                education_data.append(edu_record)
            
            db["education"].insert_all(education_data)
        
        # Insert playing career with foreign key to coach
        if coach_data.get("playing_career"):
            playing_data = []
            for playing in coach_data["playing_career"]:
                playing_record = {
                    "coach_name": coach_name,
                    "team": playing["team"],
                    "level": playing["level"],
                    "start_year": playing["start_year"],
                    "end_year": playing["end_year"]
                }
                playing_data.append(playing_record)
            
            db["playing"].insert_all(playing_data)
    
    # Add foreign key constraints
    db["positions"].add_foreign_key("coach_name", "coaches", "name", ignore=True)
    db["education"].add_foreign_key("coach_name", "coaches", "name", ignore=True)
    db["playing"].add_foreign_key("coach_name", "coaches", "name", ignore=True)
    
    print(f"Data successfully inserted into {db_path}")
    print(f"Tables created: {db.table_names()}")
    print(f"\nTable counts:")
    print(f"  coaches: {db['coaches'].count}")
    print(f"  positions: {db['positions'].count}")
    print(f"  education: {db['education'].count}")
    print(f"  playing: {db['playing'].count}")


if __name__ == "__main__":
    # Default JSON file name
    json_file = "coaching_histories.json"
    
    # Allow custom file name from command line
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    
    print(f"Loading data from {json_file}...")
    data = load_json_file(json_file)
    
    # Insert the data
    insert_coaching_data(data)
    
    # Optional: Display some sample data
    db = sqlite_utils.Database("coaches.db")
    
    print("\n" + "="*50)
    print("Sample data from coaches table:")
    print("="*50)
    for coach in db["coaches"].rows:
        print(f"\nCoach: {coach['name']}")
        print(f"  Team: {coach['team']}")
        print(f"  Title: {coach['title']}")
