# Win Variance v5: Statistical Methods

This document explains each statistical method used in the win variance analysis, what problem it solves, and what it tells us about how teams win.

## The question

Can we measure whether a team wins in many different ways or in basically the same way every time? And can we do that without the answer being contaminated by schedule strength or noisy statistics?

## Data

Source: ESPN box scores via the `wehoop` package. One row per team per game for the 2025-26 NCAA WBB season. Both sides of each game are included so we can compute what the opponent did.

Teams must have at least 20 wins to be included in the final rankings. Features are computed from all games (wins and losses) for season averages, but only winning games are classified into archetypes.

---

## Step 1: Game-level features (the nine dimensions)

Each game is described by nine statistics that capture different aspects of how a team played:

**Five offensive factors:**

| Feature | Formula | What it measures |
|---------|---------|-----------------|
| eFG% | (FGM + 0.5 × 3PM) / FGA | Shooting efficiency, giving extra credit for threes |
| TOV% | TO / (FGA + 0.44 × FTA + TO) | Turnover rate per possession |
| ORB% | ORB / (ORB + Opp DRB) | Share of available offensive rebounds grabbed |
| FT Rate | FTM / FGA | Free throws made relative to shot attempts |
| 3PA Rate | 3PA / FGA | Share of shots taken from three-point range |

**Four defensive factors:**

| Feature | Formula | What it measures |
|---------|---------|-----------------|
| Opp eFG% | (Opp FGM + 0.5 × Opp 3PM) / Opp FGA | How efficiently opponents shoot against you |
| Opp TOV% | Opp TO / (Opp FGA + 0.44 × Opp FTA + Opp TO) | How often you force turnovers |
| DRB% | DRB / (DRB + Opp ORB) | Share of defensive rebounds secured |
| Opp FT Rate | Opp FTM / Opp FGA | How often opponents get to the free throw line against you |

These nine dimensions form the feature space for all downstream analysis.

---

## Step 2: Opponent adjustment (residuals)

**Problem:** A team's raw stats in a game reflect both how the team played and who they played. Beating a weak defensive team by shooting well doesn't tell us much. Shooting well against a great defense does.

**Method:** For each team, we compute season-average profiles from *all* their games:

- **Offensive profile:** What the team typically does (avg eFG%, avg TOV%, etc.)
- **Defensive profile:** What the team typically allows (avg Opp eFG%, avg Opp TOV%, etc.)

For each winning game where Team A beats Team B, we compute residuals:

- **Offensive residuals:** Team A's stat in this game minus Team B's season-average defensive stat (what B typically allows). Example: if A shot 52% eFG and B typically allows 45% eFG, the residual is +7 percentage points.
- **Defensive residuals:** What B did in this game minus B's season-average offensive stat. Example: if B shot 38% eFG in this game but averages 44%, the residual is -6 points — meaning A held B well below their norm.

One exception: DRB% is adjusted relative to the team's *own* season average, not the opponent's, because defensive rebounding depends more on your own positioning than on the opponent's offense.

**What it offers:** Residuals isolate how a team deviated from what was expected given the opponent. A team that beats weak opponents the same way every time will show small residuals and low variance. A team that genuinely adapts its approach will show varied residuals even after accounting for opponent quality.

**Impact:** The Spearman rank correlation between raw and opponent-adjusted entropy rankings was 0.518 — meaning opponent adjustment reshuffles the rankings substantially. It's not a cosmetic correction.

---

## Step 3: Intraclass Correlation Coefficient (ICC)

**Problem:** Not all nine features carry equal signal. Some features (like 3PA Rate) are stable team-identity markers — a team that shoots a lot of threes does so consistently. Other features (like FT Rate) are dominated by game-to-game noise from officiating randomness. Treating all features equally in clustering lets noisy features create meaningless clusters.

**Method:** ICC(1), a one-way random effects intraclass correlation, measures how much of a feature's total variance is between-team (signal) versus within-team (noise):

$$\text{ICC} = \frac{MS_b - MS_w}{MS_b + (k_0 - 1) \cdot MS_w}$$

where $MS_b$ is the between-team mean square, $MS_w$ is the within-team mean square, and $k_0$ is an adjusted group size that accounts for teams having different numbers of wins.

ICC ranges from 0 (all variance is within-team noise) to 1 (all variance is between teams). Features with high ICC reflect stable team identity; features with low ICC are game-level noise.

**How it's used:** Each feature is weighted by $\sqrt{\text{ICC}}$ in the clustering step. The square root moderates the effect — low-ICC features aren't zeroed out, just damped. A floor of 0.1 prevents any feature from being completely silenced.

**What it offers:** Clusters form around the features that actually distinguish team playing styles, rather than being driven by high-variance noise in things like foul rates.

---

## Step 4: K-means clustering (archetypes)

**Problem:** We want to classify each individual win into a "type" of win — an archetype — so we can ask whether a team's wins are all the same type or spread across several.

**Method:**

1. **Standardize:** Z-score each of the nine residual features across all eligible wins (mean 0, SD 1).
2. **Weight:** Multiply each z-scored column by its ICC weight from Step 3.
3. **Cluster:** Run k-means with $k = 5$ on the 9-dimensional weighted space. The algorithm uses 50 random starts and 200 max iterations to avoid local minima.

The choice of $k = 5$ is validated by checking silhouette scores (a cluster quality metric) for $k = 3$ through $k = 8$.

Each cluster centroid defines an archetype — a characteristic way of winning. Archetypes are labeled by their most distinctive feature (e.g., "High Δ eFG%" for a cluster centered on shooting well above what opponents typically allow).

**Closeness weighting:** Not all wins are equally informative. A 30-point blowout probably tells us less about a team's strategic range than a 3-point game where the team had to find a way to win. Each win is weighted by:

$$w = \frac{1}{1 + \text{margin} / S}$$

where $S$ is the closeness scale (default 10). A 10-point win gets weight 0.5; a 1-point win gets 0.91; a 30-point blowout gets 0.25.

**What it offers:** Five archetypes give us a vocabulary for describing *how* a team won a particular game — whether through elite shooting, defensive pressure, rebounding dominance, etc.

---

## Step 5: Shannon entropy

**Problem:** Given a team's distribution of wins across the five archetypes, we need a single number that captures how spread out or concentrated that distribution is.

**Method:** Closeness-weighted Shannon entropy:

$$H = -\sum_{k=1}^{5} p_k \ln(p_k)$$

where $p_k$ is the closeness-weighted share of wins in archetype $k$. This is normalized by dividing by $\ln(5)$ (the maximum possible entropy for 5 categories) to produce a 0-to-1 scale.

- **Entropy = 1:** Wins are perfectly evenly distributed across all five archetypes. Maximum versatility.
- **Entropy = 0:** All wins are in a single archetype. Complete specialization.

**What it offers:** A principled, information-theoretic measure of how many different ways a team wins. It's sensitive to both the number of archetypes used and the evenness of the distribution.

---

## Step 6: Herfindahl-Hirschman Index (HHI)

**Problem:** Entropy captures overall spread, but we also want a measure that's more sensitive to concentration at the top — does one archetype dominate?

**Method:** HHI is the sum of squared archetype shares:

$$\text{HHI} = \sum_{k=1}^{5} p_k^2$$

HHI ranges from $1/5 = 0.2$ (perfectly even) to $1.0$ (all wins in one archetype). We normalize to a 0–1 scale and invert to create a "spread score" where 1 = maximally spread out:

$$\text{spread\_score} = 1 - \frac{\text{HHI} - 1/K}{1 - 1/K}$$

**Why both entropy and HHI?** They capture different aspects of the same distribution. A team using 3 archetypes at 33% each has lower entropy than one using 5 at 20% each, but both have relatively low HHI. A team with one archetype at 50% and four at 12.5% has moderate entropy but higher HHI. Using both gives a more complete picture.

The **dominance ratio** (top share divided by second share) is also computed as a diagnostic. A ratio near 1 means the top two archetypes are balanced; a ratio much greater than 1 means one archetype dominates.

---

## Step 7: Versatility score

The final ranking metric is a simple average of the two archetype-distribution measures:

$$\text{versatility} = 0.5 \times \text{entropy\_norm} + 0.5 \times \text{spread\_score}$$

Both components come from the same archetype distribution but weight different aspects of it. The equal weighting is a deliberate choice to avoid over-tuning.

---

## Step 8: Closeness-scale sensitivity analysis

**Problem:** The closeness weighting (Step 4) uses a scale parameter $S = 10$. Is that choice consequential, or would a different scale produce essentially the same rankings?

**Method:** Re-compute entropy rankings at scales $S = 5, 10, 20, 50, \infty$ (where $\infty$ means all wins weighted equally). Compare rankings via pairwise Spearman rank correlations.

Teams with the largest rank changes between the tightest scale ($S = 5$, where only close games matter) and unweighted ($S = \infty$) are flagged. These are teams whose versatility picture changes depending on whether you focus on competitive games or blowouts.

**What it offers:** Transparency about a modeling choice. If the rankings are stable across scales, the closeness weighting is cosmetic. If they shift substantially, the weighting is doing real analytical work and the choice of scale matters.

---

## Step 9: CV profiles (diagnostic, not scored)

**Problem:** The versatility score tells us *whether* a team wins in varied ways, but not *which dimensions* vary. Two teams with the same versatility score might get there differently — one varying its shot selection game to game, the other varying its defensive intensity.

**Method:** Coefficient of variation (CV) — the ratio of weighted standard deviation to weighted mean — is computed for each of six "strategic dimensions" that group the raw box score stats:

| Dimension | Component stats |
|-----------|----------------|
| Shooting | eFG%, 3PA Rate |
| Ball Care | TOV%, Assist Rate |
| Rebounding | ORB%, DRB% |
| Free Throws | FT Attempt Rate, FT Accuracy |
| Scoring Mix | Paint Point Share, Fast Break Share |
| Defensive Quality | Opp eFG%, Opp TOV%, Opp FT Rate |

CV uses the closeness weights as reliability weights, computed using the formula:

$$\text{CV} = \frac{\sqrt{\text{Var}_w(x)}}{\bar{x}_w}$$

**What it offers:** A team-level profile showing which strategic levers a team varies from game to game and which it holds constant. This is purely diagnostic — it is not folded into the versatility score. The correlation between CV profiles and the versatility score is near zero (r ≈ 0.02), confirming they measure different things: the versatility score captures *archetype diversity*, while CVs capture *within-dimension variability*.

---

## Summary of what each method contributes

| Method | Problem it solves | Key output |
|--------|------------------|------------|
| Opponent adjustment | Schedule strength contaminates raw stats | Residual features per game |
| ICC weighting | Noisy features distort clusters | Per-feature reliability weights |
| K-means clustering | Need discrete "types" of wins | 5 archetypes per win |
| Shannon entropy | Quantify distribution spread | 0–1 versatility measure |
| HHI / spread score | Sensitivity to top-heavy concentration | 0–1 concentration measure |
| Closeness weighting | Blowouts are less informative | Per-game reliability weights |
| Sensitivity analysis | Is the closeness scale consequential? | Rank stability across scales |
| CV profiles | Which dimensions vary? | Per-team variability fingerprint |

---

## What this analysis does not do

- **It doesn't predict tournament success.** Versatility might help in March, or it might not. This analysis describes *how* teams win, not *how well* they'll do.
- **It doesn't account for roster changes.** A team that lost a starter mid-season might appear versatile because it played differently before and after the injury, not because of strategic flexibility.
- **It doesn't separate coaching intent from circumstance.** A team might win in varied ways because the coach adapts, or because the team is inconsistent. The data can't distinguish these.
- **It uses only box score data.** Play-by-play, lineup, and tracking data would add dimensions this analysis can't see.
