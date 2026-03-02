# ============================================================================
# Win Variance Analysis: NCAA WBB 2025-26 (v4)
#
# How do teams win in different ways?
#
# Three metrics (all closeness-weighted: w = 1 / (1 + margin / CLOSENESS_SCALE)):
#
#   1. Win Profile Clustering
#      - k-means on standardized 9D feature space → N_ARCHETYPES archetypes
#      - Per-team weighted Shannon entropy of archetype distribution
#        High entropy = wins spread across many distinct game types
#        Low entropy  = specialist, wins predominantly one way
#
#   2. Bimodality Testing (per team)
#      - PCA on each team's wins (offense 5D → PC1, defense 4D → PC1)
#      - Bimodality coefficient (BC) on PC1: BC > 0.555 → bimodal tendency
#      - GMM: compare BIC for G=1 vs G=2 components; BIC_diff > 0 → two modes
#      - Bimodal teams have TWO distinct winning patterns, not just high noise
#
#   3. Weighted CV profiles by strategic dimension
#      - Same 6 groups as v3 (Shooting, Ball Care, Rebounding, etc.)
#      - Reliability-weighted CV using closeness_weight
#
# Key changes from v3:
#   - MIN_WINS raised from 10 → 20 (more stable clustering + bimodality)
#   - Closeness weighting throughout: close wins reveal strategy, blowouts add
#     garbage-time noise
#   - Mahalanobis dispersion removed — it couldn't distinguish genuine
#     flexibility from schedule heterogeneity or performance inconsistency
#   - Entropy + bimodality replace it: entropy asks "how many modes?",
#     bimodality asks "are there exactly two distinct patterns?"
#   - A combined versatility score merges both signals
#
# Remaining limitation: schedule variance still inflates entropy/bimodality
# for teams that play both elite and weak opponents. A full fix would use
# opponent-adjusted residuals as features. This is a v5 problem.
#
# Packages required: wehoop, tidyverse, ggrepel, mclust
# ============================================================================

library(wehoop)
library(tidyverse)
library(ggrepel)
library(mclust)      # GMM bimodality test

# ---- CONFIG ----------------------------------------------------------------

SEASON          <- 2026
MIN_WINS        <- 20        # raised from 10 for stable estimates
CLOSENESS_SCALE <- 10        # w = 1/(1 + margin/10): 10-pt win → w=0.5
N_ARCHETYPES    <- 5         # k-means clusters; silhouette check below
CACHE_FILE      <- "data/wbb_team_box_2026.rds"

# Feature vectors
OFF_FEATURES <- c("efg_pct", "tov_pct", "orb_pct", "ft_rate", "three_par")
DEF_FEATURES <- c("opp_efg_pct", "opp_tov_pct", "drb_pct", "opp_ft_rate")
ALL_FEATURES <- c(OFF_FEATURES, DEF_FEATURES)

# CV stat groups
CV_GROUPS <- list(
  Shooting    = c("efg_pct", "three_par"),
  Ball_Care   = c("tov_pct", "ast_rate"),
  Rebounding  = c("orb_pct", "drb_pct"),
  Free_Throws = c("ft_attempt_rate", "ft_accuracy"),
  Scoring_Mix = c("paint_share", "fastbreak_share"),
  Def_Quality = c("opp_efg_pct", "opp_tov_pct", "opp_ft_rate")
)

# Conference tier definitions
POWER_CONFERENCES <- c("SEC", "Big Ten", "Big 12", "ACC")
HIGH_MAJOR        <- c("Big East", "AAC", "WCC", "Mountain West", "Atlantic 10")

TIER_COLORS <- c(
  "Power 4"       = "#6b21a8",
  "High Major"    = "#2563eb",
  "Mid/Low Major" = "#9ca3af",
  "All"           = "#6b21a8"
)


# ============================================================================
# STEP 0a: PULL GAME DATA
# ============================================================================

if (file.exists(CACHE_FILE)) {
  team_box <- readRDS(CACHE_FILE)
  message("Loaded cached data: ", nrow(team_box), " rows")
} else {
  dir.create("data", showWarnings = FALSE)
  team_box <- load_wbb_team_box(seasons = SEASON)
  saveRDS(team_box, CACHE_FILE)
  message("Pulled and cached: ", nrow(team_box), " rows")
}


# ============================================================================
# STEP 0b: CONFERENCE LOOKUP FROM LOCAL CSV
# ============================================================================

TEAMS_CSV <- "data/teams.csv"

NAME_CORRECTIONS <- tribble(
  ~csv_name,                      ~espn_name,
  "Abilene Christian",            "Abilene Christian",
  "Arkansas St.",                 "Arkansas State",
  "Colorado St.",                 "Colorado State",
  "Fla. Gulf Coast",              "Florida Gulf Coast",
  "LIU",                          "LIU",
  "Loyola-Chicago",               "Loyola Chicago",
  "Mississippi",                  "Ole Miss",
  "Montana St.",                  "Montana State",
  "MTSU",                         "Middle Tennessee",
  "N.C. State",                   "NC State",
  "Nicholls St.",                 "Nicholls",
  "Northwestern St.",             "Northwestern State",
  "Penn",                         "Pennsylvania",
  "Purdue Fort Wayne",            "Purdue Fort Wayne",
  "SIU Edwardsville",             "SIU Edwardsville",
  "Southeastern La.",             "Southeastern Louisiana",
  "Southern Miss",                "Southern Miss",
  "St. Bonaventure",              "St. Bonaventure",
  "St. Francis (PA)",             "Saint Francis",
  "St. John's",                   "St. John's",
  "St. Mary's",                   "Saint Mary's",
  "St. Peter's",                  "Saint Peter's",
  "TCU",                          "TCU",
  "Tex. A&M-Corpus Christi",      "Texas A&M-Corpus Christi",
  "Texas A&M-C. Christi",         "Texas A&M-Corpus Christi",
  "UMKC",                         "Kansas City",
  "VCU",                          "VCU",
  "Western Ky.",                  "Western Kentucky"
)

normalize_name <- function(x) {
  x %>% tolower() %>% gsub("[^a-z0-9]", "", .)
}

message("Loading conference data from ", TEAMS_CSV, "...")
csv_teams <- read_csv(TEAMS_CSV, show_col_types = FALSE) %>%
  filter(division == "I") %>%
  select(csv_name = team, conference_short_name = conference) %>%
  left_join(NAME_CORRECTIONS, by = "csv_name") %>%
  mutate(
    join_name = if_else(!is.na(espn_name), espn_name, csv_name),
    join_key  = normalize_name(join_name)
  ) %>%
  select(join_key, conference_short_name)

message("  ", nrow(csv_teams), " D1 teams loaded from CSV")

espn_teams <- team_box %>%
  distinct(team_id, team_short_display_name) %>%
  mutate(join_key = normalize_name(team_short_display_name))

teams_info <- espn_teams %>%
  left_join(csv_teams, by = "join_key") %>%
  filter(!is.na(conference_short_name)) %>%
  select(team_id, conference_short_name) %>%
  distinct(team_id, .keep_all = TRUE)

unmatched <- espn_teams %>%
  anti_join(csv_teams, by = "join_key") %>%
  arrange(team_short_display_name)

if (nrow(unmatched) > 0) {
  message("\n  Teams with no conference match (", nrow(unmatched), "):")
  walk(unmatched$team_short_display_name, ~ message("    ", .x))
}

message("\nConference lookup matched ", nrow(teams_info), " teams")

has_conferences <- nrow(teams_info) > 0
if (has_conferences) {
  teams_info <- teams_info %>%
    mutate(
      conf_tier = case_when(
        conference_short_name %in% POWER_CONFERENCES ~ "Power 4",
        conference_short_name %in% HIGH_MAJOR        ~ "High Major",
        TRUE                                          ~ "Mid/Low Major"
      ),
      conf_tier = factor(conf_tier, levels = c("Power 4", "High Major", "Mid/Low Major"))
    )
} else {
  message("No conference data — continuing without it")
}


# ============================================================================
# STEP 0c: BUILD OPPONENT JOIN
# ============================================================================

opp_stats <- team_box %>%
  select(
    game_id,
    team_id,
    opp_fgm   = field_goals_made,
    opp_fga   = field_goals_attempted,
    opp_3pm   = three_point_field_goals_made,
    opp_3pa   = three_point_field_goals_attempted,
    opp_ftm   = free_throws_made,
    opp_fta   = free_throws_attempted,
    opp_orb   = offensive_rebounds,
    opp_drb   = defensive_rebounds,
    opp_to    = turnovers,
    opp_score = team_score
  )

wins_with_opp <- team_box %>%
  filter(team_winner == TRUE) %>%
  inner_join(opp_stats, by = "game_id", suffix = c("", "_opp")) %>%
  filter(team_id != team_id_opp)

message("\nTotal winning game-rows after opponent join: ", nrow(wins_with_opp))


# ============================================================================
# STEP 0d: COMPUTE FEATURES + CLOSENESS WEIGHT
#
# Closeness weight: w = 1 / (1 + margin / CLOSENESS_SCALE)
#   - A 1-point win  → w ≈ 0.91
#   - A 10-point win → w = 0.50
#   - A 30-point win → w = 0.25
#   - A 50-point win → w = 0.17
# Blowouts are dominated by garbage time and opponent-driven noise; close
# wins better reveal a team's strategic choices under pressure.
# ============================================================================

win_features <- wins_with_opp %>%
  mutate(
    # === WBB FIVE FACTORS (OFFENSIVE) ===
    efg_pct   = (field_goals_made + 0.5 * three_point_field_goals_made) /
                 field_goals_attempted,
    tov_pct   = turnovers /
                (field_goals_attempted + 0.44 * free_throws_attempted + turnovers),
    orb_pct   = offensive_rebounds / (offensive_rebounds + opp_drb),
    ft_rate   = free_throws_made / field_goals_attempted,
    three_par = three_point_field_goals_attempted / field_goals_attempted,

    # === DEFENSIVE FACTORS ===
    opp_efg_pct = (opp_fgm + 0.5 * opp_3pm) / opp_fga,
    opp_tov_pct = opp_to / (opp_fga + 0.44 * opp_fta + opp_to),
    drb_pct     = defensive_rebounds / (defensive_rebounds + opp_orb),
    opp_ft_rate = opp_ftm / opp_fga,

    # === SCORING SOURCE SHARES ===
    paint_pts       = suppressWarnings(as.numeric(points_in_paint)),
    fastbreak_pts   = suppressWarnings(as.numeric(fast_break_points)),
    paint_share     = paint_pts / team_score,
    fastbreak_share = fastbreak_pts / team_score,

    # === ASSIST RATE ===
    ast_rate = assists / field_goals_made,

    # === FREE THROW COMPONENTS ===
    ft_attempt_rate = free_throws_attempted / field_goals_attempted,
    ft_accuracy     = ifelse(free_throws_attempted > 0,
                             free_throws_made / free_throws_attempted,
                             NA_real_),

    # === CLOSENESS WEIGHT ===
    margin           = team_score - opp_score,
    closeness_weight = 1 / (1 + margin / CLOSENESS_SCALE)
  ) %>%
  filter(
    field_goals_attempted > 0,
    is.finite(efg_pct), is.finite(tov_pct),
    is.finite(orb_pct), is.finite(ft_rate),
    is.finite(three_par),
    opp_fga > 0,
    is.finite(opp_efg_pct), is.finite(opp_tov_pct),
    is.finite(drb_pct), is.finite(opp_ft_rate)
  )

message("Games with valid features: ", nrow(win_features))
message("Closeness weight — mean: ", round(mean(win_features$closeness_weight), 3),
        "  median: ", round(median(win_features$closeness_weight), 3))


# ============================================================================
# STEP 0e: FILTER TO ELIGIBLE TEAMS
# ============================================================================

team_wins <- win_features %>%
  count(team_id, team_short_display_name, name = "n_wins") %>%
  filter(n_wins >= MIN_WINS)

message("Eligible teams (>=", MIN_WINS, " wins): ", nrow(team_wins))

wf_eligible <- win_features %>%
  filter(team_id %in% team_wins$team_id)


# ============================================================================
# METRIC 1: WIN PROFILE CLUSTERING
#
# We cluster all winning games into N_ARCHETYPES prototypical game types using
# k-means on standardized 9D feature space (offense + defense together).
#
# Then, for each team, we compute the WEIGHTED SHANNON ENTROPY of their
# distribution across archetypes — using closeness_weight so close wins
# count more than blowouts.
#
#   H = -Σ w_k * log(w_k)    where w_k = weighted share in archetype k
#   H_norm = H / log(N_ARCHETYPES)    ranges 0 (specialist) to 1 (even spread)
#
# Design choices:
#   - Clustering is done league-wide on all games (unweighted) to find the
#     archetypes that actually exist in the data
#   - Per-team distribution IS weighted by closeness (entropy computed on
#     the weighted archetype shares)
#   - k chosen by silhouette, but N_ARCHETYPES config overrides the default
# ============================================================================

# --- Standardize features ---
feature_means <- wf_eligible %>% select(all_of(ALL_FEATURES)) %>% colMeans()
feature_sds   <- wf_eligible %>% select(all_of(ALL_FEATURES)) %>% summarise(across(everything(), sd)) %>% unlist()

wf_scaled_mat <- wf_eligible %>%
  select(all_of(ALL_FEATURES)) %>%
  scale(center = feature_means, scale = feature_sds) %>%
  as.matrix()

# --- Silhouette check: k = 3..8 (subsample for speed) ---
message("\nChecking silhouette scores for k = 3..8 (subsampled)...")
set.seed(42)
sil_sample_idx <- sample(nrow(wf_scaled_mat), min(2000, nrow(wf_scaled_mat)))
sil_sample     <- wf_scaled_mat[sil_sample_idx, ]

sil_scores <- sapply(3:8, function(k) {
  km_s <- kmeans(wf_scaled_mat, centers = k, nstart = 10, iter.max = 100)
  ss   <- cluster::silhouette(km_s$cluster[sil_sample_idx],
                               dist(sil_sample))
  mean(ss[, "sil_width"])
})
names(sil_scores) <- 3:8

message("Silhouette: ", paste(names(sil_scores), round(sil_scores, 3), sep = "=", collapse = "  "))
message("Silhouette-optimal k = ", names(which.max(sil_scores)),
        "  (using N_ARCHETYPES = ", N_ARCHETYPES, " as configured)")

# --- Final clustering ---
set.seed(42)
km <- kmeans(wf_scaled_mat, centers = N_ARCHETYPES, nstart = 50, iter.max = 200)
wf_eligible <- wf_eligible %>% mutate(archetype = km$cluster)

message("Archetype sizes: ",
        paste(paste0("A", 1:N_ARCHETYPES), tabulate(wf_eligible$archetype), sep = "=", collapse = "  "))

# --- Name and describe each archetype ---
#
# Short label (for plot axes): primary distinguishing feature
# Description (printed to console): top 3 features with z-scores and
#   a plain-language basketball interpretation of what this game type means.
#
# Feature direction guide:
#   efg_pct HIGH     = shooting efficiently from the field
#   tov_pct LOW      = protecting the ball; HIGH = sloppy
#   orb_pct HIGH     = dominating the offensive glass
#   ft_rate HIGH     = getting to the line frequently
#   three_par HIGH   = shot selection skewed to the arc
#   opp_efg_pct LOW  = holding opponents to tough shots
#   opp_tov_pct HIGH = generating turnovers / pressure defense
#   drb_pct HIGH     = cleaning the defensive glass
#   opp_ft_rate LOW  = staying out of foul trouble

FEATURE_NICE <- c(
  efg_pct     = "eFG%",
  tov_pct     = "TOV%",
  orb_pct     = "ORB%",
  ft_rate     = "FT Rate",
  three_par   = "3PA Rate",
  opp_efg_pct = "Opp eFG%",
  opp_tov_pct = "Opp TOV%",
  drb_pct     = "DRB%",
  opp_ft_rate = "Opp FT Rate"
)

# Basketball interpretation for each (feature, direction) pair
FEATURE_MEANING <- c(
  efg_pct_high     = "shooting efficiently",
  efg_pct_low      = "struggling to shoot",
  tov_pct_high     = "turning the ball over",
  tov_pct_low      = "protecting the ball",
  orb_pct_high     = "dominating the offensive glass",
  orb_pct_low      = "few second chances",
  ft_rate_high     = "getting to the line",
  ft_rate_low      = "jump-shot reliant",
  three_par_high   = "perimeter-heavy shot diet",
  three_par_low    = "interior-focused offense",
  opp_efg_pct_high = "allowing easy shots",
  opp_efg_pct_low  = "generating tough shots",
  opp_tov_pct_high = "forcing turnovers / pressure D",
  opp_tov_pct_low  = "passive, non-gambling defense",
  drb_pct_high     = "locking down the defensive glass",
  drb_pct_low      = "vulnerable to offensive rebounds",
  opp_ft_rate_high = "fouling frequently",
  opp_ft_rate_low  = "disciplined, foul-avoiding defense"
)

arch_detail <- as.data.frame(km$centers) %>%
  mutate(archetype = row_number()) %>%
  pivot_longer(-archetype, names_to = "feature", values_to = "z") %>%
  group_by(archetype) %>%
  arrange(desc(abs(z)), .by_group = TRUE) %>%
  mutate(rank = row_number()) %>%
  ungroup() %>%
  mutate(
    direction  = if_else(z > 0, "high", "low"),
    meaning    = FEATURE_MEANING[paste0(feature, "_", direction)],
    feat_label = paste0(if_else(z > 0, "\u25b2", "\u25bc"), " ",
                        FEATURE_NICE[feature],
                        " (z=", sprintf("%+.2f", z), ")")
  )

# Short label from top feature (used in plot facets / heatmap y-axis)
arch_names <- arch_detail %>%
  filter(rank == 1) %>%
  mutate(
    sign_str   = if_else(z > 0, "High", "Low"),
    arch_label = paste0("A", archetype, ": ",
                        sign_str, " ", FEATURE_NICE[feature])
  ) %>%
  select(archetype, arch_label)

# Full description from top 3 features (printed to console)
arch_descriptions <- arch_detail %>%
  filter(rank <= 3) %>%
  group_by(archetype) %>%
  summarise(
    features_str = paste(feat_label, collapse = "  |  "),
    meaning_str  = paste(meaning,    collapse = "; "),
    .groups = "drop"
  ) %>%
  left_join(arch_names, by = "archetype")

message("\n=== ARCHETYPE DESCRIPTIONS ===")
for (i in seq_len(nrow(arch_descriptions))) {
  message("\n  ", arch_descriptions$arch_label[i])
  message("  Features : ", arch_descriptions$features_str[i])
  message("  In plain language: wins featuring teams ", arch_descriptions$meaning_str[i])
}

# --- Per-team weighted entropy ---
weighted_entropy <- function(archetypes, weights) {
  weights <- weights / sum(weights)
  wp <- tapply(weights, archetypes, sum)
  wp <- wp[wp > 0]
  -sum(wp * log(wp))
}

max_entropy <- log(N_ARCHETYPES)

team_archetypes <- wf_eligible %>%
  group_by(team_id, team_short_display_name) %>%
  summarise(
    n_wins            = n(),
    entropy           = weighted_entropy(archetype, closeness_weight),
    entropy_norm      = entropy / max_entropy,
    primary_archetype = as.integer(names(which.max(table(archetype)))),
    n_archetypes_used = n_distinct(archetype),
    .groups = "drop"
  ) %>%
  # Add weighted share in each archetype
  left_join(
    wf_eligible %>%
      group_by(team_id) %>%
      mutate(total_w = sum(closeness_weight)) %>%
      group_by(team_id, archetype) %>%
      summarise(arch_share = sum(closeness_weight) / first(total_w),
                .groups = "drop") %>%
      pivot_wider(names_from  = archetype, values_from = arch_share,
                  names_prefix = "arch_share_", values_fill = 0),
    by = "team_id"
  ) %>%
  arrange(desc(entropy_norm))

message("\n=== WIN PROFILE CLUSTERING: TOP 20 (most versatile by entropy) ===")
team_archetypes %>%
  slice_head(n = 20) %>%
  transmute(
    team              = team_short_display_name,
    wins              = n_wins,
    entropy_norm      = round(entropy_norm, 3),
    n_archetypes_used = n_archetypes_used,
    primary           = primary_archetype
  ) %>%
  print(n = 20)

message("\n=== WIN PROFILE CLUSTERING: BOTTOM 10 (specialists) ===")
team_archetypes %>%
  slice_tail(n = 10) %>%
  transmute(
    team         = team_short_display_name,
    wins         = n_wins,
    entropy_norm = round(entropy_norm, 3),
    primary      = primary_archetype
  ) %>%
  print(n = 10)


# ============================================================================
# METRIC 2: BIMODALITY TESTING
#
# High entropy could mean a team is uniformly spread across 5 archetypes,
# OR that they have exactly two distinct winning modes. Bimodality testing
# distinguishes these cases.
#
# Method:
#   1. For each team, PCA on their wins (offense 5D and defense 4D separately)
#   2. Bimodality Coefficient (BC) on PC1 scores:
#      BC = (γ² + 1) / (κ_excess + 3(n-1)²/((n-2)(n-3)))
#      where γ = skewness, κ_excess = excess kurtosis
#      BC > 0.555 → bimodal (uniform distribution BC = 5/9 ≈ 0.555)
#      BC > 0.9   → strong bimodal signal
#   3. GMM BIC comparison: Mclust(G=2)$bic - Mclust(G=1)$bic
#      Positive BIC diff → 2-component model preferred over 1-component
#      (mclust convention: larger BIC = better)
#
# Note: PCA and BC are unweighted here — we're testing the shape of the
# distribution, not a weighted expectation. With n=20-30 wins, power is
# moderate; treat as signal, not a confirmatory test.
# ============================================================================

bimodality_coef <- function(x) {
  x <- x[!is.na(x)]
  n <- length(x)
  if (n < 5) return(NA_real_)
  mu <- mean(x)
  s  <- sd(x)
  if (s < 1e-10) return(NA_real_)
  z  <- (x - mu) / s
  g  <- mean(z^3)          # skewness
  k  <- mean(z^4) - 3      # excess kurtosis
  denom <- k + 3 * (n - 1)^2 / ((n - 2) * (n - 3))
  if (is.nan(denom) || abs(denom) < 1e-10) return(NA_real_)
  (g^2 + 1) / denom
}

gmm_bic_diff <- function(pc1) {
  if (length(pc1) < 5 || any(is.na(pc1)) || sd(pc1) < 1e-10) return(NA_real_)
  m1 <- tryCatch(suppressMessages(Mclust(pc1, G = 1, verbose = FALSE)),
                 error = function(e) NULL)
  m2 <- tryCatch(suppressMessages(Mclust(pc1, G = 2, verbose = FALSE)),
                 error = function(e) NULL)
  if (is.null(m1) || is.null(m2)) return(NA_real_)
  m2$bic - m1$bic   # positive = 2-component preferred (larger BIC = better in mclust)
}

compute_bimodality <- function(df, off_feats, def_feats) {
  n <- nrow(df)
  empty <- tibble(bc_off = NA_real_, bc_def = NA_real_,
                  bic_diff_off = NA_real_, bic_diff_def = NA_real_)
  if (n < 5) return(empty)

  off_mat <- df %>% select(all_of(off_feats)) %>%
    filter(complete.cases(.)) %>% as.matrix()
  def_mat <- df %>% select(all_of(def_feats)) %>%
    filter(complete.cases(.)) %>% as.matrix()

  if (nrow(off_mat) < 5 || nrow(def_mat) < 5) return(empty)

  # Check for zero-variance columns before PCA
  off_ok <- apply(off_mat, 2, sd) > 1e-10
  def_ok <- apply(def_mat, 2, sd) > 1e-10

  pca_off <- tryCatch(prcomp(off_mat[, off_ok, drop = FALSE],
                              center = TRUE, scale. = TRUE),
                      error = function(e) NULL)
  pca_def <- tryCatch(prcomp(def_mat[, def_ok, drop = FALSE],
                              center = TRUE, scale. = TRUE),
                      error = function(e) NULL)

  pc1_off <- if (!is.null(pca_off) && ncol(pca_off$x) >= 1) pca_off$x[, 1] else NULL
  pc1_def <- if (!is.null(pca_def) && ncol(pca_def$x) >= 1) pca_def$x[, 1] else NULL

  tibble(
    bc_off       = if (!is.null(pc1_off)) bimodality_coef(pc1_off) else NA_real_,
    bc_def       = if (!is.null(pc1_def)) bimodality_coef(pc1_def) else NA_real_,
    bic_diff_off = if (!is.null(pc1_off)) gmm_bic_diff(pc1_off)    else NA_real_,
    bic_diff_def = if (!is.null(pc1_def)) gmm_bic_diff(pc1_def)    else NA_real_
  )
}

message("\nComputing bimodality tests (may take ~30s)...")
bimodality_results <- wf_eligible %>%
  group_by(team_id, team_short_display_name) %>%
  group_modify(~ compute_bimodality(.x, OFF_FEATURES, DEF_FEATURES)) %>%
  ungroup() %>%
  mutate(
    bc_composite    = rowMeans(cbind(bc_off, bc_def), na.rm = TRUE),
    is_bimodal_off  = !is.na(bc_off)  & bc_off  > 0.555,
    is_bimodal_def  = !is.na(bc_def)  & bc_def  > 0.555,
    gmm_bimodal_off = !is.na(bic_diff_off) & bic_diff_off > 0,
    gmm_bimodal_def = !is.na(bic_diff_def) & bic_diff_def > 0,
    bimodal_both    = is_bimodal_off & is_bimodal_def
  )

message("\n=== BIMODALITY SUMMARY ===")
message("BC > 0.555 (offense): ", sum(bimodality_results$is_bimodal_off, na.rm = TRUE),
        " teams  |  BC > 0.555 (defense): ", sum(bimodality_results$is_bimodal_def, na.rm = TRUE))
message("GMM 2-component preferred (offense): ",
        sum(bimodality_results$gmm_bimodal_off, na.rm = TRUE),
        "  (defense): ", sum(bimodality_results$gmm_bimodal_def, na.rm = TRUE))
message("Bimodal in both offense & defense: ",
        sum(bimodality_results$bimodal_both, na.rm = TRUE))

message("\n=== MOST BIMODAL TEAMS (by BC composite) ===")
bimodality_results %>%
  filter(!is.na(bc_composite)) %>%
  slice_max(bc_composite, n = 15) %>%
  transmute(
    team         = team_short_display_name,
    bc_off       = round(bc_off, 3),
    bc_def       = round(bc_def, 3),
    bc_composite = round(bc_composite, 3),
    gmm_off      = gmm_bimodal_off,
    gmm_def      = gmm_bimodal_def
  ) %>%
  print(n = 15)


# ============================================================================
# METRIC 3: WEIGHTED CV PROFILES BY STRATEGIC DIMENSION
#
# CV = weighted SD / weighted mean, using closeness_weight as reliability
# weights. The reliability-weight variance estimator avoids the zero-sum
# bias of probability weights.
# ============================================================================

weighted_cv <- function(x, w) {
  keep <- !is.na(x)
  x <- x[keep]; w <- w[keep]
  if (length(x) < 3) return(NA_real_)
  w  <- w / sum(w)
  wm <- sum(w * x)
  if (abs(wm) < 1e-10) return(NA_real_)
  # Reliability-weight variance: Var = Σw(x-μ)² / (1 - Σw²)
  wvar <- sum(w * (x - wm)^2) / (1 - sum(w^2))
  sqrt(max(0, wvar)) / wm
}

all_cv_stats <- unlist(CV_GROUPS, use.names = FALSE)

cv_profiles <- wf_eligible %>%
  group_by(team_id, team_short_display_name) %>%
  summarise(
    n_wins = n(),
    across(
      all_of(all_cv_stats),
      list(
        wmean = ~ weighted.mean(.x, closeness_weight, na.rm = TRUE),
        wcv   = ~ weighted_cv(.x, closeness_weight)
      ),
      .names = "{.col}__{.fn}"
    ),
    .groups = "drop"
  )

cv_composites <- cv_profiles %>%
  select(team_id, team_short_display_name, n_wins) %>%
  bind_cols(
    map_dfc(names(CV_GROUPS), function(grp) {
      cols <- paste0(CV_GROUPS[[grp]], "__wcv")
      cols_available <- intersect(cols, names(cv_profiles))
      if (length(cols_available) == 0) {
        tibble(!!paste0("cv_", grp) := NA_real_)
      } else {
        vals <- cv_profiles %>% select(all_of(cols_available))
        tibble(!!paste0("cv_", grp) := rowMeans(vals, na.rm = TRUE))
      }
    })
  ) %>%
  rowwise() %>%
  mutate(
    cv_composite_core = mean(c_across(c(cv_Shooting, cv_Ball_Care,
                                         cv_Rebounding, cv_Free_Throws,
                                         cv_Def_Quality)), na.rm = TRUE)
  ) %>%
  ungroup() %>%
  arrange(desc(cv_composite_core))


# ============================================================================
# COMBINED ANALYSIS
# ============================================================================

combined <- team_archetypes %>%
  inner_join(bimodality_results %>%
               select(team_id, bc_off, bc_def, bc_composite,
                      bic_diff_off, bic_diff_def,
                      is_bimodal_off, is_bimodal_def, bimodal_both),
             by = "team_id") %>%
  inner_join(cv_composites %>%
               select(team_id, cv_composite_core,
                      cv_Shooting, cv_Ball_Care, cv_Rebounding,
                      cv_Free_Throws, cv_Scoring_Mix, cv_Def_Quality),
             by = "team_id") %>%
  left_join(
    if (has_conferences) teams_info %>% select(team_id, conference_short_name, conf_tier)
    else tibble(team_id = character()),
    by = "team_id"
  )

if (!has_conferences) {
  combined <- combined %>%
    mutate(conference_short_name = NA_character_,
           conf_tier = factor("All", levels = "All"))
}

# Composite versatility score:
#   0.5 * entropy_norm (spread across archetypes)
#   + 0.5 * bc_norm    (min-max normalized bimodal strength within sample)
#
# Why min-max instead of hard threshold clamp:
#   pmax(0, bc - 0.555) / 0.445 collapses almost every team to bc_norm = 0
#   because with n=20-30 wins the BC distribution is compressed in the
#   ~0.30-0.60 range and very few teams actually clear 0.555. Min-max
#   preserves the relative differences between teams, which is what we
#   care about for ranking. The 0.555 threshold is still shown as a
#   reference line in the plot.
bc_range <- range(combined$bc_composite, na.rm = TRUE)
combined <- combined %>%
  mutate(
    bc_norm           = (bc_composite - bc_range[1]) / diff(bc_range),
    versatility_score = 0.5 * entropy_norm + 0.5 * bc_norm
  ) %>%
  arrange(desc(versatility_score))

message("\n=== COMBINED VERSATILITY SCORE: TOP 20 ===")
combined %>%
  slice_head(n = 20) %>%
  transmute(
    team              = team_short_display_name,
    wins              = n_wins,
    entropy_norm      = round(entropy_norm, 3),
    bc_composite      = round(bc_composite, 3),
    versatility_score = round(versatility_score, 3),
    conference        = conference_short_name
  ) %>%
  print(n = 20)

message("\n=== CORRELATIONS ===")
message("Entropy vs BC composite:      ",
        round(cor(combined$entropy_norm, combined$bc_composite, use = "complete"), 3))
message("Entropy vs CV core:           ",
        round(cor(combined$entropy_norm, combined$cv_composite_core, use = "complete"), 3))
message("BC composite vs CV core:      ",
        round(cor(combined$bc_composite, combined$cv_composite_core, use = "complete"), 3))
message("Versatility vs CV core:       ",
        round(cor(combined$versatility_score, combined$cv_composite_core, use = "complete"), 3))


# ============================================================================
# VISUALIZATIONS
# ============================================================================

dir.create("plots", showWarnings = FALSE)

WHITE_THEME <- theme(
  plot.background  = element_rect(fill = "white", color = NA),
  panel.background = element_rect(fill = "white", color = NA)
)

team_conf_label <- function(name, conf) {
  ifelse(is.na(conf), name, paste0(name, " (", conf, ")"))
}


# --- Plot 1: Entropy ranking lollipop ---
# Top 20 most versatile + bottom 20 most specialist

entropy_extremes <- bind_rows(
  combined %>% slice_max(entropy_norm, n = 20) %>% mutate(group = "Most Versatile (Top 20)"),
  combined %>% slice_min(entropy_norm, n = 20) %>% mutate(group = "Most Specialist (Bottom 20)")
) %>%
  distinct(team_id, .keep_all = TRUE) %>%
  mutate(team_label = team_conf_label(team_short_display_name, conference_short_name))

p1 <- entropy_extremes %>%
  ggplot(aes(x = entropy_norm,
             y = reorder(team_label, entropy_norm),
             color = conf_tier)) +
  geom_vline(xintercept = 0.5, linetype = "dashed", color = "grey60", linewidth = 0.4) +
  geom_segment(aes(xend = 0, yend = team_label),
               linewidth = 0.3, alpha = 0.35) +
  geom_point(aes(size = n_wins), alpha = 0.75) +
  scale_color_manual(values = TIER_COLORS, name = "Conference Tier") +
  scale_size_continuous(range = c(1.5, 5), name = "Wins") +
  scale_x_continuous(limits = c(0, 1), labels = scales::percent) +
  facet_wrap(~ group, scales = "free_y", ncol = 1) +
  labs(
    title    = "Win Profile Versatility: Entropy of Archetype Distribution",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 Min ", MIN_WINS,
                      " wins \u00b7 Weighted by game closeness\n",
                      "Entropy normalized 0\u2013100%: 100% = wins spread equally across all ",
                      N_ARCHETYPES, " archetypes"),
    x = "Normalized Entropy (0 = one-way winner, 100% = equally versatile across all archetypes)",
    y = NULL,
    caption = "Dashed line = 50% normalized entropy\nData: ESPN via wehoop"
  ) +
  theme_minimal(base_size = 10) +
  theme(
    plot.title       = element_text(face = "bold"),
    strip.text       = element_text(face = "bold", size = 11),
    WHITE_THEME$plot.background,
    WHITE_THEME$panel.background
  ) +
  WHITE_THEME

ggsave("plots/01_entropy_ranking.png", p1, width = 9, height = 11, dpi = 150)
message("\nSaved: plots/01_entropy_ranking.png")


# --- Plot 2: Archetype centroid heatmap ---
# What does each archetype actually look like?

centroid_long <- as.data.frame(km$centers) %>%
  mutate(archetype = row_number()) %>%
  left_join(arch_names, by = "archetype") %>%
  pivot_longer(all_of(ALL_FEATURES), names_to = "feature", values_to = "z_score") %>%
  mutate(
    feature_label = recode(feature,
      efg_pct     = "eFG% (Off)",
      tov_pct     = "TOV% (Off)",
      orb_pct     = "ORB%",
      ft_rate     = "FT Rate (Off)",
      three_par   = "3PA Rate",
      opp_efg_pct = "Opp eFG%",
      opp_tov_pct = "Opp TOV%",
      drb_pct     = "DRB%",
      opp_ft_rate = "Opp FT Rate"
    ),
    feature_group = if_else(feature %in% OFF_FEATURES, "Offense", "Defense"),
    feature_label = factor(feature_label,
                           levels = c("eFG% (Off)", "TOV% (Off)", "ORB%",
                                      "FT Rate (Off)", "3PA Rate",
                                      "Opp eFG%", "Opp TOV%", "DRB%", "Opp FT Rate"))
  )

z_max <- max(abs(centroid_long$z_score)) * 1.05

p2 <- centroid_long %>%
  ggplot(aes(x = feature_label, y = reorder(arch_label, archetype), fill = z_score)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = round(z_score, 2)), size = 2.8, color = "grey20") +
  scale_fill_gradient2(
    low = "#2563eb", mid = "white", high = "#dc2626",
    midpoint = 0, limits = c(-z_max, z_max),
    name = "z-score\n(vs league)"
  ) +
  facet_grid(. ~ feature_group, scales = "free_x", space = "free_x") +
  labs(
    title    = "Archetype Profiles: What Each Winning Pattern Looks Like",
    subtitle = paste0("k-means centroids (standardized) \u00b7 ",
                      N_ARCHETYPES, " archetypes from all eligible wins\n",
                      "Red = above league average, Blue = below league average"),
    x = NULL, y = NULL
  ) +
  theme_minimal(base_size = 10) +
  theme(
    axis.text.x      = element_text(angle = 35, hjust = 1, size = 9),
    strip.text       = element_text(face = "bold"),
    panel.grid       = element_blank(),
    plot.title       = element_text(face = "bold")
  ) +
  WHITE_THEME

ggsave("plots/02_archetype_profiles.png", p2, width = 11, height = 5, dpi = 150)
message("Saved: plots/02_archetype_profiles.png")


# --- Plot 3: Archetype composition stacked bars (top 25 by entropy) ---
# For the most versatile teams, show WHICH archetypes their wins fall into

arch_share_cols <- paste0("arch_share_", 1:N_ARCHETYPES)
arch_share_cols_present <- intersect(arch_share_cols, names(combined))

top25_entropy <- combined %>%
  slice_max(entropy_norm, n = 25) %>%
  mutate(team_label = team_conf_label(team_short_display_name, conference_short_name),
         team_ordered = reorder(team_label, entropy_norm))

arch_comp_long <- top25_entropy %>%
  select(team_short_display_name, team_label, team_ordered, entropy_norm,
         all_of(arch_share_cols_present)) %>%
  pivot_longer(all_of(arch_share_cols_present),
               names_to = "arch_col", values_to = "share") %>%
  mutate(archetype = as.integer(str_extract(arch_col, "\\d+"))) %>%
  left_join(arch_names, by = "archetype") %>%
  mutate(arch_label = factor(arch_label))

arch_palette <- setNames(
  RColorBrewer::brewer.pal(max(3, N_ARCHETYPES), "Set2")[1:N_ARCHETYPES],
  levels(arch_comp_long$arch_label)
)

p3 <- arch_comp_long %>%
  ggplot(aes(x = share, y = team_ordered, fill = arch_label)) +
  geom_col(width = 0.75) +
  scale_fill_brewer(palette = "Set2", name = "Archetype") +
  scale_x_continuous(labels = scales::percent) +
  labs(
    title    = "Archetype Composition of Most Versatile Teams",
    subtitle = paste0("Top 25 teams by normalized entropy \u00b7 Weighted by closeness\n",
                      "Teams ordered by entropy (most versatile at top)"),
    x = "Weighted share of wins in each archetype", y = NULL
  ) +
  theme_minimal(base_size = 10) +
  theme(
    plot.title      = element_text(face = "bold"),
    legend.position = "right"
  ) +
  WHITE_THEME

ggsave("plots/03_archetype_composition.png", p3, width = 11, height = 9, dpi = 150)
message("Saved: plots/03_archetype_composition.png")


# --- Plot 4: Bimodality coefficient scatter (offense vs defense) ---

bc_labels <- combined %>%
  filter(!is.na(bc_off) & !is.na(bc_def)) %>%
  {unique(c(
    slice_max(., bc_off,       n = 8)$team_short_display_name,
    slice_max(., bc_def,       n = 8)$team_short_display_name,
    slice_max(., bc_composite, n = 5)$team_short_display_name,
    filter(., bimodal_both)$team_short_display_name
  ))}

# Annotation positions derived from actual data range, not hardcoded
bc_p4 <- combined %>% filter(!is.na(bc_off) & !is.na(bc_def))
bc_xq <- quantile(bc_p4$bc_off, c(0.05, 0.90), na.rm = TRUE)
bc_yq <- quantile(bc_p4$bc_def, c(0.05, 0.90), na.rm = TRUE)
bc_x_thresh_label <- min(0.555 + 0.005,
                         quantile(bc_p4$bc_off, 0.75, na.rm = TRUE))

p4 <- bc_p4 %>%
  ggplot(aes(x = bc_off, y = bc_def)) +
  geom_point(aes(size = n_wins, color = conf_tier), alpha = 0.5) +
  scale_color_manual(values = TIER_COLORS, name = "Conference Tier") +
  geom_text_repel(
    data = combined %>%
      filter(!is.na(bc_off), !is.na(bc_def),
             team_short_display_name %in% bc_labels),
    aes(label = team_short_display_name),
    size = 2.3, max.overlaps = 20, color = "grey20",
    segment.color = "grey60", segment.size = 0.3
  ) +
  # Bimodality threshold lines
  geom_vline(xintercept = 0.555, linetype = "dashed", color = "#dc2626",
             linewidth = 0.5, alpha = 0.7) +
  geom_hline(yintercept = 0.555, linetype = "dashed", color = "#dc2626",
             linewidth = 0.5, alpha = 0.7) +
  # Quadrant labels placed within the actual data range
  annotate("label", x = bc_xq[1], y = bc_yq[2],
           label = "Defensively\nBimodal", size = 2.6,
           fill = alpha("#dbeafe", 0.9), label.size = 0) +
  annotate("label", x = bc_xq[2], y = bc_yq[2],
           label = "Bimodal\nEverywhere", size = 2.6,
           fill = alpha("#dcfce7", 0.9), label.size = 0) +
  annotate("label", x = bc_xq[2], y = bc_yq[1],
           label = "Offensively\nBimodal", size = 2.6,
           fill = alpha("#f3e8ff", 0.9), label.size = 0) +
  annotate("label", x = bc_xq[1], y = bc_yq[1],
           label = "Below\nThreshold", size = 2.6,
           fill = alpha("#f1f5f9", 0.9), label.size = 0) +
  annotate("text", x = bc_x_thresh_label,
           y = quantile(bc_p4$bc_def, 0.97, na.rm = TRUE),
           label = "BC = 0.555 (bimodal threshold)",
           size = 2.1, color = "#dc2626", hjust = 0) +
  # Zoom to actual data range with small padding
  coord_cartesian(
    xlim = c(min(bc_p4$bc_off, na.rm = TRUE) - 0.01,
             max(bc_p4$bc_off, na.rm = TRUE) + 0.01),
    ylim = c(min(bc_p4$bc_def, na.rm = TRUE) - 0.01,
             max(bc_p4$bc_def, na.rm = TRUE) + 0.01)
  ) +
  labs(
    title    = "Bimodality Test: Do Teams Have Two Distinct Winning Modes?",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 Bimodality Coefficient on first PC of wins\n",
                      "BC > 0.555 (red dashes) = bimodal tendency; most teams cluster below threshold"),
    x = "BC \u2014 Offensive PC1 (higher = two distinct offensive modes)",
    y = "BC \u2014 Defensive PC1 (higher = two distinct defensive modes)",
    size    = "Wins",
    caption = "Data: ESPN via wehoop"
  ) +
  theme_minimal(base_size = 11) +
  theme(plot.title = element_text(face = "bold")) +
  WHITE_THEME

ggsave("plots/04_bimodality_scatter.png", p4, width = 10, height = 8, dpi = 150)
message("Saved: plots/04_bimodality_scatter.png")


# --- Plot 5: Composite versatility score ranking ---
# The unified picture: entropy + bimodality together

versatility_labels <- combined %>%
  slice_max(versatility_score, n = 20) %>%
  pull(team_short_display_name)

# Reference lines at sample medians; quadrant labels at actual data extremes
p5_data <- combined %>% filter(!is.na(versatility_score))
ent_med  <- median(p5_data$entropy_norm, na.rm = TRUE)
bc_med   <- median(p5_data$bc_norm,      na.rm = TRUE)
ent_xq   <- quantile(p5_data$entropy_norm, c(0.05, 0.92), na.rm = TRUE)
bc_yq5   <- quantile(p5_data$bc_norm,      c(0.05, 0.92), na.rm = TRUE)

p5 <- p5_data %>%
  ggplot(aes(x = entropy_norm, y = bc_norm)) +
  geom_point(aes(size = n_wins, color = conf_tier), alpha = 0.5) +
  scale_color_manual(values = TIER_COLORS, name = "Conference Tier") +
  geom_text_repel(
    data = combined %>%
      filter(!is.na(versatility_score),
             team_short_display_name %in% versatility_labels),
    aes(label = team_short_display_name),
    size = 2.3, max.overlaps = 20, color = "grey20",
    segment.color = "grey60", segment.size = 0.3
  ) +
  # Median reference lines
  geom_vline(xintercept = ent_med, linetype = "dashed", color = "grey50", linewidth = 0.4) +
  geom_hline(yintercept = bc_med,  linetype = "dashed", color = "grey50", linewidth = 0.4) +
  # Diagonal = equal versatility score
  geom_abline(slope = 1, intercept = 0, linetype = "dotted",
              color = "#6b21a8", linewidth = 0.4, alpha = 0.6) +
  # Quadrant labels positioned within the actual data range
  annotate("label",
           x = ent_xq[1], y = bc_yq5[2],
           label = "Two Modes\n(specialist bimodal)",
           size = 2.6, fill = alpha("#fef3c7", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[2], y = bc_yq5[2],
           label = "Truly Adaptive\n(spread + bimodal)",
           size = 2.6, fill = alpha("#dcfce7", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[1], y = bc_yq5[1],
           label = "One-Mode\nSpecialist",
           size = 2.6, fill = alpha("#fee2e2", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[2], y = bc_yq5[1],
           label = "Diffuse\nVersatility",
           size = 2.6, fill = alpha("#dbeafe", 0.9), label.size = 0) +
  labs(
    title    = "Win Versatility: Spread vs. Bimodality",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 Versatility Score = 0.5\u00d7Entropy + 0.5\u00d7BC (min-max scaled)",
                      "\nDashed lines = sample medians; diagonal = equal contribution from both"),
    x = "Normalized Entropy (spread across archetypes)",
    y = "BC Relative Strength (min-max scaled within sample)",
    size    = "Wins",
    caption = "Data: ESPN via wehoop"
  ) +
  theme_minimal(base_size = 11) +
  theme(plot.title = element_text(face = "bold")) +
  WHITE_THEME

ggsave("plots/05_versatility_composite.png", p5, width = 10, height = 8, dpi = 150)
message("Saved: plots/05_versatility_composite.png")


# ============================================================================
# SAVE OUTPUTS
# ============================================================================

dir.create("output", showWarnings = FALSE)

write_csv(team_archetypes,    "output/team_archetypes_2026.csv")
write_csv(bimodality_results, "output/bimodality_results_2026.csv")
write_csv(cv_composites,      "output/cv_composites_weighted_2026.csv")
write_csv(combined,           "output/combined_win_variance_v4_2026.csv")
write_csv(arch_names,         "output/archetype_labels_2026.csv")

message("\n\u2713 Done. Results in output/, plots in plots/")
message("\nKey output files:")
message("  output/team_archetypes_2026.csv       \u2014 Entropy + archetype shares per team")
message("  output/bimodality_results_2026.csv    \u2014 BC + GMM BIC diff per team")
message("  output/combined_win_variance_v4_2026.csv \u2014 Full combined table")
message("\nKey plots:")
message("  plots/01_entropy_ranking.png        \u2014 Most/least versatile by entropy")
message("  plots/02_archetype_profiles.png     \u2014 What each archetype looks like")
message("  plots/03_archetype_composition.png  \u2014 Win distribution for top-25 teams")
message("  plots/04_bimodality_scatter.png     \u2014 Off vs def bimodality")
message("  plots/05_versatility_composite.png  \u2014 Entropy vs bimodality joint view")
