"""Altair charts for the Streamlit app, matching app/dashboard.html.

Colours are the dashboard's tokens (validated categorical slots 1-3, both modes):
one hue per region in a fixed order, never re-assigned by rank. Marks are thin
(2px lines, >= 8px markers), the grid is a hairline, and every chart carries a
hover tooltip; the caller puts a table view beside each one.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from data import REGIONS

LIGHT = {"ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
         "surface": "#fcfcfb", "wet": "#2a78d6", "dry": "#e34948", "neutral": "#52514e", "wash": "#2a78d6",
         "series": {"Bihar": "#2a78d6", "Maharashtra": "#eb6834", "All-India": "#1baf7a"}}
DARK = {"ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
        "surface": "#1a1a19", "wet": "#3987e5", "dry": "#e66767", "neutral": "#c3c2b7", "wash": "#3987e5",
        "series": {"Bihar": "#3987e5", "Maharashtra": "#d95926", "All-India": "#199e70"}}
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def tokens() -> dict:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:  # no browser context (tests, bare mode)
        return LIGHT


def _style(chart: alt.TopLevelMixin, height: int) -> alt.TopLevelMixin:
    T = tokens()
    return (chart.properties(height=height, background="transparent", padding={"left": 4, "right": 4, "top": 6, "bottom": 4})
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor=T["grid"], domainColor=T["axis"], tickColor=T["axis"], labelColor=T["muted"],
                            titleColor=T["ink2"], labelFont=FONT, titleFont=FONT, labelFontSize=11, titleFontSize=12,
                            titleFontWeight="normal", gridWidth=1, domainWidth=1)
            .configure_legend(labelColor=T["ink2"], titleColor=T["ink2"], labelFont=FONT, titleFont=FONT, labelFontSize=12,
                              orient="top", symbolType="circle", symbolSize=80, symbolOpacity=1, title=None)
            .configure_text(font=FONT))


def show(chart: alt.TopLevelMixin, height: int = 260) -> None:
    st.altair_chart(_style(chart, height), width="stretch", theme=None)


def _color(domain: list[str]) -> alt.Color:
    T = tokens()
    return alt.Color("series:N", scale=alt.Scale(domain=domain, range=[T["series"][r] for r in domain]),
                     legend=alt.Legend(title=None) if len(domain) > 1 else None)


def _spread(values: list[float], gap: float) -> list[float]:
    """Nudge end-label positions apart by at least `gap` (data units), keeping their mean."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = list(values)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    shift = (sum(values) - sum(out)) / len(out)
    return [v + shift for v in out]


def lines(df: pd.DataFrame, y_title: str, y_format: str = "+.0f", shade_years=(), height: int = 260,
          label_expr: str | None = None) -> None:
    """Shared-x line chart. df columns: year, series, value. Crosshair tooltip lists every series;
    the last point of each line is direct-labelled, labels nudged apart so they never overlap."""
    T = tokens()
    domain = [r for r in REGIONS if r in set(df.series)]
    wide = df.pivot_table(index="year", columns="series", values="value").reset_index()
    xs = alt.Scale(domain=[int(df.year.min()), int(df.year.max())], nice=False, zero=False)
    x = alt.X("year:Q", title=None, scale=xs, axis=alt.Axis(format="d", tickMinStep=1, grid=False))
    axis = alt.Axis(format=y_format, tickCount=5, labelExpr=label_expr) if label_expr else alt.Axis(format=y_format, tickCount=5)
    y = alt.Y("value:Q", title=y_title, axis=axis)
    base = alt.Chart(df).encode(x=x)
    layers = []
    if shade_years:
        shade = pd.DataFrame({"x0": [v - 0.4 for v in shade_years], "x1": [v + 0.4 for v in shade_years]})
        layers.append(alt.Chart(shade).mark_rect(color=T["wash"], opacity=0.1).encode(x=alt.X("x0:Q", scale=xs), x2="x1:Q"))
    layers.append(alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=T["axis"], strokeWidth=1).encode(y="z:Q"))
    layers.append(base.mark_line(strokeWidth=2, strokeJoin="round", strokeCap="round").encode(y=y, color=_color(domain)))
    last = df.dropna(subset=["value"]).sort_values("year").groupby("series").tail(1).copy()
    end = alt.Chart(last).encode(x=x, y=y)
    layers.append(end.mark_circle(size=64, opacity=1, stroke=T["surface"], strokeWidth=2).encode(color=_color(domain)))
    if len(domain) > 1:
        span = df.value.max() - min(df.value.min(), 0)
        last["label_y"] = _spread(list(last.value), 0.075 * span)
        layers.append(alt.Chart(last).mark_text(align="left", baseline="middle", dx=8, fontSize=11, color=T["ink2"]).encode(
            x=x, y=alt.Y("label_y:Q", title=y_title), text="series:N"))
    hover = alt.selection_point(fields=["year"], nearest=True, on="pointerover", clear="pointerout", empty=False)
    tips = [alt.Tooltip("year:Q", format="d", title="Year")] + [alt.Tooltip(f"{r}:Q", format=y_format, title=r) for r in domain]
    layers.append(alt.Chart(wide).mark_rule(color=T["axis"], strokeWidth=1).encode(
        x="year:Q", opacity=alt.condition(hover, alt.value(1), alt.value(0)), tooltip=tips).add_params(hover))
    layers.append(base.mark_circle(size=70, stroke=T["surface"], strokeWidth=2).encode(
        y=y, color=_color(domain), opacity=alt.condition(hover, alt.value(1), alt.value(0))).transform_filter(hover))
    show(alt.layer(*layers).resolve_scale(color="shared"), height)


def departure_bars(df: pd.DataFrame, name: str, threshold: float = -20, height: int = 200) -> None:
    """Monsoon departure by year: below normal = dry red, above = wet blue, IMD 'deficient' line."""
    T = tokens()
    d = df.assign(side=lambda t: t.value.lt(0).map({True: "below normal", False: "above normal"}))
    # same room as the HTML dashboard: at least +/-45%, so the deficient line is always on the chart
    ys = alt.Scale(domain=[min(-45, d.value.min()) - 3, max(45, d.value.max()) + 3], nice=False)
    bars = alt.Chart(d).mark_bar(cornerRadiusEnd=2, size=7).encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(values=[y for y in d.year if y % 5 == 0], labelAngle=0)),
        y=alt.Y("value:Q", title="% vs 1971–2020 normal", scale=ys, axis=alt.Axis(format="+.0f", tickCount=5)),
        color=alt.Color("side:N", scale=alt.Scale(domain=["below normal", "above normal"], range=[T["dry"], T["wet"]]),
                        legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("year:O", title=f"{name} monsoon"), alt.Tooltip("value:Q", format="+.1f", title="Departure %")])
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=T["axis"]).encode(y="z:Q")
    # the threshold is named in the caller's caption: any in-plot label would sit on some year's bar
    line = alt.Chart(pd.DataFrame({"t": [threshold]})).mark_rule(color=T["dry"], strokeWidth=1, opacity=0.6).encode(
        y="t:Q", tooltip=[alt.Tooltip("t:Q", format="+.0f", title="IMD deficient (%)")])
    show(alt.layer(zero, bars, line), height)


def coef_plot(rows: pd.DataFrame, unit: str, height: int | None = None) -> None:
    """Point estimate + 90% interval per row. rows: label, est, lo, hi, p, significant, group.
    Filled dot = significant at 10% (wild bootstrap); hollow = inconclusive."""
    T = tokens()
    groups = [g for g in [*REGIONS, "Both states"] if g in set(rows.group)]
    rng = [T["series"].get(g, T["neutral"]) for g in groups]
    color = alt.Color("group:N", scale=alt.Scale(domain=groups, range=rng), legend=None)
    y = alt.Y("label:N", sort=list(rows.label), title=None, axis=alt.Axis(labelLimit=260, labelColor=T["ink"], labelFontSize=12))
    x = alt.X("est:Q", title=unit, axis=alt.Axis(format="+.1f", tickCount=7))
    tips = [alt.Tooltip("label:N", title="Estimate"), alt.Tooltip("est:Q", format="+.2f", title="Effect"),
            alt.Tooltip("lo:Q", format="+.2f", title="90% low"), alt.Tooltip("hi:Q", format="+.2f", title="90% high"),
            alt.Tooltip("p:Q", format=".3f", title="p (wild)")]
    base = alt.Chart(rows).encode(y=y)
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=T["ink2"], strokeWidth=1.2).encode(x="z:Q")
    ci = base.mark_rule(strokeWidth=2, strokeCap="round").encode(x=alt.X("lo:Q", title=unit), x2="hi:Q", color=color, tooltip=tips)
    filled = base.transform_filter("datum.significant").mark_circle(size=80, opacity=1).encode(x=x, color=color, tooltip=tips)
    hollow = base.transform_filter("!datum.significant").mark_point(size=80, filled=True, fill=T["surface"], strokeWidth=2, opacity=1).encode(
        x=x, stroke=alt.Stroke("group:N", scale=alt.Scale(domain=groups, range=rng), legend=None), tooltip=tips)
    show(alt.layer(zero, ci, filled, hollow), height or 30 * len(rows) + 50)


def path_chart(df: pd.DataFrame, unit: str, height: int = 240) -> None:
    """Credit path vs a normal monsoon: one line + 90% band per state. df: state, step, when, est, lo, hi."""
    T = tokens()
    start = pd.DataFrame([{"state": s, "step": 0, "when": "Monsoon", "est": 0.0, "lo": 0.0, "hi": 0.0} for s in df.state.unique()])
    d = pd.concat([start, df[["state", "step", "when", "est", "lo", "hi"]]], ignore_index=True)
    order = ["Monsoon", *df.sort_values("step").when.unique()]
    domain = [s for s in REGIONS if s in set(d.state)]
    color = alt.Color("state:N", scale=alt.Scale(domain=domain, range=[T["series"][s] for s in domain]), legend=alt.Legend(title=None))
    x = alt.X("when:N", sort=order, title=None, axis=alt.Axis(labelAngle=0))
    tips = [alt.Tooltip("state:N", title="State"), alt.Tooltip("when:N", title="When"), alt.Tooltip("est:Q", format="+.1f", title=unit),
            alt.Tooltip("lo:Q", format="+.1f", title="90% low"), alt.Tooltip("hi:Q", format="+.1f", title="90% high")]
    base = alt.Chart(d).encode(x=x, color=color)
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=T["ink2"], strokeWidth=1.2).encode(y="z:Q")
    band = base.mark_area(opacity=0.14).encode(y=alt.Y("lo:Q", title=unit, axis=alt.Axis(format="+.0f", tickCount=5)), y2="hi:Q")
    line = base.mark_line(strokeWidth=2.2).encode(y="est:Q")
    pts = base.mark_circle(size=70, opacity=1, stroke=T["surface"], strokeWidth=2).encode(y="est:Q", tooltip=tips)
    show(alt.layer(zero, band, line, pts), height)
