"""Build the self-contained dashboard (design plan s.8 Option A): app/dashboard.html.

Reads only saved outputs in data/processed and reports/tables; nothing is
re-estimated in the browser. The page embeds the data as JSON, so it opens
offline and can be shared as one file.

Usage:
    python -I src/reporting.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from ingestion import ROOT
from models import REPORTS
from transformations import PROCESSED

APP = ROOT / "app"
TEMPLATE = APP / "dashboard_template.html"
OUT = APP / "dashboard.html"
REGIONS = ["Bihar", "Maharashtra", "All-India"]


def _records(df: pd.DataFrame, cols=None, digits=3):
    df = df[cols] if cols else df
    df = df.replace({np.nan: None})
    return [{k: (round(v, digits) if isinstance(v, float) else v) for k, v in r.items()} for r in df.to_dict("records")]


SCENARIO_TERMS = ["rain_shortfall_pct", "yield_shortfall_pct", "price_fall_pct"]


def scenario_inputs(s: pd.DataFrame, credit: pd.DataFrame) -> dict:
    """Headline model M4 refitted per region with its full covariance, so the page can combine
    several shocks: effect = x'b, interval from x'Vx, prediction interval adds the residual variance."""
    import models
    spec = next(sp for sp in models.SPECS if sp.id == models.HEADLINE)
    out = {}
    for region in REGIONS:
        d = s[s.region == region].dropna(subset=[spec.outcome, *spec.terms]).sort_values("year")
        X = models.design(d, spec)
        X = X.loc[:, X.std().gt(0) | (X.columns == "const")]
        y = d[spec.outcome].to_numpy(float)
        beta, _, e = models.ols(y, X.to_numpy(float), "hac1")
        V = models._cov(X.to_numpy(float), e, "hac1", None)
        n, k = X.shape
        last = credit[(credit.region == region) & credit.agri_total_long_cr.notna()].sort_values("year").iloc[-1]
        out[region] = {"terms": list(X.columns), "b": beta.round(6).tolist(), "V": V.round(8).tolist(),
                       "sigma2": float(e @ e / (n - k)), "dof": n - k, "t90": float(stats.t.ppf(0.95, n - k)),
                       "n": n, "years": f"{d.year.min()}-{d.year.max()}",
                       "mean_growth": float(y.mean()), "credit_cr": float(last.agri_total_long_cr), "credit_year": int(last.year),
                       "range": {t: [float(d[t].min()), float(d[t].max())] for t in SCENARIO_TERMS}}
    return out


def district_levels() -> dict:
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    p = p[~p.excluded]
    last = p.year.max()
    return {st: {"direct_cr": float(g[g.year == last].direct.sum()), "year": int(last),
                 "shortfall_range": [float(g.rain_shortfall_pct.min()), float(g.rain_shortfall_pct.max())]}
            for st, g in p.groupby("state")}


def collect() -> dict:
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    cl = pd.read_csv(PROCESSED / "credit_agri_long_region_year.csv")
    credit = s.merge(cl[["region", "year", "agri_total_long_cr"]], on=["region", "year"], how="left")
    rain = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    rain = rain[rain.district.isna()].rename(columns={"region_id": "region"})
    coefs = pd.read_csv(REPORTS / "tables" / "model_coefficients.csv")
    runs = sorted((REPORTS / "model_runs").glob("run_*.json"))
    run = json.loads(runs[-1].read_text()) if runs else {}
    reg = pd.read_csv(ROOT / "data" / "metadata" / "source_register.csv")
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model_run": run.get("run_id", ""),
        "regions": REGIONS,
        "credit": _records(credit, ["region", "year", "credit_source", "agri_total_long_cr", "credit_real_growth_pct",
                                    "credit_nominal_growth_pct", "loan_waiver_year"]),
        "rain": _records(rain, ["region", "year", "jjas_mm", "jjas_normal_mm", "jjas_departure_pct", "jjas_imd_category"]),
        "shocks": _records(s, ["region", "year", "yield_shortfall_pct", "price_fall_pct", "rain_departure_pct"]),
        "summary": _records(pd.read_csv(REPORTS / "tables" / "cyclicality_summary.csv")),
        "state_coefs": _records(coefs[coefs.term != "const"],
                                ["spec", "question", "robustness_of", "region", "outcome", "term", "coef", "ci90_low",
                                 "ci90_high", "p_wild", "q_bh_headline", "classification", "n", "years"]),
        "district": _records(pd.read_csv(REPORTS / "tables" / "district_coefficients.csv")),
        "district_robust": _records(pd.read_csv(REPORTS / "tables" / "district_robustness.csv")),
        "fc_state": _records(pd.read_csv(REPORTS / "tables" / "forecast_state_scores.csv")),
        "fc_district": _records(pd.read_csv(REPORTS / "tables" / "forecast_district_ranking.csv")),
        "fc_holdout": _records(pd.read_csv(REPORTS / "tables" / "forecast_drought_holdout.csv")),
        "unit_root": _records(pd.read_csv(REPORTS / "tables" / "unit_root_tests.csv")),
        "scenario": scenario_inputs(s, credit),
        "district_levels": district_levels(),
        "ew_state": _records(pd.read_csv(REPORTS / "tables" / "early_warning_state.csv")),
        "ew_district": _records(pd.read_csv(REPORTS / "tables" / "early_warning_district.csv")),
        "bt_state": _records(pd.read_csv(REPORTS / "tables" / "early_warning_backtest_state.csv")),
        "bt_district": _records(pd.read_csv(REPORTS / "tables" / "early_warning_backtest_district.csv")),
        "validation": _records(pd.read_csv(ROOT / "data" / "metadata" / "validation_results.csv")),
        "sources": _records(reg, ["source_id", "variable_group", "publisher", "publication_or_table", "url_or_reference",
                                  "units", "coverage", "caveats"]),
    }


def build():
    data = json.dumps(collect(), separators=(",", ":"), allow_nan=False)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data.replace("</", "<\\/"))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
