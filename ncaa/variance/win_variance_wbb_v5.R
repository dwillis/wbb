# ============================================================================
# Win Variance Analysis: NCAA WBB 2025-26 (v5)
#
# How do teams win in different ways?
#
# Changes from v4:
#   - Opponent-adjusted residuals: for each winning game, features are
#     expressed as residuals from the opponent's season-average profile.
#     This separates "team played differently" from "team played a weak
#     or strong opponent." Season averages are computed from ALL games
#     (wins + losses) for robustness.
#   - ICC-weighted clustering: features with higher between-team signal
#     (intraclass correlation) get more weight in k-means. This demotes
#     high-noise features (FT rate, TOV%) that created clusters reflecting
#     officiating/random variance rather than team strategy.
#   - Bimodality (BC + GMM) removed — underpowered at n=20-30 wins.
#     Replaced by archetype concentration metrics computed directly from
#     the share distribution: HHI and dominance ratio.
#   - Closeness-scale sensitivity analysis: entropy rankings computed at
#     multiple CLOSENESS_SCALE values (5, 10, 20, 50, Inf) with rank
#     correlations reported to assess whether the weighting is signal or noise.
#   - CV profiles retained as diagnostic detail, clearly separated from
#     the combined versatility score.
#   - Versatility score = 0.5 * entropy_norm + 0.5 * (1 - hhi_norm),
#     replacing the entropy + bimodality formula.
#   - Raw-vs-residual comparison diagnostic added to measure the impact
#     of opponent adjustment.
#
# Four analysis components:
#
#   1. Opponent-Adjusted Feature Computation
#      - Season averages: team offensive profile + defensive profile (what
#        they allow) computed from ALL games
#      - For each win: offensive residual = raw stat - opponent's avg
#        defensive stat; defensive residual = opp's raw stat in this game
#        - opp's season avg offensive stat
#      - Positive offensive residual = performed BETTER than what opponent
#        typically allows; negative defensive residual = held opponent
#        BELOW their usual offensive performance
#
#   2. Win Profile Clustering (ICC-weighted, opponent-adjusted)
#      - ICC computed on residual features
#      - k-means on ICC-weighted, standardized 9D residual space
#      - Per-team closeness-weighted Shannon entropy + HHI
#
#   3. Closeness-Scale Sensitivity
#      - Entropy rankings at scales 5, 10, 20, 50, Inf
#      - Spearman rank correlations across scales
#
#   4. Weighted CV profiles by strategic dimension (diagnostic)
#      - Reliability-weighted CV using closeness_weight
#      - Presented as supporting detail, not part of versatility score
#
# Packages required: wehoop, tidyverse, ggrepel
# ============================================================================

library(wehoop)
library(tidyverse)
library(ggrepel)

# ---- CONFIG ----------------------------------------------------------------

SEASON          <- 2026
MIN_WINS        <- 20
CLOSENESS_SCALE <- 10        # primary scale: w = 1/(1 + margin/10)
N_ARCHETYPES    <- 5         # k-means clusters; silhouette check below
CACHE_FILE      <- "data/wbb_team_box_2026.rds"

# Sensitivity analysis scales
SENSITIVITY_SCALES <- c(5, 10, 20, 50, Inf)

# Opponent adjustment: use residuals (TRUE) or raw features (FALSE)
# When TRUE, features are opponent-adjusted residuals;
# a raw-vs-residual comparison diagnostic is always printed.
USE_RESIDUALS <- TRUE

# Feature vectors
OFF_FEATURES <- c("efg_pct", "tov_pct", "orb_pct", "ft_rate", "three_par")
DEF_FEATURES <- c("opp_efg_pct", "opp_tov_pct", "drb_pct", "opp_ft_rate")
ALL_FEATURES <- c(OFF_FEATURES, DEF_FEATURES)

# CV stat groups (diagnostic)
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

normalize_name <- function(x) {
  x <- iconv(x, from = "UTF-8", to = "ASCII//TRANSLIT")
  x %>% tolower() %>% gsub("[^a-z0-9]", "", .)
}

message("Loading conference data from ", TEAMS_CSV, "...")
csv_teams <- read_csv(TEAMS_CSV, show_col_types = FALSE) %>%
  filter(division == "I") %>%
  select(team, espn_name, conference_short_name = conference) %>%
  mutate(join_key = normalize_name(espn_name)) %>%
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
# STEP 0c: BUILD OPPONENT JOIN (ALL GAMES)
#
# We join opponent stats for ALL games (not just wins) because we need
# season-average profiles for every team to compute opponent adjustments.
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

# Join ALL games (wins + losses) with opponent stats
all_games_with_opp <- team_box %>%
  inner_join(opp_stats, by = "game_id", suffix = c("", "_opp")) %>%
  filter(team_id != team_id_opp)

message("\nAll game-rows after opponent join: ", nrow(all_games_with_opp))


# ============================================================================
# STEP 0d: COMPUTE FEATURES FOR ALL GAMES
#
# Same feature definitions applied to every game (wins + losses).
# This gives us the data to compute season-average profiles.
# ============================================================================

compute_game_features <- function(df) {
  df %>%
    mutate(
      # === WBB FIVE FACTORS (OFFENSIVE) ===
      efg_pct   = (field_goals_made + 0.5 * three_point_field_goals_made) /
                   field_goals_attempted,
      tov_pct   = turnovers /
                  (field_goals_attempted + 0.44 * free_throws_attempted + turnovers),
      orb_pct   = offensive_rebounds / (offensive_rebounds + opp_drb),
      ft_rate   = free_throws_made / field_goals_attempted,
      three_par = three_point_field_goals_attempted / field_goals_attempted,

      # === DEFENSIVE FACTORS (what opponent did = what this team allowed) ===
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
                               NA_real_)
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
}

all_game_features <- compute_game_features(all_games_with_opp)
message("All games with valid features: ", nrow(all_game_features))


# ============================================================================
# STEP 0e: COMPUTE SEASON-AVERAGE PROFILES AND OPPONENT-ADJUSTED RESIDUALS
#
# For each team, compute two season profiles from ALL their games:
#
#   Offensive profile: season average of efg_pct, tov_pct, orb_pct,
#                      ft_rate, three_par
#   Defensive profile: season average of opp_efg_pct, opp_tov_pct,
#                      drb_pct, opp_ft_rate (= what they ALLOW on average)
#
# For a winning game where team A beats team B:
#
#   Offensive residuals (team A's offense vs what B allows):
#     efg_pct_resid = A's efg_pct - B's avg opp_efg_pct
#     tov_pct_resid = A's tov_pct - B's avg opp_tov_pct
#     orb_pct_resid = A's orb_pct - (1 - B's avg drb_pct)
#     ft_rate_resid = A's ft_rate - B's avg opp_ft_rate
#     three_par_resid = A's three_par - B's avg three_par_allowed
#       (three_par_allowed ≈ opp's avg three_par, since shot selection is
#        mostly the shooter's choice; but some defenses do influence this.
#        We use opponent's avg three_par against them, computed from their
#        opponents' three_par in all games.)
#
#   Defensive residuals (B's offense in this game vs B's average):
#     opp_efg_pct_resid = B's efg_pct_this_game - B's avg efg_pct
#     opp_tov_pct_resid = B's tov_pct_this_game - B's avg tov_pct
#     drb_pct_resid     = A's drb_pct - A's avg drb_pct  (relative to OWN avg)
#     opp_ft_rate_resid = B's ft_rate_this_game - B's avg ft_rate
#
# Interpretation:
#   Positive efg_pct_resid = team shot BETTER than what opponent usually allows
#   Negative opp_efg_pct_resid = opponent shot WORSE than their usual → good defense
#
# Note on drb_pct: unlike the other defensive features, defensive rebound rate
# depends on your own team's positioning, not the opponent's offense. So we
# adjust drb_pct relative to the team's own season average, not the opponent's.
# ============================================================================

message("\n=== COMPUTING SEASON AVERAGES AND OPPONENT ADJUSTMENTS ===")

# Season offensive averages per team (what each team DOES on offense)
team_off_avg <- all_game_features %>%
  group_by(team_id) %>%
  summarise(
    avg_efg_pct   = mean(efg_pct,   na.rm = TRUE),
    avg_tov_pct   = mean(tov_pct,   na.rm = TRUE),
    avg_orb_pct   = mean(orb_pct,   na.rm = TRUE),
    avg_ft_rate   = mean(ft_rate,   na.rm = TRUE),
    avg_three_par = mean(three_par, na.rm = TRUE),
    n_games       = n(),
    .groups = "drop"
  )

# Season defensive averages per team (what each team ALLOWS)
team_def_avg <- all_game_features %>%
  group_by(team_id) %>%
  summarise(
    avg_opp_efg_pct = mean(opp_efg_pct, na.rm = TRUE),  # what they allow
    avg_opp_tov_pct = mean(opp_tov_pct, na.rm = TRUE),
    avg_drb_pct     = mean(drb_pct,     na.rm = TRUE),
    avg_opp_ft_rate = mean(opp_ft_rate, na.rm = TRUE),
    # What opponents shoot from 3 against this team (≈ three_par allowed)
    avg_opp_three_par = mean(opp_3pa / opp_fga, na.rm = TRUE),
    .groups = "drop"
  )

message("Season averages computed for ", nrow(team_off_avg), " teams (",
        round(mean(team_off_avg$n_games), 1), " avg games per team)")

# --- Build win features with opponent adjustment ---
wins_with_opp <- all_games_with_opp %>%
  filter(team_winner == TRUE)

win_features_raw <- compute_game_features(wins_with_opp) %>%
  mutate(
    margin           = team_score - opp_score,
    closeness_weight = 1 / (1 + margin / CLOSENESS_SCALE)
  )

# Join opponent's season averages to each winning game
# team_id_opp is the opponent in this game
win_features <- win_features_raw %>%
  # Opponent's defensive averages (what this opponent allows → offensive adjustment)
  left_join(
    team_def_avg %>%
      rename(opp_avg_opp_efg_pct = avg_opp_efg_pct,
             opp_avg_opp_tov_pct = avg_opp_tov_pct,
             opp_avg_drb_pct     = avg_drb_pct,
             opp_avg_opp_ft_rate = avg_opp_ft_rate,
             opp_avg_opp_three_par = avg_opp_three_par),
    by = c("team_id_opp" = "team_id")
  ) %>%
  # Opponent's offensive averages (what opponent usually does → defensive adjustment)
  left_join(
    team_off_avg %>%
      select(team_id, opp_avg_efg_pct = avg_efg_pct,
             opp_avg_tov_pct = avg_tov_pct,
             opp_avg_orb_pct = avg_orb_pct,
             opp_avg_ft_rate = avg_ft_rate,
             opp_avg_three_par = avg_three_par),
    by = c("team_id_opp" = "team_id")
  ) %>%
  # Team's own season defensive average (for drb_pct adjustment)
  left_join(
    team_def_avg %>%
      select(team_id, own_avg_drb_pct = avg_drb_pct),
    by = "team_id"
  ) %>%
  # Compute residuals
  mutate(
    # --- Offensive residuals: my stat - what opponent typically allows ---
    # opp_avg_opp_efg_pct = opponent's avg allowed eFG% (from their defensive profile)
    efg_pct_resid   = efg_pct   - opp_avg_opp_efg_pct,
    tov_pct_resid   = tov_pct   - opp_avg_opp_tov_pct,
    orb_pct_resid   = orb_pct   - (1 - opp_avg_drb_pct),  # their DRB% → our expected ORB%
    ft_rate_resid   = ft_rate   - opp_avg_opp_ft_rate,
    three_par_resid = three_par - opp_avg_opp_three_par,

    # --- Defensive residuals: what opponent did - what opponent usually does ---
    # Negative = we held them below their average (good defense)
    opp_efg_pct_resid = opp_efg_pct - opp_avg_efg_pct,
    opp_tov_pct_resid = opp_tov_pct - opp_avg_tov_pct,
    drb_pct_resid     = drb_pct     - own_avg_drb_pct,  # vs own season average
    opp_ft_rate_resid = opp_ft_rate - opp_avg_ft_rate
  )

message("Win features with opponent adjustment: ", nrow(win_features))
message("Closeness weight — mean: ", round(mean(win_features$closeness_weight), 3),
        "  median: ", round(median(win_features$closeness_weight), 3))

# Define residual feature names
RESID_FEATURES <- c("efg_pct_resid", "tov_pct_resid", "orb_pct_resid",
                    "ft_rate_resid", "three_par_resid",
                    "opp_efg_pct_resid", "opp_tov_pct_resid",
                    "drb_pct_resid", "opp_ft_rate_resid")

# Check residual distributions
message("\nResidual summary statistics:")
resid_summary <- win_features %>%
  select(all_of(RESID_FEATURES)) %>%
  summarise(across(everything(), list(
    mean = ~ round(mean(.x, na.rm = TRUE), 4),
    sd   = ~ round(sd(.x, na.rm = TRUE), 4)
  ))) %>%
  pivot_longer(everything(),
               names_to = c("feature", "stat"),
               names_pattern = "(.+)_(mean|sd)$") %>%
  pivot_wider(names_from = stat, values_from = value)
message("  (means should be positive for offensive and negative for defensive,")
message("   since these are winning games — winners perform above opponent averages)")
print(resid_summary, n = 20)

# Choose which features to use for clustering
CLUSTER_FEATURES <- if (USE_RESIDUALS) RESID_FEATURES else ALL_FEATURES
message("\nClustering on: ", if (USE_RESIDUALS) "OPPONENT-ADJUSTED RESIDUALS" else "RAW FEATURES")


# ============================================================================
# STEP 0f: FILTER TO ELIGIBLE TEAMS
# ============================================================================

team_wins <- win_features %>%
  count(team_id, team_short_display_name, name = "n_wins") %>%
  filter(n_wins >= MIN_WINS)

message("Eligible teams (>=", MIN_WINS, " wins): ", nrow(team_wins))

wf_eligible <- win_features %>%
  filter(team_id %in% team_wins$team_id)


# ============================================================================
# STEP 1: ICC COMPUTATION — FEATURE SIGNAL-TO-NOISE
#
# Intraclass Correlation Coefficient (ICC-1) measures how much of each
# feature's total variance is between-team (signal) vs within-team (noise).
#
#   ICC = (MSb - MSw) / (MSb + (k0 - 1) * MSw)
#
# where MSb = between-team mean square, MSw = within-team mean square,
# k0 = typical group size (harmonic-ish adjustment for unbalanced groups).
#
# Features with high ICC (e.g., three_par, efg_pct) reflect stable team
# identity. Features with low ICC (e.g., opp_ft_rate, ft_rate) are
# dominated by game-to-game noise and should be downweighted in clustering.
#
# We use sqrt(ICC) as the weight so that the influence is moderated —
# low-ICC features aren't zeroed out, just damped.
# ============================================================================

message("\n=== ICC COMPUTATION (feature signal-to-noise) ===")

compute_icc <- function(df, feature, group_var = "team_id") {
  # One-way random effects ICC(1)
  vals <- df[[feature]]
  grps <- df[[group_var]]
  keep <- !is.na(vals)
  vals <- vals[keep]; grps <- grps[keep]

  grp_f <- factor(grps)
  n_groups <- nlevels(grp_f)
  if (n_groups < 3) return(NA_real_)

  N <- length(vals)
  grp_sizes <- table(grp_f)

  grand_mean <- mean(vals)
  grp_means  <- tapply(vals, grp_f, mean)

  SSb <- sum(grp_sizes * (grp_means - grand_mean)^2)
  SSw <- sum((vals - grp_means[grp_f])^2)

  dfb <- n_groups - 1
  dfw <- N - n_groups

  MSb <- SSb / dfb
  MSw <- SSw / dfw

  # k0: adjusted group size for unbalanced designs
  k0 <- (1 / dfb) * (N - sum(grp_sizes^2) / N)

  icc <- (MSb - MSw) / (MSb + (k0 - 1) * MSw)
  max(0, icc)  # floor at 0 (negative ICC means no between-group signal)
}

icc_values <- sapply(CLUSTER_FEATURES, function(f) compute_icc(wf_eligible, f))
icc_table  <- tibble(
  feature  = names(icc_values),
  icc      = round(as.numeric(icc_values), 4),
  weight   = round(sqrt(as.numeric(icc_values)), 4)
) %>%
  arrange(desc(icc))

message("\nFeature ICCs and clustering weights",
        if (USE_RESIDUALS) " (opponent-adjusted residuals):" else " (raw features):")
print(icc_table, n = 20)

# Extract weight vector in feature order
icc_weights <- sqrt(pmax(0, icc_values[CLUSTER_FEATURES]))
# Floor: don't let any weight drop below 0.1 (keeps feature in play, just damped)
icc_weights <- pmax(icc_weights, 0.1)

message("\nICC weight vector (floored at 0.1):")
message("  ", paste(CLUSTER_FEATURES, round(icc_weights, 3), sep = "=", collapse = "  "))


# ============================================================================
# METRIC 1: WIN PROFILE CLUSTERING (ICC-WEIGHTED)
#
# k-means on standardized, ICC-weighted 9D feature space.
#
# Procedure:
#   1. Standardize each feature (z-score across all eligible wins)
#   2. Multiply each z-scored column by its ICC weight
#   3. k-means on the weighted matrix
#
# Effect: clusters form primarily around high-ICC features (shooting
# efficiency, shot selection) rather than noise-dominated features
# (free throw rate, opponent turnover rate).
#
# Per-team metrics:
#   - Weighted Shannon entropy of archetype distribution (same as v4)
#   - HHI (Herfindahl-Hirschman Index) of archetype shares: sum(p_k^2)
#     High HHI = concentrated in few archetypes; Low HHI = spread out
#   - Dominance ratio: share_1 / share_2 (top two archetype shares)
#     Ratio near 1 = two balanced modes; ratio >> 1 = single dominant mode
# ============================================================================

# --- Standardize features ---
feature_means <- wf_eligible %>% select(all_of(CLUSTER_FEATURES)) %>% colMeans()
feature_sds   <- wf_eligible %>% select(all_of(CLUSTER_FEATURES)) %>%
  summarise(across(everything(), sd)) %>% unlist()

wf_z_mat <- wf_eligible %>%
  select(all_of(CLUSTER_FEATURES)) %>%
  scale(center = feature_means, scale = feature_sds) %>%
  as.matrix()

# Apply ICC weights: multiply each column by its weight
wf_scaled_mat <- sweep(wf_z_mat, 2, icc_weights, FUN = "*")

message("\n=== Clustering on ICC-weighted features ===")

# --- Silhouette check: k = 3..8 (subsample for speed) ---
message("Checking silhouette scores for k = 3..8 (subsampled)...")
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

best_k <- as.integer(names(which.max(sil_scores)))
message("Silhouette: ", paste(names(sil_scores), round(sil_scores, 3), sep = "=", collapse = "  "))
message("Silhouette-optimal k = ", best_k,
        "  (using N_ARCHETYPES = ", N_ARCHETYPES, " as configured)")

# --- Final clustering ---
set.seed(42)
km <- kmeans(wf_scaled_mat, centers = N_ARCHETYPES, nstart = 50, iter.max = 200)
wf_eligible <- wf_eligible %>% mutate(archetype = km$cluster)

message("Archetype sizes: ",
        paste(paste0("A", 1:N_ARCHETYPES), tabulate(wf_eligible$archetype),
              sep = "=", collapse = "  "))

# --- Name and describe each archetype ---
# Centroids are in the ICC-weighted space; to label them meaningfully,
# use the unweighted z-score centroids (divide back by weights).
# This tells us what each archetype looks like in standard-deviation units
# of the original features.

unweighted_centers <- sweep(km$centers, 2, icc_weights, FUN = "/")

# Feature labels work for both raw and residual features
FEATURE_NICE <- c(
  # Raw features
  efg_pct     = "eFG%",
  tov_pct     = "TOV%",
  orb_pct     = "ORB%",
  ft_rate     = "FT Rate",
  three_par   = "3PA Rate",
  opp_efg_pct = "Opp eFG%",
  opp_tov_pct = "Opp TOV%",
  drb_pct     = "DRB%",
  opp_ft_rate = "Opp FT Rate",
  # Residual features (same concepts, marked as adjusted)
  efg_pct_resid     = "\u0394 eFG%",
  tov_pct_resid     = "\u0394 TOV%",
  orb_pct_resid     = "\u0394 ORB%",
  ft_rate_resid     = "\u0394 FT Rate",
  three_par_resid   = "\u0394 3PA Rate",
  opp_efg_pct_resid = "\u0394 Opp eFG%",
  opp_tov_pct_resid = "\u0394 Opp TOV%",
  drb_pct_resid     = "\u0394 DRB%",
  opp_ft_rate_resid = "\u0394 Opp FT Rate"
)

# Meanings work the same for residuals — positive residual means "more than expected"
FEATURE_MEANING <- c(
  # Raw feature meanings
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
  opp_ft_rate_low  = "disciplined, foul-avoiding defense",
  # Residual feature meanings (relative to opponent expected)
  efg_pct_resid_high     = "shooting better than opponent allows",
  efg_pct_resid_low      = "shooting worse than opponent allows",
  tov_pct_resid_high     = "more turnovers than opponent forces",
  tov_pct_resid_low      = "fewer turnovers than opponent forces",
  orb_pct_resid_high     = "more offensive rebounds than expected",
  orb_pct_resid_low      = "fewer offensive rebounds than expected",
  ft_rate_resid_high     = "more FTs than opponent allows",
  ft_rate_resid_low      = "fewer FTs than opponent allows",
  three_par_resid_high   = "more 3PA than opponent faces",
  three_par_resid_low    = "fewer 3PA than opponent faces",
  opp_efg_pct_resid_high = "opponent shooting above their average",
  opp_efg_pct_resid_low  = "holding opponent below their average",
  opp_tov_pct_resid_high = "forcing more turnovers than opponent's norm",
  opp_tov_pct_resid_low  = "opponent taking care of ball vs their norm",
  drb_pct_resid_high     = "rebounding above own average",
  drb_pct_resid_low      = "rebounding below own average",
  opp_ft_rate_resid_high = "opponent getting more FTs than their norm",
  opp_ft_rate_resid_low  = "opponent getting fewer FTs than their norm"
)

# Determine offense/defense grouping for the active feature set
if (USE_RESIDUALS) {
  OFF_CLUSTER_FEATURES <- c("efg_pct_resid", "tov_pct_resid", "orb_pct_resid",
                            "ft_rate_resid", "three_par_resid")
  DEF_CLUSTER_FEATURES <- c("opp_efg_pct_resid", "opp_tov_pct_resid",
                            "drb_pct_resid", "opp_ft_rate_resid")
} else {
  OFF_CLUSTER_FEATURES <- OFF_FEATURES
  DEF_CLUSTER_FEATURES <- DEF_FEATURES
}

arch_detail <- as.data.frame(unweighted_centers) %>%
  mutate(archetype = row_number()) %>%
  pivot_longer(-archetype, names_to = "feature", values_to = "z") %>%
  group_by(archetype) %>%
  arrange(desc(abs(z)), .by_group = TRUE) %>%
  mutate(rank = row_number()) %>%
  ungroup() %>%
  mutate(
    direction  = if_else(z > 0, "high", "low"),
    meaning    = FEATURE_MEANING[paste0(feature, "_", direction)],
    feat_nice  = FEATURE_NICE[feature],
    feat_label = paste0(if_else(z > 0, "\u25b2", "\u25bc"), " ",
                        feat_nice,
                        " (z=", sprintf("%+.2f", z), ")")
  )

arch_names <- arch_detail %>%
  filter(rank == 1) %>%
  mutate(
    sign_str   = if_else(z > 0, "High", "Low"),
    arch_label = paste0("S", archetype, ": ",
                        sign_str, " ", feat_nice)
  ) %>%
  select(archetype, arch_label)

arch_descriptions <- arch_detail %>%
  filter(rank <= 3) %>%
  group_by(archetype) %>%
  summarise(
    features_str = paste(feat_label, collapse = "  |  "),
    meaning_str  = paste(meaning,    collapse = "; "),
    .groups = "drop"
  ) %>%
  left_join(arch_names, by = "archetype")

message("\n=== ARCHETYPE DESCRIPTIONS (ICC-weighted",
        if (USE_RESIDUALS) ", opponent-adjusted" else "",
        " clustering) ===")
for (i in seq_len(nrow(arch_descriptions))) {
  message("\n  ", arch_descriptions$arch_label[i])
  message("  Features : ", arch_descriptions$features_str[i])
  message("  In plain language: wins featuring teams ", arch_descriptions$meaning_str[i])
}

# --- Per-team entropy + concentration metrics ---
weighted_entropy <- function(archetypes, weights) {
  weights <- weights / sum(weights)
  wp <- tapply(weights, archetypes, sum)
  wp <- wp[wp > 0]
  -sum(wp * log(wp))
}

max_entropy <- log(N_ARCHETYPES)

# HHI: Herfindahl-Hirschman Index of archetype concentration
# HHI = sum(share_k^2), ranges from 1/N_ARCHETYPES (perfectly even) to 1 (all in one)
compute_hhi <- function(archetypes, weights) {
  weights <- weights / sum(weights)
  shares <- tapply(weights, archetypes, sum)
  # Include zero shares for unused archetypes
  all_shares <- rep(0, N_ARCHETYPES)
  all_shares[as.integer(names(shares))] <- shares
  sum(all_shares^2)
}

# Dominance ratio: top share / second share
# Near 1 = two balanced modes; >> 1 = single dominant mode
compute_dominance_ratio <- function(archetypes, weights) {
  weights <- weights / sum(weights)
  shares <- tapply(weights, archetypes, sum)
  all_shares <- rep(0, N_ARCHETYPES)
  all_shares[as.integer(names(shares))] <- shares
  sorted <- sort(all_shares, decreasing = TRUE)
  if (sorted[2] < 1e-10) return(Inf)  # only one archetype used
  sorted[1] / sorted[2]
}

team_archetypes <- wf_eligible %>%
  group_by(team_id, team_short_display_name) %>%
  summarise(
    n_wins            = n(),
    entropy           = weighted_entropy(archetype, closeness_weight),
    entropy_norm      = entropy / max_entropy,
    hhi               = compute_hhi(archetype, closeness_weight),
    dominance_ratio   = compute_dominance_ratio(archetype, closeness_weight),
    primary_archetype = as.integer(names(which.max(table(archetype)))),
    n_archetypes_used = n_distinct(archetype),
    .groups = "drop"
  ) %>%
  # Normalize HHI to 0-1 where 0 = most concentrated, 1 = most spread
  # HHI ranges from 1/K (even) to 1.0 (single archetype)
  mutate(
    hhi_norm     = (hhi - 1/N_ARCHETYPES) / (1 - 1/N_ARCHETYPES),  # 0=even, 1=concentrated
    spread_score = 1 - hhi_norm  # 0=concentrated, 1=even
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
    hhi               = round(hhi, 3),
    dominance_ratio   = round(dominance_ratio, 2),
    n_archetypes_used = n_archetypes_used,
    primary           = primary_archetype
  ) %>%
  print(n = 20)

message("\n=== BOTTOM 10 (specialists) ===")
team_archetypes %>%
  slice_tail(n = 10) %>%
  transmute(
    team            = team_short_display_name,
    wins            = n_wins,
    entropy_norm    = round(entropy_norm, 3),
    hhi             = round(hhi, 3),
    dominance_ratio = round(dominance_ratio, 2),
    primary         = primary_archetype
  ) %>%
  print(n = 10)

# --- Top two archetype split for top-entropy teams (diagnostic) ---
message("\n=== TOP-2 ARCHETYPE SPLIT (top 15 by entropy) ===")
message("(dominance_ratio near 1.0 = two balanced winning modes)")
team_archetypes %>%
  slice_head(n = 15) %>%
  transmute(
    team            = team_short_display_name,
    entropy_norm    = round(entropy_norm, 3),
    dominance_ratio = round(dominance_ratio, 2),
    primary         = primary_archetype,
    n_used          = n_archetypes_used
  ) %>%
  print(n = 15)


# ============================================================================
# METRIC 2: CLOSENESS-SCALE SENSITIVITY ANALYSIS
#
# If the entropy ranking changes substantially across CLOSENESS_SCALE values,
# the weighting scheme is doing real work. If rankings are stable, the
# weighting is cosmetic and unweighted analysis would suffice.
#
# Method:
#   - For each scale in SENSITIVITY_SCALES:
#     - Recompute closeness_weight = 1 / (1 + margin / scale)
#       (scale = Inf → weight = 1 for all games, i.e., unweighted)
#     - Recompute per-team weighted entropy using the same archetype assignments
#     - Rank teams by entropy
#   - Report pairwise Spearman rank correlations across scales
#   - Identify teams with the largest rank movement
# ============================================================================

message("\n=== CLOSENESS-SCALE SENSITIVITY ANALYSIS ===")

# Compute entropy at each scale (reusing archetype assignments from primary clustering)
sensitivity_entropies <- map_dfc(SENSITIVITY_SCALES, function(sc) {
  # Compute new weights
  if (is.infinite(sc)) {
    new_weights <- rep(1, nrow(wf_eligible))
  } else {
    new_weights <- 1 / (1 + wf_eligible$margin / sc)
  }

  # Per-team entropy with these weights
  team_ent <- wf_eligible %>%
    mutate(.w = new_weights) %>%
    group_by(team_id) %>%
    summarise(
      .ent = weighted_entropy(archetype, .w),
      .groups = "drop"
    ) %>%
    mutate(.ent_norm = .ent / max_entropy) %>%
    select(team_id, .ent_norm)

  col_name <- if (is.infinite(sc)) "scale_Inf" else paste0("scale_", sc)
  team_ent %>%
    rename(!!col_name := .ent_norm) %>%
    select(-team_id)
}) %>%
  bind_cols(
    wf_eligible %>%
      group_by(team_id, team_short_display_name) %>%
      summarise(.groups = "drop") %>%
      select(team_id, team_short_display_name),
    .
  )

# Spearman rank correlations between scales
scale_cols <- grep("^scale_", names(sensitivity_entropies), value = TRUE)
rank_cor_mat <- cor(
  sensitivity_entropies %>% select(all_of(scale_cols)),
  method = "spearman",
  use = "complete"
)

message("\nSpearman rank correlations between closeness scales:")
scale_labels <- gsub("scale_", "", scale_cols)
dimnames(rank_cor_mat) <- list(scale_labels, scale_labels)
print(round(rank_cor_mat, 3))

# Identify teams with largest rank movement between extremes (scale=5 vs unweighted)
extreme_cols <- c(scale_cols[1], scale_cols[length(scale_cols)])

rank_movement <- sensitivity_entropies %>%
  mutate(
    rank_tight    = rank(-!!sym(extreme_cols[1])),
    rank_unweight = rank(-!!sym(extreme_cols[2])),
    rank_change   = abs(rank_tight - rank_unweight)
  ) %>%
  arrange(desc(rank_change))

message("\n=== TEAMS WITH LARGEST RANK MOVEMENT (scale=",
        gsub("scale_", "", extreme_cols[1]), " vs unweighted) ===")
rank_movement %>%
  slice_head(n = 15) %>%
  transmute(
    team         = team_short_display_name,
    rank_tight   = rank_tight,
    rank_unweight = rank_unweight,
    rank_change  = rank_change,
    ent_tight    = round(!!sym(extreme_cols[1]), 3),
    ent_unweight = round(!!sym(extreme_cols[2]), 3)
  ) %>%
  print(n = 15)


# ============================================================================
# METRIC 3: WEIGHTED CV PROFILES BY STRATEGIC DIMENSION (DIAGNOSTIC)
#
# These are NOT part of the versatility score. They describe HOW a team
# varies — which strategic dimensions are most/least consistent — and
# are useful for interpreting why a team scores high or low on versatility.
#
# CV = weighted SD / weighted mean, using closeness_weight as reliability
# weights.
# ============================================================================

message("\n=== CV PROFILES (diagnostic) ===")

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
#
# Versatility score = 0.5 * entropy_norm + 0.5 * spread_score
#
# where spread_score = 1 - hhi_norm (from archetype concentration).
#
# Both components come from the same archetype distribution, but they
# capture different aspects:
#   - Entropy is sensitive to the number of archetypes used and their
#     evenness (a team using 3 archetypes at 33% each has lower entropy
#     than one using 5 at 20% each)
#   - HHI is a concentration measure that's more sensitive to the
#     dominance of the top archetype(s)
#
# A team could have moderate entropy (3 archetypes used) but low HHI
# (none of the 3 dominates), or high entropy (5 archetypes) but moderate
# HHI (one archetype at 40% with the rest spread).
# ============================================================================

combined <- team_archetypes %>%
  inner_join(cv_composites %>%
               select(team_id, cv_composite_core,
                      cv_Shooting, cv_Ball_Care, cv_Rebounding,
                      cv_Free_Throws, cv_Scoring_Mix, cv_Def_Quality),
             by = "team_id") %>%
  left_join(
    sensitivity_entropies %>% select(team_id, all_of(scale_cols)),
    by = "team_id"
  ) %>%
  left_join(
    rank_movement %>% select(team_id, rank_change),
    by = "team_id"
  ) %>%
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

# Versatility score
combined <- combined %>%
  mutate(
    versatility_score = 0.5 * entropy_norm + 0.5 * spread_score
  ) %>%
  arrange(desc(versatility_score))

message("\n=== COMBINED VERSATILITY SCORE: TOP 20 ===")
combined %>%
  slice_head(n = 20) %>%
  transmute(
    team              = team_short_display_name,
    wins              = n_wins,
    entropy_norm      = round(entropy_norm, 3),
    hhi               = round(hhi, 3),
    spread_score      = round(spread_score, 3),
    versatility_score = round(versatility_score, 3),
    dominance_ratio   = round(dominance_ratio, 2),
    conference        = conference_short_name
  ) %>%
  print(n = 20)

message("\n=== CORRELATIONS ===")
message("Entropy vs spread_score (1-HHI): ",
        round(cor(combined$entropy_norm, combined$spread_score, use = "complete"), 3))
message("Entropy vs CV core:              ",
        round(cor(combined$entropy_norm, combined$cv_composite_core, use = "complete"), 3))
message("Spread_score vs CV core:         ",
        round(cor(combined$spread_score, combined$cv_composite_core, use = "complete"), 3))
message("Versatility vs CV core:          ",
        round(cor(combined$versatility_score, combined$cv_composite_core, use = "complete"), 3))

# --- Diagnostic: CV profiles for top/bottom versatility teams ---
message("\n=== CV PROFILE DIAGNOSTIC: TOP 10 VERSATILITY TEAMS ===")
message("(Which strategic dimensions are these teams most variable in?)")
combined %>%
  slice_head(n = 10) %>%
  transmute(
    team              = team_short_display_name,
    versatility_score = round(versatility_score, 3),
    cv_Shooting       = round(cv_Shooting, 3),
    cv_Ball_Care      = round(cv_Ball_Care, 3),
    cv_Rebounding     = round(cv_Rebounding, 3),
    cv_Free_Throws    = round(cv_Free_Throws, 3),
    cv_Def_Quality    = round(cv_Def_Quality, 3)
  ) %>%
  print(n = 10)

message("\n=== CV PROFILE DIAGNOSTIC: BOTTOM 10 VERSATILITY TEAMS ===")
combined %>%
  slice_tail(n = 10) %>%
  transmute(
    team              = team_short_display_name,
    versatility_score = round(versatility_score, 3),
    cv_Shooting       = round(cv_Shooting, 3),
    cv_Ball_Care      = round(cv_Ball_Care, 3),
    cv_Rebounding     = round(cv_Rebounding, 3),
    cv_Free_Throws    = round(cv_Free_Throws, 3),
    cv_Def_Quality    = round(cv_Def_Quality, 3)
  ) %>%
  print(n = 10)


# ============================================================================
# RAW-VS-RESIDUAL COMPARISON
#
# How much does opponent adjustment change the rankings?
# We run the same clustering pipeline on RAW features (without opponent
# adjustment) and compare the resulting entropy rankings to the residual-based
# rankings using Spearman rank correlation.
#
# Large rank changes identify teams whose apparent versatility was inflated
# or deflated by schedule heterogeneity.
# ============================================================================

if (USE_RESIDUALS) {
  message("\n=== RAW-VS-RESIDUAL COMPARISON ===")
  message("Running parallel clustering on RAW features for comparison...")

  # Standardize raw features
  raw_means <- wf_eligible %>% select(all_of(ALL_FEATURES)) %>% colMeans()
  raw_sds   <- wf_eligible %>% select(all_of(ALL_FEATURES)) %>%
    summarise(across(everything(), sd)) %>% unlist()

  raw_z_mat <- wf_eligible %>%
    select(all_of(ALL_FEATURES)) %>%
    scale(center = raw_means, scale = raw_sds) %>%
    as.matrix()

  # ICC on raw features for weighting
  raw_icc <- sapply(ALL_FEATURES, function(f) compute_icc(wf_eligible, f))
  raw_icc_wts <- pmax(sqrt(pmax(0, raw_icc[ALL_FEATURES])), 0.1)

  raw_scaled <- sweep(raw_z_mat, 2, raw_icc_wts, FUN = "*")

  set.seed(42)
  km_raw <- kmeans(raw_scaled, centers = N_ARCHETYPES, nstart = 50, iter.max = 200)

  # Per-team entropy from raw clustering
  raw_archetypes <- wf_eligible %>%
    mutate(raw_arch = km_raw$cluster) %>%
    group_by(team_id, team_short_display_name) %>%
    summarise(
      raw_entropy_norm = weighted_entropy(raw_arch, closeness_weight) / max_entropy,
      .groups = "drop"
    )

  # Compare raw vs residual rankings
  comparison <- combined %>%
    select(team_id, team_short_display_name, resid_entropy = entropy_norm,
           resid_versatility = versatility_score) %>%
    inner_join(raw_archetypes, by = c("team_id", "team_short_display_name")) %>%
    mutate(
      rank_resid = rank(-resid_entropy),
      rank_raw   = rank(-raw_entropy_norm),
      rank_delta = rank_raw - rank_resid  # positive = opponent adj moved them UP
    ) %>%
    arrange(desc(abs(rank_delta)))

  rho_raw_resid <- cor(comparison$resid_entropy, comparison$raw_entropy_norm,
                       method = "spearman")
  message("Spearman rank correlation (raw vs residual entropy): ",
          round(rho_raw_resid, 3))

  message("\n=== TEAMS MOST AFFECTED BY OPPONENT ADJUSTMENT ===")
  message("(positive rank_delta = opponent adjustment INCREASED perceived versatility)")
  comparison %>%
    slice_head(n = 15) %>%
    transmute(
      team           = team_short_display_name,
      rank_residual  = rank_resid,
      rank_raw       = rank_raw,
      rank_delta     = rank_delta,
      ent_residual   = round(resid_entropy, 3),
      ent_raw        = round(raw_entropy_norm, 3)
    ) %>%
    print(n = 15)

  # Save comparison
  raw_resid_comparison <- comparison
} else {
  message("\n(Raw-vs-residual comparison skipped: USE_RESIDUALS = FALSE)")
  raw_resid_comparison <- NULL
}


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
    title    = "Win Profile Versatility: Entropy of Style Distribution",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 Min ", MIN_WINS,
                      " wins \u00b7 ICC-weighted clustering",
                      if (USE_RESIDUALS) " \u00b7 Opponent-adjusted" else "",
                      " \u00b7 Closeness-weighted entropy\n",
                      "Entropy normalized 0\u2013100%: 100% = wins spread equally across all ",
                      N_ARCHETYPES, " styles"),
    x = "Normalized Entropy (0 = one-way winner, 100% = equally versatile)",
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


# --- Plot 2: Archetype centroid heatmap (using unweighted z-scores for labeling) ---

# Build feature label vectors for the active feature set
heatmap_nice <- FEATURE_NICE[CLUSTER_FEATURES]
heatmap_off  <- OFF_CLUSTER_FEATURES
heatmap_def  <- DEF_CLUSTER_FEATURES

centroid_long <- as.data.frame(unweighted_centers) %>%
  mutate(archetype = row_number()) %>%
  left_join(arch_names, by = "archetype") %>%
  pivot_longer(all_of(CLUSTER_FEATURES), names_to = "feature", values_to = "z_score") %>%
  mutate(
    feature_label = FEATURE_NICE[feature],
    icc_wt = icc_weights[feature],
    feature_group = if_else(feature %in% heatmap_off, "Offense", "Defense"),
    feature_label_icc = paste0(feature_label, "\n(ICC wt: ", round(icc_wt, 2), ")"),
    feature_label     = factor(feature_label, levels = heatmap_nice),
    feature_label_icc = factor(feature_label_icc,
                               levels = paste0(heatmap_nice,
                                               "\n(ICC wt: ",
                                               round(icc_weights[CLUSTER_FEATURES], 2),
                                               ")"))
  )

z_max <- max(abs(centroid_long$z_score)) * 1.05

p2 <- centroid_long %>%
  ggplot(aes(x = feature_label_icc, y = reorder(arch_label, archetype), fill = z_score)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = round(z_score, 2)), size = 2.8, color = "grey20") +
  scale_fill_gradient2(
    low = "#2563eb", mid = "white", high = "#dc2626",
    midpoint = 0, limits = c(-z_max, z_max),
    name = "z-score\n(vs league)"
  ) +
  facet_grid(. ~ feature_group, scales = "free_x", space = "free_x") +
  labs(
    title    = "Style Profiles: What Each Winning Pattern Looks Like",
    subtitle = paste0(
      if (USE_RESIDUALS) "Opponent-adjusted residuals \u00b7 " else "",
      "ICC-weighted k-means centroids (shown as unweighted z-scores) \u00b7 ",
      N_ARCHETYPES, " styles\n",
      "Red = above league avg, Blue = below \u00b7 ",
      "ICC weight shown in parentheses (higher = more team-identity signal)"),
    x = NULL, y = NULL
  ) +
  theme_minimal(base_size = 10) +
  theme(
    axis.text.x      = element_text(angle = 35, hjust = 1, size = 8),
    strip.text       = element_text(face = "bold"),
    panel.grid       = element_blank(),
    plot.title       = element_text(face = "bold")
  ) +
  WHITE_THEME

ggsave("plots/02_archetype_profiles.png", p2, width = 12, height = 5, dpi = 150)
message("Saved: plots/02_archetype_profiles.png")


# --- Plot 3: Archetype composition stacked bars (top 25 by entropy) ---

arch_share_cols <- paste0("arch_share_", 1:N_ARCHETYPES)
arch_share_cols_present <- intersect(arch_share_cols, names(combined))

top25_entropy <- combined %>%
  slice_max(entropy_norm, n = 25) %>%
  mutate(team_label = team_conf_label(team_short_display_name, conference_short_name),
         team_ordered = reorder(team_label, entropy_norm))

arch_comp_long <- top25_entropy %>%
  select(team_short_display_name, team_label, team_ordered, entropy_norm, versatility_score,
         all_of(arch_share_cols_present)) %>%
  pivot_longer(all_of(arch_share_cols_present),
               names_to = "arch_col", values_to = "share") %>%
  mutate(archetype = as.integer(str_extract(arch_col, "\\d+"))) %>%
  left_join(arch_names, by = "archetype") %>%
  mutate(arch_label = factor(arch_label))

p3_vscore_labels <- top25_entropy %>%
  select(team_ordered, versatility_score)

p3 <- arch_comp_long %>%
  ggplot(aes(x = share, y = team_ordered, fill = arch_label)) +
  geom_col(width = 0.75) +
  geom_text(
    data = p3_vscore_labels,
    aes(x = 1.01, y = team_ordered, label = sprintf("%.3f", versatility_score), fill = NULL),
    hjust = 0, size = 3, color = "grey30", inherit.aes = FALSE
  ) +
  scale_fill_brewer(palette = "Set2", name = "Style") +
  scale_x_continuous(labels = scales::percent, expand = expansion(mult = c(0, 0.08))) +
  labs(
    title    = "How The Most Versatile Teams Win",
    subtitle = paste0("The weighted share of wins in each style (all teams have 20+ wins) \u00b7 Score = versatility score"),
    x = "Weighted share of wins in each style", y = NULL
  ) +
  theme_minimal(base_size = 10) +
  theme(
    plot.title      = element_text(face = "bold"),
    legend.position = "right"
  ) +
  WHITE_THEME

ggsave("plots/03_archetype_composition.png", p3, width = 11, height = 9, dpi = 150)
message("Saved: plots/03_archetype_composition.png")


# --- Plot 4: Archetype concentration (HHI vs Entropy) ---
# Replaces the bimodality scatter from v4.
# This shows whether high-entropy teams are genuinely spread out (low HHI)
# or just have noisy assignments.

conc_labels <- combined %>% {
  unique(c(
    slice_max(., entropy_norm,      n = 8)$team_short_display_name,
    slice_min(., entropy_norm,      n = 5)$team_short_display_name,
    slice_max(., versatility_score, n = 5)$team_short_display_name,
    # Label teams where entropy and HHI disagree most
    slice_max(., abs(entropy_norm - spread_score), n = 5)$team_short_display_name
  ))
}

p4 <- combined %>%
  ggplot(aes(x = entropy_norm, y = hhi)) +
  geom_point(aes(size = n_wins, color = conf_tier), alpha = 0.5) +
  scale_color_manual(values = TIER_COLORS, name = "Conference Tier") +
  geom_text_repel(
    data = combined %>%
      filter(team_short_display_name %in% conc_labels),
    aes(label = team_short_display_name),
    size = 2.3, max.overlaps = 20, color = "grey20",
    segment.color = "grey60", segment.size = 0.3
  ) +
  # Reference lines: even distribution values
  geom_hline(yintercept = 1/N_ARCHETYPES, linetype = "dashed",
             color = "#16a34a", linewidth = 0.5, alpha = 0.7) +
  annotate("text",
           x = min(combined$entropy_norm, na.rm = TRUE) + 0.01,
           y = 1/N_ARCHETYPES + 0.008,
           label = paste0("HHI = ", round(1/N_ARCHETYPES, 2),
                          " (perfectly even across ", N_ARCHETYPES, " styles)"),
           size = 2.2, color = "#16a34a", hjust = 0) +
  scale_y_reverse() +  # lower HHI (more spread) at top
  labs(
    title    = "Archetype Concentration vs Entropy",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 ICC-weighted clustering",
                      if (USE_RESIDUALS) " \u00b7 Opponent-adjusted" else "",
                      "\n",
                      "Lower HHI = more evenly spread across archetypes; ",
                      "y-axis inverted so 'best' is top-right"),
    x = "Normalized Entropy (higher = more archetypes used)",
    y = "HHI (lower = more even distribution across archetypes)",
    size    = "Wins",
    caption = "Data: ESPN via wehoop"
  ) +
  theme_minimal(base_size = 11) +
  theme(plot.title = element_text(face = "bold")) +
  WHITE_THEME

ggsave("plots/04_archetype_concentration.png", p4, width = 10, height = 8, dpi = 150)
message("Saved: plots/04_archetype_concentration.png")


# --- Plot 5: Composite versatility score ranking ---

versatility_labels <- combined %>%
  slice_max(versatility_score, n = 20) %>%
  pull(team_short_display_name)

p5_data <- combined %>% filter(!is.na(versatility_score))
ent_med  <- median(p5_data$entropy_norm, na.rm = TRUE)
spr_med  <- median(p5_data$spread_score, na.rm = TRUE)
ent_xq   <- quantile(p5_data$entropy_norm, c(0.05, 0.92), na.rm = TRUE)
spr_yq   <- quantile(p5_data$spread_score, c(0.05, 0.92), na.rm = TRUE)

p5 <- p5_data %>%
  ggplot(aes(x = entropy_norm, y = spread_score)) +
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
  geom_hline(yintercept = spr_med, linetype = "dashed", color = "grey50", linewidth = 0.4) +
  # Diagonal = equal versatility contribution
  geom_abline(slope = 1, intercept = 0, linetype = "dotted",
              color = "#6b21a8", linewidth = 0.4, alpha = 0.6) +
  # Quadrant labels
  annotate("label",
           x = ent_xq[1], y = spr_yq[2],
           label = "Spread Across\nFew Styles",
           size = 2.6, fill = alpha("#fef3c7", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[2], y = spr_yq[2],
           label = "Truly Versatile\n(high entropy + low concentration)",
           size = 2.6, fill = alpha("#dcfce7", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[1], y = spr_yq[1],
           label = "One-Mode\nSpecialist",
           size = 2.6, fill = alpha("#fee2e2", 0.9), label.size = 0) +
  annotate("label",
           x = ent_xq[2], y = spr_yq[1],
           label = "Uses Many Styles\nbut One Dominates",
           size = 2.6, fill = alpha("#dbeafe", 0.9), label.size = 0) +
  labs(
    title    = "Win Versatility: Entropy vs Concentration",
    subtitle = paste0("2025-26 NCAA WBB \u00b7 Versatility = 0.5\u00d7Entropy + 0.5\u00d7Spread",
                      "\nDashed lines = sample medians; diagonal = equal contribution from both"),
    x = "Normalized Entropy (spread across styles)",
    y = "Spread Score (1 - normalized HHI; higher = less concentrated)",
    size    = "Wins",
    caption = "Data: ESPN via wehoop"
  ) +
  theme_minimal(base_size = 11) +
  theme(plot.title = element_text(face = "bold")) +
  WHITE_THEME

ggsave("plots/05_versatility_composite.png", p5, width = 10, height = 8, dpi = 150)
message("Saved: plots/05_versatility_composite.png")


# --- Plot 6: Sensitivity analysis heatmap ---
# Show how rank correlations change across closeness scales

rank_cor_long <- as.data.frame(rank_cor_mat) %>%
  mutate(scale_y = rownames(.)) %>%
  pivot_longer(-scale_y, names_to = "scale_x", values_to = "rho") %>%
  mutate(
    scale_x = factor(scale_x, levels = gsub("scale_", "", scale_cols)),
    scale_y = factor(scale_y, levels = rev(gsub("scale_", "", scale_cols)))
  )

p6 <- rank_cor_long %>%
  ggplot(aes(x = scale_x, y = scale_y, fill = rho)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = round(rho, 3)), size = 3.2, color = "grey20") +
  scale_fill_gradient2(
    low = "#ef4444", mid = "#fef3c7", high = "#16a34a",
    midpoint = 0.9, limits = c(min(rank_cor_long$rho) - 0.01, 1),
    name = "Spearman \u03c1"
  ) +
  labs(
    title    = "Closeness-Scale Sensitivity: Rank Correlation Matrix",
    subtitle = paste0("Spearman rank correlation of team entropy rankings\n",
                      "across closeness scales (5 = tight weighting, Inf = unweighted)"),
    x = "Closeness Scale", y = "Closeness Scale",
    caption = paste0("High correlations (>0.95) = weighting is cosmetic; ",
                     "lower correlations = weighting changes ranking meaningfully")
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title  = element_text(face = "bold"),
    panel.grid  = element_blank()
  ) +
  WHITE_THEME

ggsave("plots/06_sensitivity_heatmap.png", p6, width = 7, height = 6, dpi = 150)
message("Saved: plots/06_sensitivity_heatmap.png")


# --- Plot 7: ICC feature weights bar chart ---

p7 <- icc_table %>%
  mutate(feature_label = FEATURE_NICE[feature],
         feature_label = factor(feature_label, levels = rev(FEATURE_NICE[icc_table$feature]))) %>%
  ggplot(aes(x = icc, y = feature_label)) +
  geom_col(aes(fill = icc), width = 0.7) +
  geom_text(aes(label = round(icc, 3)), hjust = -0.1, size = 3.2) +
  scale_fill_gradient(low = "#f87171", high = "#16a34a", name = "ICC",
                      limits = c(0, max(icc_table$icc) * 1.1)) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.15))) +
  labs(
    title    = "Feature Signal-to-Noise: Intraclass Correlation (ICC)",
    subtitle = paste0("Higher ICC = more between-team signal (team identity)\n",
                      "Lower ICC = more within-team noise (game-to-game randomness)\n",
                      "sqrt(ICC) used as clustering weight (floored at 0.10)"),
    x = "ICC(1)", y = NULL,
    caption = "ICC(1) computed from one-way random effects model across all eligible teams"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title      = element_text(face = "bold"),
    legend.position = "none"
  ) +
  WHITE_THEME

ggsave("plots/07_icc_feature_weights.png", p7, width = 8, height = 5, dpi = 150)
message("Saved: plots/07_icc_feature_weights.png")


# --- Plot 8: Raw vs Residual rank comparison (only when USE_RESIDUALS) ---

if (USE_RESIDUALS && !is.null(raw_resid_comparison)) {

  # Label teams with largest rank movement and top/bottom teams
  rr_labels <- raw_resid_comparison %>% {
    unique(c(
      slice_head(., n = 10)$team_short_display_name,  # biggest movers
      slice_max(., resid_entropy, n = 5)$team_short_display_name,
      slice_min(., resid_entropy, n = 5)$team_short_display_name
    ))
  }

  p8 <- raw_resid_comparison %>%
    left_join(
      combined %>% select(team_id, conf_tier, n_wins),
      by = "team_id"
    ) %>%
    ggplot(aes(x = raw_entropy_norm, y = resid_entropy)) +
    geom_abline(slope = 1, intercept = 0, linetype = "dashed",
                color = "grey50", linewidth = 0.5) +
    geom_point(aes(size = n_wins, color = conf_tier), alpha = 0.5) +
    scale_color_manual(values = TIER_COLORS, name = "Conference Tier") +
    geom_text_repel(
      data = raw_resid_comparison %>%
        left_join(combined %>% select(team_id, conf_tier, n_wins), by = "team_id") %>%
        filter(team_short_display_name %in% rr_labels),
      aes(label = team_short_display_name),
      size = 2.3, max.overlaps = 20, color = "grey20",
      segment.color = "grey60", segment.size = 0.3
    ) +
    annotate("label",
             x = quantile(raw_resid_comparison$raw_entropy_norm, 0.08),
             y = quantile(raw_resid_comparison$resid_entropy, 0.92),
             label = "Opponent adj\nINCREASED\nversatility",
             size = 2.4, fill = alpha("#dcfce7", 0.9), label.size = 0) +
    annotate("label",
             x = quantile(raw_resid_comparison$raw_entropy_norm, 0.92),
             y = quantile(raw_resid_comparison$resid_entropy, 0.08),
             label = "Opponent adj\nDECREASED\nversatility",
             size = 2.4, fill = alpha("#fee2e2", 0.9), label.size = 0) +
    labs(
      title    = "Impact of Opponent Adjustment on Win Versatility",
      subtitle = paste0("2025-26 NCAA WBB \u00b7 Spearman \u03c1 = ",
                        round(rho_raw_resid, 3),
                        "\nDashed line = no change from adjustment; ",
                        "distance from line = adjustment impact"),
      x = "Entropy (raw features, no opponent adjustment)",
      y = "Entropy (opponent-adjusted residuals)",
      size = "Wins",
      caption = paste0("Teams above the line appear MORE versatile after opponent adjustment;\n",
                       "teams below the line had schedule-inflated versatility")
    ) +
    theme_minimal(base_size = 11) +
    theme(plot.title = element_text(face = "bold")) +
    WHITE_THEME

  ggsave("plots/08_raw_vs_residual.png", p8, width = 10, height = 8, dpi = 150)
  message("Saved: plots/08_raw_vs_residual.png")
}


# ============================================================================
# SAVE OUTPUTS
# ============================================================================

dir.create("output", showWarnings = FALSE)

write_csv(team_archetypes,        "output/team_archetypes_v5_2026.csv")
write_csv(cv_composites,          "output/cv_composites_v5_2026.csv")
write_csv(combined,               "output/combined_win_variance_v5_2026.csv")
write_csv(arch_names,             "output/archetype_labels_v5_2026.csv")
write_csv(icc_table,              "output/icc_feature_weights_2026.csv")
write_csv(sensitivity_entropies,  "output/sensitivity_entropies_2026.csv")
write_csv(rank_movement,          "output/sensitivity_rank_movement_2026.csv")
if (USE_RESIDUALS && !is.null(raw_resid_comparison)) {
  write_csv(raw_resid_comparison, "output/raw_vs_residual_comparison_2026.csv")
}

message("\n\u2713 Done. Results in output/, plots in plots/")
message("\nKey output files:")
message("  output/combined_win_variance_v5_2026.csv  \u2014 Full combined table")
message("  output/icc_feature_weights_2026.csv       \u2014 ICC and clustering weights per feature")
message("  output/sensitivity_entropies_2026.csv     \u2014 Entropy at each closeness scale")
message("  output/sensitivity_rank_movement_2026.csv \u2014 Teams that move most across scales")
if (USE_RESIDUALS) {
  message("  output/raw_vs_residual_comparison_2026.csv \u2014 Rank impact of opponent adjustment")
}
message("\nKey plots:")
message("  plots/01_entropy_ranking.png          \u2014 Most/least versatile by entropy")
message("  plots/02_archetype_profiles.png       \u2014 Archetype centroids with ICC weights shown")
message("  plots/03_archetype_composition.png    \u2014 Win distribution for top-25 teams")
message("  plots/04_archetype_concentration.png  \u2014 HHI vs entropy (replaces bimodality)")
message("  plots/05_versatility_composite.png    \u2014 Entropy vs spread joint view")
message("  plots/06_sensitivity_heatmap.png      \u2014 Rank stability across closeness scales")
message("  plots/07_icc_feature_weights.png      \u2014 Feature signal-to-noise ratios")
if (USE_RESIDUALS) {
  message("  plots/08_raw_vs_residual.png          \u2014 Impact of opponent adjustment on rankings")
}
