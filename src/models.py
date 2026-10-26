"""Stage-1 cyclicality models (spec s.9, design plan s.5.1).

All specifications are fixed in SPECS below before estimation. Outcome is
real agricultural credit growth (% log points, end-March t); every shock is
adverse-signed (see shock_indicators.py), so

    coefficient > 0 : credit rises when conditions worsen -> countercyclical
    coefficient < 0 : credit falls when conditions worsen  -> procyclical

and an estimate whose wild-bootstrap p-value is >= ALPHA is 'inconclusive'.

Inference with ~20 annual observations:
  * single-region models: OLS with Newey-West (HAC, 1 lag) standard errors;
  * pooled Bihar+Maharashtra models: standard errors clustered by year
    (two states are far too few clusters to cluster by state);
  * p-values from a restricted wild bootstrap (Rademacher weights, drawn per
    observation for single-region and per year for pooled models), which is
    more reliable than t-tables at this sample size.

Usage:
    python -I src/models.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from ingestion import ROOT
from transformations import PROCESSED

REPORTS = ROOT / "reports"
ALPHA = 0.10
N_BOOT = 9999
SEED = 20261026
MIN_DF = 8      # refuse to estimate with fewer residual degrees of freedom
MIN_EVENTS = 3  # refuse a binary shock indicator with fewer events than this

ADVERSE_SHOCKS = {"rain_shortfall_pct", "rain_deficit_pct", "rain_excess_pct", "drought_flag",
                  "yield_shortfall_pct", "price_fall_pct", "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct",
                  "rain_shortfall_lead_placebo_pct", "rain_standardised_shortfall",
                  "drought_flag_75lpa", "drought_flag_70lpa", "spi_drought_flag", "rain_spi_shortfall"}


@dataclass(frozen=True)
class Spec:
    id: str
    question: str
    terms: tuple[str, ...]
    outcome: str = "credit_real_growth_pct"
    pooled: bool = False             # Bihar + Maharashtra with state intercepts
    interact_bihar: tuple[str, ...] = ()  # pooled only: add term x Bihar
    sample: str = ""                 # optional pandas query
    regions: tuple[str, ...] = ("Bihar", "Maharashtra", "All-India")
    robustness_of: str = ""


SPECS = [
    # --- headline models (pre-specified)
    Spec("M1", "Does credit respond to the preceding monsoon?", ("rain_shortfall_pct",)),
    Spec("M2", "Do deficits and excess rain act differently (asymmetry)?", ("rain_deficit_pct", "rain_excess_pct")),
    Spec("M3", "Weather, production and price shocks together", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct")),
    Spec("M4", "M3 controlling for loan-waiver years", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year")),
    Spec("M5", "Delayed response: monsoon t-2 and persistence", ("rain_shortfall_pct", "rain_shortfall_lag2_pct", "credit_real_growth_lag1_pct")),
    Spec("M6", "Pooled states: does Bihar respond differently from Maharashtra?",
         ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"), pooled=True,
         interact_bihar=("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct"), regions=("Pooled",)),
    Spec("P1", "Placebo: monsoon AFTER the credit date should not matter", ("rain_shortfall_lead_placebo_pct",)),
    # --- robustness (spec s.20.2)
    Spec("R1", "Nominal instead of real credit", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         outcome="credit_nominal_growth_pct", robustness_of="M4"),
    Spec("R2", "Credit relative to All-India (absorbs national shocks)", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         outcome="credit_real_growth_rel_allindia_pct", regions=("Bihar", "Maharashtra"), robustness_of="M4"),
    Spec("R3", "Direct farm credit only (2011-2026, nominal)", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         outcome="credit_direct_growth_pct", robustness_of="M4"),
    Spec("R4", "Direct credit excluding metro branches (2011-2026, nominal)", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         outcome="credit_direct_nonmetro_growth_pct", robustness_of="M4"),
    Spec("R5", "Drought indicator (departure <= -20%) instead of continuous rainfall", ("drought_flag", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R6", "Standardised rainfall anomaly", ("rain_standardised_shortfall", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R7", "Excluding loan-waiver credit years", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct"),
         sample="loan_waiver_year == 0", robustness_of="M3"),
    Spec("R8", "Post-2010 sample (DBIE credit only)", ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         sample="year >= 2011", robustness_of="M4"),
    # --- design-plan robustness (plan s.4, s.5.4), added 2026-10-26 after the headline results were known
    Spec("R9", "Drought = rainfall below 75% of normal", ("drought_flag_75lpa", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R10", "Drought = rainfall below 70% of normal", ("drought_flag_70lpa", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R11", "Drought = SPI <= -1", ("spi_drought_flag", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R12", "Continuous SPI instead of % departure", ("rain_spi_shortfall", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year"),
         robustness_of="M4"),
    Spec("R13", "Control: real non-agricultural credit growth (2011-2026)",
         ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year", "nonagri_real_growth_pct"), robustness_of="M4"),
    Spec("R14", "Control: real GSDP growth (states, 2013-2025)",
         ("rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct", "loan_waiver_year", "gsdp_real_growth_pct"),
         regions=("Bihar", "Maharashtra"), robustness_of="M4"),
]


# ------------------------------------------------------------------ estimation core
def _cov(X, e, cov_type, groups):
    """Sandwich covariance for one or many residual vectors.

    X: (n,k); e: (n,) or (B,n). Returns (k,k) or (B,k,k).
    """
    n, k = X.shape
    bread = np.linalg.inv(X.T @ X)
    E = np.atleast_2d(e)
    if cov_type == "hac1":
        u = E[:, :, None] * X[None]                       # scores (B,n,k)
        S = np.einsum("bti,btj->bij", u, u)
        cross = np.einsum("bti,btj->bij", u[:, 1:], u[:, :-1])
        S = S + 0.5 * (cross + cross.transpose(0, 2, 1))  # Bartlett weight 1 - 1/(L+1), L = 1
        S *= n / (n - k)
    elif cov_type == "cluster":
        u = E[:, :, None] * X[None]
        codes, G = np.unique(groups, return_inverse=True)[1], len(np.unique(groups))
        U = np.zeros((E.shape[0], G, k))
        np.add.at(U, (slice(None), codes), u)
        S = np.einsum("bgi,bgj->bij", U, U) * (G / (G - 1)) * ((n - 1) / (n - k))
    else:
        raise ValueError(cov_type)
    V = bread[None] @ S @ bread[None]
    return V[0] if np.ndim(e) == 1 else V


def ols(y, X, cov_type="hac1", groups=None):
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    V = _cov(X, e, cov_type, groups)
    return beta, np.sqrt(np.diag(V)), e


def wild_bootstrap_p(y, X, j, cov_type, groups, rng, B=N_BOOT):
    """Restricted (null-imposed) wild bootstrap p-value for H0: beta_j = 0."""
    beta, se, _ = ols(y, X, cov_type, groups)
    t_obs = beta[j] / se[j]
    Xr = np.delete(X, j, axis=1)
    br = np.linalg.lstsq(Xr, y, rcond=None)[0]
    fit_r, e_r = Xr @ br, y - Xr @ br
    if cov_type == "cluster":
        g_codes = np.unique(groups, return_inverse=True)[1]
        v = rng.choice([-1.0, 1.0], size=(B, g_codes.max() + 1))[:, g_codes]
    else:
        v = rng.choice([-1.0, 1.0], size=(B, len(y)))
    Y = fit_r[None] + e_r[None] * v                       # (B,n)
    bread = np.linalg.inv(X.T @ X)
    Bt = Y @ X @ bread                                   # (B,k)
    E = Y - Bt @ X.T
    Vb = _cov(X, E, cov_type, groups)
    t_b = Bt[:, j] / np.sqrt(Vb[:, j, j])
    return float((np.sum(np.abs(t_b) >= abs(t_obs)) + 1) / (B + 1))


# ------------------------------------------------------------------ running specs
@dataclass
class Result:
    rows: list = field(default_factory=list)
    diag: list = field(default_factory=list)
    skipped: list = field(default_factory=list)


def classify(term, coef, p):
    if term not in ADVERSE_SHOCKS or term.endswith("lead_placebo_pct") or term == "rain_excess_pct":
        return ""
    if p >= ALPHA:
        return "inconclusive"
    return "countercyclical" if coef > 0 else "procyclical"


def design(df, spec):
    cols = list(spec.terms)
    X = df[cols].astype(float)
    if spec.pooled:
        bihar = (df.region == "Bihar").astype(float)
        for t in spec.interact_bihar:
            X[f"{t}:Bihar"] = df[t] * bihar
        X.insert(0, "Bihar", bihar)
    X.insert(0, "const", 1.0)
    return X


def run(shocks: pd.DataFrame) -> Result:
    rng = np.random.default_rng(SEED)
    res = Result()
    for spec in SPECS:
        for region in spec.regions:
            d = shocks[shocks.region.isin(["Bihar", "Maharashtra"])] if spec.pooled else shocks[shocks.region == region]
            if spec.sample:
                d = d.query(spec.sample)
            d = d.dropna(subset=[spec.outcome, *spec.terms]).sort_values(["year", "region"] if spec.pooled else "year")
            X = design(d, spec)
            reason, notes = "", []
            for t in spec.terms:
                binary = set(d[t].unique()) <= {0, 1}
                events = int(d[t].sum()) if binary else None
                if d[t].std() == 0 and t in ADVERSE_SHOCKS:
                    reason = f"{t} has no variation in this sample"
                elif binary and t in ADVERSE_SHOCKS and events < MIN_EVENTS:
                    reason = f"{t} has {events} event(s) (< {MIN_EVENTS})"
                elif binary and events == 1:
                    notes.append(f"{t} has one event ({int(d.loc[d[t] == 1, 'year'].iloc[0])}): equivalent to dropping that year")
            X = X.loc[:, X.std().gt(0) | (X.columns == "const")]  # control with no events in sample (e.g. waiver)
            n, k = X.shape
            if reason:
                res.skipped.append({"spec": spec.id, "region": region, "n": n, "k": k, "reason": reason})
                continue
            if n - k < MIN_DF:
                res.skipped.append({"spec": spec.id, "region": region, "n": n, "k": k,
                                    "reason": f"only {n - k} residual degrees of freedom (< {MIN_DF})"})
                continue
            y, Xa = d[spec.outcome].to_numpy(float), X.to_numpy(float)
            cov_type, groups = ("cluster", d.year.to_numpy()) if spec.pooled else ("hac1", None)
            beta, se, e = ols(y, Xa, cov_type, groups)
            dof = (len(np.unique(groups)) - 1) if spec.pooled else (n - k)
            tcrit = stats.t.ppf(1 - ALPHA / 2, dof)
            r2 = 1 - e @ e / np.sum((y - y.mean()) ** 2)
            for j, term in enumerate(X.columns):
                p_wild = wild_bootstrap_p(y, Xa, j, cov_type, groups, rng) if term != "const" else np.nan
                p_t = 2 * stats.t.sf(abs(beta[j] / se[j]), dof)
                res.rows.append({
                    "spec": spec.id, "question": spec.question, "robustness_of": spec.robustness_of,
                    "region": region, "outcome": spec.outcome, "term": term,
                    "coef": beta[j], "se": se[j], "ci90_low": beta[j] - tcrit * se[j], "ci90_high": beta[j] + tcrit * se[j],
                    "p_t": p_t, "p_wild": p_wild, "classification": classify(term, beta[j], p_wild),
                    "n": n, "years": f"{d.year.min()}-{d.year.max()}", "r2": r2, "cov_type": cov_type,
                })
            from diagnostics import diagnose
            res.diag.append({"spec": spec.id, "region": region, "n": n, "k": k, "r2": r2,
                             "adj_r2": 1 - (1 - r2) * (n - 1) / (n - k), "notes": "; ".join(notes),
                             **diagnose(y, Xa, e, list(X.columns), d.year.to_numpy())})
    return res


def benjamini_hochberg(p):
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    out = np.empty_like(q)
    out[order] = q
    return out


HEADLINE = "M4"
SHOCK_TERMS = {"rain_shortfall_pct": "Weather (monsoon shortfall)", "yield_shortfall_pct": "Production (yield below trend)",
               "price_fall_pct": "Price (real crop-price fall)"}
# size of an illustrative adverse shock used to translate coefficients into credit-growth points
ILLUSTRATIVE = {"rain_shortfall_pct": 20.0, "yield_shortfall_pct": 10.0, "price_fall_pct": 5.0}


def summary(coefs: pd.DataFrame) -> pd.DataFrame:
    """One row per region x shock: headline estimate plus how often robustness specs agree in sign."""
    rows = []
    for region in ["Bihar", "Maharashtra", "All-India"]:
        for term, label in SHOCK_TERMS.items():
            h = coefs[(coefs.spec == HEADLINE) & (coefs.region == region) & (coefs.term == term)]
            if h.empty:
                continue
            h = h.iloc[0]
            rob = coefs[(coefs.robustness_of != "") & (coefs.region == region) & (coefs.term == term)]
            size = ILLUSTRATIVE[term]
            rows.append({
                "region": region, "shock": label, "term": term, "headline_spec": HEADLINE,
                "coef_pp_per_unit": h.coef, "ci90_low": h.ci90_low, "ci90_high": h.ci90_high,
                "p_wild": h.p_wild, "q_bh": h.q_bh_headline, "classification": h.classification,
                "illustrative_shock": size,
                "effect_on_credit_growth_pp": h.coef * size,
                "effect_ci90_low": h.ci90_low * size, "effect_ci90_high": h.ci90_high * size,
                "robustness_specs": len(rob), "robustness_same_sign": int((np.sign(rob.coef) == np.sign(h.coef)).sum()),
                "robustness_significant_same_sign": int(((np.sign(rob.coef) == np.sign(h.coef)) & (rob.p_wild < ALPHA)).sum()),
            })
    return pd.DataFrame(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main():
    shocks_path = PROCESSED / "shocks_region_year.csv"
    shocks = pd.read_csv(shocks_path)
    res = run(shocks)
    (REPORTS / "tables").mkdir(parents=True, exist_ok=True)
    (REPORTS / "model_runs").mkdir(parents=True, exist_ok=True)
    coefs = pd.DataFrame(res.rows)
    # Benjamini-Hochberg across all headline shock tests (M1-M6), which share one family of questions
    fam = coefs.classification.ne("") & coefs.spec.str.match(r"M\d")
    coefs.loc[fam, "q_bh_headline"] = benjamini_hochberg(coefs.loc[fam, "p_wild"].to_numpy())
    coefs.to_csv(REPORTS / "tables" / "model_coefficients.csv", index=False)
    summary(coefs).to_csv(REPORTS / "tables" / "cyclicality_summary.csv", index=False)
    pd.DataFrame(res.diag).to_csv(REPORTS / "tables" / "model_diagnostics.csv", index=False)
    pd.DataFrame(res.skipped, columns=["spec", "region", "n", "k", "reason"]).to_csv(REPORTS / "tables" / "model_skipped.csv", index=False)
    from diagnostics import unit_root_tests
    unit_root_tests(shocks[shocks.year.between(2006, 2025)]).to_csv(REPORTS / "tables" / "unit_root_tests.csv", index=False)

    import statsmodels, scipy
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {
        "run_id": run_id, "alpha": ALPHA, "n_boot": N_BOOT, "seed": SEED,
        "input": {"file": str(shocks_path.relative_to(ROOT)), "sha256_16": _sha(shocks_path)},
        "specs": [s.__dict__ for s in SPECS],
        "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "statsmodels": statsmodels.__version__, "os": platform.platform()},
    }
    (REPORTS / "model_runs" / f"run_{run_id}.json").write_text(json.dumps(meta, indent=2, default=list))
    print(f"run {run_id}: {coefs.spec.nunique()} specs, {len(coefs)} coefficients, {len(res.skipped)} skipped")
    return coefs


if __name__ == "__main__":
    main()
