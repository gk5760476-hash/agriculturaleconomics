"""Build documented analytical tables in data/processed from data/interim.

Timing convention (design plan s.4, De & Vij 2013):
    credit year t       = amount outstanding at end-March t (FY t-1/t)
    monsoon year        = June-September of calendar year t-1
    crop year           = agricultural year (t-1)-(t), July-June
so every shock that can affect end-March-t credit predates it.

Usage:
    python -I src/transformations.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ingestion import INTERIM, ROOT

PROCESSED = ROOT / "data" / "processed"
REGIONS = ["Bihar", "Maharashtra", "All-India"]

RAIN_NORMAL_PERIOD = (1971, 2020)  # IMD's current LPA period
# IMD rainfall departure categories (per cent of normal)
IMD_BANDS = [(-100.01, -99.5, "No rain"), (-99.5, -59.5, "Large deficient"), (-59.5, -19.5, "Deficient"),
             (-19.5, 19.5, "Normal"), (19.5, 59.5, "Excess"), (59.5, np.inf, "Large excess")]

AGRI = "I. AGRICULTURE"
# DBIE spells some labels differently across years; raw spellings stay in data/interim.
POPULATION_GROUP_FIX = {"SEMI-URBAN": "SEMI URBAN"}  # SEMI-URBAN 2010-2022, SEMI URBAN 2023-2026
BANK_GROUP_FIX = {"SMALL FINANCE BANK": "SMALL FINANCE BANKS"}  # applied after upper-casing


# ----------------------------------------------------------------- credit
def credit_state_detail() -> pd.DataFrame:
    """Districts summed to state; all dimensions retained (all states)."""
    d = pd.read_parquet(INTERIM / "credit" / "bsr1_scb_credit_district_long.parquet")
    d["population_group"] = d.population_group.astype(str).replace(POPULATION_GROUP_FIX)
    d["bank_group"] = d.bank_group.astype(str).str.upper().replace(BANK_GROUP_FIX)
    dims =["year", "state", "population_group", "bank_group", "occupation_group", "occupation_subgroup"]
    s = (d.groupby(dims, observed=True)[["n_accounts", "credit_limit_cr", "amount_outstanding_cr"]]
         .sum(min_count=1).reset_index())
    s.to_csv(PROCESSED / "credit_state_year_detail.csv", index=False)

    # District-level agricultural credit for the focus states (for a later district-year extension).
    f = d[d.state.isin(["BIHAR", "MAHARASHTRA"]) & (d.occupation_group == AGRI)]
    f = (f.groupby(["state", "district", "year", "occupation_subgroup"], observed=True)
         [["n_accounts", "credit_limit_cr", "amount_outstanding_cr"]].sum(min_count=1).reset_index())
    f.to_csv(PROCESSED / "credit_agri_district_year_focus.csv", index=False)
    return s


def credit_region_year(detail: pd.DataFrame) -> pd.DataFrame:
    """Headline credit measures for Bihar, Maharashtra and All-India (sum of states)."""
    detail = detail.copy()
    detail["region"] = detail.state.str.title().where(detail.state.isin(["BIHAR", "MAHARASHTRA"]))
    allindia = detail.assign(region="All-India")
    d = pd.concat([detail.dropna(subset=["region"]), allindia])

    is_agri = d.occupation_group == AGRI
    direct = is_agri & (d.occupation_subgroup == "1. Direct Finance")
    indirect = is_agri & (d.occupation_subgroup == "2. Indirect Finance")
    nonmetro = d.population_group != "METROPOLITAN"
    rural = d.population_group == "RURAL"

    def agg(mask, col="amount_outstanding_cr"):
        return d[mask].groupby(["region", "year"])[col].sum()

    out = pd.DataFrame({
        "agri_direct_outstanding_cr": agg(direct),
        "agri_indirect_outstanding_cr": agg(indirect),
        "agri_total_outstanding_cr": agg(is_agri),
        "agri_direct_nonmetro_outstanding_cr": agg(direct & nonmetro),
        "agri_direct_rural_outstanding_cr": agg(direct & rural),
        "agri_direct_limit_cr": agg(direct, "credit_limit_cr"),
        "agri_direct_accounts": agg(direct, "n_accounts"),
        "nonagri_outstanding_cr": agg(~is_agri),
        "total_outstanding_cr": agg(is_agri | ~is_agri),
    }).reset_index()
    out["agri_share_of_total_pct"] = 100 * out.agri_total_outstanding_cr / out.total_outstanding_cr
    out = out.sort_values(["region", "year"])
    for c in ["agri_direct_outstanding_cr", "agri_total_outstanding_cr",
              "agri_direct_nonmetro_outstanding_cr", "nonagri_outstanding_cr"]:
        out[c.replace("_outstanding_cr", "_growth_pct")] = 100 * out.groupby("region")[c].transform(
            lambda s: np.log(s).diff())
    out.to_csv(PROCESSED / "credit_region_year.csv", index=False)
    return out


# --------------------------------------------------------------- rainfall
def rainfall_region_year() -> pd.DataFrame:
    m = pd.read_csv(INTERIM / "rainfall" / "imd_region_monthly_rainfall.csv")
    key = ["region_id", "state", "district", "year"]
    m["district"] = m.district.fillna("")
    y = m.groupby(key).agg(
        annual_mm=("rainfall_mm", "sum"),
        n_cells=("n_cells", "first"),
    ).reset_index()
    jjas = m[m.month.between(6, 9)].groupby(key).rainfall_mm.sum().rename("jjas_mm")
    y = y.join(jjas, on=key)

    lo, hi = RAIN_NORMAL_PERIOD
    base = y[y.year.between(lo, hi)].groupby("region_id")
    norm = pd.DataFrame({"jjas_normal_mm": base.jjas_mm.mean(), "jjas_sd_mm": base.jjas_mm.std(),
                         "annual_normal_mm": base.annual_mm.mean(), "normal_n_years": base.year.nunique()})
    y = y.join(norm, on="region_id")
    y["jjas_departure_pct"] = 100 * (y.jjas_mm - y.jjas_normal_mm) / y.jjas_normal_mm
    y["jjas_standardised_anomaly"] = (y.jjas_mm - y.jjas_normal_mm) / y.jjas_sd_mm
    y["annual_departure_pct"] = 100 * (y.annual_mm - y.annual_normal_mm) / y.annual_normal_mm
    y["jjas_imd_category"] = pd.cut(y.jjas_departure_pct, [b[0] for b in IMD_BANDS] + [np.inf],
                                    labels=[b[2] for b in IMD_BANDS]).astype(str)
    y["jjas_below_75pct_lpa"] = (y.jjas_mm < 0.75 * y.jjas_normal_mm).astype(int)
    y.to_csv(PROCESSED / "rainfall_region_year.csv", index=False)
    return y


# ------------------------------------------------------------- foodgrains
def foodgrains_region_year() -> pd.DataFrame:
    f = pd.read_csv(INTERIM / "foodgrains" / "rbi_hbs_foodgrains_state_year.csv")
    f["region"] = f.state.replace({"All India": "All-India"})
    f = f[f.region.isin(REGIONS)].drop(columns="state")
    f["yield_check_kg_ha"] = 1000 * f.foodgrain_production_kt / f.foodgrain_area_kha
    f["yield_check_diff_pct"] = 100 * (f.yield_check_kg_ha / f.foodgrain_yield_kg_ha - 1)
    f = f.sort_values(["region", "crop_year_start"])
    f["production_growth_pct"] = 100 * f.groupby("region").foodgrain_production_kt.transform(lambda s: np.log(s).diff())
    f["yield_growth_pct"] = 100 * f.groupby("region").foodgrain_yield_kg_ha.transform(lambda s: np.log(s).diff())
    f.to_csv(PROCESSED / "foodgrains_region_year.csv", index=False)
    return f


# ------------------------------------------------- RBI handbook state tables
RUPEES_PER_CRORE = 1e7
HBS_REGION = {"Bihar": "Bihar", "Maharashtra": "Maharashtra", "All India": "All-India"}


def _hbs(table: str) -> pd.DataFrame:
    h = pd.read_csv(INTERIM / "handbook" / "rbi_hbs_state_tables_long.csv")
    h = h[(h.table == table) & h.state.isin(HBS_REGION)].copy()
    h["region"] = h.state.map(HBS_REGION)
    return h


def credit_agri_long(credit: pd.DataFrame) -> pd.DataFrame:
    """Agricultural credit back to end-March 2004 from HBS Table 157, spliced to DBIE.

    HBS 'date' 2009-04-01 = FY 2009-10 = end-March 2010, i.e. credit year = period_start + 1.
    Over the overlap the two sources agree to HBS's 10-crore rounding.
    """
    h = _hbs("t157")
    h = h.assign(year=h.period_start + 1, agri_total_hbs_cr=h.value / RUPEES_PER_CRORE)[["region", "year", "agri_total_hbs_cr"]]
    d = credit[["region", "year", "agri_total_outstanding_cr"]].rename(columns={"agri_total_outstanding_cr": "agri_total_dbie_cr"})
    out = h.merge(d, on=["region", "year"], how="outer").sort_values(["region", "year"])
    out["agri_total_long_cr"] = out.agri_total_dbie_cr.fillna(out.agri_total_hbs_cr)
    out["agri_total_long_source"] = np.where(out.agri_total_dbie_cr.notna(), "DBIE BSR-1", "RBI HBS Table 157")
    out["agri_total_long_growth_pct"] = 100 * out.groupby("region").agri_total_long_cr.transform(lambda s: np.log(s).diff())
    out.to_csv(PROCESSED / "credit_agri_long_region_year.csv", index=False)
    return out


def macro_region_year() -> pd.DataFrame:
    """Agri GSVA, GSDP (Rs crore) and CPI inflation by region and financial year."""
    specs = {"t029": "agri_gsva_current_cr", "t030": "agri_gsva_constant_2011_12_cr",
             "t021": "gsdp_current_cr", "t022": "gsdp_constant_2011_12_cr", "t108": "cpi_inflation_pct"}
    parts = []
    for t, name in specs.items():
        h = _hbs(t)
        v = h.value if t == "t108" else h.value / RUPEES_PER_CRORE
        parts.append(h.assign(variable=name, value=v)[["region", "period_start", "variable", "value"]])
    m = pd.concat(parts).pivot_table(index=["region", "period_start"], columns="variable", values="value").reset_index()
    m.columns.name = None
    m["fiscal_year"] = m.period_start.astype(str) + "-" + (m.period_start + 1).astype(str).str[-2:]
    m["agri_share_gsdp_pct"] = 100 * m.agri_gsva_current_cr / m.gsdp_current_cr
    m.to_csv(PROCESSED / "macro_region_year.csv", index=False)
    return m


# ------------------------------------------------------------------ prices
WPI_REFERENCE_BASE = "2011-12"


def wpi_spliced() -> pd.DataFrame:
    """WPI items on base 2011-12 = 100, 2004-05 to latest.

    The 2004-05 series is linked at FY 2011-12 (factor = 100 / its 2011-12 value);
    the 2011-12 series is used wherever published. Real index = item / all commodities x 100.
    """
    w = pd.read_csv(INTERIM / "prices" / "wpi_items_fy_by_base.csv")
    wide = w.pivot_table(index=["item", "fiscal_year"], columns="wpi_base", values="index").reset_index()
    link = wide[wide.fiscal_year == WPI_REFERENCE_BASE].set_index("item")["2004-05"].rename("link")
    wide = wide.join(100 / link, on="item")
    wide["wpi_2011_12"] = wide["2011-12"].fillna(wide["2004-05"] * wide.link)
    wide["wpi_source_base"] = np.where(wide["2011-12"].notna(), "2011-12", "2004-05 linked")
    allc = wide[wide.item == "all_commodities"].set_index("fiscal_year").wpi_2011_12.rename("wpi_all_commodities")
    wide = wide.join(allc, on="fiscal_year")
    wide["real_wpi_2011_12"] = 100 * wide.wpi_2011_12 / wide.wpi_all_commodities
    wide = wide.sort_values(["item", "fiscal_year"])
    wide["real_price_growth_pct"] = 100 * wide.groupby("item").real_wpi_2011_12.transform(lambda s: np.log(s).diff())
    out = wide[["item", "fiscal_year", "wpi_2011_12", "wpi_source_base", "wpi_all_commodities",
                "real_wpi_2011_12", "real_price_growth_pct"]]
    out.to_csv(PROCESSED / "wpi_crop_prices_fy.csv", index=False)
    return out


def msp_crop_year() -> pd.DataFrame:
    """MSP by crop year: KMS t/t+1 and RMS t+1/t+2 both belong to crop year t/t+1."""
    m = pd.read_csv(ROOT / "data" / "raw" / "prices" / "msp" / "des_msp_2004-05_to_2026-27_transcribed.csv")
    start = m.marketing_season.str[:4].astype(int) - (m.season_type == "RMS").astype(int)
    m["crop_year"] = start.astype(str) + "-" + (start + 1).astype(str).str[-2:]
    m = m.sort_values(["crop", "variety", "crop_year"])
    m["msp_growth_pct"] = 100 * m.groupby(["crop", "variety"]).msp_rs_per_quintal.transform(lambda s: np.log(s).diff())
    m.to_csv(PROCESSED / "msp_crop_year.csv", index=False)
    return m


def policy_dummies(years) -> pd.DataFrame:
    """Credit-year indicators from the hand-coded event list (region-specific where scoped)."""
    ev = pd.read_csv(ROOT / "data" / "raw" / "policy" / "policy_events.csv")
    rows = []
    for region in REGIONS:
        for y in years:
            def hit(types):
                e = ev[ev.type.isin(types) & (ev.first_affected_credit_year == y)
                       & ev.scope.isin(["All-India", region] if region != "All-India" else ["All-India"])]
                return int(len(e) > 0), ";".join(e.event_id)
            w, wid = hit(["loan_waiver"])
            s, sid = hit(["macro_shock"])
            rows.append((region, y, w, wid, s, sid))
    return pd.DataFrame(rows, columns=["region", "year", "loan_waiver_year", "loan_waiver_events",
                                       "macro_shock_year", "macro_shock_events"])


# ------------------------------------------------------------------ panel
def analysis_panel(credit, rain, food, credit_long=None, macro=None, wpi=None) -> pd.DataFrame:
    years = range(min(credit.year.min(), 1972), credit.year.max() + 2)
    p = pd.MultiIndex.from_product([REGIONS, years], names=["region", "year"]).to_frame(index=False)
    p["fiscal_year"] = (p.year - 1).astype(str) + "-" + p.year.astype(str).str[-2:]
    p = p.merge(credit, on=["region", "year"], how="left")

    r = rain[rain.district == ""].rename(columns={"region_id": "region"})
    rcols = ["jjas_mm", "jjas_departure_pct", "jjas_standardised_anomaly", "jjas_imd_category", "jjas_below_75pct_lpa"]
    r = r[["region", "year"] + rcols].rename(columns={"year": "monsoon_year", **{c: f"monsoon_{c}" for c in rcols}})
    p["monsoon_year"] = p.year - 1
    p = p.merge(r, on=["region", "monsoon_year"], how="left")

    fcols = ["foodgrain_production_kt", "foodgrain_area_kha", "foodgrain_yield_kg_ha",
             "production_growth_pct", "yield_growth_pct"]
    p["crop_year_start"] = p.year - 1
    p = p.merge(food[["region", "crop_year", "crop_year_start"] + fcols], on=["region", "crop_year_start"], how="left")

    # Longer credit series, macro controls and prices all refer to FY (t-1)-t, ending March t.
    p = p.merge(credit_long[["region", "year", "agri_total_long_cr", "agri_total_long_source",
                             "agri_total_long_growth_pct"]], on=["region", "year"], how="left")
    p = p.merge(macro.drop(columns="period_start"), on=["region", "fiscal_year"], how="left")
    prices = wpi.pivot_table(index="fiscal_year", columns="item", values="real_price_growth_pct")
    prices.columns = [f"wpi_real_growth_{c}_pct" for c in prices.columns]
    defl = wpi[wpi.item == "all_commodities"].set_index("fiscal_year").wpi_2011_12.rename("wpi_all_commodities_2011_12")
    p = p.join(defl, on="fiscal_year").join(prices.drop(columns="wpi_real_growth_all_commodities_pct"), on="fiscal_year")
    p["agri_total_long_real_cr_2011_12"] = 100 * p.agri_total_long_cr / p.wpi_all_commodities_2011_12
    p = p.merge(policy_dummies(sorted(p.year.unique())), on=["region", "year"], how="left")

    p = p[p[["agri_total_long_cr", "monsoon_jjas_mm", "foodgrain_production_kt"]].notna().any(axis=1)]
    p.to_csv(PROCESSED / "analysis_panel_state_year.csv", index=False)
    return p


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    detail = credit_state_detail()
    credit = credit_region_year(detail)
    rain = rainfall_region_year()
    food = foodgrains_region_year()
    credit_long = credit_agri_long(credit)
    macro = macro_region_year()
    wpi = wpi_spliced()
    msp_crop_year()
    panel = analysis_panel(credit, rain, food, credit_long, macro, wpi)
    print(f"panel: {len(panel)} rows; credit {credit.year.min()}-{credit.year.max()}; "
          f"rainfall {rain.year.min()}-{rain.year.max()}; foodgrains {food.crop_year.min()}..{food.crop_year.max()}")


if __name__ == "__main__":
    main()
