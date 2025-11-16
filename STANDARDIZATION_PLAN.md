# Job Title Standardization Plan for NCAA Positions

## Overview
This plan outlines the approach for standardizing job titles in `ncaa/positions.csv` according to the following policies:

1. **Classification**: Positions with "coach" in the title are considered coaching positions; all others are "staff"
2. **Canonical Titles**: Head Coach, Associate Head Coach, Assistant Coach
3. **Data Preservation**: Original titles will be preserved with new columns added for standardized versions

## Current Data Analysis

### Data Structure
- **File**: `ncaa/positions.csv`
- **Columns**: rowid, coach_name, coach_name_label, college, title, start_year, end_year
- **Total Records**: ~12,000+ positions

### Title Variations Found
**Head Coach variations (~1,800+ records)**:
- Head Women's Basketball Coach (1,117)
- Head Coach (616)
- Head Men's Basketball Coach (44)
- Head Basketball Coach (35)
- Interim Head Coach (77)
- Head Girls' Basketball Coach (51+33)
- And many others with "Head Coach" in the title

**Associate Head Coach variations (~650+ records)**:
- Associate Head Coach (573)
- Associate Head Coach/Recruiting Coordinator (46)
- Associate Head Women's Basketball Coach (32)

**Assistant Coach variations (~6,000+ records)**:
- Assistant Coach (4,586)
- Assistant Coach/Recruiting Coordinator (409)
- Assistant Women's Basketball Coach (307)
- Assistant Men's Basketball Coach (64)
- Volunteer Assistant Coach (63)
- Lead Assistant Coach (17)
- And many combinations with additional duties

**Staff positions (non-coaching)**:
- Director of Basketball Operations (221)
- Graduate Assistant (466) - Note: these contain "Assistant" but are typically non-coaching
- Video Coordinator (112)
- Director of Operations (105)
- Student Manager (69)
- Recruiting Coordinator (47)
- Athletic Trainer (15)
- Strength and Conditioning Coach (22+26)
- And many others

## Standardization Logic

### Step 1: Position Classification
Create a `position_type` column:
- If title contains "coach" (case-insensitive) → "coaching"
- Else → "staff"

### Step 2: Canonical Title Mapping
Create a `canonical_title` column for coaching positions:

**Head Coach** - Any title containing:
- "head coach"
- "interim head coach"
- But NOT containing "associate head coach" or "assistant head coach"

**Associate Head Coach** - Any title containing:
- "associate head coach"
- "associate head"

**Assistant Coach** - Any title containing:
- "assistant coach" (but not "associate head coach")
- "volunteer assistant coach"
- "lead assistant coach"
- But NOT "graduate assistant" (these are staff)

**Staff positions** - `canonical_title` = NA or "Staff"

### Step 3: Output Schema
New columns to add:
- `position_type`: "coaching" or "staff"
- `canonical_title`: One of: "Head Coach", "Associate Head Coach", "Assistant Coach", or NA/blank for staff

---

# Implementation Option 1: R with tidyverse

## File: `scripts/standardize_positions.R`

```r
library(tidyverse)

# Read the data
positions <- read_csv("ncaa/positions.csv")

# Standardize job titles
positions_standardized <- positions %>%
  mutate(
    # Convert title to lowercase for matching
    title_lower = str_to_lower(title),

    # Step 1: Classify position type
    position_type = if_else(
      str_detect(title_lower, "coach"),
      "coaching",
      "staff"
    ),

    # Step 2: Assign canonical title
    canonical_title = case_when(
      # Associate Head Coach (check this first to avoid misclassification)
      str_detect(title_lower, "associate head") ~ "Associate Head Coach",

      # Head Coach (but not Associate Head Coach or Assistant Head Coach)
      str_detect(title_lower, "head coach") &
        !str_detect(title_lower, "assistant head coach") ~ "Head Coach",

      # Interim Head Coach
      str_detect(title_lower, "interim head coach") ~ "Head Coach",

      # Assistant Coach (but exclude Graduate Assistant)
      str_detect(title_lower, "assistant coach") &
        !str_detect(title_lower, "graduate assistant") ~ "Assistant Coach",

      # Volunteer Assistant Coach
      str_detect(title_lower, "volunteer.*coach") ~ "Assistant Coach",

      # Lead Assistant Coach
      str_detect(title_lower, "lead assistant") ~ "Assistant Coach",

      # For coaching positions not matching above, mark as coaching but needs review
      position_type == "coaching" ~ "Other Coaching",

      # Staff positions
      TRUE ~ NA_character_
    )
  ) %>%
  # Remove temporary column
  select(-title_lower)

# Write the standardized data
write_csv(positions_standardized, "ncaa/positions_standardized.csv")

# Generate summary report
summary_report <- positions_standardized %>%
  group_by(canonical_title, position_type) %>%
  summarise(
    count = n(),
    sample_titles = paste(head(unique(title), 3), collapse = " | "),
    .groups = "drop"
  ) %>%
  arrange(desc(count))

write_csv(summary_report, "ncaa/standardization_summary.csv")

# Print summary
cat("\n=== Standardization Summary ===\n")
print(summary_report)

# Check for potential issues
issues <- positions_standardized %>%
  filter(position_type == "coaching" & canonical_title == "Other Coaching") %>%
  count(title, sort = TRUE)

if (nrow(issues) > 0) {
  cat("\n=== Coaching positions needing review ===\n")
  print(issues)
  write_csv(issues, "ncaa/positions_needing_review.csv")
}
```

## Usage (R)
```bash
# Run the standardization
Rscript scripts/standardize_positions.R

# Output files:
# - ncaa/positions_standardized.csv (main output)
# - ncaa/standardization_summary.csv (summary statistics)
# - ncaa/positions_needing_review.csv (titles that need manual review)
```

---

# Implementation Option 2: Python with pandas

## File: `scripts/standardize_positions.py`

```python
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
    summary = df.groupby(['canonical_title', 'position_type']).agg(
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
        issues.to_csv(issues_file, header=['count'])
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
```

## Usage (Python)
```bash
# Run the standardization
python scripts/standardize_positions.py

# Output files:
# - ncaa/positions_standardized.csv (main output)
# - ncaa/positions_summary.csv (summary statistics)
# - ncaa/positions_needing_review.csv (titles that need manual review)
```

---

## Edge Cases and Considerations

### 1. Graduate Assistants
**Issue**: Contains "assistant" but are typically not coaching positions according to NCAA definitions.
**Solution**: Explicitly exclude "graduate assistant" from canonical "Assistant Coach" category. These will be classified as staff.

### 2. Strength & Conditioning Coaches
**Issue**: Contains "coach" but may not be considered coaching staff in the basketball context.
**Current approach**: Classified as "coaching" with canonical title "Other Coaching"
**Recommendation**: Decide if these should be:
- Option A: Reclassified as "staff"
- Option B: Keep as coaching with canonical title
- Option C: Create a separate category

### 3. Player Development Coaches
**Issue**: Similar to strength & conditioning - contains "coach" but unclear if it's a canonical coaching position.
**Current approach**: Classified as "Other Coaching"

### 4. Special Cases
- **AAU Coach**: External position, classified as coaching but marked "Other Coaching"
- **Coach** (just "Coach"): 77 records - needs clarification on what these are
- **Titles with multiple roles**: "Assistant Coach/Recruiting Coordinator" - we take the primary role (Assistant Coach)

### 5. High School Positions
Many records include high school coaching positions. These will be standardized the same way as college positions.

---

## Validation Steps

After running either script:

1. **Check the summary report**
   - Verify counts make sense
   - Review sample titles for each canonical category

2. **Review "Other Coaching" positions**
   - Examine `positions_needing_review.csv`
   - Decide if any should be reclassified as staff or added to canonical categories

3. **Spot check specific coaches**
   - Verify that career progressions make sense
   - Example: A coach moving from Assistant → Associate Head → Head should show proper canonical titles

4. **Data quality checks**
   ```r
   # R
   positions_standardized %>%
     filter(position_type == "coaching" & is.na(canonical_title)) %>%
     count(title)
   ```

   ```python
   # Python
   df[(df['position_type'] == 'coaching') & (df['canonical_title'].isna())]['title'].value_counts()
   ```

---

## Recommendations

1. **Run the Python version first** - it provides more detailed output and is easier to iterate on
2. **Review the "Other Coaching" category** - decide if positions like "Strength and Conditioning Coach" should be reclassified
3. **Consider adding a "coaching_role_primary" field** - to distinguish between primary coaching roles vs. support roles
4. **Create a mapping table** - for future reference, export a CSV showing original_title → canonical_title mappings

## Next Steps

1. Choose implementation (R or Python)
2. Create the `scripts/` directory if it doesn't exist
3. Run the standardization script
4. Review output files
5. Make any necessary adjustments to the logic
6. Re-run if needed
7. Document any manual decisions made
8. Commit the standardized data and scripts to git

---

## Output Files Summary

Both implementations produce:
- **positions_standardized.csv**: Original data + `position_type` + `canonical_title` columns
- **standardization_summary.csv**: Summary statistics by canonical title
- **positions_needing_review.csv**: Coaching positions that don't fit canonical categories (if any)
