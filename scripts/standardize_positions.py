import pandas as pd
import re

def classify_position(title):
    """Classify position as coaching or staff."""
    if pd.isna(title):
        return "staff"
    return "coaching" if "coach" in title.lower() else "staff"

def assign_canonical_title(row):
    """Assign canonical title based on original title."""
    title = row['title']
    position_type = row['position_type']

    if pd.isna(title):
        return None

    title_lower = title.lower()

    # Only process coaching positions
    if position_type != "coaching":
        return None

    # Associate Head Coach (check first to avoid misclassification)
    if "associate head" in title_lower:
        return "Associate Head Coach"

    # Head Coach (but not Assistant Head Coach)
    if "head coach" in title_lower and "assistant head coach" not in title_lower:
        return "Head Coach"

    # Interim Head Coach
    if "interim head coach" in title_lower:
        return "Head Coach"

    # Assistant Coach (but exclude Graduate Assistant)
    if "assistant coach" in title_lower and "graduate assistant" not in title_lower:
        return "Assistant Coach"

    # Volunteer Assistant Coach
    if re.search(r"volunteer.*coach", title_lower):
        return "Assistant Coach"

    # Lead Assistant Coach
    if "lead assistant" in title_lower:
        return "Assistant Coach"

    # Other coaching positions that don't fit canonical categories
    return "Other Coaching"

def standardize_positions(input_file, output_file):
    """Main function to standardize positions."""

    # Read the data
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)

    print(f"Total records: {len(df)}")

    # Step 1: Classify position type
    df['position_type'] = df['title'].apply(classify_position)

    # Step 2: Assign canonical title
    df['canonical_title'] = df.apply(assign_canonical_title, axis=1)

    # Write standardized data
    df.to_csv(output_file, index=False)
    print(f"\nStandardized data written to {output_file}")

    # Generate summary report
    summary = df.groupby(['canonical_title', 'position_type'], dropna=False).agg(
        count=('title', 'size'),
        sample_titles=('title', lambda x: ' | '.join(x.unique()[:3]))
    ).reset_index().sort_values('count', ascending=False)

    summary_file = output_file.replace('_standardized.csv', '_summary.csv')
    summary.to_csv(summary_file, index=False)

    print("\n=== Standardization Summary ===")
    print(summary.to_string(index=False))

    # Check for positions needing review
    issues = df[
        (df['position_type'] == 'coaching') &
        (df['canonical_title'] == 'Other Coaching')
    ]['title'].value_counts()

    if len(issues) > 0:
        print("\n=== Coaching positions needing review ===")
        print(f"Total unique titles: {len(issues)}")
        print(f"Total records: {issues.sum()}")
        print("\nTop 20 titles:")
        print(issues.head(20))

        issues_file = output_file.replace('_standardized.csv', '_needing_review.csv')
        issues_df = pd.DataFrame({'title': issues.index, 'count': issues.values})
        issues_df.to_csv(issues_file, index=False)
        print(f"\nFull list written to {issues_file}")

    # Distribution summary
    print("\n=== Position Type Distribution ===")
    print(df['position_type'].value_counts())

    print("\n=== Canonical Title Distribution ===")
    print(df['canonical_title'].value_counts(dropna=False))

    return df

if __name__ == "__main__":
    input_file = "ncaa/positions.csv"
    output_file = "ncaa/positions_standardized.csv"

    df_standardized = standardize_positions(input_file, output_file)

    print("\n✓ Standardization complete!")
    print(f"Output written to: {output_file}")
    print(f"Summary written to: {output_file.replace('_standardized.csv', '_summary.csv')}")

    issues_count = len(df_standardized[
        (df_standardized['position_type'] == 'coaching') &
        (df_standardized['canonical_title'] == 'Other Coaching')
    ])

    if issues_count > 0:
        print(f"Review needed: {output_file.replace('_standardized.csv', '_needing_review.csv')}")
