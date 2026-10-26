"""Model diagnostics (spec s.20.1). With ~20 observations these tests have low
power: a large p-value does not show that an assumption holds.
"""
from __future__ import annotations

import warnings

import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera


def diagnose(y, X, e, names, years) -> dict:
    with warnings.catch_warnings():
        # a one-event dummy makes leave-that-year-out fits singular; Cook's D is then NaN for it
        warnings.simplefilter("ignore")
        return _diagnose(y, X, e, names, years)


def _diagnose(y, X, e, names, years) -> dict:
    fit = sm.OLS(y, X).fit()
    out = {}
    time_series = len(np.unique(years)) == len(years)
    out["breusch_godfrey_p"] = float(acorr_breusch_godfrey(fit, nlags=1)[1]) if time_series else np.nan
    out["breusch_pagan_p"] = float(het_breuschpagan(e, X)[1]) if X.shape[1] > 1 else np.nan
    out["jarque_bera_p"] = float(jarque_bera(e)[1])
    out["max_vif"] = float(max(variance_inflation_factor(X, j) for j in range(1, X.shape[1]))) if X.shape[1] > 2 else np.nan

    infl = fit.get_influence()
    cooks = infl.cooks_distance[0]
    i = int(np.nanargmax(cooks))
    out["max_cooks_d"] = float(cooks[i])
    out["most_influential_year"] = int(years[i])
    # leave-one-out sensitivity of the first shock coefficient, in standard errors
    j = 1 if names[1] != "Bihar" else 2
    dfb = infl.dfbetas[:, j]
    out["first_shock_term"] = names[j]
    out["max_abs_dfbetas_first_shock"] = float(np.max(np.abs(dfb)))
    out["dfbetas_year"] = int(years[int(np.argmax(np.abs(dfb)))])
    # conventional cut-offs: Cook's D > 4/n, |DFBETAS| > 2/sqrt(n)
    out["influential_flag"] = bool(out["max_cooks_d"] > 4 / len(y) or out["max_abs_dfbetas_first_shock"] > 2 / np.sqrt(len(y)))
    return out
