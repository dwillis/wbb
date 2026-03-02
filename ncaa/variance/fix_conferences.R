#!/usr/bin/env Rscript
# Update teams.csv conference assignments for 2025-26 realignment
suppressMessages(library(tidyverse))

csv <- read_csv("data/teams.csv", show_col_types = FALSE)

# Conference moves effective 2024-25 season
moves <- tribble(
  ~team,                   ~new_conference,
  # Pac-12 to Big Ten
  "UCLA",                  "Big Ten",
  "Southern Cal",          "Big Ten",
  "Oregon",                "Big Ten",
  "Washington",            "Big Ten",
  # Pac-12 to Big 12
  "Arizona",               "Big 12",
  "Arizona State",         "Big 12",
  "Colorado",              "Big 12",
  "Utah",                  "Big 12",
  # Pac-12 to ACC
  "Stanford",              "ACC",
  "California",            "ACC",
  "Southern Methodist",    "ACC",
  # Big 12 to SEC
  "Texas",                 "SEC",
  "Oklahoma",              "SEC",
  # AAC to Big 12
  "Cincinnati",            "Big 12",
  "Houston",               "Big 12",
  "Central Florida",       "Big 12",
  "Brigham Young",         "Big 12"
)

# Show what will change
csv_d1 <- csv %>% filter(division == "I")
changes <- csv_d1 %>%
  inner_join(moves, by = "team") %>%
  filter(conference != new_conference) %>%
  select(team, old = conference, new = new_conference)

cat("Conference changes to apply:\n")
print(changes, n = 30)

# Apply changes
csv_updated <- csv %>%
  left_join(moves, by = "team") %>%
  mutate(conference = coalesce(new_conference, conference)) %>%
  select(-new_conference)

# Verify
cat("\nVerification - moved teams:\n")
csv_updated %>%
  filter(team %in% moves$team) %>%
  select(team, conference) %>%
  print(n = 20)

# Check what's still in Pac-12
cat("\nPac-12 teams remaining:\n")
csv_updated %>%
  filter(conference == "Pac-12", division == "I") %>%
  select(team) %>%
  print(n = 20)

# Write
write_csv(csv_updated, "data/teams.csv")
cat("\nWrote updated data/teams.csv\n")
