# Win Variance v5: Methodology Overview

**Data:** ESPN box scores via `wehoop`, 2025-26 NCAA WBB. Minimum 20 wins for inclusion. Season-average profiles are computed from all games; only winning games are classified into styles.

---

## Nine input features

Five offensive factors and four defensive factors, computed per game:

| | Feature | Formula |
|---|---------|---------|
| Off | eFG% | (FGM + 0.5 × 3PM) / FGA |
| Off | TOV% | TO / (FGA + 0.44 × FTA + TO) |
| Off | ORB% | ORB / (ORB + Opp DRB) |
| Off | FT Rate | FTM / FGA |
| Off | 3PA Rate | 3PA / FGA |
| Def | Opp eFG% | (Opp FGM + 0.5 × Opp 3PM) / Opp FGA |
| Def | Opp TOV% | Opp TO / (Opp FGA + 0.44 × Opp FTA + Opp TO) |
| Def | DRB% | DRB / (DRB + Opp ORB) |
| Def | Opp FT Rate | Opp FTM / Opp FGA |

---

## Opponent adjustment

Each game's raw features are converted to residuals against the opponent's season-average profile. For a win by Team A over Team B:

- **Offensive residual:** A's stat − B's season-average defensive stat (what B typically allows)
- **Defensive residual:** B's stat in this game − B's season-average offensive stat

Exception: DRB% is adjusted against the team's own season average, not the opponent's. Residuals isolate genuine performance deviation from opponent-driven noise. The Spearman rank correlation between raw and opponent-adjusted entropy rankings was 0.518.

---

## ICC feature weighting

Intraclass Correlation Coefficient (ICC-1) measures between-team signal as a share of total variance:

$$\text{ICC} = \frac{MS_b - MS_w}{MS_b + (k_0 - 1) \cdot MS_w}$$

Each feature is weighted by $\sqrt{\text{ICC}}$ in clustering, floored at 0.1. High-ICC features (stable team identifiers like 3PA Rate) receive more weight; low-ICC features (officiating-driven noise like Opp FT Rate) are damped.

---

## K-means clustering (five styles)

1. Z-score each residual feature across all eligible wins
2. Multiply by ICC weight
3. K-means, $k = 5$, 50 random starts, 200 max iterations

$k = 5$ selected via silhouette score evaluation across $k = 3$–$8$. Each win is assigned to one of five styles.

**Closeness weighting:** Each win is weighted by $w = 1 / (1 + \text{margin} / 10)$ so that close games carry more weight than blowouts.

---

## Versatility metrics

**Shannon entropy** of the closeness-weighted style distribution:

$$H = -\sum_{k=1}^{5} p_k \ln(p_k), \quad \text{normalized by } \ln(5)$$

**HHI** (Herfindahl-Hirschman Index) of style shares, normalized and inverted to a spread score:

$$\text{spread\_score} = 1 - \frac{\text{HHI} - 1/5}{1 - 1/5}$$

**Versatility score** (final ranking metric):

$$\text{versatility} = 0.5 \times \text{entropy\_norm} + 0.5 \times \text{spread\_score}$$

---

## Sensitivity analysis

Entropy rankings are recomputed at closeness scales $S \in \{5, 10, 20, 50, \infty\}$. Pairwise Spearman rank correlations across scales assess whether the $S = 10$ choice is consequential.

