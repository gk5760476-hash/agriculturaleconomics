"""Stress tests of the district-panel finding, pre-registered in ROADMAP.md (E1-E2, I1, K1-K8).

E  event study: credit on monsoon shortfalls from t+1 (two placebos after the credit date) back to t-4
I  inference: D2 / D10 with standard errors clustered two ways (district and state-year)
K  mechanism (Bihar): accounts vs average loan size, sanctioned limits, bank groups, branch location

Same fixed effects as district_panel.py (district + state x year). K1-K8 form one
Benjamini-Hochberg family.

Usage:
    python -I src/district_robustness.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import models
from district_panel import CREDIT_TO_UNIT, EXCLUDED_UNITS, N_BOOT_DISTRICT, _partial_out, _wild_single
from ingestion import INTERIM
from models import ALPHA, REPORTS, SEED
from transformations import BANK_GROUP_FIX, POPULATION_GROUP_FIX, PROCESSED

LAGS = ["rain_shortfall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct"]
EVENT = ["rain_shortfall_lead2_placebo_pct", "rain_shortfall_lead_placebo_pct", *LAGS, "rain_shortfall_lag4_pct"]
EVENT_LABEL = {"rain_shortfall_lead2_placebo_pct": "monsoon t+1 (placebo)", "rain_shortfall_lead_placebo_pct": "monsoon t (placebo)",
               "rain_shortfall_pct": "monsoon t-1", "rain_shortfall_lag2_pct": "monsoon t-2",
               "rain_shortfall_lag3_pct": "monsoon t-3", "rain_shortfall_lag4_pct": "monsoon t-4"}


def mechanism_outcomes() -> pd.DataFrame:
    """District x year direct-finance aggregates by measure, bank group and branch location."""
    d = pd.read_parquet(INTERIM / "credit" / "bsr1_scb_credit_district_long.parquet",
                        filters=[("state", "in", ["BIHAR", "MAHARASHTRA"]), ("occupation_subgroup", "==", "1. Direct Finance")])
    d["bank_group"] = d.bank_group.astype(str).str.upper().replace(BANK_GROUP_FIX)
    d["population_group"] = d.population_group.astype(str).replace(POPULATION_GROUP_FIX)
    d["state"] = d.state.astype(str)
    d["unit"] = [CREDIT_TO_UNIT.get((s, x), x.title()) for s, x in zip(d.state, d.district.astype(str))]
    d["unit_id"] = d.state.str.title() + "|" + d.unit
    key = ["unit_id", "year"]

    def tot(mask=None, col="amount_outstanding_cr"):
        x = d if mask is None else d[mask]
        return x.groupby(key)[col].sum(min_count=1)

    out = pd.DataFrame({
        "direct_accounts": tot(col="n_accounts"),
        "direct_limit_cr": tot(col="credit_limit_cr"),
        "direct_cr": tot(),
        "direct_public_cr": tot(d.bank_group == "PUBLIC SECTOR BANKS"),
        "direct_private_cr": tot(d.bank_group == "PRIVATE SECTOR BANKS"),
        "direct_rrb_cr": tot(d.bank_group.isin(["REGIONAL RURAL BANKS", "INDIVIDUAL REGIONAL RURAL BANKS"])),
        "direct_rural_cr": tot(d.population_group == "RURAL"),
        "direct_semiurban_urban_cr": tot(d.population_group.isin(["SEMI URBAN", "URBAN"])),
    }).reset_index()
    out["avg_loan_rs_lakh"] = 100 * out.direct_cr / out.direct_accounts  # Rs crore -> lakh per account
    for c in [c for c in out.columns if c not in key]:
        out[f"log_{c}"] = 100 * np.log(out[c].where(out[c] > 0))
    return out


def _cluster_cov(X, e, g):
    return models._cov(X, e, "cluster", g)


def fit(d, outcome, terms, twoway=False, rng=None, boot=True):
    d = d.dropna(subset=[outcome, *terms])
    Z = _partial_out(d, [outcome, *terms], ["unit_id", "state_year"])
    y, X = Z[outcome].to_numpy(), Z[terms].to_numpy()
    g1, g2 = d.unit_id.to_numpy(), d.state_year.to_numpy()
    n, G = len(y), d.unit_id.nunique()
    k_fe = G + d.state_year.nunique() - 1
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    fe_adj = (n - X.shape[1]) / (n - X.shape[1] - k_fe)
    V = _cluster_cov(X, e, g1) * fe_adj
    if twoway:  # Cameron-Gelbach-Miller: V_district + V_stateyear - V_intersection (district-year = one obs)
        V = V + _cluster_cov(X, e, g2) * fe_adj - _cluster_cov(X, e, np.arange(n)) * fe_adj
        G = min(G, d.state_year.nunique())
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    tcrit = stats.t.ppf(1 - ALPHA / 2, G - 1)
    rows = []
    for j, t in enumerate(terms):
        if boot:
            p_w = models.wild_bootstrap_p(y, X, j, "cluster", g1, rng, B=N_BOOT_DISTRICT) if X.shape[1] > 1 \
                else _wild_single(y, X, g1, rng)
        else:
            p_w = np.nan
        rows.append({"term": t, "coef": beta[j], "se": se[j], "ci90_low": beta[j] - tcrit * se[j],
                     "ci90_high": beta[j] + tcrit * se[j], "p_t": 2 * stats.t.sf(abs(beta[j] / se[j]), G - 1),
                     "p_wild_district": p_w, "effect_20pt_pct": 20 * beta[j], "effect_20pt_low": 20 * (beta[j] - tcrit * se[j]),
                     "effect_20pt_high": 20 * (beta[j] + tcrit * se[j]), "n": n, "districts": d.unit_id.nunique(),
                     "years": f"{d.year.min()}-{d.year.max()}", "clusters": "district+state-year" if twoway else "district"})
    return rows


def run() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    p = p[~p.excluded]
    p = p.merge(mechanism_outcomes(), on=["unit_id", "year"], how="left", suffixes=("", "_m"))
    bihar = p[p.state == "Bihar"]
    rows = []

    def add(spec, question, df, outcome, terms, **kw):
        for r in fit(df, outcome, terms, rng=rng, **kw):
            rows.append({"spec": spec, "question": question, "outcome": outcome, **r})

    add("E1", "Event study, both states", p, "log_direct", EVENT)
    add("E2", "Event study, Bihar", bihar, "log_direct", EVENT)
    add("I1", "D2 with two-way clustered SEs", p, "log_direct", LAGS, twoway=True, boot=False)
    add("I1-Bihar", "D10 with two-way clustered SEs", bihar, "log_direct", LAGS, twoway=True, boot=False)
    for spec, outcome, q in [("K1", "log_direct_accounts", "Number of direct-finance accounts"),
                             ("K2", "log_avg_loan_rs_lakh", "Average loan size"),
                             ("K3", "log_direct_limit_cr", "Sanctioned credit limit"),
                             ("K4", "log_direct_public_cr", "Public sector banks"),
                             ("K5", "log_direct_private_cr", "Private sector banks"),
                             ("K6", "log_direct_rrb_cr", "Regional rural banks"),
                             ("K7", "log_direct_rural_cr", "Rural branches"),
                             ("K8", "log_direct_semiurban_urban_cr", "Semi-urban and urban branches")]:
        add(spec, f"Bihar mechanism: {q}", bihar, outcome, LAGS)

    out = pd.DataFrame(rows)
    out["horizon"] = out.term.map(EVENT_LABEL)
    fam = out.spec.str.startswith("K")
    out.loc[fam, "q_bh_mechanism"] = models.benjamini_hochberg(out.loc[fam, "p_wild_district"].to_numpy())
    out.to_csv(REPORTS / "tables" / "district_robustness.csv", index=False)
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    r = run()
    print(r[["spec", "horizon", "effect_20pt_pct", "effect_20pt_low", "effect_20pt_high", "p_t", "p_wild_district",
             "q_bh_mechanism", "n", "districts", "years"]].round(3).to_string(index=False))
