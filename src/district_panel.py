"""District-year extension (spec s.7.3; De & Vij 2013 design).

Panel: Bihar and Maharashtra districts x end-March credit year 2010-2026,
agricultural credit (DBIE BSR-1) matched to the district's June-September
monsoon of calendar year t-1 (IMD 0.25 deg grid, district boundary masks).

Specification (D1):
    100*log(credit_dt) = a_d + l_st + b * rain_shortfall_d,t-1 + e_dt
District fixed effects absorb permanent differences; state x year fixed
effects absorb everything common to a state in a year (waivers, national
policy, prices, inflation, state rainfall). b is identified only from
differences in monsoon shortfall across districts of the same state in the
same year, which is plausibly unrelated to bank behaviour. b > 0 means credit
is higher after a drier monsoon (countercyclical); b x 20 is the % change in
credit after a 20-point shortfall.

Standard errors are clustered by district; p-values from a restricted wild
cluster bootstrap (Rademacher weights per district). Fixed effects are
partialled out first (Frisch-Waugh-Lovell).

Usage:
    python -I src/district_panel.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import models
from models import ALPHA, REPORTS, SEED
from transformations import PROCESSED

N_BOOT_DISTRICT = 4999
DROUGHT_THRESHOLD = -20.0

# DBIE district label -> boundary-file district (state-qualified). Spelling variants, official
# renames (Aurangabad -> Chhatrapati Sambhajinagar 2023, Osmanabad -> Dharashiv 2023,
# Ahmadnagar -> Ahilyanagar 2025) and the Thane/Palghar split (Palghar carved out 2014,
# reported separately from 2016) merged into one consistent unit for the whole period.
CREDIT_TO_UNIT = {
    ("BIHAR", "KAIMUR"): "Kaimur (Bhabua)",
    ("BIHAR", "PASCHIMI CHAMPARAN"): "Pashchim Champaran",
    ("MAHARASHTRA", "AHMADNAGAR"): "Ahmednagar",
    ("MAHARASHTRA", "AHILYANAGAR"): "Ahmednagar",
    ("MAHARASHTRA", "BID"): "Beed",
    ("MAHARASHTRA", "NASIK"): "Nashik",
    ("MAHARASHTRA", "CHHATRAPATI SAMBHAJINAGAR"): "Aurangabad",
    ("MAHARASHTRA", "DHARASHIV"): "Osmanabad",
    ("MAHARASHTRA", "THANE"): "Thane+Palghar",
    ("MAHARASHTRA", "PALGHAR"): "Thane+Palghar",
}
BOUNDARY_TO_UNIT = {("Maharashtra", "Thane"): "Thane+Palghar", ("Maharashtra", "Palghar"): "Thane+Palghar"}
# metro centres: 'agricultural' credit booked there is mostly corporate/indirect, not farm lending
EXCLUDED_UNITS = {("Maharashtra", "Mumbai"), ("Maharashtra", "Mumbai Suburban")}


def concordance() -> pd.DataFrame:
    c = pd.read_csv(PROCESSED / "credit_agri_district_year_focus.csv")
    rows = []
    for (state, district), g in c.groupby(["state", "district"]):
        unit = CREDIT_TO_UNIT.get((state, district), district.title())
        rows.append({"state": state.title(), "credit_district": district, "unit": unit,
                     "first_year": g.year.min(), "last_year": g.year.max(),
                     "excluded": (state.title(), unit) in EXCLUDED_UNITS})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT_META / "district_concordance.csv", index=False)
    return out


def build_panel() -> pd.DataFrame:
    conc = concordance()
    unit_of = {(r.state.upper(), r.credit_district): r.unit for r in conc.itertuples()}

    c = pd.read_csv(PROCESSED / "credit_agri_district_year_focus.csv")
    c["unit"] = [unit_of[(s, d)] for s, d in zip(c.state, c.district)]
    c["state"] = c.state.str.title()
    c["subgroup"] = c.occupation_subgroup.map({"1. Direct Finance": "direct", "2. Indirect Finance": "indirect"})
    credit = c.pivot_table(index=["state", "unit", "year"], columns="subgroup", values="amount_outstanding_cr",
                           aggfunc="sum").reset_index()
    credit.columns.name = None
    credit["total"] = credit[["direct", "indirect"]].sum(axis=1, min_count=1)

    r = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    r = r[r.district.notna() & r.state.isin(["Bihar", "Maharashtra"])].copy()
    r["unit"] = [BOUNDARY_TO_UNIT.get((s, d), d) for s, d in zip(r.state, r.district)]
    # merged units: cell-count-weighted mean of rainfall and of the normal
    r["w"] = r.n_cells
    rain = (r.assign(jw=r.jjas_mm * r.w, nw=r.jjas_normal_mm * r.w)
            .groupby(["state", "unit", "year"])[["jw", "nw", "w"]].sum())
    rain = pd.DataFrame({"jjas_mm": rain.jw / rain.w, "jjas_normal_mm": rain.nw / rain.w}).reset_index()
    rain["shortfall"] = -100 * (rain.jjas_mm - rain.jjas_normal_mm) / rain.jjas_normal_mm
    sf = rain.set_index(["state", "unit", "year"]).shortfall

    p = credit.copy()
    for lag, name in [(1, "rain_shortfall_pct"), (2, "rain_shortfall_lag2_pct"), (3, "rain_shortfall_lag3_pct"),
                      (4, "rain_shortfall_lag4_pct"), (0, "rain_shortfall_lead_placebo_pct"),
                      (-1, "rain_shortfall_lead2_placebo_pct")]:
        p[name] = sf.reindex(pd.MultiIndex.from_arrays([p.state, p.unit, p.year - lag])).to_numpy()
    p["rain_deficit_pct"] = np.maximum(0, p.rain_shortfall_pct)
    p["rain_excess_pct"] = np.maximum(0, -p.rain_shortfall_pct)
    p["drought_flag"] = (p.rain_shortfall_pct >= -DROUGHT_THRESHOLD).astype(int)
    p["log_direct"] = 100 * np.log(p.direct.where(p.direct > 0))
    p["log_total"] = 100 * np.log(p.total.where(p.total > 0))
    p = p.sort_values(["state", "unit", "year"])
    p["growth_direct"] = p.groupby(["state", "unit"]).log_direct.diff()
    p["excluded"] = [(s, u) in EXCLUDED_UNITS for s, u in zip(p.state, p.unit)]
    p["unit_id"] = p.state + "|" + p.unit  # 'Aurangabad' exists in both states
    p["state_year"] = p.state + "_" + p.year.astype(str)
    p.to_csv(PROCESSED / "district_panel.csv", index=False)
    return p


# ------------------------------------------------------------------ estimation
SPECS = [
    ("D1", "Log credit on preceding-monsoon shortfall (De & Vij eq. 1)", "log_direct", ["rain_shortfall_pct"], ""),
    ("D2", "Dynamics: shortfall in monsoons t-1, t-2, t-3", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], ""),
    ("D3", "Drought indicator (district departure <= -20%)", "log_direct", ["drought_flag"], ""),
    ("D4", "Asymmetry: deficit vs excess rain", "log_direct", ["rain_deficit_pct", "rain_excess_pct"], ""),
    ("D5", "Does Bihar differ from Maharashtra?", "log_direct", ["rain_shortfall_pct", "rain_shortfall_pct:Bihar"], ""),
    ("D6", "Credit growth instead of level", "growth_direct", ["rain_shortfall_pct"], ""),
    ("D7", "Total (direct + indirect) agricultural credit", "log_total", ["rain_shortfall_pct"], ""),
    ("D8", "Bihar only", "log_direct", ["rain_shortfall_pct"], "state == 'Bihar'"),
    ("D9", "Maharashtra only", "log_direct", ["rain_shortfall_pct"], "state == 'Maharashtra'"),
    ("DP", "Placebo: monsoon AFTER the credit date", "log_direct", ["rain_shortfall_lead_placebo_pct"], ""),
    # Is the delayed fall lending or loan-waiver write-offs? Bihar had no state waiver in 2010-2026.
    ("D10", "Dynamics, Bihar only (no state waiver)", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], "state == 'Bihar'"),
    ("D11", "Dynamics, Maharashtra only (2017 and 2019 waivers)", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], "state == 'Maharashtra'"),
    ("D12", "Dynamics, credit growth outcome", "growth_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], ""),
    ("D13", "Dynamics, Maharashtra before its first waiver (credit years to 2017)", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], "state == 'Maharashtra' and year <= 2017"),
    # Do drier districts simply have slower credit trends? Add a linear trend per district.
    ("D14", "Dynamics with district-specific trends", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], ""),
    ("D15", "Dynamics with district-specific trends, Bihar only", "log_direct",
     ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"], "state == 'Bihar'"),
]
TREND_SPECS = {"D14", "D15"}


def _partial_out(df, cols, fe_cols):
    """Residualise cols on the fixed effects (alternating projections, exact at convergence)."""
    out = df[cols].astype(float).copy()
    for _ in range(200):
        prev = out.copy()
        for fe in fe_cols:
            out = out - out.groupby(df[fe].to_numpy()).transform("mean")
        if np.max(np.abs(out.to_numpy() - prev.to_numpy())) < 1e-10:
            break
    return out


def estimate(panel: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    base = panel[~panel.excluded].copy()
    base["rain_shortfall_pct:Bihar"] = base.rain_shortfall_pct * (base.state == "Bihar")
    for sid, question, outcome, terms, sample in SPECS:
        d = base.query(sample) if sample else base
        d = d.dropna(subset=[outcome, *terms])
        cols = [outcome, *terms]
        if sid in TREND_SPECS:
            # state x year FE absorb each state's common trend, so drop one reference district per state
            ref = d.groupby("state").unit_id.min()
            trend = pd.get_dummies(d.unit_id, dtype=float).drop(columns=ref.to_list())
            trend = trend.mul(d.year - d.year.mean(), axis=0)
            trend.columns = [f"trend:{c}" for c in trend.columns]
            d = pd.concat([d, trend], axis=1)
            cols += list(trend.columns)
        Z = _partial_out(d, cols, ["unit_id", "state_year"])
        y, X = Z[outcome].to_numpy(), Z[cols[1:]].to_numpy()
        groups = d.unit_id.to_numpy()
        n, G = len(y), d.unit_id.nunique()
        k_fe = G + d.state_year.nunique() - 1
        beta, se, _ = models.ols(y, X, "cluster", groups)
        se = se * np.sqrt((n - X.shape[1]) / (n - X.shape[1] - k_fe))  # restore FE degrees of freedom
        tcrit = stats.t.ppf(1 - ALPHA / 2, G - 1)
        for j, term in enumerate(terms):
            p_wild = models.wild_bootstrap_p(y, X, j, "cluster", groups, rng, B=N_BOOT_DISTRICT) if X.shape[1] > 1 \
                else _wild_single(y, X, groups, rng)
            rows.append({"spec": sid, "question": question, "outcome": outcome, "term": term,
                         "coef": beta[j], "se_cluster_district": se[j],
                         "ci90_low": beta[j] - tcrit * se[j], "ci90_high": beta[j] + tcrit * se[j],
                         "p_t": 2 * stats.t.sf(abs(beta[j] / se[j]), G - 1), "p_wild": p_wild,
                         "classification": models.classify(term, beta[j], p_wild),
                         "effect_of_20pt_shortfall_pct": 20 * beta[j] if "shortfall" in term or "deficit" in term else np.nan,
                         "n": n, "districts": G, "years": f"{d.year.min()}-{d.year.max()}"})
    out = pd.DataFrame(rows)
    fam = out.classification.ne("")
    out.loc[fam, "q_bh"] = models.benjamini_hochberg(out.loc[fam, "p_wild"].to_numpy())
    (REPORTS / "tables").mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORTS / "tables" / "district_coefficients.csv", index=False)
    return out


def _wild_single(y, X, groups, rng):
    """Wild cluster bootstrap when the only regressor is the tested one (restricted model = 0)."""
    beta, se, _ = models.ols(y, X, "cluster", groups)
    codes = np.unique(groups, return_inverse=True)[1]
    v = rng.choice([-1.0, 1.0], size=(N_BOOT_DISTRICT, codes.max() + 1))[:, codes]
    Y = y[None] * v  # under the null the fixed-effect residualised outcome is all residual
    se_b = np.sqrt(np.diagonal(models._cov(X, Y - (Y @ X @ np.linalg.inv(X.T @ X)) @ X.T, "cluster", groups),
                               axis1=1, axis2=2))[:, 0]
    b = (Y @ X @ np.linalg.inv(X.T @ X))[:, 0]
    return float((np.sum(np.abs(b / se_b) >= abs(beta[0] / se[0])) + 1) / (len(b) + 1))


ROOT_META = PROCESSED.parent / "metadata"

if __name__ == "__main__":
    panel = build_panel()
    use = panel[~panel.excluded]
    print(f"panel: {use.unit_id.nunique()} units, {use.year.min()}-{use.year.max()}, {len(use)} rows "
          f"({panel.excluded.sum()} excluded metro rows)")
    pd.set_option("display.width", 250)
    res = estimate(panel)
    print(res[["spec", "term", "coef", "ci90_low", "ci90_high", "p_t", "p_wild", "q_bh", "classification",
               "effect_of_20pt_shortfall_pct", "n", "districts"]].round(3).to_string(index=False))
