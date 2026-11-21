"""Train the final model on all labeled FR cohorts and score the 2025-26 freshman class.

Output: freshman_watchlist_2026.csv — 2025-26 freshmen ranked by predicted
sophomore-season impact (a 2026-27 breakout watchlist). A true 2026-27 freshman
ranking requires a full in-season scrape (wbb players -s 2026-27); the 5-game
players27.csv sample is far too small to rank reliably.
"""

import sys
from pathlib import Path

import unicodedata

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def fix_mojibake(s):
    s = str(s or "")
    try:  # lossless if the string was UTF-8 bytes misread as latin1, else unchanged
        fixed = s.encode("latin1").decode("utf-8")
        if fixed != s:
            return unicodedata.normalize("NFC", fixed)
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return unicodedata.normalize("NFC", s)

sys.path.insert(0, str(Path(__file__).parent))
import features as F
import outcome as O

HERE = Path(__file__).parent
MIN_MP = 150


def main():
    panel = pd.read_csv(HERE / "panel.csv")
    panel = O.add_outcome(panel)
    df = F.prepare(panel, min_mp=MIN_MP)

    labeled = df[df["has_next_season"] & df["impact_composite"].notna()]
    target = df[df["Season"] == "2025-2026"].copy()

    X_train = F.feature_matrix(labeled).values
    y_train = labeled["impact_composite"].values
    model = Ridge(alpha=1.0).fit(X_train, y_train)

    target = target.assign(predicted_composite=model.predict(F.feature_matrix(target).values))
    target = target.sort_values("predicted_composite", ascending=False).reset_index(drop=True)
    target["percentile"] = target["predicted_composite"].rank(pct=True) * 100
    target["rank"] = target.index + 1
    target["tier"] = np.select(
        [target["rank"] <= 25, target["rank"] <= 50, target["rank"] <= 100],
        ["breakout candidate", "watch closely", "on the radar"],
        default="")
    target["low_minutes"] = target["MP"] < MIN_MP

    for c in ["Player", "Team", "High School", "Hometown"]:
        target[c] = target[c].map(fix_mojibake)
    cols = ["rank", "Player", "Team", "Conference", "Pos", "G", "MP", "mpg",
            "TS%", "USG%", "BPM", "WS/40", "predicted_composite", "percentile", "tier",
            "low_minutes", "High School", "Hometown"]
    out = target[cols].copy()
    out.columns = ["rank", "player", "team", "conference", "pos", "g", "mp", "mpg",
                   "ts_pct", "usg_pct", "bpm", "ws_per_40", "predicted_composite",
                   "percentile", "tier", "low_minutes", "high_school", "hometown"]
    path = HERE / "freshman_watchlist_2026.csv"
    out.to_csv(path, index=False, float_format="%.3f")
    print(f"wrote {path} ({len(out)} players, MP>={MIN_MP} for training; watchlist includes all 2025-26 FRs ranked)")
    print(out.head(25).to_string(index=False))


if __name__ == "__main__":
    main()
