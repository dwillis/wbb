#!/usr/bin/env python3
"""
Analyze coach bios to determine gender based on pronouns using the llm library.
"""

import json
import llm
import argparse
from pathlib import Path
from typing import Dict, Optional


def determine_gender(bio_text: str, coach_name: str, model_name: str) -> Optional[str]:
    """
    Use LLM to determine gender based on pronouns in bio text.
    
    Returns:
        'F' for female (she/her pronouns)
        'M' for male (he/him/his pronouns)
        'N' for non-binary (they/them pronouns)
        None if no pronouns found or not a biography
    """
    prompt = f"""Analyze this coach biography and determine the gender based on pronouns used.

Coach Name: {coach_name}

Biography Text:
{bio_text}

Instructions:
- If the text uses she/her/hers pronouns when referring to this coach, respond with: F
- If the text uses he/him/his pronouns when referring to this coach, respond with: M
- If the text uses they/them/their pronouns when referring to this coach, respond with: N
- If there are no pronouns referring to this coach, or this is not an actual biography, respond with: None

Only respond with one of these four values: F, M, N, or None
Do not provide any explanation, just the single value."""

    try:
        model = llm.get_model(model_name)
        response = model.prompt(prompt)
        result = response.text().strip()
        
        # Validate response
        if result in ['F', 'M', 'N']:
            return result
        elif result == 'None':
            return None
        else:
            print(f"Warning: Unexpected response '{result}' for {coach_name}, treating as None")
            return None
            
    except Exception as e:
        print(f"Error processing {coach_name}: {e}")
        return None


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Analyze coach bios to determine gender based on pronouns using LLM'
    )
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='gpt-4o-mini',
        help='LLM model to use (default: gpt-4o-mini)'
    )
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent
    input_file = base_dir / 'coach_bios.json'
    output_file = base_dir / 'coach_bios_gender.json'
    
    print(f"Using model: {args.model}")
    print("Loading coach bios...")
    with open(input_file, 'r', encoding='utf-8') as f:
        coaches = json.load(f)
    
    print(f"Loaded {len(coaches)} coach bios")
    print("\nAnalyzing gender from pronouns using LLM...\n")
    
    # Process each coach
    for i, coach in enumerate(coaches, 1):
        coach_name = coach.get('name', 'Unknown')
        bio_text = coach.get('text', '')
        
        print(f"[{i}/{len(coaches)}] Processing {coach_name}...", end=' ')
        
        gender = determine_gender(bio_text, coach_name, args.model)
        coach['gender'] = gender
        
        if gender:
            print(f"→ {gender}")
        else:
            print("→ None")
    
    print(f"\nSaving results to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(coaches, f, indent=2, ensure_ascii=False)
    
    # Print statistics
    gender_counts = {}
    for coach in coaches:
        gender = coach.get('gender')
        gender_counts[gender] = gender_counts.get(gender, 0) + 1
    
    print("\nGender Distribution:")
    print(f"  Female (F): {gender_counts.get('F', 0)}")
    print(f"  Male (M): {gender_counts.get('M', 0)}")
    print(f"  Non-binary (N): {gender_counts.get('N', 0)}")
    print(f"  Unknown (None): {gender_counts.get(None, 0)}")
    print(f"\nTotal: {len(coaches)}")
    print("\nDone!")


if __name__ == '__main__':
    main()
