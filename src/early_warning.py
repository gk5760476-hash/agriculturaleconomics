"""Transparent rules-based monitoring (spec s.12). A monitoring aid, not a forecast.

State level, for each region and credit year t (indicators known by end-March t):
    adverse agricultural indicators: monsoon t-1 deficient; yield below trend; real crop-price fall
    credit indicator: real agricultural credit growth weak
Categories
    Data insufficient  any of the four inputs missing
    Elevated concern   >= 2 adverse agricultural indicators, or any severe one, AND credit weak or
                       not yet observed; or >= 2 adverse agricultural indicators regardless of credit
    Watch              >= 1 adverse or weak-credit indicator
    Normal monitoring  none
Every row lists the indicators that fired.

District level (latest monsoon): drought flags for every district; Bihar districts with a
deficient monsoon 2-3 years ago are flagged 'Watch (lagged credit risk)' following the
district-panel estimates.

Backtest (spec s.12.5, s.20.3): does an agricultural-distress signal at t precede weak
credit growth at t+1? Reported as hit rate, false-alarm rate and precision vs the base rate.

Usage:
    python -I src/early_warning.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from ingestion import ROOT
from models import REPORTS
from transformations import PROCESSED

CFG = yaml.safe_load((ROOT / "config" / "project_config.yaml").read_text())["early_warning"]
CATEGORIES = ["Normal monitoring", "Watch", "Elevated concern", "Data insufficient"]


def state_signals() -> pd.DataFrame:
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    s = s[s.year >= 2006].copy()
    c = CFG
    sd = s.groupby("region")[["yield_shortfall_pct", "price_fall_pct"]].transform("std")
    s["ind_rain"] = s.rain_departure_pct <= c["rain"]["adverse_departure_pct"]
    s["ind_rain_severe"] = -s.rain_standardised_shortfall <= c["rain"]["severe_standardised_anomaly"]
    s["ind_yield"] = s.yield_shortfall_pct >= c["yield"]["adverse_sd"] * sd.yield_shortfall_pct
    s["ind_yield_severe"] = s.yield_shortfall_pct >= c["yield"]["severe_sd"] * sd.yield_shortfall_pct
    s["ind_price"] = s.price_fall_pct >= c["price"]["adverse_sd"] * sd.price_fall_pct
    s["ind_price_severe"] = s.price_fall_pct >= c["price"]["severe_sd"] * sd.price_fall_pct
    s["ind_credit_weak"] = s.credit_real_growth_pct < c["credit"]["weak_real_growth_pct"]
    s["ind_credit_severe"] = s.credit_real_growth_pct < c["credit"]["severe_real_growth_pct"]

    inputs = ["rain_departure_pct", "yield_shortfall_pct", "price_fall_pct", "credit_real_growth_pct"]
    rows = []
    for r in s.itertuples():
        missing = [k for k in inputs if pd.isna(getattr(r, k))]
        agri = [name for name, f in [("monsoon deficient", r.ind_rain), ("yield below trend", r.ind_yield),
                                     ("real crop-price fall", r.ind_price)] if f]
        severe = [name for name, f in [("severely dry monsoon", r.ind_rain_severe),
                                       ("yield > 2 SD below trend", r.ind_yield_severe),
                                       ("crop-price fall > 2 SD", r.ind_price_severe)] if f]
        credit = ["real credit contracted" + (" > 10%" if r.ind_credit_severe else "")] if r.ind_credit_weak else []
        if len(agri) >= 2 or (severe and credit) or (len(agri) >= 1 and r.ind_credit_severe):
            cat = "Elevated concern"
        elif agri or credit or severe:
            cat = "Watch"
        else:
            cat = "Normal monitoring"
        # missing inputs never hide a signal that did fire, but a quiet row with gaps is not 'Normal'
        if missing and cat == "Normal monitoring":
            cat = "Data insufficient"
        rows.append({"region": r.region, "year": r.year, "category": cat,
                     "indicators": "; ".join(agri + severe + credit) or "none",
                     "missing_inputs": "; ".join(missing),
                     "rain_departure_pct": r.rain_departure_pct, "yield_shortfall_pct": r.yield_shortfall_pct,
                     "price_fall_pct": r.price_fall_pct, "credit_real_growth_pct": r.credit_real_growth_pct,
                     "n_agri_adverse": len(agri), "credit_weak": bool(r.ind_credit_weak)})
    out = pd.DataFrame(rows)
    out.to_csv(REPORTS / "tables" / "early_warning_state.csv", index=False)
    return out


def district_signals() -> pd.DataFrame:
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    p = p[~p.excluded]
    r = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    latest = int(r.year.max())
    dc = CFG["district"]
    rows = []
    for (state, unit), g in p.groupby(["state", "unit"]):
        dep = -g.set_index("year")[["rain_shortfall_lead_placebo_pct"]].iloc[:, 0]  # monsoon of calendar year = credit year
        dep_latest = dep.get(latest, np.nan)
        lagged = [y for y in (latest - 1, latest - 2) if dep.get(y, np.nan) <= dc["lagged_drought_departure_pct"]]
        if dep_latest <= CFG["rain"]["adverse_departure_pct"]:
            cat, why = "Watch", f"monsoon {latest} departure {dep_latest:.0f}%"
        elif state in dc["lagged_watch_states"] and lagged:
            cat, why = "Watch (lagged credit risk)", "deficient monsoon in " + ", ".join(map(str, lagged)) + \
                " - Bihar credit has been lower 2-3 years after such shortfalls"
        else:
            cat, why = "Normal monitoring", "none"
        last_credit = g.dropna(subset=["direct"]).sort_values("year").iloc[-1]
        rows.append({"state": state, "district": unit, "assessed_monsoon": latest, "category": cat, "reason": why,
                     "monsoon_departure_pct": dep_latest,
                     "latest_credit_year": int(last_credit.year), "direct_credit_cr": last_credit.direct,
                     "direct_credit_growth_pct": last_credit.growth_direct})
    out = pd.DataFrame(rows).sort_values(["state", "category", "district"])
    out.to_csv(REPORTS / "tables" / "early_warning_district.csv", index=False)
    return out


def backtest(sig: pd.DataFrame) -> pd.DataFrame:
    """Signal at t (>= 1 adverse agricultural indicator) vs weak credit at t+1."""
    rows = []
    for region, g in sig.groupby("region"):
        g = g.set_index("year").sort_index()
        signal = g.n_agri_adverse >= 1
        target = (g.credit_real_growth_pct.shift(-1) < g.credit_real_growth_pct.median())  # below-median growth next year
        ok = g.credit_real_growth_pct.shift(-1).notna() & g.yield_shortfall_pct.notna() & g.price_fall_pct.notna()
        sgn, tgt = signal[ok], target[ok]
        tp, fp = int((sgn & tgt).sum()), int((sgn & ~tgt).sum())
        fn, tn = int((~sgn & tgt).sum()), int((~sgn & ~tgt).sum())
        rows.append({"region": region, "years": f"{sgn.index.min()}-{sgn.index.max()}", "n": int(ok.sum()),
                     "signals": tp + fp, "target_events": tp + fn, "hits": tp, "missed": fn, "false_alarms": fp,
                     "hit_rate": tp / (tp + fn) if tp + fn else np.nan,
                     "false_alarm_rate": fp / (fp + tn) if fp + tn else np.nan,
                     "precision": tp / (tp + fp) if tp + fp else np.nan,
                     "base_rate": (tp + fn) / ok.sum()})
    out = pd.DataFrame(rows)
    out["note"] = "target = real credit growth at t+1 below the region's median; signal = >=1 adverse agricultural indicator at t"
    out.to_csv(REPORTS / "tables" / "early_warning_backtest_state.csv", index=False)
    return out


def backtest_district() -> pd.DataFrame:
    """District drought (monsoon t-1 <= -20%) vs below-state-year-median credit growth at t+1 and t+2."""
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    p = p[~p.excluded].sort_values(["unit_id", "year"])
    p["below_median"] = p.growth_direct < p.groupby("state_year").growth_direct.transform("median")
    rows = []
    for state, g in [("Both", p), *p.groupby("state")]:
        for h in (1, 2):
            tgt = g.groupby("unit_id").below_median.shift(-h)
            ok = tgt.notna() & g.drought_flag.notna() & g.groupby("unit_id").growth_direct.shift(-h).notna()
            s, t = g.drought_flag[ok].astype(bool), tgt[ok].astype(bool)
            tp, fp, fn, tn = (s & t).sum(), (s & ~t).sum(), (~s & t).sum(), (~s & ~t).sum()
            rows.append({"state": state, "horizon_years": h, "n": int(ok.sum()), "drought_signals": int(tp + fp),
                         "precision": tp / (tp + fp) if tp + fp else np.nan, "base_rate": (tp + fn) / ok.sum(),
                         "hit_rate": tp / (tp + fn), "false_alarm_rate": fp / (fp + tn)})
    out = pd.DataFrame(rows)
    out["lift"] = out.precision / out.base_rate
    out.to_csv(REPORTS / "tables" / "early_warning_backtest_district.csv", index=False)
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    sig = state_signals()
    print(sig.pivot_table(index="year", columns="region", values="category", aggfunc="first").tail(8))
    print(backtest(sig).round(2).to_string(index=False))
    print(backtest_district().round(2).to_string(index=False))
    d = district_signals()
    print(d.category.value_counts().to_string())
    print(d[d.category != "Normal monitoring"][["state", "district", "category", "reason"]].head(15).to_string(index=False))
