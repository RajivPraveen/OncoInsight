import html

import plotly.graph_objects as go
import streamlit as st
from charts import RING, animated_sites, scorecard_heatmap
from theme import (
    BLUE,
    MODALITY_COLORS,
    STATUS,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    plain,
    query,
    section,
    show,
    table,
)

page_setup("Hospital comparison",
           "A report card for every hospital with at least 20 patients, plus automatic alerts when a measure jumps "
           "from one year to the next. Built for the team that runs quality and operations.",
           kicker="Results",
           question="Which hospitals stand out, good or bad, and did anything change suddenly?",
           answer="Waits for chemotherapy vary a lot between hospitals. The report card shows each hospital's numbers "
                  "side by side, and the alerts flag years where a measure moved by <b>25% or more</b>.")

alerts = query("select * from ops.kpi_alerts")
kpi = query("select * from marts.mart_kpi_annual where year_of_diagnosis >= 2000")
kpi_cards([
    {"label": "Hospitals compared", "value": kpi[kpi.entity_type == "Hospital"].entity.nunique()},
    {"label": "Alerts raised", "value": len(alerts), "sub": "across all years"},
    {"label": "Serious alerts", "value": int((alerts.severity == "high").sum())},
    {"label": "Alerts about waiting times", "value": int(alerts.kpi.str.contains("days|90d").sum())},
])

section("Hospital report card", blurb="Each row is a hospital. Hover a cell for its value.")
p = query("""select hospital_name, count(*) n,
             percentile_cont(0.5) within group (order by days_to_chemotherapy) filter (where days_to_chemotherapy between 0 and 730) med_chemo,
             100.0*avg(chemo_delayed_over_90d::int) filter (where days_to_chemotherapy between 0 and 730) pct90,
             percentile_cont(0.5) within group (order by days_to_radiation) filter (where days_to_radiation between 0 and 730) med_rt,
             100.0*avg(received_chemotherapy::int) filter (where receptor_subtype in ('Triple negative','HR-/HER2+','HR+/HER2+')
                   and stage_major in ('II','III')) chemo_ind,
             100.0*avg((stage_major in ('III','IV'))::int) adv, 100.0*avg(any_progression_or_recurrence::int) rec,
             avg(total_estimated_cost_usd) cost, avg(n_follow_up_visits) fu
          from marts.mart_patient_360 where is_benchmarkable group by 1 having count(*) >= 20 order by n desc""")
labels = {"med_chemo": "Typical days to chemo", "pct90": "% chemo after 90 days", "med_rt": "Typical days to radiation",
          "chemo_ind": "% got chemo when recommended", "adv": "% advanced cancer", "rec": "% cancer came back",
          "cost": "Average cost ($)", "fu": "Check-ups per patient"}
worse = {"med_chemo": True, "pct90": True, "med_rt": True, "chemo_ind": False, "adv": True, "rec": True, "cost": True, "fu": False}
p["hospital_name"] = p.hospital_name + " (" + p.n.astype(str) + " patients)"
show(scorecard_heatmap(p, "hospital_name", list(labels), labels, worse, ""), key="score")
how_to_read("each number is that hospital's actual value. Colour compares it with the other hospitals: <b>red</b> = "
            "worse than most, <b>blue</b> = better, grey = about average. The '% advanced cancer' column shows how sick "
            "each hospital's patients were, so you can judge the rest fairly.")

section("Chemotherapy waits, year by year", blurb="Press ▶ to play. Each bubble is a hospital; bigger = more patients.")
show(animated_sites(kpi), key="anim")
how_to_read("further right = longer typical wait; higher = more patients waiting over 90 days. The red line is 90 "
            "days. Hospitals in the bottom-left are doing well.")

section("Track a measure over time", blurb="Diamonds mark years where an alert was raised.")
c = st.columns([2, 2])
entities = ["All sites"] + sorted(kpi[kpi.entity_type == "Hospital"].entity.unique())
entity = c[0].selectbox("Hospital", entities, format_func=lambda e: "All hospitals" if e == "All sites" else e)
MEASURES = {"median_days_to_chemotherapy": "Typical days to chemotherapy", "pct_chemo_over_90d": "% chemo after 90 days",
            "median_days_to_radiation": "Typical days to radiation", "new_diagnoses": "New patients",
            "mean_estimated_cost_usd": "Average cost ($)"}
measure = c[1].selectbox("Measure", list(MEASURES), format_func=MEASURES.get)
e = kpi[kpi.entity == entity].sort_values("year_of_diagnosis")
ea = alerts[(alerts.entity == entity) & (alerts.kpi == measure)]
fig = go.Figure(go.Scatter(x=e.year_of_diagnosis, y=e[measure], mode="lines+markers", name=MEASURES[measure],
                           line=dict(color=BLUE, width=2.5), marker=dict(size=9, line=RING),
                           hovertemplate="%{x}: <b>%{y:,.1f}</b><extra></extra>"))
if len(ea):
    fig.add_trace(go.Scatter(x=ea.period.astype(int), y=ea.current_value, mode="markers", name="alert",
                             marker=dict(size=18, symbol="diamond", line=RING,
                                         color=[STATUS["critical"] if s == "high" else STATUS["serious"] for s in ea.severity]),
                             text=ea.message, hovertemplate="%{text}<extra></extra>"))
fig.update_layout(height=380, title=f"{MEASURES[measure]} · {'All hospitals' if entity == 'All sites' else entity}",
                  hovermode="x unified", xaxis_title="year diagnosed")
show(fig, key="trend")
mod = e[["year_of_diagnosis", "surgery_patients", "chemotherapy_patients", "radiation_patients", "endocrine_patients"]]
fig = go.Figure()
for col, name in (("surgery_patients", "Surgery"), ("chemotherapy_patients", "Chemotherapy"),
                  ("radiation_patients", "Radiation"), ("endocrine_patients", "Endocrine")):
    fig.add_trace(go.Bar(x=mod.year_of_diagnosis, y=mod[col], name=plain(name), marker=dict(color=MODALITY_COLORS[name], line=RING)))
fig.update_layout(barmode="stack", height=320, bargap=0.25, xaxis_title="year diagnosed",
                  title=f"Patients receiving each treatment, by year · {'All hospitals' if entity == 'All sites' else entity}")
show(fig, key="mod")

section("Alerts", blurb="Raised automatically when a measure moves 25% or more compared with the previous 3 years.")
f = st.columns(3)
sev = f[0].multiselect("Severity", ["high", "medium"], default=["high", "medium"], format_func=str.capitalize)
kp = f[1].multiselect("Measure", sorted(alerts.kpi.unique()), format_func=lambda k: MEASURES.get(k, k.replace("_", " ")))
ent = f[2].multiselect("Hospital", sorted(alerts.entity.unique()))
a = alerts[alerts.severity.isin(sev)]
a = a[a.kpi.isin(kp)] if kp else a
a = a[a.entity.isin(ent)] if ent else a
for r in a.sort_values(["period", "severity"], ascending=[False, True]).head(20).itertuples():
    tag = (f"<span style='color:{STATUS['critical']};font-weight:600'>● High</span>" if r.severity == "high"
           else f"<span style='color:{STATUS['serious']};font-weight:600'>● Medium</span>")
    st.markdown(f"{tag} &nbsp;·&nbsp; **{r.period}** &nbsp;·&nbsp; {html.escape(str(r.message))}", unsafe_allow_html=True)
table(a, f"All {len(a)} alerts")
note("<b>How alerts work:</b> a measure is flagged when it changes by 25% or more against the median of the "
     "previous 3 years, with at least 8 patients and a statistically unusual jump. Alerts about patient numbers "
     "mostly reflect when the research study recruited, not real changes in demand.")
footer()
