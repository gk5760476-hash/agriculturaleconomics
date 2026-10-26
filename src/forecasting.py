"""Stage-2 out-of-sample validation (design plan s.5.2-5.4; spec s.12.5, s.20.3).

State level: one-year-ahead forecasts of real agricultural credit growth by
rolling origin (expanding window: fit on years <= T, forecast T+1, T from the
first year with MIN_TRAIN observations). Shocks enter only with the timing
rule (monsoon t-1, crop year (t-1)-t, prices FY (t-1)-t are known by end-March
t, but a forecast made at end-March T for T+1 uses the shocks dated T+1, which
are observed only up to the monsoon of T - i.e. a nowcast made after the
monsoon; yield and price for T+1 are not yet final and are excluded from the
'ex-ante' model).

Models
  naive_mean   mean past growth ("credit grows at trend")    <- baseline to beat
  naive_last   last year's growth
  ar1          growth on lagged growth
  rain         growth on monsoon shortfall t-1 and t-2 (ex-ante: known by Oct of T)
  full         rain + yield shortfall + price fall (ex-post: needs crop-year data)

District level (Bihar): can the lag pattern rank districts? Fit growth on
shortfall t-2, t-3 with district + year effects on years <= T, predict each
district's deviation from the year mean at T+1, compare with a zero-deviation
naive forecast.

Usage:
    python -I src/forecasting.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from district_panel import _partial_out
from models import REPORTS
from transformations import PROCESSED

MIN_TRAIN = 10
STATE_MODELS = {
    "ar1": ["credit_real_growth_lag1_pct"],
    "rain": ["rain_shortfall_pct", "rain_shortfall_lag2_pct"],
    "full": ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "yield_shortfall_pct", "price_fall_pct"],
}
DROUGHT_CREDIT_YEARS = {"Bihar": [2010, 2011, 2014], "Maharashtra": [2015, 2016], "All-India": [2010, 2015, 2016]}


def _ols_predict(train, test, terms, outcome):
    X = np.column_stack([np.ones(len(train)), train[terms].to_numpy(float)])
    b = np.linalg.lstsq(X, train[outcome].to_numpy(float), rcond=None)[0]
    return float(np.r_[1.0, test[terms].to_numpy(float)] @ b)


def state_forecasts() -> pd.DataFrame:
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    y = "credit_real_growth_pct"
    rows = []
    for region, g in s.groupby("region"):
        g = g.dropna(subset=[y]).sort_values("year").reset_index(drop=True)
        for i in range(MIN_TRAIN, len(g)):
            train, test = g.iloc[:i], g.iloc[i]
            row = {"region": region, "year": int(test.year), "actual": test[y], "n_train": i,
                   "naive_mean": train[y].mean(), "naive_last": train[y].iloc[-1]}
            for name, terms in STATE_MODELS.items():
                tr = train.dropna(subset=terms)
                ok = not test[terms].isna().any() and len(tr) >= MIN_TRAIN - 1
                row[name] = _ols_predict(tr, test, terms, y) if ok else np.nan
            rows.append(row)
    f = pd.DataFrame(rows)
    f["drought_year"] = [y in DROUGHT_CREDIT_YEARS.get(r, []) for r, y in zip(f.region, f.year)]
    f.to_csv(REPORTS / "tables" / "forecast_state_oos.csv", index=False)
    return f


def score(f: pd.DataFrame) -> pd.DataFrame:
    rows = []
    models = ["naive_mean", "naive_last", *STATE_MODELS]
    for region, g in f.groupby("region"):
        ok = g[models].notna().all(axis=1)
        g = g[ok]
        base = np.abs(g.actual - g.naive_mean)
        for m in models:
            err = g.actual - g[m]
            d = np.abs(err) - base
            # Diebold-Mariano-type test on absolute-error differences (small sample: t with n-1 df)
            dm_p = 2 * stats.t.sf(abs(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))), len(d) - 1) if m != "naive_mean" and d.std() > 0 else np.nan
            rows.append({"region": region, "model": m, "n_forecasts": len(g), "years": f"{g.year.min()}-{g.year.max()}",
                         "mae": np.abs(err).mean(), "rmse": np.sqrt((err ** 2).mean()),
                         # design plan s.5.4 asks for MAPE; growth rates near zero inflate it, so MAE stays the headline
                         "mape": 100 * (np.abs(err) / np.abs(g.actual)).mean(),
                         "mae_vs_naive_mean": np.abs(err).mean() / base.mean(),
                         "wins_vs_naive_mean": int((np.abs(err) < base).sum()), "dm_p_vs_naive_mean": dm_p,
                         "mae_drought_years": np.abs(err[g.drought_year]).mean() if g.drought_year.any() else np.nan})
    out = pd.DataFrame(rows)
    out.to_csv(REPORTS / "tables" / "forecast_state_scores.csv", index=False)
    return out


def drought_holdout() -> pd.DataFrame:
    """Leave-one-drought-out (design plan s.5.4): fit on every other year, predict the held-out
    drought credit year. Uses future years too, so it tests fit, not real-time forecasting."""
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    y = "credit_real_growth_pct"
    rows = []
    for region, years in DROUGHT_CREDIT_YEARS.items():
        g = s[(s.region == region)].dropna(subset=[y])
        for yr in years:
            test = g[g.year == yr]
            if test.empty:
                continue
            test, train = test.iloc[0], g[g.year != yr]
            row = {"region": region, "held_out_year": yr, "monsoon_departure_pct": test.rain_departure_pct,
                   "actual": test[y], "naive_mean": train[y].mean()}
            for name, terms in STATE_MODELS.items():
                if name == "ar1":
                    continue
                tr = train.dropna(subset=terms)
                row[name] = _ols_predict(tr, test, terms, y) if not test[terms].isna().any() else np.nan
            for m in ["naive_mean", "rain", "full"]:
                row[f"abs_err_{m}"] = abs(row["actual"] - row[m])
            rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(REPORTS / "tables" / "forecast_drought_holdout.csv", index=False)
    return out


def district_ranking(state="Bihar", terms=("rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct")) -> pd.DataFrame:
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    p = p[~p.excluded & (p.state == state)].dropna(subset=["growth_direct", *terms])
    terms = list(terms)
    rows = []
    for T in range(p.year.min() + 5, p.year.max()):
        train, test = p[p.year <= T], p[p.year == T + 1]
        Z = _partial_out(train, ["growth_direct", *terms], ["unit_id", "state_year"])
        b = np.linalg.lstsq(Z[terms].to_numpy(), Z.growth_direct.to_numpy(), rcond=None)[0]
        # predicted deviation from the year mean: demean test shocks within the year
        xt = test[terms] - test[terms].mean()
        pred = xt.to_numpy() @ b
        actual = (test.growth_direct - test.growth_direct.mean()).to_numpy()
        rho = stats.spearmanr(pred, actual).statistic
        rows.append({"state": state, "forecast_year": T + 1, "districts": len(test),
                     "mae_model": np.abs(actual - pred).mean(), "mae_naive_zero": np.abs(actual).mean(),
                     "spearman_rank_corr": rho})
    out = pd.DataFrame(rows)
    out.to_csv(REPORTS / "tables" / "forecast_district_ranking.csv", index=False)
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    f = state_forecasts()
    print(score(f).round(3).to_string(index=False))
    print(drought_holdout().round(2).to_string(index=False))
    r = district_ranking()
    print(r.round(3).to_string(index=False))
    print("mean rank corr:", round(r.spearman_rank_corr.mean(), 3), " MAE model/naive:",
          round(r.mae_model.mean() / r.mae_naive_zero.mean(), 3),
          " t-test rank corr>0 p:", round(stats.ttest_1samp(r.spearman_rank_corr, 0).pvalue, 3))
