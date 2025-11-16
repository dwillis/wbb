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

      # Staff positions - empty string for null
      TRUE ~ ""
    ),

    # Convert empty strings to NA for cleaner CSV output
    canonical_title = if_else(canonical_title == "", NA_character_, canonical_title)
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
print(summary_report, n = Inf)

# Check for potential issues
issues <- positions_standardized %>%
  filter(position_type == "coaching" & canonical_title == "Other Coaching") %>%
  count(title, sort = TRUE)

if (nrow(issues) > 0) {
  cat("\n=== Coaching positions needing review ===\n")
  cat(sprintf("Total unique titles: %d\n", nrow(issues)))
  cat(sprintf("Total records: %d\n\n", sum(issues$n)))
  print(issues, n = 20)
  write_csv(issues, "ncaa/positions_needing_review.csv")
}

# Distribution summary
cat("\n=== Position Type Distribution ===\n")
position_counts <- positions_standardized %>%
  count(position_type, sort = TRUE)
print(position_counts)

cat("\n=== Canonical Title Distribution ===\n")
canonical_counts <- positions_standardized %>%
  count(canonical_title, sort = TRUE)
print(canonical_counts, n = Inf)

cat("\n✓ Standardization complete!\n")
cat(sprintf("Output written to: ncaa/positions_standardized.csv\n"))
cat(sprintf("Summary written to: ncaa/standardization_summary.csv\n"))
if (nrow(issues) > 0) {
  cat(sprintf("Review needed: ncaa/positions_needing_review.csv\n"))
}
