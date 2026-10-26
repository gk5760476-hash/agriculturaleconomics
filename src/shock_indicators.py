"""Pre-specified shock indicators (spec s.10) on the region x credit-year panel.

Sign convention: every *adverse* indicator is oriented so that a larger value
means worse conditions for farmers. A positive regression coefficient on an
adverse indicator therefore means credit RISES in distress (countercyclical);
a negative one means credit FALLS (procyclical).

Definitions are fixed here, before estimation, and must not be tuned to results:
  weather   rain_shortfall_pct   = -(JJAS departure from 1971-2020 normal), monsoon t-1
            rain_deficit_pct     = max(0, shortfall);  rain_excess_pct = max(0, -shortfall)
            drought_flag         = departure <= -20  (IMD 'deficient' or worse)
            excess_flag          = departure >= +20  (IMD 'excess' or more)
  production yield_shortfall_pct = -(100 x residual of log foodgrain yield on a
                                     region-specific linear trend), crop year (t-1)-t
  price     price_fall_pct       = -(area-weighted real WPI growth of the region's crops), FY (t-1)-t
            weights: mean crop area 2004-05..2006-07 (HBS Tables 67-70, 76-78), fixed

Usage:
    python -I src/shock_indicators.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ingestion import INTERIM
from transformations import PROCESSED, REGIONS

DROUGHT_THRESHOLD = -20.0
EXCESS_THRESHOLD = 20.0
PRICE_WEIGHT_YEARS = (2004, 2006)  # crop-year starts averaged for area weights

# HBS area table -> WPI item(s) priced for that crop group (equal-weighted within group)
CROP_GROUPS = {
    "t067": ["paddy"],                               # rice
    "t068": ["wheat"],
    "t069": ["maize"],                               # coarse cereals
    "t070": ["arhar", "gram", "moong", "urad"],      # pulses
    "t076": ["soyabean", "rapeseed_mustard"],        # oilseeds
    "t077": ["raw_cotton"],
    "t078": ["sugarcane"],
}
HBS_REGION = {"Bihar": "Bihar", "Maharashtra": "Maharashtra", "All India": "All-India"}


def price_weights() -> pd.DataFrame:
    h = pd.read_csv(INTERIM / "handbook" / "rbi_hbs_state_tables_long.csv")
    lo, hi = PRICE_WEIGHT_YEARS
    a = h[h.table.isin(CROP_GROUPS) & h.state.isin(HBS_REGION) & h.period_start.between(lo, hi)]
    area = a.groupby(["state", "table"]).value.mean().rename("base_area_kha").reset_index()
    area["region"] = area.state.map(HBS_REGION)
    area["weight"] = area.base_area_kha / area.groupby("region").base_area_kha.transform("sum")
    area["wpi_items"] = area.table.map(lambda t: "+".join(CROP_GROUPS[t]))
    out = area[["region", "table", "wpi_items", "base_area_kha", "weight"]].sort_values(["region", "weight"], ascending=[True, False])
    out.to_csv(PROCESSED / "price_shock_crop_weights.csv", index=False)
    return out


def crop_price_index(weights: pd.DataFrame) -> pd.DataFrame:
    """Region x FY weighted real price growth (%)."""
    w = pd.read_csv(PROCESSED / "wpi_crop_prices_fy.csv")
    g = w.pivot_table(index="fiscal_year", columns="item", values="real_price_growth_pct")
    rows = []
    for region, wr in weights.groupby("region"):
        s = sum(r.weight * g[r.wpi_items.split("+")].mean(axis=1) for r in wr.itertuples())
        rows.append(pd.DataFrame({"region": region, "fiscal_year": g.index, "crop_real_price_growth_pct": s.values}))
    return pd.concat(rows)


def yield_deviation(panel: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=panel.index)
    for region, d in panel.groupby("region"):
        ok = d.foodgrain_yield_kg_ha.notna()
        x, y = d.loc[ok, "crop_year_start"].to_numpy(float), np.log(d.loc[ok, "foodgrain_yield_kg_ha"].to_numpy())
        b = np.polyfit(x, y, 1)
        out.loc[d.index[ok]] = 100 * (y - np.polyval(b, x))
    return out


def build_shocks() -> pd.DataFrame:
    p = pd.read_csv(PROCESSED / "analysis_panel_state_year.csv").sort_values(["region", "year"])
    rain = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    rain = rain[rain.district.isna()].set_index(["region_id", "year"]).jjas_departure_pct

    s = p[["region", "year", "fiscal_year", "monsoon_year", "crop_year", "loan_waiver_year", "macro_shock_year"]].copy()
    dep = p.monsoon_jjas_departure_pct
    s["rain_departure_pct"] = dep
    s["rain_shortfall_pct"] = -dep
    s["rain_deficit_pct"] = np.maximum(0, -dep).where(dep.notna())
    s["rain_excess_pct"] = np.maximum(0, dep).where(dep.notna())
    s["drought_flag"] = (dep <= DROUGHT_THRESHOLD).astype(int).where(dep.notna())
    s["excess_flag"] = (dep >= EXCESS_THRESHOLD).astype(int).where(dep.notna())
    s["rain_standardised_shortfall"] = -p.monsoon_jjas_standardised_anomaly
    # monsoon t-2 (one more lag) and monsoon t (after end-March t: placebo, must not matter)
    s["rain_shortfall_lag2_pct"] = -pd.Series([rain.get((r, y - 2), np.nan) for r, y in zip(p.region, p.year)], index=p.index)
    s["rain_shortfall_lead_placebo_pct"] = -pd.Series([rain.get((r, y), np.nan) for r, y in zip(p.region, p.year)], index=p.index)

    s["yield_deviation_pct"] = yield_deviation(p)
    s["yield_shortfall_pct"] = -s.yield_deviation_pct

    prices = crop_price_index(price_weights())
    s = s.merge(prices, on=["region", "fiscal_year"], how="left")
    s["price_fall_pct"] = -s.crop_real_price_growth_pct

    # outcomes
    p = p.set_index(["region", "year"])
    key = pd.MultiIndex.from_frame(s[["region", "year"]])
    real = np.log(p.agri_total_long_real_cr_2011_12)
    s["credit_real_growth_pct"] = (100 * real.groupby(level="region").diff()).reindex(key).to_numpy()
    s["credit_nominal_growth_pct"] = p.agri_total_long_growth_pct.reindex(key).to_numpy()
    s["credit_direct_growth_pct"] = p.agri_direct_growth_pct.reindex(key).to_numpy()
    s["credit_direct_nonmetro_growth_pct"] = p.agri_direct_nonmetro_growth_pct.reindex(key).to_numpy()
    s["credit_source"] = p.agri_total_long_source.reindex(key).to_numpy()
    ai = s[s.region == "All-India"].set_index("year").credit_real_growth_pct
    s["credit_real_growth_rel_allindia_pct"] = s.credit_real_growth_pct - s.year.map(ai)
    s["credit_real_growth_lag1_pct"] = s.groupby("region").credit_real_growth_pct.shift(1)

    s = s[s.year.between(2004, 2026)]
    s.to_csv(PROCESSED / "shocks_region_year.csv", index=False)
    return s


if __name__ == "__main__":
    s = build_shocks()
    cols = ["credit_real_growth_pct", "rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct"]
    print(s.groupby("region")[cols].agg(["count", "mean", "std"]).round(1).T)
    print(pd.read_csv(PROCESSED / "price_shock_crop_weights.csv").round(3).to_string(index=False))
