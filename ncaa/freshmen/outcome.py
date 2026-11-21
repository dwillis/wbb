"""Composite outcome: next-season (sophomore) impact.

Weights are deliberately simple and documented. MP growth captures rising role
(minutes are the coach's revealed confidence signal); WS/40 and BPM capture
per-possession value; PER is a stable season-level anchor. Composite is z-scored
within each FR cohort so seasons are comparable.
"""

import numpy as np
import pandas as pd

# next_PER is excluded: r=0.90 with next WS/40 (redundant). Weights renormalized.
WEIGHTS = {
    "next_ws40_z": 0.5,
    "next_bpm_z": 0.3,
    "next_mp_growth_z": 0.2,
}


def add_outcome(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    df["next_ws40"] = pd.to_numeric(df["next_WS/40"], errors="coerce")
    df["next_bpm"] = pd.to_numeric(df["next_BPM"], errors="coerce")
    df["next_per"] = pd.to_numeric(df["next_PER"], errors="coerce")
    df["next_mp_growth"] = df["next_MP"] - df["MP"]

    def z_within(s: pd.Series, g: pd.Series) -> pd.Series:
        return s.groupby(g).transform(lambda x: (x - x.mean()) / (x.std(ddof=0) or 1.0))

    for src, dst in [("next_ws40", "next_ws40_z"), ("next_bpm", "next_bpm_z"),
                     ("next_mp_growth", "next_mp_growth_z"), ("next_per", "next_per_z")]:
        df[dst] = z_within(df[src], df["Season"])

    df["impact_composite"] = sum(df[k] * w for k, w in WEIGHTS.items())
    df["breakout"] = df.groupby("Season")["impact_composite"].transform(
        lambda s: s >= s.quantile(0.75))
    return df
