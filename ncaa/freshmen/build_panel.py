"""Build the freshman panel: one row per FR-season 2017-18 through 2025-26.

Sources:
  ncaa/players/playersNN.csv  -> season stats (Sports-Reference export)
  ncaa/games/wbbstatsNN.csv   -> team SRS/SOS/minutes/win pct
  ncaa/rosters/rosters_YYYY-YY.csv (cross-check only, logged, never used to fill)

Outputs:
  ncaa/freshmen/panel.csv     -> one row per freshman season, with next-season outcome columns
  ncaa/freshmen/build_log.txt -> mismatch/drop counts (nothing is silently dropped)
"""

import csv
import logging
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NCAA = ROOT / "ncaa"
OUT_DIR = Path(__file__).resolve().parent


import unicodedata

def fold_ascii(s):
    s = str(s or "")
    if any(m in s for m in ("â", "Ã", "Â", "ðŸ")):
        try:
            s = s.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

FILE_SEASON = {18: "2017-2018", 19: "2018-2019", 20: "2019-2020", 21: "2020-2021",
               22: "2021-2022", 23: "2022-2023", 24: "2023-2024", 25: "2024-2025",
               26: "2025-2026"}
NEXT_SEASON = {v: f"{int(v[:4]) + 1}-{int(v[5:]) + 1}" for v in FILE_SEASON.values()}
COVID_SEASON = "2020-2021"

NUMERIC_COLS = ["#", "G", "GS", "MP", "FG", "FGA", "FG%", "3P", "3PA", "3P%", "2P", "2PA", "2P%",
                "eFG%", "FT", "FTA", "FT%", "ORB", "DRB", "TRB", "AST", "STL", "BLK", "TOV", "PF",
                "PTS", "PER", "TS%", "3PAr", "FTr", "PProd", "ORB%", "DRB%", "TRB%",
                "AST%", "STL%", "BLK%", "TOV%", "USG%", "OWS", "DWS", "WS", "WS/40",
                "OBPM", "DBPM", "BPM"]
NEXT_COLS = ["G", "GS", "MP", "PTS", "PER", "TS%", "USG%", "TRB%", "AST%", "STL%", "BLK%",
             "TOV%", "WS", "WS/40", "OWS", "DWS", "OBPM", "DBPM", "BPM"]

logging.basicConfig(filename=OUT_DIR / "build_log.txt", filemode="w",
                    level=logging.INFO, format="%(message)s")
log = logging.getLogger()


def load_players():
    frames = []
    for yy, expected in FILE_SEASON.items():
        path = NCAA / "players" / f"players{yy}.csv"
        df = pd.read_csv(path, dtype=str)
        seasons = df["Season"].dropna().unique()
        if len(seasons) != 1 or seasons[0] != expected:
            log.warning("%s: Season col=%s (expected %s)", path.name, list(seasons), expected)
        for c in NUMERIC_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        dup = df.duplicated(subset=["player_id", "Season"]).sum()
        if dup:
            log.warning("%s: dropping %d duplicate (player_id, Season) rows", path.name, dup)
            df = df.drop_duplicates(subset=["player_id", "Season"], keep="first")
        frames.append(df)
        log.info("players%02d: %d rows, %d blank Class", yy, len(df), (df["Class"].fillna("") == "").sum())
    return pd.concat(frames, ignore_index=True)


def load_wbbstats():
    frames = []
    for yy, season in FILE_SEASON.items():
        path = NCAA / "games" / f"wbbstats{yy}.csv"
        df = pd.read_csv(path)
        df = df[["School", "OverallSRS", "OverallSOS", "Minutes", "WinPct", "Season"]].rename(
            columns={"School": "Team", "OverallSRS": "team_srs", "OverallSOS": "team_sos",
                     "Minutes": "team_minutes", "WinPct": "team_winpct"})
        df["Team"] = df["Team"].map(alnum_key)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def alnum_key(s):
    return re.sub(r"[^a-z0-9]", "", fold_ascii(s).lower())

def norm_name(s):
    s = fold_ascii(s).lower()
    s = re.sub(r"[^a-z ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_team(s):
    return alnum_key(s)


def norm_roster_year(s):
    s = str(s or "").lower().strip().rstrip(".")
    s = re.sub(r"[\s\-]+", "", s)
    if s.startswith(("fr", "fy", "fresh", "r-fr", "rfr", "rsfr")):
        return "Fr"
    if s.startswith(("so", "soph")):
        return "So"
    if s.startswith(("jr", "jun")):
        return "Jr"
    if s.startswith(("sr", "sen")):
        return "Sr"
    return s


def main():
    players = load_players()
    stats = load_wbbstats()

    # next-season outcome columns
    nxt = players[["player_id", "Season"] + NEXT_COLS].rename(
        columns={c: f"next_{c}" for c in NEXT_COLS})
    fr = players[players["Class"] == "FR"].copy()
    fr["next_season"] = fr["Season"].map(NEXT_SEASON)
    panel = fr.merge(nxt, left_on=["player_id", "next_season"],
                     right_on=["player_id", "Season"], how="left", suffixes=("", "_next"))
    panel = panel.drop(columns=["Season_next"])
    panel["has_next_season"] = panel["next_MP"].notna()
    log.info("FR rows: %d; with next-season data: %d (%.1f%%)",
             len(panel), panel["has_next_season"].sum(),
             100 * panel["has_next_season"].mean())

    # team context join (punctuation-insensitive team-name match)
    panel = panel.rename(columns={"Team": "Team_raw"})
    panel["Team"] = panel["Team_raw"].map(alnum_key)
    merged = panel.merge(stats, on=["Team", "Season"], how="left")
    unmatched = merged["team_srs"].isna().sum()
    log.info("team-context unmatched: %d / %d (%.1f%%)", unmatched, len(merged),
             100 * unmatched / max(len(merged), 1))
    if unmatched:
        miss = merged.loc[merged["team_srs"].isna(), ["Season", "Team"]].drop_duplicates()
        log.info("unmatched teams:\n%s", miss.to_string())
    panel = merged

    # roster cross-check (normalize season + names; never overwrite players data)
    roster_frames = []
    for path in sorted((NCAA / "rosters").glob("rosters_*.csv")):
        m = re.match(r"rosters_(\d{4})-(\d{2})\.csv", path.name)
        if not m:
            continue
        season = f"{m.group(1)}-{int(m.group(1)) + 1}"
        header = pd.read_csv(path, nrows=0).columns
        ycol = "academic_year" if "academic_year" in header else ("year" if "year" in header else None)
        if ycol is None:
            log.warning("roster file skipped (no year column): %s", path.name)
            continue
        r = pd.read_csv(path, dtype=str, usecols=["season", "team", "name", ycol],
                        on_bad_lines="skip").rename(columns={ycol: "year"})
        # roster season "2024-25" -> players season "2024-2025"
        r["season_players"] = r["season"].map(
            lambda s: f"{s.split('-')[0]}-{int(s.split('-')[0]) + 1}" if isinstance(s, str) and "-" in s else None)
        r = r.rename(columns={"academic_year": "year"})
        roster_frames.append(r)
    rosters = pd.concat(roster_frames, ignore_index=True)
    rosters["name_key"] = rosters["name"].map(norm_name)
    rosters["team_key"] = rosters["team"].map(norm_team)
    rosters["roster_year_norm"] = rosters["year"].map(norm_roster_year)
    rosters = rosters.drop_duplicates(subset=["season_players", "name_key", "team_key"])
    panel["name_key"] = panel["Player"].map(norm_name)
    panel["team_key"] = panel["Team_raw"].map(alnum_key) if "Team_raw" in panel else panel["Team"].map(alnum_key)
    panel = panel.merge(rosters[["season_players", "name_key", "team_key", "roster_year_norm"]],
                        left_on=["Season", "name_key", "team_key"],
                        right_on=["season_players", "name_key", "team_key"],
                        how="left").drop(columns=["season_players"])
    matched = panel["roster_year_norm"].notna().sum()
    agree = (panel["roster_year_norm"] == "Fr").sum()
    log.info("roster cross-check: matched %d / %d (%.1f%%); of matched, Freshman: %d (%.1f%%)",
             matched, len(panel), 100 * matched / len(panel), agree, 100 * agree / max(matched, 1))

    panel["covid_season"] = panel["Season"] == COVID_SEASON
    panel = panel.rename(columns={"Team": "team_key", "Team_raw": "Team"}).drop(columns=["name_key"])
    out = OUT_DIR / "panel.csv"
    panel.to_csv(out, index=False)
    log.info("wrote %s (%d rows)", out, len(panel))


if __name__ == "__main__":
    main()
