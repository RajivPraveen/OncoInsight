import plotly.graph_objects as go
import streamlit as st
from charts import RING, sunburst_journey, world_map
from theme import (
    AQUA,
    BLUE,
    MAGENTA,
    MODALITY_COLORS,
    ORANGE,
    STATUS,
    VIOLET,
    YELLOW,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    kpi_cards,
    note,
    page_setup,
    patients,
    query,
    section,
    show,
    small_cohort_guard,
)

page_setup("Breast cancer care, measured end to end",
           "How patients move from diagnosis through surgery, chemotherapy, radiation and endocrine therapy - where "
           "delays happen, how outcomes and costs differ, and whether care is equitable. Built on real, public "
           "patient-level data.",
           kicker="OncoInsight · overview",
           chips=["1,098 TCGA-BRCA patients", "40 contributing sites", "2,509-patient METABRIC validation cohort",
                  "FHIR R4 → dbt → Dagster", "Claude analytics assistant"])

f = cohort_filters()
p = apply_filters(patients(), f)
if not small_cohort_guard(len(p)):
    st.stop()

timed = p[p.days_to_chemotherapy.between(0, 730)]
alerts_high = int(query("select count(*) n from ops.kpi_alerts where severity='high'").n[0])
kpi_cards([
    {"label": "Patients in cohort", "value": f"{len(p):,}", "sub": f"{p.hospital_id.nunique()} sites", "color": BLUE, "icon": "👥"},
    {"label": "Median days to chemo", "value": f"{timed.days_to_chemotherapy.median():.0f}" if len(timed) else "—",
     "sub": f"n = {len(timed)} adjuvant starts", "color": ORANGE, "icon": "⏱️"},
    {"label": "Chemo starts > 90 days", "value": f"{100 * timed.chemo_delayed_over_90d.mean():.1f}%" if len(timed) else "—",
     "sub": "linked to worse survival", "color": STATUS["critical"], "icon": "⚠️"},
    {"label": "Recurrence / progression", "value": f"{100 * p.any_progression_or_recurrence.mean():.1f}%",
     "sub": "crude, during follow-up", "color": MAGENTA, "icon": "🔁"},
    {"label": "Mean estimated cost", "value": fmt_usd(p.total_estimated_cost_usd.mean()),
     "sub": "CMS 2026 reference prices", "color": AQUA, "icon": "💵"},
    {"label": "Open high alerts", "value": alerts_high, "sub": "KPI monitor", "color": YELLOW, "icon": "🚨"},
])

note("<b>How to use this dashboard.</b> The filter row above scopes every chart on every page - pick a stage, subtype "
     "or age group and the numbers update everywhere. Start with <b>Why OncoInsight?</b> for the story, or jump to "
     "<b>Treatment pathways</b> and click any pathway to drill in.", VIOLET)

left, right = st.columns([1.15, 1])
with left:
    section("The patients", BLUE, "🧬")
    show(sunburst_journey(p), key="sunburst")
with right:
    section("The journey at a glance", ORANGE, "🧭")
    received = {"Surgery": p.received_surgery.mean(), "Chemotherapy": p.received_chemotherapy.mean(),
                "Radiation": p.received_radiation.mean(), "Endocrine": p.received_endocrine.mean(),
                "HER2-targeted": p.received_her2_targeted.mean()}
    fig = go.Figure(go.Bar(x=[v * 100 for v in received.values()], y=list(received), orientation="h",
                           marker=dict(color=[MODALITY_COLORS[k] for k in received], line=RING),
                           text=[f"{v:.0%}" for v in received.values()], textposition="outside",
                           hovertemplate="%{y}: <b>%{x:.1f}%</b> of patients<extra></extra>"))
    fig.update_layout(height=280, title="Share of patients receiving each modality", xaxis=dict(range=[0, 112], title="%"),
                      yaxis=dict(autorange="reversed"), margin=dict(r=40), bargap=0.35)
    show(fig, key="modalities")
    med = {k: p[c].where(p[c].between(0, 730)).median() for k, c in
           (("Chemotherapy", "days_to_chemotherapy"), ("Radiation", "days_to_radiation"), ("Endocrine", "days_to_endocrine"))}
    fig2 = go.Figure(go.Bar(x=list(med.values()), y=list(med), orientation="h",
                            marker=dict(color=[MODALITY_COLORS[k] for k in med], line=RING),
                            text=[f"{v:.0f} days" for v in med.values()], textposition="outside",
                            hovertemplate="%{y}: median <b>%{x:.0f}</b> days after diagnosis<extra></extra>"))
    fig2.add_vline(x=90, line_color=STATUS["critical"], line_width=1, annotation_text="90 days")
    fig2.update_layout(height=230, title="Median days from diagnosis to start", yaxis=dict(autorange="reversed"),
                       xaxis=dict(range=[0, 230]), margin=dict(r=40))
    show(fig2, key="median_start")

section("Where patients came from", AQUA, "🌍")
show(world_map(p), key="map")
footer()
