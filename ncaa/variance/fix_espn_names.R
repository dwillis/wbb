#!/usr/bin/env Rscript
# Temporary script to add espn_name column to data/teams.csv
suppressMessages(library(tidyverse))

espn <- read_csv("/tmp/espn_teams.csv", show_col_types = FALSE)
csv_raw <- read_csv("data/teams.csv", show_col_types = FALSE)
csv_d1 <- csv_raw %>% filter(trimws(division) == "I")

norm <- function(x) {
  x <- iconv(x, from = "UTF-8", to = "ASCII//TRANSLIT")
  tolower(gsub("[^a-z0-9]", "", tolower(x)))
}

# Map csv_name -> espn_name for teams that don't normalize-match
# csv_name must match EXACTLY what's in teams.csv "team" column
corrections <- tribble(
  ~csv_name,                              ~espn_name,
  # --- Original corrections (verified CSV names) ---
  "Abilene Christian",                    "Abilene Chrstn",
  "Alabama State",                        "Alabama St",
  "Alcorn State",                         "Alcorn St",
  "Appalachian State",                    "App State",
  "Arizona State",                        "Arizona St",
  "Arkansas State",                       "Arkansas St",
  "Arkansas-Pine Bluff",                  "AR-Pine Bluff",
  "Boise State",                          "Boise St",
  "Cal State Bakersfield",                "Bakersfield",
  "Cal State Fullerton",                  "Fullerton",
  "Central Arkansas",                     "C Arkansas",
  "Central Connecticut",                  "C Connecticut",
  "Central Michigan",                     "C Michigan",
  "California Baptist",                   "CA Baptist",
  "Charleston Southern",                  "Charleston So",
  "College of Charleston",                "Charleston",
  "Chicago State",                        "Chicago St",
  "Cleveland State",                      "Cleveland St",
  "Coastal Carolina",                     "Coastal",
  "Colorado State",                       "Colorado St",
  "Coppin State",                         "Coppin St",
  "Delaware State",                       "Delaware St",
  "Eastern Illinois",                     "E Illinois",
  "Eastern Kentucky",                     "E Kentucky",
  "Eastern Michigan",                     "E Michigan",
  "Eastern Washington",                   "E Washington",
  "Fairleigh Dickinson",                  "FDU",
  "Florida State",                        "Florida St",
  "Fresno State",                         "Fresno St",
  "George Washington",                    "G Washington",
  "Georgia Southern",                     "GA Southern",
  "Georgia State",                        "Georgia St",
  "Houston Christian",                    "Hou Christian",
  "Illinois State",                       "Illinois St",
  "Indiana State",                        "Indiana St",
  "Jackson State",                        "Jackson St",
  "Kansas State",                         "Kansas St",
  "Kennesaw State",                       "Kennesaw St",
  "Long Beach State",                     "Long Beach St",
  "Loyola-Chicago",                       "Loyola Chicago",
  "Michigan State",                       "Michigan St",
  "Mississippi",                          "Ole Miss",
  "Mississippi State",                    "Mississippi St",
  "Mississippi Valley State",             "Miss Valley St",
  "Missouri State",                       "Missouri St",
  "Montana State",                        "Montana St",
  "Morehead State",                       "Morehead St",
  "Morgan State",                         "Morgan St",
  "Murray State",                         "Murray St",
  "Nicholls State",                       "Nicholls",
  "Norfolk State",                        "Norfolk St",
  "North Dakota State",                   "N Dakota St",
  "Northern Arizona",                     "N Arizona",
  "Northern Colorado",                    "N Colorado",
  "Northern Illinois",                    "N Illinois",
  "Northern Kentucky",                    "N Kentucky",
  "Northwestern State",                   "N'Western St",
  "New Mexico State",                     "New Mexico St",
  "Oklahoma State",                       "Oklahoma St",
  "Oregon State",                         "Oregon St",
  "Portland State",                       "Portland St",
  "Prairie View A&M",                     "Prairie View",
  "Sacramento State",                     "Sacramento St",
  "Sam Houston State",                    "Sam Houston",
  "San Diego State",                      "San Diego St",
  "USC Upstate",                          "SC Upstate",
  "South Dakota State",                   "S Dakota St",
  "SIU Edwardsville",                     "SIU Edwardsville",
  "Southeastern Louisiana",              "SE Louisiana",
  "Stephen F. Austin",                    "SF Austin",
  "St. Bonaventure",                      "St. Bonaventure",
  "St. Peter's",                          "Saint Peter's",
  "St. Thomas",                           "St. Thomas",
  "Tarleton State",                       "Tarleton St",
  "Texas-Arlington",                      "UT Arlington",
  "Weber State",                          "Weber St",
  "Western Carolina",                     "W Carolina",
  "Western Illinois",                     "W Illinois",
  "Western Michigan",                     "W Michigan",
  "Wichita State",                        "Wichita St",
  "Youngstown State",                     "Youngstown St",
  # --- New corrections for the 54 unmatched ---
  "A&M-Corpus Christi",                   "Texas A&M-CC",
  "Arkansas-Little Rock",                 "Little Rock",
  "Boston",                               "Boston U",
  "Brigham Young",                        "BYU",
  "CSUN",                                 "CSU Northridge",
  "Central Florida",                      "UCF",
  "East Tennessee State",                 "ETSU",
  "Florida Atlantic",                     "FAU",
  "Florida Gulf Coast",                   "FGCU",
  "Illinois-Chicago",                     "UIC",
  "Jacksonville St.",                     "Jax State",
  "Lindenwood (MO)",                      "Lindenwood",
  "Louisiana Monroe",                     "UL Monroe",
  "Loyola Marymount",                     "LMU",
  "Loyola-Maryland",                      "Loyola MD",
  "Maryland-Eastern Shore",               "MD Eastern",
  "Massachusetts",                        "UMass",
  "McNeese State",                        "McNeese",
  "Miami Ohio",                           "Miami OH",
  "Middle Tennessee",                     "MTSU",
  "New Jersey Institute of Technology",   "NJIT",
  "North Carolina Central",              "NC Central",
  "Pennsylvania",                         "Penn",
  "Pittsburgh",                           "Pitt",
  "Presbyterian College",                 "Presbyterian",
  "Purdue-Fort Wayne",                    "Purdue FW",
  "Queens (NC)",                          "Queens",
  "Saint Francis (PA)",                   "Saint Francis",
  "Saint Joseph's (PA)",                  "Saint Joseph's",
  "Saint Mary's (CA)",                    "Saint Mary's",
  "San Jose State",                       "San José St",
  "Seattle",                              "Seattle U",
  "South Carolina St.",                   "SC State",
  "Southeast Missouri State",            "SE Missouri",
  "Southern Cal",                         "USC",
  "Southern Ill.",                        "S Illinois",
  "Southern Ind.",                        "So Indiana",
  "Southern Methodist",                   "SMU",
  "St. Francis College Brooklyn",         "St Joseph BKN",
  "Tex. A&M-Commerce",                   "E Texas A&M",
  "Texas Christian",                      "TCU",
  "Texas State",                          "Texas St",
  "Texas-El Paso",                        "UTEP",
  "UC Santa Barbara",                     "Santa Barbara",
  "UNCW",                                 "UNC Wilmington",
  "UT-Rio Grande Valley",                 "UT Rio Grande",
  "UT-San Antonio",                       "UTSA",
  "Utah St.",                             "Utah State",
  "Virginia Commonwealth",               "VCU",
  "Washington State",                     "Washington St",
  # --- Schools that might not be in ESPN D-I currently ---
  "Hartford",                             "Hartford",
  "IUPUI",                                "IUPUI",
  "Bethune-Cookman",                      "Bethune",
  "Albany",                               "UAlbany",
  "N.C. A&T",                             "NC A&T",
  "N.C. Central",                         "NC Central",
  "N.C. State",                           "NC State",
  "St. John's",                           "St John's"
)

# Apply corrections and build espn_name column
csv_d1_with_espn <- csv_d1 %>%
  left_join(corrections, by = c("team" = "csv_name")) %>%
  mutate(espn_name = coalesce(espn_name, team))

# Verify
espn_keyed <- espn %>% mutate(ekey = norm(team_short_display_name))
csv_check <- csv_d1_with_espn %>% mutate(ekey = norm(espn_name))

matched <- csv_check %>% semi_join(espn_keyed, by = "ekey")
unmatched <- csv_check %>% anti_join(espn_keyed, by = "ekey")

cat("D-I teams:", nrow(csv_d1), "\n")
cat("Matched:", nrow(matched), "\n")
cat("Still unmatched:", nrow(unmatched), "\n")
if (nrow(unmatched) > 0) {
  cat("\nUnmatched teams:\n")
  unmatched %>%
    select(team, espn_name) %>%
    arrange(team) %>%
    print(n = 200)
}

# Also check: which of the 24 originally-NA teams are now matched?
problem_ids <- c(127, 232, 197, 2815, 2198, 325, 68, 2571, 36, 21,
                 2449, 2458, 9, 290, 2628, 193, 161, 2617, 93, 147,
                 204, 2710, 2032, 2377)
problem_espn <- espn %>% filter(team_id %in% problem_ids)
problem_matched <- problem_espn %>%
  mutate(ekey = norm(team_short_display_name)) %>%
  semi_join(csv_check %>% select(ekey), by = "ekey")
cat("\nOf the 24 originally-NA teams, now matched:", nrow(problem_matched), "/24\n")
problem_still <- problem_espn %>%
  mutate(ekey = norm(team_short_display_name)) %>%
  anti_join(csv_check %>% select(ekey), by = "ekey")
if (nrow(problem_still) > 0) {
  cat("Still missing:\n")
  print(problem_still)
}

# --- Write updated teams.csv with espn_name column ---
# For D-I teams, use the corrected espn_name; for non-D-I, leave espn_name = team
csv_updated <- csv_raw %>%
  left_join(
    csv_d1_with_espn %>% select(team, espn_name),
    by = "team"
  ) %>%
  mutate(espn_name = coalesce(espn_name, team))

# Write with the same column order, adding espn_name after team
csv_final <- csv_updated %>%
  select(team, espn_name, everything())

write_csv(csv_final, "data/teams.csv")
cat("\nWrote data/teams.csv with espn_name column (", nrow(csv_final), "rows)\n")
cat("Sample D-I entries:\n")
csv_final %>%
  filter(trimws(division) == "I") %>%
  filter(team != espn_name) %>%
  select(team, espn_name) %>%
  head(10) %>%
  print()
