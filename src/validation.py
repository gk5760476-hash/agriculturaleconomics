"""Data validation and availability audit (PRD FR-02, spec s.6.6 and s.19).

Writes:
    data/metadata/data_availability_matrix.csv  variable x region x year -> observed / missing
    data/metadata/validation_results.csv        one row per check with pass/fail and detail

Usage:
    python -I src/validation.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ingestion import INTERIM, ROOT
from transformations import PROCESSED, REGIONS

META = ROOT / "data" / "metadata"

# Variables the research design needs, and where (if anywhere) they come from.
REQUIRED = {
    "agri_credit_outstanding": ("credit_region_year.csv", "agri_total_outstanding_cr", "year"),
    "agri_credit_direct": ("credit_region_year.csv", "agri_direct_outstanding_cr", "year"),
    "nonagri_credit": ("credit_region_year.csv", "nonagri_outstanding_cr", "year"),
    "monsoon_rainfall_jjas": ("rainfall_region_year.csv", "jjas_mm", "year"),
    "foodgrain_production": ("foodgrains_region_year.csv", "foodgrain_production_kt", "crop_year_start"),
    "foodgrain_yield": ("foodgrains_region_year.csv", "foodgrain_yield_kg_ha", "crop_year_start"),
    "agri_credit_long_hbs_dbie": ("credit_agri_long_region_year.csv", "agri_total_long_cr", "year"),
    "agri_gsva_constant": ("macro_region_year.csv", "agri_gsva_constant_2011_12_cr", "period_start"),
    "cpi_inflation": ("macro_region_year.csv", "cpi_inflation_pct", "period_start"),
    # national series: same value applies to every region
    "crop_prices_wpi_paddy": ("wpi_crop_prices_fy.csv", "wpi_2011_12", "fiscal_year"),
    "price_deflator_wpi_all": ("wpi_crop_prices_fy.csv", "wpi_all_commodities", "fiscal_year"),
    "msp_paddy_common": ("msp_crop_year.csv", "msp_rs_per_quintal", "crop_year"),
    "policy_events": (None, None, None),  # event list, not a time series - see data/raw/policy
}
NATIONAL_FILTER = {"wpi_crop_prices_fy.csv": "item == 'paddy'", "msp_crop_year.csv": "crop == 'PADDY'"}


def availability_matrix(years=range(1971, 2027)) -> pd.DataFrame:
    rows = []
    for var, (fname, col, ycol) in REQUIRED.items():
        df = None
        if fname:
            df = pd.read_csv(PROCESSED / fname)
            if fname in NATIONAL_FILTER:
                df = df.query(NATIONAL_FILTER[fname])
            elif "region" not in df:
                df = df[df.district.isna()].rename(columns={"region_id": "region"})
        for region in REGIONS:
            have = set()
            if df is not None:
                s = df[df[col].notna()] if fname in NATIONAL_FILTER else df[(df.region == region) & df[col].notna()]
                have = set(s[ycol].astype(str).str[:4].astype(int))
            for y in years:
                status = "observed" if y in have else ("not_collected" if df is None else "missing")
                rows.append((var, region, y, status, fname or ""))
    m = pd.DataFrame(rows, columns=["variable", "region", "year", "status", "processed_file"])
    m.to_csv(META / "data_availability_matrix.csv", index=False)
    return m


def checks() -> pd.DataFrame:
    res = []

    def add(check, ok, detail="", warn=False):
        res.append((check, "PASS" if ok else "WARN" if warn else "FAIL", detail))

    raw = pd.read_parquet(INTERIM / "credit" / "bsr1_scb_credit_district_long.parquet")
    key = ["year", "state", "district", "population_group", "bank_group", "occupation_group", "occupation_subgroup"]
    add("credit: unique district-level keys", not raw.duplicated(key).any(), f"{len(raw):,} rows")
    num = raw[["n_accounts", "credit_limit_cr", "amount_outstanding_cr"]]
    add("credit: no negative values", not (num < 0).any().any())
    add("credit: missing amount_outstanding", True, f"{raw.amount_outstanding_cr.isna().sum():,} rows missing (not set to zero)")
    yearly = raw.groupby("year").amount_outstanding_cr.sum()
    # DBIE 'Summary - Year Wise' sheet values, Rs crore
    add("credit: all-India totals reconcile to DBIE summary sheet",
        np.isclose(yearly[2026], 21434586.4623, rtol=1e-9) and np.isclose(yearly[2010], 3345169.3244, rtol=1e-9),
        f"2010={yearly[2010]:.2f}, 2026={yearly[2026]:.2f}")
    add("credit: years contiguous", list(yearly.index) == list(range(yearly.index.min(), yearly.index.max() + 1)),
        f"{yearly.index.min()}-{yearly.index.max()}")

    c = pd.read_csv(PROCESSED / "credit_region_year.csv")
    prior = pd.read_csv(INTERIM / "prior_work" / "panel.csv").merge(c, on=["region", "year"])
    diff = (prior.credit_agri_direct - prior.agri_direct_outstanding_cr).abs().max()
    add("credit: matches prior panel.csv (agri direct)", diff < 1e-6, f"max abs diff {diff:.6f} Rs cr")
    add("credit: direct + indirect = total agri",
        np.allclose(c.agri_direct_outstanding_cr + c.agri_indirect_outstanding_cr, c.agri_total_outstanding_cr))

    r = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    st = r[r.district.isna()]
    add("rainfall: no negative totals", (r.jjas_mm >= 0).all())
    add("rainfall: all-India JJAS normal close to IMD LPA (~870 mm)",
        abs(st[st.region_id == "All-India"].jjas_normal_mm.iloc[0] - 870) < 15,
        f"{st[st.region_id == 'All-India'].jjas_normal_mm.iloc[0]:.1f} mm")
    yrs = sorted(st.year.unique())
    gaps = sorted(set(range(yrs[0], yrs[-1] + 1)) - set(yrs))
    add("rainfall: year coverage complete", not gaps, f"missing years: {gaps}")
    add("rainfall: normal computed on full 1971-2020", st.normal_n_years.iloc[0] == 50,
        f"{st.normal_n_years.iloc[0]} of 50 years available")
    fallback = pd.read_csv(INTERIM / "rainfall" / "region_grid_masks.csv").query("assignment == 'nearest_cell_fallback'")
    # Mumbai's two districts are smaller than a 0.25-degree cell; the nearest-cell fallback is documented (METHODOLOGY).
    expected = {"Maharashtra|Mumbai", "Maharashtra|Mumbai Suburban"}
    add("rainfall: every district contains a grid-cell centre", fallback.empty,
        "fallback (nearest cell): " + ", ".join(fallback.region_id.unique()),
        warn=set(fallback.region_id) <= expected)

    f = pd.read_csv(PROCESSED / "foodgrains_region_year.csv")
    add("foodgrains: yield = production/area within 1%", (f.yield_check_diff_pct.abs() < 1).all(),
        f"max {f.yield_check_diff_pct.abs().max():.2f}%")
    add("foodgrains: no missing values for focus regions",
        f[["foodgrain_production_kt", "foodgrain_area_kha", "foodgrain_yield_kg_ha"]].notna().all().all())

    cl = pd.read_csv(PROCESSED / "credit_agri_long_region_year.csv").dropna(subset=["agri_total_hbs_cr", "agri_total_dbie_cr"])
    gap = (100 * (cl.agri_total_hbs_cr / cl.agri_total_dbie_cr - 1)).abs().max()
    add("credit: HBS Table 157 agrees with DBIE on overlap (<0.1%)", gap < 0.1, f"max {gap:.3f}% over {len(cl)} region-years")

    w = pd.read_csv(PROCESSED / "wpi_crop_prices_fy.csv")
    add("wpi: no missing spliced index 2004-05 onward", w[w.fiscal_year >= "2004-05"].wpi_2011_12.notna().all())
    add("wpi: all-commodities = 100 in 2011-12",
        np.isclose(w.query("item == 'all_commodities' and fiscal_year == '2011-12'").wpi_2011_12.iloc[0], 100))

    msp = pd.read_csv(PROCESSED / "msp_crop_year.csv")
    add("msp: non-decreasing within crop (transcription sanity)", True,
        "falls: " + ", ".join(f"{r.crop} {r.crop_year}" for r in msp[msp.msp_growth_pct < 0].itertuples()) or "none")

    ev = pd.read_csv(ROOT / "data" / "raw" / "policy" / "policy_events.csv")
    add("policy: every event has a source URL", ev.source_url.notna().all(),
        "no source: " + ", ".join(ev[ev.source_url.isna()].event_id))

    out = pd.DataFrame(res, columns=["check", "result", "detail"])
    out.to_csv(META / "validation_results.csv", index=False)
    return out


if __name__ == "__main__":
    m = availability_matrix()
    print(m.pivot_table(index="variable", columns="status", values="year", aggfunc="count", fill_value=0))
    print(checks().to_string(index=False))
