#!/usr/bin/env -S uv run python
"""
Load coaching histories JSON into SQLite database with normalized tables.
Uses sqlite-utils Python API to create coaches table and related tables 
for positions, education, and playing_career.

Usage:
    uv run python load_coaching_histories.py [json_file] [db_file]
    
Example:
    uv run python load_coaching_histories.py coaching_histories.json coaching_histories.db
"""

import json
from pathlib import Path
from sqlite_utils import Database

def load_coaching_histories(json_file="coaching_histories.json", db_file="coaching_histories.db"):
    """Load coaching histories from JSON into SQLite database with normalized structure."""
    
    # Load JSON data
    print(f"Loading data from {json_file}...")
    with open(json_file, 'r') as f:
        coaches_data = json.load(f)
    
    print(f"Found {len(coaches_data)} coaches")
    
    # Create/connect to database
    db = Database(db_file, recreate=True)
    print(f"Created database: {db_file}")
    
    # Prepare data for coaches table (without nested arrays)
    coaches_records = []
    positions_records = []
    education_records = []
    playing_career_records = []
    
    for coach in coaches_data:
        # Extract coach base data (excluding nested arrays)
        coach_record = {
            'url': coach['url'],
            'team_id': coach['team_id'],
            'team': coach['team'],
            'name': coach['name'],
            'title': coach['title'],
            'season': coach['season']
        }
        coaches_records.append(coach_record)
        
        # Extract positions
        for position in coach.get('positions', []):
            position_record = {
                'coach_url': coach['url'],
                'team_id': coach['team_id'],
                'college': position.get('college'),
                'title': position.get('title'),
                'start_year': position.get('start_year'),
                'end_year': position.get('end_year')
            }
            positions_records.append(position_record)
        
        # Extract education
        for edu in coach.get('education', []):
            education_record = {
                'coach_url': coach['url'],
                'team_id': coach['team_id'],
                'college': edu.get('college'),
                'degree': edu.get('degree'),
                'year': edu.get('year')
            }
            education_records.append(education_record)
        
        # Extract playing career
        for playing in coach.get('playing_career', []):
            playing_record = {
                'coach_url': coach['url'],
                'team_id': coach['team_id'],
                'team': playing.get('team'),
                'level': playing.get('level'),
                'start_year': playing.get('start_year'),
                'end_year': playing.get('end_year')
            }
            playing_career_records.append(playing_record)
    
    # Insert coaches table with url as primary key
    print(f"\nInserting {len(coaches_records)} coaches...")
    db['coaches'].insert_all(coaches_records, pk='url', replace=True)
    
    # Insert positions table
    print(f"Inserting {len(positions_records)} positions...")
    if positions_records:
        db['positions'].insert_all(positions_records, replace=True)
        # Add foreign key constraint
        db['positions'].add_foreign_key('coach_url', 'coaches', 'url', ignore=True)
    
    # Insert education table
    print(f"Inserting {len(education_records)} education records...")
    if education_records:
        db['education'].insert_all(education_records, replace=True)
        # Add foreign key constraint
        db['education'].add_foreign_key('coach_url', 'coaches', 'url', ignore=True)
    
    # Insert playing_career table
    print(f"Inserting {len(playing_career_records)} playing career records...")
    if playing_career_records:
        db['playing_career'].insert_all(playing_career_records, replace=True)
        # Add foreign key constraint
        db['playing_career'].add_foreign_key('coach_url', 'coaches', 'url', ignore=True)
    
    # Create indexes for better query performance
    print("\nCreating indexes...")
    db['positions'].create_index(['coach_url'], if_not_exists=True)
    db['positions'].create_index(['team_id'], if_not_exists=True)
    db['positions'].create_index(['college'], if_not_exists=True)
    db['positions'].create_index(['start_year'], if_not_exists=True)
    
    db['education'].create_index(['coach_url'], if_not_exists=True)
    db['education'].create_index(['team_id'], if_not_exists=True)
    db['education'].create_index(['college'], if_not_exists=True)
    
    db['playing_career'].create_index(['coach_url'], if_not_exists=True)
    db['playing_career'].create_index(['team_id'], if_not_exists=True)
    db['playing_career'].create_index(['team'], if_not_exists=True)
    db['playing_career'].create_index(['level'], if_not_exists=True)
    
    db['coaches'].create_index(['name'], if_not_exists=True)
    db['coaches'].create_index(['team'], if_not_exists=True)
    db['coaches'].create_index(['season'], if_not_exists=True)
    
    # Print summary
    print("\n" + "="*60)
    print("Database created successfully!")
    print("="*60)
    print(f"\nTable row counts:")
    print(f"  coaches:        {db['coaches'].count:,}")
    print(f"  positions:      {db['positions'].count:,}")
    print(f"  education:      {db['education'].count:,}")
    print(f"  playing_career: {db['playing_career'].count:,}")
    
    print(f"\nDatabase file: {db_file}")
    print(f"Database size: {Path(db_file).stat().st_size:,} bytes")
    
    # Print example queries
    print("\n" + "="*60)
    print("Example queries:")
    print("="*60)
    print("""
# Get a coach and all their positions
from sqlite_utils import Database
db = Database('coaching_histories.db')

coach = list(db['coaches'].rows_where("name = 'Joni Taylor'"))[0]
positions = list(db['positions'].rows_where("coach_url = ?", [coach['url']]))

# Find coaches who played at Kentucky
playing_at_kentucky = db.execute('''
    SELECT DISTINCT c.name, c.team, c.title
    FROM playing_career pc
    JOIN coaches c ON pc.coach_url = c.url
    WHERE pc.team = 'Kentucky'
    ORDER BY c.name
''').fetchall()

# Count positions by college
position_counts = db.execute('''
    SELECT college, COUNT(*) as count
    FROM positions
    GROUP BY college
    ORDER BY count DESC
    LIMIT 10
''').fetchall()

# Find coaches who both played and coached at the same school
same_school = db.execute('''
    SELECT DISTINCT c.name, c.team as current_team, p.college
    FROM coaches c
    JOIN positions pos ON c.url = pos.coach_url
    JOIN playing_career p ON c.url = p.coach_url
    WHERE pos.college = p.team
    ORDER BY c.name
''').fetchall()
""")
    
    return db

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    json_file = sys.argv[1] if len(sys.argv) > 1 else "coaching_histories.json"
    db_file = sys.argv[2] if len(sys.argv) > 2 else "coaching_histories.db"
    
    if not Path(json_file).exists():
        print(f"Error: {json_file} not found")
        sys.exit(1)
    
    db = load_coaching_histories(json_file, db_file)
    
    print("\n✓ Database loaded successfully!")
