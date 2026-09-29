import numpy as np
import plotly.graph_objects as go
import streamlit as st
from charts import RING, cost_stack
from theme import (
    BLUE,
    ORANGE,
    STATUS,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    patients,
    plain,
    query,
    section,
    show,
    small_cohort_guard,
    table,
)

from oncoinsight.analytics.cost_scenarios import Scenario, reprice

page_setup("Cost",
           "What each patient's treatment costs, where the money goes, and how much realistic changes could save. "
           "Costs are estimates: each patient's actual treatments priced at 2026 Medicare rates (hospital facility "
           "fees not included).",
           kicker="Results",
           question="What does breast cancer treatment cost, and what could the network save?",
           answer="About <b>$15K</b> per patient on average, mostly drugs. HER2+ patients cost about <b>2×</b> more "
                  "because of HER2-targeted drugs. Giving radiation in fewer, larger doses alone would cut total cost "
                  "by about <b>21%</b>.")
f = cohort_filters()
cohort = apply_filters(patients(), f)
if not small_cohort_guard(len(cohort)):
    st.stop()
lines = query("select patient_id, cost_component, price_id, units, unit_price_usd, estimated_amount_usd, "
              "used_default_quantity from core.fact_estimated_cost")
lines = lines[lines.patient_id.isin(cohort.patient_id)]

base = cohort.total_estimated_cost_usd
kpi_cards([
    {"label": "Average cost per patient", "value": fmt_usd(base.mean())},
    {"label": "Typical (median) cost", "value": fmt_usd(base.median()), "sub": "half of patients cost less"},
    {"label": "Total for these patients", "value": fmt_usd(base.sum()), "sub": f"{len(cohort):,} patients"},
    {"label": "Share spent on drugs", "value": f"{100 * cohort.drug_cost_usd.sum() / max(base.sum(), 1):.0f}%"},
])

tab1, tab2 = st.tabs(["Where the money goes", "What if we changed something?"])
with tab1:
    DIMS = {"pathway": "Treatment path", "stage_major": "Cancer stage", "receptor_subtype": "Tumour type", "site_type": "Hospital type"}
    dim = st.radio("Break down by", list(DIMS), horizontal=True, format_func=DIMS.get)
    g = cohort.groupby(dim)
    d = g.agg(n=("patient_id", "size"), mean_cost_usd=("total_estimated_cost_usd", "mean"),
              drug=("drug_cost_usd", "sum"), admin=("administration_cost_usd", "sum"),
              rad=("radiation_cost_usd", "sum"), surg=("surgery_cost_usd", "sum"),
              tot=("total_estimated_cost_usd", "sum")).reset_index().rename(columns={dim: "dimension_value"})
    d = d[d.n >= 11]
    for a, b in (("drug", "pct_drug"), ("admin", "pct_administration"), ("rad", "pct_radiation"), ("surg", "pct_surgery")):
        d[b] = 100 * d[a] / d.tot.replace(0, np.nan)
    if dim == "pathway":
        d["dimension_value"] = d.dimension_value.map(plain)
    show(cost_stack(d, DIMS[dim]), key="stack")
    how_to_read("each bar is the average cost per patient, split into what the money was spent on. The number at "
                "the end is the total.")
    pw = cohort.groupby("pathway").agg(n=("patient_id", "size"), cost=("total_estimated_cost_usd", "median"),
                                       rec=("any_progression_or_recurrence", "mean"), mort=("os_event", "mean")).reset_index()
    pw = pw[pw.n >= 10]
    section("Cost vs. outcome for each treatment path")
    fig = go.Figure(go.Scatter(x=pw.cost, y=pw.rec * 100, mode="markers+text", text=pw.pathway.map(plain).str.replace("Surgery → ", ""),
                               textposition="top center", textfont=dict(size=10, color="#4b5563"),
                               marker=dict(size=np.sqrt(pw.n) * 2.2, color=pw.mort * 100, colorscale=[[0, "#dde7f3"], [1, "#1b3a61"]],
                                           colorbar=dict(title="% died"), line=RING, opacity=0.9),
                               customdata=pw[["n", "mort"]],
                               hovertemplate="<b>Surgery → %{text}</b><br>typical cost $%{x:,.0f}<br>cancer came back %{y:.0f}%"
                                             "<br>died %{customdata[1]:.0%} · %{customdata[0]} patients<extra></extra>"))
    fig.update_layout(height=480, xaxis_title="typical cost per patient ($)", yaxis_title="% whose cancer came back",
                      margin=dict(t=20))
    show(fig, key="value")
    how_to_read("each bubble is a treatment path (all start with surgery). Further right = more expensive, higher = "
                "cancer came back more often. Bigger bubble = more patients; darker = more deaths. Not adjusted for "
                "stage, so paths used for advanced cancer look worse.")

with tab2:
    note("Try a change below and see what it would do to the cost of the patients currently shown. Every "
         "individual treatment is re-priced, so the totals are exact rather than rough averages.")
    c = st.columns(4)
    hypo = c[0].toggle("Give radiation in fewer, larger doses", value=False,
                       help="Called hypofractionation. Clinical trials show 15-16 sessions (or even 5) work as well as 25.")
    fx = c[0].slider("Radiation sessions per patient", 5, 25, 16, disabled=not hypo)
    biosim = c[1].slider("Discount from cheaper copies of trastuzumab (%)", 0, 70, 0,
                         help="Biosimilars: lower-cost versions of the HER2 drug trastuzumab")
    drug_infl = c[2].slider("Change in other drug prices (%)", -30, 30, 0)
    fee = c[3].slider("Change in doctor fees (%)", -10, 10, 0)
    s = reprice(lines, Scenario(hypo, fx, biosim, drug_infl, fee))
    s["estimated_amount_usd"] = s.baseline
    base_total, scen_total = s.estimated_amount_usd.sum(), s.scenario.sum()
    delta = scen_total - base_total
    kpi_cards([
        {"label": "Cost today", "value": fmt_usd(base_total)},
        {"label": "Cost with your changes", "value": fmt_usd(scen_total)},
        {"label": "Difference", "value": fmt_usd(delta, signed=True), "sub": f"{delta / base_total:+.1%}"},
        {"label": "Difference per patient", "value": fmt_usd(delta / len(cohort), signed=True)},
    ])
    comp = s.groupby("cost_component")[["estimated_amount_usd", "scenario"]].sum()
    comp["delta"] = comp.scenario - comp.estimated_amount_usd
    labels = [{"administration": "Giving the drugs"}.get(c, c.title()) for c in comp.index]
    fig = go.Figure(go.Waterfall(
        x=["Today"] + labels + ["With changes"], measure=["absolute"] + ["relative"] * len(comp) + ["total"],
        y=[base_total] + comp.delta.tolist() + [0], connector=dict(line=dict(color="#d4d2cc")),
        increasing=dict(marker=dict(color=STATUS["critical"])), decreasing=dict(marker=dict(color=STATUS["good"])),
        totals=dict(marker=dict(color=BLUE)), text=[fmt_usd(base_total)] + [fmt_usd(v, signed=True) if abs(v) >= 0.5 else "" for v in comp.delta] + [fmt_usd(scen_total)],
        textposition="outside", hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>"))
    fig.update_layout(height=420, title="From today's cost to the new cost", yaxis_title="total cost ($)",
                      showlegend=False)
    show(fig, key="waterfall")
    how_to_read("start at today's total on the left. Each middle bar shows how much one type of cost goes up "
                "(<b>red</b>) or down (<b>green</b>). The last bar is the new total.")
    per = s.merge(cohort[["patient_id", "pathway"]], on="patient_id").groupby("pathway")[["estimated_amount_usd", "scenario"]].sum()
    n = cohort.pathway.value_counts()
    per = per.loc[n[n >= 10].index.intersection(per.index)]
    per = (per.div(n, axis=0)).dropna().sort_values("estimated_amount_usd")
    fig2 = go.Figure()
    per.index = per.index.map(plain)
    fig2.add_trace(go.Bar(y=per.index, x=per.estimated_amount_usd, name="Today", orientation="h", marker=dict(color=BLUE, line=RING)))
    fig2.add_trace(go.Bar(y=per.index, x=per.scenario, name="With changes", orientation="h", marker=dict(color=ORANGE, line=RING)))
    fig2.update_layout(barmode="group", height=160 + 44 * len(per), bargap=0.3, xaxis_title="average cost per patient ($)",
                       title="Average cost per patient for each treatment path")
    show(fig2, key="scen_pw")
    table(comp.reset_index(), "Change by type of cost")
footer()
