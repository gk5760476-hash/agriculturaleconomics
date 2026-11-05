"""The six pages of the Streamlit app; same content and numbers as app/dashboard.html."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
from data import (REGIONS, STATES, WHEN, coef, crore, district_outside, district_scenario, frame, sign,
                  state_scenario, status)

SHOCK_LABEL = {"rain_shortfall_pct": "monsoon", "yield_shortfall_pct": "yield", "price_fall_pct": "price"}


def table(df: pd.DataFrame, label: str = "Show table", **column_config) -> None:
    """Table view beside every chart (values reachable without hover; CSV download in its toolbar)."""
    with st.expander(label):
        st.dataframe(df, hide_index=True, width="stretch", column_config=column_config or None)


def by_region(df: pd.DataFrame, value: str, since: int) -> pd.DataFrame:
    return (df[df.year >= since][["region", "year", value]].rename(columns={"region": "series", value: "value"})
            .dropna(subset=["value"]))


# ------------------------------------------------------------------ Overview
def overview(d: dict) -> None:
    d1, b2, b3, m13 = coef(d, "D1", "rain_shortfall_pct"), coef(d, "D15", "rain_shortfall_lag2_pct"), \
        coef(d, "D15", "rain_shortfall_lag3_pct"), coef(d, "D13", "rain_shortfall_pct")
    summ = frame(d, "summary")
    n_sig = int((summ.classification != "inconclusive").sum())
    with st.container(border=True):
        st.subheader("What the data show")
        st.markdown(f"**No sign that credit rises in the season after a drought.** Comparing districts in the same state and year "
                    f"({int(d1.n):,} district-years, {int(d1.districts)} districts, {d1.years}), a 20-point monsoon shortfall is associated "
                    f"with {sign(d1.effect_of_20pt_shortfall_pct)}% agricultural credit the following March (90% interval "
                    f"{sign(20 * d1.ci90_low)}% to {sign(20 * d1.ci90_high)}%). This rules out the 3–5% rise found for all-India districts "
                    "in 1993–2010 (De & Vij 2013).")
        st.markdown(f"**In Bihar, credit is lower two to three years after a dry monsoon.** Allowing for each district's own trend, a "
                    f"20-point shortfall is followed by {sign(20 * b2.coef)}% (two years on) and {sign(20 * b3.coef)}% (three years on) "
                    f"credit; q-values {b2.q_bh:.2f} and {b3.q_bh:.2f}. Bihar had no state loan waiver, so write-offs do not explain it. "
                    "The fall is in the number of borrowers, not loan size, mainly at regional rural banks and rural branches; the "
                    "monsoons after the credit date show no effect. Treat as suggestive: the estimate shrinks by about 40% once "
                    "district trends are included, and it does not forecast district credit well.")
        st.markdown(f"**Maharashtra: no clear response.** No delayed fall. Before its 2017 waiver there is a hint of a small immediate "
                    f"rise ({sign(20 * m13.coef)}% per 20-point shortfall, q = {m13.q_bh:.2f}) that does not survive correction for "
                    "multiple tests.")
        st.markdown(f"**State-level series are too short to decide.** With about 20 years per state, {n_sig} of {len(summ)} weather, "
                    "yield and price effects reach significance and none survives the multiple-test correction. They are reported "
                    "as inconclusive, not as \"no effect\".")

    st.subheader("Latest position")
    credit, rain, ew = frame(d, "credit"), frame(d, "rain"), frame(d, "ew_state")
    for col, r in zip(st.columns(3), REGIONS):
        c = credit[(credit.region == r) & credit.agri_total_long_cr.notna()].sort_values("year").iloc[-1]
        col.metric(f"{r} · agri credit, Mar {int(c.year)}", crore(c.agri_total_long_cr),
                   f"{sign(c.credit_real_growth_pct)}% real growth on the year", delta_color="off", border=True,
                   delta_arrow="up" if c.credit_real_growth_pct > 0 else "down" if c.credit_real_growth_pct < 0 else "off")
    for col, r in zip(st.columns(3), REGIONS):
        x = rain[rain.region == r].sort_values("year").iloc[-1]
        e = ew[(ew.region == r) & (ew.category != "Data insufficient")].sort_values("year")
        e = e.iloc[-1] if len(e) else ew[ew.region == r].sort_values("year").iloc[-1]
        with col.container(border=True):
            st.metric(f"{r} · monsoon {int(x.year)}", f"{sign(x.jjas_departure_pct, 0)}%")
            st.caption(f"IMD: {x.jjas_imd_category} · monitoring for {int(e.year)}: {status(e.category)}")


# ------------------------------------------------------------------ Credit trends
def credit(d: dict) -> None:
    st.subheader("Real growth of agricultural credit outstanding")
    st.caption("Year-on-year change, % (log points), deflated by WPI all commodities, end-March of each year. "
               "Shaded: loan-waiver credit years (2008 national; 2018 and 2020 Maharashtra).")
    c = frame(d, "credit")
    g = by_region(c, "credit_real_growth_pct", 2006)
    charts.lines(g, "% real growth", shade_years=(2008, 2018, 2020))
    table(g.pivot(index="year", columns="series", values="value").reset_index()[["year", *REGIONS]].round(1),
          year=st.column_config.NumberColumn("Year", format="%d"))

    st.subheader("Credit outstanding")
    st.caption("₹ crore, nominal. 2004–2009 RBI Handbook Table 157; from 2010 DBIE BSR-1 (they agree within 0.003% where both exist).")
    for col, r in zip(st.columns(3), REGIONS):
        with col:
            st.markdown(f"**{r}**")
            s = c[(c.region == r) & c.agri_total_long_cr.notna()][["year", "agri_total_long_cr"]]
            charts.lines(s.assign(series=r).rename(columns={"agri_total_long_cr": "value"}), "₹ crore", y_format=",.0f", height=200,
                         label_expr="datum.value >= 1e5 ? format(datum.value / 1e5, '.1f') + ' lakh' : format(datum.value / 1e3, '.0f') + 'k'")
            table(s.rename(columns={"year": "Year", "agri_total_long_cr": "₹ crore"}).round(0),
                  Year=st.column_config.NumberColumn(format="%d"), **{"₹ crore": st.column_config.NumberColumn(format="localized")})
    st.caption("Concept: amount outstanding with scheduled commercial banks (incl. RRBs and small finance banks) at end-March — "
               "a stock, not disbursement. Excludes cooperative banks.")


# ------------------------------------------------------------------ Weather & agriculture
def agriculture(d: dict) -> None:
    st.subheader("June–September monsoon")
    st.caption("% departure from the 1971–2020 mean, IMD 0.25° gridded rainfall averaged over the region. "
               "Red line: −20%, IMD \"deficient\".")
    rain = frame(d, "rain")
    for col, r in zip(st.columns(3), REGIONS):
        with col:
            st.markdown(f"**{r}**")
            s = rain[(rain.region == r) & (rain.year >= 1990)][["year", "jjas_departure_pct", "jjas_imd_category"]]
            charts.departure_bars(s.rename(columns={"jjas_departure_pct": "value"}), r)
            table(s.rename(columns={"year": "Monsoon", "jjas_departure_pct": "Departure %", "jjas_imd_category": "IMD category"}).round(1),
                  Monsoon=st.column_config.NumberColumn(format="%d"))
    sh = frame(d, "shocks")
    st.subheader("Foodgrain yield shortfall")
    st.caption("% below the region's 2004-05 to 2024-25 linear trend (positive = worse), shown against the credit year it precedes.")
    y = by_region(sh, "yield_shortfall_pct", 2005)
    charts.lines(y, "% below trend")
    table(y.pivot(index="year", columns="series", values="value").reset_index()[["year", *REGIONS]].round(1),
          year=st.column_config.NumberColumn("Year", format="%d"))
    st.subheader("Real crop-price fall")
    st.caption("Area-weighted fall in real WPI of each region's crops (2004–07 crop mix), % (positive = worse). "
               "National prices: the states differ only through crop mix.")
    p = by_region(sh, "price_fall_pct", 2006)
    charts.lines(p, "% real price fall")
    table(p.pivot(index="year", columns="series", values="value").reset_index()[["year", *REGIONS]].round(1),
          year=st.column_config.NumberColumn("Year", format="%d"))


# ------------------------------------------------------------------ Results
def results(d: dict) -> None:
    with st.container(border=True):
        st.subheader("What does a dry monsoon imply for credit? District estimates")
        st.caption("Applies the district-panel estimates to a monsoon departure you choose. Changes are relative to districts of the "
                   "same state with a normal monsoon; bands are 90% intervals. ₹ crore = the % change applied to the state's latest "
                   "direct farm credit.")
        dep = st.slider("Monsoon departure (%)", -60, 40, -20, 5, key="dist_dep")
        sc = district_scenario(d, dep)
        bh, mh = sc[(sc.state == "Bihar") & (sc.step == 3)].iloc[0], sc[(sc.state == "Maharashtra") & (sc.step == 1)].iloc[0]
        st.markdown(f"#### Monsoon {sign(dep, 0)}% → Bihar {sign(bh.est)}% three years on ({sign(bh.lo)} to {sign(bh.hi)}); "
                    f"Maharashtra {sign(mh.est)}% next March ({sign(mh.lo)} to {sign(mh.hi)})")
        charts.path_chart(sc, "% credit vs normal monsoon")
        rows = {"When": WHEN}
        for s in STATES:
            t = sc[sc.state == s].sort_values("step")
            rows[f"{s} %"] = [sign(v) + (" *" if sig else "") for v, sig in zip(t.est, t.significant)]
            rows[f"{s} 90% range"] = [f"{sign(a)} to {sign(b)}" for a, b in zip(t.lo, t.hi)]
            rows[f"{s} ₹ crore"] = [sign(v, 0) for v in t.crore]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        out = district_outside(d, dep)
        if out:
            st.warning(f"Outside the district departures observed in {' and '.join(out)} since 2009 — treat as extrapolation.", icon="⚠️")
        lv = d["district_levels"]
        st.caption(f"\\* significant at 10% (wild bootstrap). Bihar lags use district trends (D15); Maharashtra lags use D11. "
                   f"₹ crore on direct credit of March {lv['Bihar']['year']}: Bihar {crore(lv['Bihar']['direct_cr'])}, "
                   f"Maharashtra {crore(lv['Maharashtra']['direct_cr'])}.")

    with st.container(border=True):
        st.subheader("Compare regions: weather, yield and price shocks together")
        st.caption("Headline state model (M4, ~20 years per region). Effect = change in next year's real credit growth versus normal "
                   "conditions; the 90% interval reflects estimation uncertainty, the prediction interval adds the year-to-year noise "
                   "in credit growth. No estimate here is robust — read as illustration.")
        c1, c2, c3 = st.columns(3)
        rdep = c1.slider("Monsoon departure (%)", -60, 40, -20, 5, key="st_dep")
        ys = c2.slider("Yield below trend (%)", -20, 30, 0, 5, key="st_yield")
        pf = c3.slider("Real crop-price fall (%)", -20, 30, 0, 5, key="st_price")
        res = state_scenario(d, {"rain_shortfall_pct": -rdep, "yield_shortfall_pct": ys, "price_fall_pct": pf})
        st.dataframe(pd.DataFrame({
            "Region": res.region,
            "Effect on real credit growth (pp)": res.effect_pp.map(sign),
            "90% interval": [f"{sign(a)} to {sign(b)}" for a, b in zip(res.lo, res.hi)],
            "Predicted growth next year (%)": res.growth_pct.map(sign),
            "90% prediction interval": [f"{sign(a)} to {sign(b)}" for a, b in zip(res.growth_lo, res.growth_hi)],
            "≈ ₹ crore vs normal": res.crore.map(lambda v: sign(v, 0)),
        }), hide_index=True, width="stretch")
        flagged = [f"{r} ({', '.join(SHOCK_LABEL[t] for t in o)})" for r, o in zip(res.region, res.outside) if o]
        if flagged:
            st.warning(f"Outside the range seen in 2006–2025 for {'; '.join(flagged)} — treat as extrapolation.", icon="⚠️")
        st.caption(f"Predicted growth = the model's prediction for a year with these shocks and no loan waiver (2006–2025 fit). "
                   f"₹ crore = effect × the region's latest agricultural credit (March {d['scenario']['All-India']['credit_year']}), "
                   "an approximate first-year difference at current prices.")

    st.subheader("District panel: effect of a 20-point monsoon shortfall on credit")
    st.caption("% change in direct agricultural credit outstanding. District + state×year fixed effects; standard errors clustered by "
               "district (71 districts). Filled dot = significant at 10% (wild bootstrap); hollow = inconclusive; line = 90% interval.")
    pick = [("D1", "rain_shortfall_pct", "Both states · next March"), ("D2", "rain_shortfall_lag2_pct", "Both · 2 years on"),
            ("D2", "rain_shortfall_lag3_pct", "Both · 3 years on"), ("D14", "rain_shortfall_lag3_pct", "Both · 3 yrs on, trends"),
            ("D8", "rain_shortfall_pct", "Bihar · next March"), ("D15", "rain_shortfall_lag2_pct", "Bihar · 2 yrs on, trends"),
            ("D15", "rain_shortfall_lag3_pct", "Bihar · 3 yrs on, trends"), ("D9", "rain_shortfall_pct", "Maharashtra · next March"),
            ("D11", "rain_shortfall_lag3_pct", "Maharashtra · 3 years on"), ("DP", "rain_shortfall_lead_placebo_pct", "Placebo: later monsoon")]
    rows = []
    for spec, term, label in pick:
        c = coef(d, spec, term)
        rows.append({"label": label, "est": 20 * c.coef, "lo": 20 * c.ci90_low, "hi": 20 * c.ci90_high, "p": c.p_wild,
                     "q": c.q_bh, "significant": c.classification in ("countercyclical", "procyclical"),
                     "group": "Bihar" if label.startswith("Bihar") else "Maharashtra" if label.startswith("Maharashtra") else "Both states"})
    rows = pd.DataFrame(rows)
    charts.coef_plot(rows, "% credit per 20-pt shortfall")
    table(rows.drop(columns=["group"]).round(3))

    rb = frame(d, "district_robust")
    st.subheader("Bihar event study: timing of the credit response")
    st.caption("% change in direct credit per 20-point shortfall in each monsoon, estimated jointly (2010–2024). "
               "The two monsoons after the credit date are placebos and should be zero.")
    e2 = rb[rb.spec == "E2"]
    order = ["rain_shortfall_lead2_placebo_pct", "rain_shortfall_lead_placebo_pct", "rain_shortfall_pct",
             "rain_shortfall_lag2_pct", "rain_shortfall_lag3_pct", "rain_shortfall_lag4_pct"]
    e2 = e2.set_index("term").loc[order].reset_index()
    ev = pd.DataFrame({"label": e2.horizon, "est": e2.effect_20pt_pct, "lo": e2.effect_20pt_low, "hi": e2.effect_20pt_high,
                       "p": e2.p_wild_district, "significant": e2.p_wild_district < 0.1, "group": "Bihar"})
    charts.coef_plot(ev, "% credit per 20-pt shortfall")
    table(ev.drop(columns=["group"]).round(3))

    st.subheader("Bihar: what falls? Monsoon three years earlier")
    st.caption("% change per 20-point shortfall in monsoon t−3. Fewer borrowers rather than smaller loans; concentrated in regional "
               "rural banks and rural branches. q = Benjamini–Hochberg across all 24 mechanism tests.")
    K = [("K1", "Number of accounts"), ("K2", "Average loan size"), ("K3", "Sanctioned limit"), ("K4", "Public sector banks"),
         ("K5", "Private banks"), ("K6", "Regional rural banks"), ("K7", "Rural branches"), ("K8", "Semi-urban & urban branches")]
    k = rb[rb.term == "rain_shortfall_lag3_pct"].set_index("spec")
    mech = pd.DataFrame([{"label": lab, "est": k.loc[s, "effect_20pt_pct"], "lo": k.loc[s, "effect_20pt_low"],
                          "hi": k.loc[s, "effect_20pt_high"], "p": k.loc[s, "p_wild_district"], "q": k.loc[s, "q_bh_mechanism"],
                          "significant": k.loc[s, "p_wild_district"] < 0.1, "group": "Bihar"} for s, lab in K])
    charts.coef_plot(mech, "% per 20-pt shortfall (t−3)")
    table(mech.drop(columns=["group"]).round(3))

    st.subheader("State time series: weather, production and price shocks (headline model M4)")
    st.caption("Change in real credit growth (percentage points) after an illustrative adverse shock: 20-point monsoon shortfall, "
               "yield 10% below trend, 5% real crop-price fall. Newey-West errors; ~20 years per region.")
    summ = frame(d, "summary")
    sr = pd.DataFrame({"label": summ.region + " · " + summ.shock.str.split(" \\(").str[0], "est": summ.effect_on_credit_growth_pp,
                       "lo": summ.effect_ci90_low, "hi": summ.effect_ci90_high, "p": summ.p_wild, "q": summ.q_bh,
                       "significant": summ.classification != "inconclusive", "group": summ.region})
    charts.coef_plot(sr, "pp real credit growth")
    table(summ[["region", "shock", "robustness_specs", "robustness_same_sign", "robustness_significant_same_sign"]].rename(columns={
        "region": "Region", "shock": "Shock", "robustness_specs": "Specs", "robustness_same_sign": "Same sign",
        "robustness_significant_same_sign": "Same sign & significant"}), "Robustness: how often alternative specifications agree")

    st.subheader("Can these relationships forecast credit? Out-of-sample test")
    st.caption("One-year-ahead forecasts of real credit growth, expanding window, 2016–2025. "
               "Ratio < 1 means better than the naive 'grows at its past average' forecast.")
    fc = frame(d, "fc_state")
    names = {"naive_mean": "Naive: past average", "naive_last": "Naive: last year", "ar1": "Autoregressive",
             "rain": "Monsoon t−1, t−2", "full": "Monsoon + yield + price"}
    st.dataframe(pd.DataFrame({"Region": fc.region, "Model": fc.model.map(names), "MAE (pp)": fc.mae.round(1),
                               "Error vs naive": fc.mae_vs_naive_mean.round(2), "Years better": fc.wins_vs_naive_mean.astype(str) + "/" + fc.n_forecasts.astype(str),
                               "p vs naive": pd.to_numeric(fc.dm_p_vs_naive_mean).round(2), "MAPE %": fc.mape.round(0)}),
                 hide_index=True, width="stretch", placeholder="—")
    rho = frame(d, "fc_district").spearman_rank_corr.mean()
    st.warning(f"No model beats the naive forecast reliably. Ranking Bihar districts by their lagged shortfall gives a mean rank "
               f"correlation of {rho:.2f} with next year's credit growth — too weak to forecast with. The scenario tools above are "
               "descriptive, not forecasts. MAPE runs to hundreds of % because growth is often near zero.", icon="⚠️")

    with st.container(border=True):
        st.subheader("More validation from the design plan")
        ho = frame(d, "fc_holdout")
        st.caption(f"Leave-one-drought-out: each drought credit year is predicted from all other years. Mean absolute error over "
                   f"{len(ho)} held-out years: naive {ho.abs_err_naive_mean.mean():.1f} pp, monsoon model {ho.abs_err_rain.mean():.1f} pp, "
                   f"full model {ho.abs_err_full.mean():.1f} pp — no consistent gain.")
        st.dataframe(ho[["region", "held_out_year", "monsoon_departure_pct", "actual", "naive_mean", "rain", "full"]].rename(columns={
            "region": "Region", "held_out_year": "Held-out credit year", "monsoon_departure_pct": "Monsoon %", "actual": "Actual growth",
            "naive_mean": "Naive", "rain": "Monsoon model", "full": "Full model"}).round(1), hide_index=True, width="stretch",
            column_config={"Held-out credit year": st.column_config.NumberColumn(format="%d")})
        st.caption("Alternative drought definitions and controls (headline M4 otherwise unchanged). Specifications with fewer than "
                   "3 drought years are not estimated.")
        sc_ = frame(d, "state_coefs")
        shock_of = {"R9": "drought_flag_75lpa", "R10": "drought_flag_70lpa", "R11": "spi_drought_flag", "R12": "rain_spi_shortfall",
                    "R13": "rain_shortfall_pct", "R14": "rain_shortfall_pct"}
        plan = sc_[[shock_of.get(s) == t or (s in ("R13", "R14") and t in ("yield_shortfall_pct", "price_fall_pct"))
                    for s, t in zip(sc_.spec, sc_.term)]]
        st.dataframe(pd.DataFrame({"Spec": plan.spec, "Change": plan.question, "Region": plan.region,
                                   "Shock": plan.term.str.replace("_pct", "").str.replace("_", " "), "Coef": plan.coef.round(2),
                                   "90% low": plan.ci90_low.round(2), "90% high": plan.ci90_high.round(2),
                                   "p (wild)": plan.p_wild.round(3), "Reading": plan.classification}), hide_index=True, width="stretch")
        st.caption("Unit-root tests on the model series (2006–2025). ADF: H0 unit root; KPSS: H0 stationary (p-values capped at 0.10 "
                   "by its lookup table). Low power at n = 20.")
        ur = frame(d, "unit_root")
        st.dataframe(pd.DataFrame({"Region": ur.region, "Series": ur.label, "ADF p": ur.adf_p.round(3),
                                   "KPSS p": ur.kpss_p.map(lambda v: f"≥ {v:.3f}" if v >= 0.1 else f"{v:.3f}"),
                                   "Reading": ur.verdict}), hide_index=True, width="stretch")

    st.info("**How to read these.** Positive = credit higher after worse conditions (countercyclical); negative = credit lower "
            "(procyclical). Estimates are conditional associations. The district design compares districts of the same state in "
            "the same year, so state policy, prices and inflation cancel out; rainfall differences between neighbouring districts "
            "are plausibly unrelated to bank behaviour, but the mechanism (less lending vs less demand vs restructuring) is not "
            "identified.")


# ------------------------------------------------------------------ Early warning
def early_warning(d: dict) -> None:
    st.subheader("State monitoring categories by credit year")
    st.caption("Rules: monsoon departure ≤ −20%, yield > 1 SD below trend, real crop-price fall > 1 SD, real credit contraction. "
               "Two adverse agricultural signals, or a severe one with weak credit, = Elevated concern.")
    ew = frame(d, "ew_state")
    ew["cell"] = [status(c) + ("" if i in (None, "none") or pd.isna(i) else f" — {i}") for c, i in zip(ew.category, ew.indicators)]
    grid = ew.pivot(index="year", columns="region", values="cell").sort_index(ascending=False)
    grid.index = grid.index.astype(int).rename("Year")
    st.table(grid[REGIONS])  # static table: long indicator lists wrap instead of being cut off

    dl = frame(d, "ew_district")
    st.subheader(f"District watch list — monsoon {int(dl.assessed_monsoon.iloc[0])}")
    st.caption("Districts with a deficient monsoon, and Bihar districts with a deficient monsoon 1–2 years earlier "
               "(the lag found in the district panel).")
    which = st.segmented_control("Show", ["All flagged", "All districts"], default="All flagged", key="ew_filter")
    rows = dl if which == "All districts" else dl[dl.category != "Normal monitoring"]
    st.dataframe(pd.DataFrame({"State": rows.state, "District": rows.district, "Category": rows.category.map(status),
                               "Reason": rows.reason, "Monsoon dep. %": rows.monsoon_departure_pct.round(0),
                               "Direct credit (latest)": rows.direct_credit_cr.map(crore)}), hide_index=True, width="stretch")
    st.caption(f"{len(rows)} districts shown.")

    st.subheader("Does the signal anticipate weak credit? Historical backtest")
    st.caption("Precision = share of signals followed by below-median credit growth; compare with the base rate. "
               "A precision near the base rate means no predictive value.")
    bs, bd = frame(d, "bt_state"), frame(d, "bt_district")
    bt = pd.concat([pd.DataFrame({"Level": bs.region, "Horizon": "1 year", "Signals": bs.signals, "Precision": bs.precision,
                                  "Base rate": bs.base_rate, "Hit rate": bs.hit_rate, "False-alarm rate": bs.false_alarm_rate}),
                    pd.DataFrame({"Level": "Districts · " + bd.state, "Horizon": bd.horizon_years.map(lambda h: f"{h} year{'s' if h > 1 else ''}"),
                                  "Signals": bd.drought_signals, "Precision": bd.precision, "Base rate": bd.base_rate,
                                  "Hit rate": bd.hit_rate, "False-alarm rate": bd.false_alarm_rate})])
    st.dataframe(bt.round(2), hide_index=True, width="stretch")
    st.warning("Result: the signals do not reliably anticipate weaker credit growth. Use this page as a descriptive monitor that "
               "points to places worth checking, not as a forecast.", icon="⚠️")
    st.caption("Not for individual credit decisions, loan approval or fund allocation. A flag means: verify local credit demand, "
               "disbursement timing and eligibility on the ground.")


# ------------------------------------------------------------------ Data & methods
def methods(d: dict) -> None:
    st.subheader("Sources")
    src = frame(d, "sources")
    src = src[~src.source_id.astype(str).str.startswith(("SRC-META", "SRC-DOC", "SRC-READ"))]
    st.dataframe(src.rename(columns={"source_id": "ID", "variable_group": "Group", "publisher": "Publisher",
                                     "publication_or_table": "Table / product", "url_or_reference": "Link / reference",
                                     "units": "Units", "coverage": "Coverage", "caveats": "Caveats"}),
                 hide_index=True, width="stretch")
    st.subheader("Timing and definitions")
    st.markdown("Credit year *t* = amount outstanding at end-March *t*. It is matched to the June–September monsoon of calendar year "
                "*t*−1, the agricultural year (*t*−1)–*t* and prices of financial year (*t*−1)–*t*, so every shock predates the credit "
                "it is compared with. Rainfall departure is measured against the 1971–2020 mean of IMD 0.25° gridded rainfall. Yield "
                "shortfall = % below a region-specific linear trend. Price fall = area-weighted fall in real WPI of the region's crops, "
                "with weights fixed at the 2004–07 crop mix.")
    st.subheader("Data checks")
    v = frame(d, "validation")
    icon = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "🛑 FAIL"}
    # full height: the one expected WARN (Mumbai's nearest rainfall cell) must not hide below a scroll
    st.dataframe(pd.DataFrame({"Result": v.result.map(icon), "Check": v.check, "Detail": v.detail.fillna("")}), hide_index=True,
                 width="stretch", height=35 * (len(v) + 1) + 3)
    st.subheader("Limitations")
    st.markdown("\n".join(f"- {t}" for t in [
        "Credit is a stock: it mixes new lending, rollovers, restructuring and write-offs.",
        "Two states and ~20 years: state-level estimates have low power; an inconclusive result is not evidence of no effect.",
        "Crop prices are national WPI series; states differ only through crop mix.",
        "District units are current boundaries; Thane and Palghar are merged, Mumbai is excluded (metro-booked lending).",
        "Yield and price shocks partly respond to farmer and policy behaviour; only rainfall is plausibly external.",
        "Policy events are coded by credit year, not month; every event cites an official source (Maharashtra waivers: their Government Resolutions)."]))
