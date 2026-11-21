"""Feature engineering for the freshman model.

Z-scores are computed within each FR season (z-scoring the whole panel would
leak era effects). NaNs are median-imputed within season before z-scoring.
"""

import numpy as np
import pandas as pd

RATE_FEATURES = ["TS%", "eFG%", "USG%", "AST%", "STL%", "BLK%", "TOV%",
                 "ORB%", "DRB%", "TRB%", "WS/40", "BPM", "OBPM", "DBPM", "PER",
                 "3PAr", "FTr"]
CONTEXT_FEATURES = ["team_srs", "team_sos", "team_winpct"]
DERIVED_FEATURES = ["mpg", "gs_per_g", "minutes_share"]
FEATURES = RATE_FEATURES + CONTEXT_FEATURES + DERIVED_FEATURES


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["mpg"] = np.where(df["G"] > 0, df["MP"] / df["G"], np.nan)
    df["gs_per_g"] = np.where(df["G"] > 0, df["GS"] / df["G"], np.nan)
    df["minutes_share"] = np.where(df["team_minutes"] > 0, df["MP"] / df["team_minutes"], np.nan)
    return df


def prepare(panel: pd.DataFrame, min_mp: float = 150.0, exclude_covid: bool = False) -> pd.DataFrame:
    """Filter + z-score features. Returns df with z_<feat> columns added.

    Rows lacking outcome info are kept (needed for scoring new cohorts);
    callers separate them via has_next_season.
    """
    df = add_derived(panel)
    df = df[df["MP"].fillna(0) >= min_mp].copy()
    if exclude_covid:
        df = df[df["Season"] != "2020-2021"].copy()
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"z_{col}"] = (df.groupby("Season")[col]
                           .transform(lambda s: (s - s.median()) / (s.std(ddof=0) or 1.0)))
        df[f"z_{col}"] = df[f"z_{col}"].fillna(0.0)
    return df


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[[f"z_{c}" for c in FEATURES]].rename(columns=lambda c: c[2:])
