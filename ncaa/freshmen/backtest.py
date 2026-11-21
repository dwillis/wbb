"""Forward-chaining backtest for the freshman impact model.

Usage: uv run --with scikit-learn python ncaa/freshmen/backtest.py [--min-mp 150] [--exclude-covid]

Trains on FR cohorts whose sophomore season is fully in the past, tests on the
next cohort. Baselines: rank by FR BPM, MP, WS/40. Writes backtest_results.csv.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
import features as F
import outcome as O

HERE = Path(__file__).parent


def load(min_mp, exclude_covid=False):
    panel = pd.read_csv(HERE / "panel.csv")
    panel = O.add_outcome(panel)
    df = F.prepare(panel, min_mp=min_mp, exclude_covid=exclude_covid)
    return df


def metrics(y_true, pred, breakout):
    rho = spearmanr(y_true, pred).statistic
    k = 20
    top_pred = set(np.argsort(-pred)[:k])
    top_true = set(np.argsort(-y_true.values)[:k])
    p_at_20 = len(top_pred & top_true) / k
    try:
        auc = roc_auc_score(breakout, pred)
    except ValueError:
        auc = np.nan
    return rho, p_at_20, auc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-mp", type=float, default=150.0)
    ap.add_argument("--exclude-covid", action="store_true")
    args = ap.parse_args()

    df = load(args.min_mp, args.exclude_covid)
    labeled = df[df["has_next_season"] & df["impact_composite"].notna()].copy()
    seasons = sorted(labeled["Season"].unique())
    print(f"cohorts: {seasons}  labeled rows: {len(labeled)}  (min_mp={args.min_mp}, exclude_covid={args.exclude_covid})")

    X = F.feature_matrix(labeled).values
    test_seasons = [s for s in seasons if s >= "2020-2021"]
    rows = []
    for test in test_seasons:
        tr = labeled["Season"] < test
        te = labeled["Season"] == test
        if tr.sum() < 200 or te.sum() < 50:
            continue
        Xtr, ytr = X[tr.values], labeled.loc[tr, "impact_composite"].values
        Xte = X[te.values]
        yte = labeled.loc[te, "impact_composite"]
        bte = labeled.loc[te, "breakout"].astype(int)

        ridge = Ridge(alpha=1.0).fit(Xtr, ytr)
        gbr = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05,
                                            max_depth=3, min_samples_leaf=20,
                                            random_state=0).fit(Xtr, ytr)
        preds = {"ridge": ridge.predict(Xte), "hist_gbr": gbr.predict(Xte),
                 "baseline_bpm": labeled.loc[te, "BPM"].fillna(0).values,
                 "baseline_mp": labeled.loc[te, "MP"].fillna(0).values,
                 "baseline_ws40": labeled.loc[te, "WS/40"].fillna(0).values}
        for name, pred in preds.items():
            rho, p20, auc = metrics(yte, pred, bte)
            rows.append({"test_season": test, "model": name, "spearman": round(rho, 3),
                         "precision@20": round(p20, 3), "auc_breakout": round(auc, 3),
                         "n_test": int(te.sum())})
        print(f"== {test} (n={te.sum()}, train={tr.sum()}) ==")
        for r in rows:
            if r["test_season"] == test:
                print(f"  {r['model']:<14} rho={r['spearman']:+.3f}  P@20={r['precision@20']:.2f}  AUC={r['auc_breakout']:.3f}")

    res = pd.DataFrame(rows)
    res.to_csv(HERE / "backtest_results.csv", index=False)
    print("\n== mean across folds ==")
    print(res.groupby("model")[["spearman", "precision@20", "auc_breakout"]].mean().round(3))
    print("\ncomposite component correlations (labeled rows):")
    comp = labeled[["next_ws40_z", "next_bpm_z", "next_mp_growth_z", "next_per_z"]].corr(method="spearman")
    print(comp.round(2))


if __name__ == "__main__":
    main()
