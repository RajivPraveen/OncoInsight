import numpy as np
import plotly.graph_objects as go
import streamlit as st
from charts import RING, cost_stack
from theme import (
    AQUA,
    BLUE,
    GREEN,
    MAGENTA,
    ORANGE,
    STATUS,
    VIOLET,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    kpi_cards,
    note,
    page_setup,
    patients,
    query,
    show,
    small_cohort_guard,
    table,
)

from oncoinsight.analytics.cost_scenarios import Scenario, reprice

page_setup("Cost & what-if", "What does treatment cost by pathway, stage and subtype, and what would change under "
           "realistic policy scenarios? Costs apply 2026 CMS national prices to each patient's observed treatment.",
           kicker="Outcomes & value", chips=["Physician Fee Schedule RVU26D", "ASP Part B Oct-2026", "NADAC",
                                             "facility fees excluded"])
f = cohort_filters()
cohort = apply_filters(patients(), f)
if not small_cohort_guard(len(cohort)):
    st.stop()
lines = query("select patient_id, cost_component, price_id, units, unit_price_usd, estimated_amount_usd, "
              "used_default_quantity from core.fact_estimated_cost")
lines = lines[lines.patient_id.isin(cohort.patient_id)]

base = cohort.total_estimated_cost_usd
kpi_cards([
    {"label": "Mean per patient", "value": fmt_usd(base.mean()), "color": BLUE, "icon": "💵"},
    {"label": "Median per patient", "value": fmt_usd(base.median()), "color": ORANGE, "icon": "📊"},
    {"label": "Cohort total", "value": fmt_usd(base.sum()), "sub": f"{len(cohort):,} patients", "color": AQUA, "icon": "🧾"},
    {"label": "Drug share", "value": f"{100 * cohort.drug_cost_usd.sum() / max(base.sum(), 1):.0f}%", "color": MAGENTA, "icon": "💊"},
    {"label": "Lines using defaults", "value": f"{lines.used_default_quantity.mean():.0%}", "sub": "standard regimen assumed", "color": VIOLET, "icon": "🧮"},
])

tab1, tab2 = st.tabs(["🧭 Where the money goes", "🎛️ What-if simulator"])
with tab1:
    dim = st.radio("Break down by", ["pathway", "stage_major", "receptor_subtype", "site_type"], horizontal=True,
                   format_func=lambda s: s.replace("_", " ").replace("major", "").title())
    g = cohort.groupby(dim)
    d = g.agg(n=("patient_id", "size"), mean_cost_usd=("total_estimated_cost_usd", "mean"),
              drug=("drug_cost_usd", "sum"), admin=("administration_cost_usd", "sum"),
              rad=("radiation_cost_usd", "sum"), surg=("surgery_cost_usd", "sum"),
              tot=("total_estimated_cost_usd", "sum")).reset_index().rename(columns={dim: "dimension_value"})
    d = d[d.n >= 11]
    for a, b in (("drug", "pct_drug"), ("admin", "pct_administration"), ("rad", "pct_radiation"), ("surg", "pct_surgery")):
        d[b] = 100 * d[a] / d.tot.replace(0, np.nan)
    show(cost_stack(d, dim.replace("_", " ")), key="stack")
    pw = cohort.groupby("pathway").agg(n=("patient_id", "size"), cost=("total_estimated_cost_usd", "median"),
                                       rec=("any_progression_or_recurrence", "mean"), mort=("os_event", "mean")).reset_index()
    pw = pw[pw.n >= 10]
    fig = go.Figure(go.Scatter(x=pw.cost, y=pw.rec * 100, mode="markers+text", text=pw.pathway.str.replace("Surgery → ", "S → "),
                               textposition="top center", textfont=dict(size=10, color="#52514e"),
                               marker=dict(size=np.sqrt(pw.n) * 2.2, color=pw.mort * 100, colorscale=[[0, "#cde2fb"], [1, "#0d366b"]],
                                           colorbar=dict(title="mortality %"), line=RING, opacity=0.9),
                               customdata=pw[["n", "mort"]],
                               hovertemplate="<b>%{text}</b><br>median $%{x:,.0f}<br>recurrence %{y:.1f}%"
                                             "<br>mortality %{customdata[1]:.1%} · n=%{customdata[0]}<extra></extra>"))
    fig.update_layout(height=480, xaxis_title="median estimated cost (USD)", yaxis_title="crude recurrence / progression %",
                      title="Value map: cost vs outcome by pathway (bubble = patients, colour = crude mortality)")
    show(fig, key="value")
    note("Crude outcomes are not case-mix adjusted, so pathways with more advanced disease look worse. Use this as "
         "a conversation starter about value, not a verdict.", ORANGE)

with tab2:
    note("Move the sliders to model policy scenarios on the <b>current cohort</b>. The simulator re-prices every cost "
         "line (not averages), so results aggregate correctly to pathways.", GREEN)
    c = st.columns(4)
    hypo = c[0].toggle("Hypofractionate whole-breast radiation", value=False,
                       help="Cap each course's delivery fractions (START/Ontario trials: 15-16; FAST-Forward: 5)")
    fx = c[0].slider("Fractions per course", 5, 25, 16, disabled=not hypo)
    biosim = c[1].slider("Trastuzumab biosimilar discount %", 0, 70, 0)
    drug_infl = c[2].slider("Other drug price change %", -30, 30, 0)
    fee = c[3].slider("Physician fee schedule change %", -10, 10, 0)
    s = reprice(lines, Scenario(hypo, fx, biosim, drug_infl, fee))
    s["estimated_amount_usd"] = s.baseline
    base_total, scen_total = s.estimated_amount_usd.sum(), s.scenario.sum()
    delta = scen_total - base_total
    kpi_cards([
        {"label": "Baseline cohort cost", "value": fmt_usd(base_total), "color": BLUE, "icon": "📌"},
        {"label": "Scenario cohort cost", "value": fmt_usd(scen_total), "color": ORANGE, "icon": "🎛️"},
        {"label": "Change", "value": fmt_usd(delta, signed=True), "sub": f"{delta / base_total:+.1%}",
         "color": STATUS["good"] if delta < -0.5 else (STATUS["critical"] if delta > 0.5 else BLUE),
         "icon": "📉" if delta < -0.5 else ("📈" if delta > 0.5 else "⏸️")},
        {"label": "Per patient", "value": fmt_usd(delta / len(cohort), signed=True), "color": VIOLET, "icon": "👤"},
    ])
    comp = s.groupby("cost_component")[["estimated_amount_usd", "scenario"]].sum()
    comp["delta"] = comp.scenario - comp.estimated_amount_usd
    labels = [c.title() for c in comp.index]
    fig = go.Figure(go.Waterfall(
        x=["Baseline"] + labels + ["Scenario"], measure=["absolute"] + ["relative"] * len(comp) + ["total"],
        y=[base_total] + comp.delta.tolist() + [0], connector=dict(line=dict(color="#c3c2b7")),
        increasing=dict(marker=dict(color=STATUS["critical"])), decreasing=dict(marker=dict(color=STATUS["good"])),
        totals=dict(marker=dict(color=BLUE)), text=[fmt_usd(base_total)] + [fmt_usd(v, signed=True) for v in comp.delta] + [fmt_usd(scen_total)],
        textposition="outside", hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>"))
    fig.update_layout(height=420, title="Cost bridge: baseline → scenario, by cost component", yaxis_title="USD (cohort)",
                      showlegend=False)
    show(fig, key="waterfall")
    per = s.merge(cohort[["patient_id", "pathway"]], on="patient_id").groupby("pathway")[["estimated_amount_usd", "scenario"]].sum()
    n = cohort.pathway.value_counts()
    per = per.loc[n[n >= 10].index.intersection(per.index)]
    per = (per.div(n, axis=0)).dropna().sort_values("estimated_amount_usd")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(y=per.index, x=per.estimated_amount_usd, name="Baseline", orientation="h", marker=dict(color=BLUE, line=RING)))
    fig2.add_trace(go.Bar(y=per.index, x=per.scenario, name="Scenario", orientation="h", marker=dict(color=ORANGE, line=RING)))
    fig2.update_layout(barmode="group", height=160 + 44 * len(per), bargap=0.3, xaxis_title="mean cost per patient (USD)",
                       title="Mean cost per patient by pathway: baseline vs scenario")
    show(fig2, key="scen_pw")
    table(comp.reset_index(), "Scenario by cost component")
footer()
