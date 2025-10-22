#!/usr/bin/env python3
"""
Extract coaching histories from coach biographies using Claude via the llm library.
Processes coach_bios.json and outputs coaching_histories.json with structured career data.
"""

import json
import llm
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
import argparse


def load_extraction_prompt() -> str:
    """Load the extraction prompt from the markdown file."""
    prompt_path = Path(__file__).parent / "extraction_prompt.md"
    with open(prompt_path, 'r') as f:
        return f.read()


def load_coach_bios() -> List[Dict[str, Any]]:
    """Load all coach biographies from the JSON file."""
    bios_path = Path(__file__).parent / "coach_bios.json"
    with open(bios_path, 'r') as f:
        return json.load(f)


def load_existing_histories() -> Optional[List[Dict[str, Any]]]:
    """Load existing coaching histories if available."""
    histories_path = Path(__file__).parent / "coaching_histories.json"
    if histories_path.exists():
        with open(histories_path, 'r') as f:
            return json.load(f)
    return None


def merge_coach_data(bio: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge biography data with existing history data.
    If existing data has positions/education, preserve it.
    Otherwise, prepare structure for new extraction.
    """
    if existing:
        return {
            'team_id': bio['team_id'],
            'team': bio['team'],
            'name': bio['name'],
            'title': bio['title'],
            'url': bio['url'],
            'season': bio['season'],
            'text': bio['text'],  # Keep text for potential re-processing
            'positions': existing.get('positions', []),
            'education': existing.get('education', []),
            'playing_career': existing.get('playing_career', [])
        }
    else:
        return {
            **bio,
            'positions': [],
            'education': [],
            'playing_career': []
        }


def chunk_coaches(coaches: List[Dict[str, Any]], chunk_size: int = 10) -> List[List[Dict[str, Any]]]:
    """
    Split coaches into chunks to avoid context window limits.
    Processing 10 coaches at a time should be safe for most biographies.
    """
    chunks = []
    for i in range(0, len(coaches), chunk_size):
        chunks.append(coaches[i:i + chunk_size])
    return chunks


def extract_coaching_history(coach: Dict[str, Any], base_prompt: str, model) -> Dict[str, Any]:
    """
    Extract coaching history for a single coach using the LLM.
    Returns the coach data with added positions and education arrays.
    """
    # Build the prompt with the coach's biography
    full_prompt = f"""{base_prompt}

## Coach Biography to Process

**Name:** {coach['name']}
**Current Team:** {coach['team']}
**Current Title:** {coach['title']}

**Biography Text:**
{coach['text']}

Extract the coaching positions, education history, and playing career for this coach and return ONLY a valid JSON object with "positions", "education", and "playing_career" arrays. Do not include any markdown formatting or code blocks."""

    try:
        # Use the llm library to call Claude
        response = model.prompt(full_prompt)
        response_text = response.text().strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Try to find JSON object in the response (in case there's extra text)
        # Look for the first { and last }
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            response_text = response_text[start_idx:end_idx + 1]
        
        # Parse the JSON response
        extracted_data = json.loads(response_text)
        
        # Validate the response has the required fields
        if 'positions' not in extracted_data or 'education' not in extracted_data:
            print(f"Warning: Invalid response for {coach['name']} - missing required fields")
            extracted_data = {'positions': [], 'education': [], 'playing_career': []}
        
        # Merge with original coach data
        result = {
            'team_id': coach['team_id'],
            'team': coach['team'],
            'name': coach['name'],
            'title': coach['title'],
            'url': coach['url'],
            'season': coach['season'],
            'positions': extracted_data.get('positions', []),
            'education': extracted_data.get('education', []),
            'playing_career': extracted_data.get('playing_career', [])
        }
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for {coach['name']}: {e}")
        print(f"Response text: {response_text[:200]}...")
        # Return minimal structure on error
        return {
            'team_id': coach['team_id'],
            'team': coach['team'],
            'name': coach['name'],
            'title': coach['title'],
            'url': coach['url'],
            'season': coach['season'],
            'positions': [],
            'education': [],
            'playing_career': []
        }
    except Exception as e:
        print(f"Error processing {coach['name']}: {e}")
        # Return minimal structure on error
        return {
            'team_id': coach['team_id'],
            'team': coach['team'],
            'name': coach['name'],
            'title': coach['title'],
            'url': coach['url'],
            'season': coach['season'],
            'positions': [],
            'education': [],
            'playing_career': []
        }


def main():
    """Main processing function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Extract coaching histories from coach biographies using Claude'
    )
    parser.add_argument(
        '--only-empty',
        action='store_true',
        help='Only process coaches with empty positions arrays (requires existing coaching_histories.json)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume processing from existing coaching_histories.json, only processing coaches with empty positions'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: only process 5 coaches'
    )
    args = parser.parse_args()
    
    print("Loading extraction prompt...")
    base_prompt = load_extraction_prompt()
    
    print("Loading coach biographies...")
    coaches_bios = load_coach_bios()
    
    # Load existing histories if resume or only-empty mode
    existing_histories = None
    if args.resume or args.only_empty:
        print("Loading existing coaching histories...")
        existing_histories = load_existing_histories()
        if existing_histories is None:
            print("Error: coaching_histories.json not found. Cannot use --resume or --only-empty mode.")
            sys.exit(1)
        print(f"Found {len(existing_histories)} existing coach records")
        
        # Create a lookup dictionary by name and team
        existing_lookup = {
            (h['name'], h['team']): h 
            for h in existing_histories
        }
    else:
        existing_lookup = {}
    
    # Merge biographical data with existing history data
    coaches = []
    for bio in coaches_bios:
        key = (bio['name'], bio['team'])
        existing = existing_lookup.get(key)
        merged = merge_coach_data(bio, existing)
        coaches.append(merged)
    
    # Filter to only coaches with empty positions if requested
    if args.only_empty or args.resume:
        coaches_to_process = [c for c in coaches if not c['positions']]
        print(f"Filtering to coaches with empty positions: {len(coaches_to_process)} to process")
    else:
        coaches_to_process = coaches
    
    # Limit to 5 coaches if in test mode
    if args.test:
        coaches_to_process = coaches_to_process[:5]
        print(f"Test mode: limiting to {len(coaches_to_process)} coaches")
    
    total_coaches = len(coaches_to_process)
    if total_coaches == 0:
        print("No coaches to process!")
        return
    
    print(f"Found {total_coaches} coaches to process")
    
    # Initialize the LLM model
    print("Initializing Claude Haiku 4.5 model...")
    model = llm.get_model("claude-haiku-4.5")
    
    # Process coaches one at a time with progress tracking
    processed_coaches = {}
    for i, coach in enumerate(coaches_to_process, 1):
        print(f"Processing {i}/{total_coaches}: {coach['name']} ({coach['team']})...")
        
        result = extract_coaching_history(coach, base_prompt, model)
        key = (result['name'], result['team'])
        processed_coaches[key] = result
        
        # Print progress every 50 coaches
        if i % 50 == 0:
            print(f"  Progress: {i}/{total_coaches} coaches processed ({i*100//total_coaches}%)")
    
    # Build final results list
    # If resuming, merge with all existing coaches; otherwise use only processed
    if args.resume or args.only_empty:
        # Start with all coaches, update the ones we processed
        results = []
        for coach in coaches:
            key = (coach['name'], coach['team'])
            if key in processed_coaches:
                results.append(processed_coaches[key])
            else:
                # Remove 'text' field if it exists (from merge_coach_data)
                coach_copy = {k: v for k, v in coach.items() if k != 'text'}
                results.append(coach_copy)
    else:
        results = list(processed_coaches.values())
    
    # Save results
    output_path = Path(__file__).parent / "coaching_histories.json"
    print(f"\nSaving results to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ Successfully processed {total_coaches} coaches!")
    print(f"  Output saved to: {output_path}")
    
    # Print summary statistics
    coaches_with_positions = sum(1 for r in results if r['positions'])
    coaches_with_education = sum(1 for r in results if r['education'])
    coaches_with_playing = sum(1 for r in results if r.get('playing_career', []))
    print(f"\nSummary:")
    print(f"  Total coaches in output: {len(results)}")
    print(f"  Coaches with positions extracted: {coaches_with_positions}/{len(results)}")
    print(f"  Coaches with education extracted: {coaches_with_education}/{len(results)}")
    print(f"  Coaches with playing career extracted: {coaches_with_playing}/{len(results)}")
    
    if args.resume or args.only_empty:
        remaining = sum(1 for r in results if not r['positions'])
        print(f"  Coaches still needing processing: {remaining}")


if __name__ == "__main__":
    main()
