# Freshman Breakout Model (NCAA WBB)

Predicts which freshmen will have the biggest *sophomore-season* impact, from
freshman-season stats. Season-level v1 — no in-season game logs (that's v2).

## Question it answers

"Which 2025-26 freshmen are most likely to break out in 2026-27?"
Answer: `freshman_watchlist_2026.csv` (ranked, 719 players, model trained on
2017-18 through 2024-25 FR cohorts; validated forward-chaining).

**Honest caveat:** this is a *sophomore breakout* watchlist, not a prediction
of the 2026-27 freshman class — a true 2026-27 freshman list needs a full
in-season scrape (`wbb players -s 2026-27`); as of this writing players27.csv
is a 5-game / 5-team sample and cannot rank anyone reliably.

## TL;DR answer to "do I need time-based snapshots?"

No — not for v1. Season totals from 2018–2026 carry real signal (Ridge,
forward-chained backtest: Spearman ρ ≈ 0.66 vs 0.61 for a BPM-only baseline;
precision@20 ≈ 0.46 vs 0.43). Snapshots (monthly splits / minutes ramp) only
matter if you want *in-season* early detection — "flag her by December" — and
should be a v2 feature built from game-by-game data.

## Files

- `build_panel.py` — join players18–26 + wbbstats (team SRS/SOS/minutes) + roster cross-check → `panel.csv`, `build_log.txt`
- `features.py` — rate stats, per-game/minutes-share derivations, within-season z-scores
- `outcome.py` — composite sophomore-impact outcome (weights documented there)
- `backtest.py` — forward-chaining backtest vs baselines → `backtest_results.csv`
- `predict.py` — final model → `freshman_watchlist_2026.csv`
- `freshman_model.qmd` — rendered report

## Run

```bash
uv run python ncaa/freshmen/build_panel.py
uv run --with scikit-learn python ncaa/freshmen/backtest.py   # add --exclude-covid, --min-mp 100|200
uv run --with scikit-learn python ncaa/freshmen/predict.py
```

(scikit-learn is intentionally not added to `pyproject.toml`; `uv run --with` injects it.)

## Method in one paragraph

Target: composite of next-season (sophomore) **WS/40 (0.5) + BPM (0.3) + MP
growth (0.2)**, z-scored within cohort (PER was dropped — r=0.90 with WS/40).
Features: freshman-season rate stats (TS%, eFG%, USG%, AST/STL/BLK/TOV/TRB
percentages, BPM family, PER, WS/40), volume (MPG, GS/g, minutes share), and
team context (SRS, SOS, win pct), all z-scored within season. Model: ridge
regression (beat HistGradientBoosting on the backtest). Training cohorts
2017-18…2024-25; 2025-26 has no outcome yet and is the scoring cohort.

## Results (forward-chained, mean over folds 2020-21…2024-25)

| model | Spearman ρ | precision@20 | AUC (breakout) |
|---|---|---|---|
| ridge | 0.665 | 0.46 | 0.86 |
| hist gradient boosting | 0.649 | 0.44 | 0.86 |
| baseline: rank by FR BPM | 0.613 | 0.43 | 0.83 |
| baseline: rank by FR MP | 0.161 | 0.20 | 0.59 |

Robust to min-MP 100/150/200 and to dropping the COVID (2020-21) cohort.

## Known limitations

- No age data; redshirts appear as FR in a later year and aren't distinguished.
- MP threshold screens out true low-minute gems (watch `low_minutes` flag).
- 2020-21 shortened season included but flagged (`covid_season`).
- 30% of FRs have no next-season row (left school / did not play); they're
  excluded from training (censored, not failed).
- Roster cross-check only matches ~80% of rows (team-name variants); it is a
  sanity check, not a data source.
- Team context unmatched for 0 rows after ASCII/mojibake repair.
- Small-sample noise is real: treat rank 25–100 as "watch", not verdicts.
