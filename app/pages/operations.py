import plotly.graph_objects as go
import streamlit as st
from charts import RING, animated_sites, scorecard_heatmap
from theme import (
    AQUA,
    BLUE,
    MODALITY_COLORS,
    ORANGE,
    STATUS,
    VIOLET,
    YELLOW,
    footer,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    show,
    table,
)

page_setup("Hospital scorecard & KPI alerts", "How does each treating site compare on timeliness, treatment mix, "
           "outcomes and cost? Which KPIs moved unexpectedly? Built for the operations and quality team.",
           kicker="Operations", chips=["20+ patient treating sites", "trailing 3-year baselines", "robust z-scores"])

alerts = query("select * from ops.kpi_alerts")
kpi = query("select * from marts.mart_kpi_annual where year_of_diagnosis >= 2000")
kpi_cards([
    {"label": "Alerts detected", "value": len(alerts), "sub": "all diagnosis years", "color": BLUE, "icon": "🔔"},
    {"label": "High severity", "value": int((alerts.severity == "high").sum()), "color": STATUS["critical"], "icon": "🚨"},
    {"label": "Timeliness alerts", "value": int(alerts.kpi.str.contains("days|90d").sum()), "color": ORANGE, "icon": "⏱️"},
    {"label": "Sites monitored", "value": kpi[kpi.entity_type == "Hospital"].entity.nunique(), "color": AQUA, "icon": "🏥"},
])

section("Site scorecard", BLUE, "🏥")
p = query("""select hospital_name, count(*) n,
             percentile_cont(0.5) within group (order by days_to_chemotherapy) filter (where days_to_chemotherapy between 0 and 730) med_chemo,
             100.0*avg(chemo_delayed_over_90d::int) filter (where days_to_chemotherapy between 0 and 730) pct90,
             percentile_cont(0.5) within group (order by days_to_radiation) filter (where days_to_radiation between 0 and 730) med_rt,
             100.0*avg(received_chemotherapy::int) filter (where receptor_subtype in ('Triple negative','HR-/HER2+','HR+/HER2+')
                   and stage_major in ('II','III')) chemo_ind,
             100.0*avg((stage_major in ('III','IV'))::int) adv, 100.0*avg(any_progression_or_recurrence::int) rec,
             avg(total_estimated_cost_usd) cost, avg(n_follow_up_visits) fu
          from marts.mart_patient_360 where is_benchmarkable group by 1 having count(*) >= 20 order by n desc""")
labels = {"med_chemo": "Median days → chemo", "pct90": "Chemo > 90 d %", "med_rt": "Median days → RT",
          "chemo_ind": "Chemo when indicated %", "adv": "Stage III–IV % (case mix)", "rec": "Crude recurrence %",
          "cost": "Mean est. cost $", "fu": "Follow-up visits"}
worse = {"med_chemo": True, "pct90": True, "med_rt": True, "chemo_ind": False, "adv": True, "rec": True, "cost": True, "fu": False}
p["hospital_name"] = p.hospital_name + " (n=" + p.n.astype(str) + ")"
show(scorecard_heatmap(p, "hospital_name", list(labels), labels, worse,
                       "Each cell shows the site's value; colour = how it compares with other sites (red = worse, blue = better)"),
     key="score")
note("Case mix (stage III–IV share) is shown next to outcomes so a site with sicker patients isn't penalised without "
     "context. The <b>Time to treatment</b> page has the formally case-mix-adjusted O/E comparison.", VIOLET)

section("Timeliness over time", ORANGE, "🎞️")
show(animated_sites(kpi), key="anim")

section("KPI trend explorer", AQUA, "📈")
c = st.columns([2, 2])
entities = ["All sites"] + sorted(kpi[kpi.entity_type == "Hospital"].entity.unique())
entity = c[0].selectbox("Entity", entities)
measure = c[1].selectbox("KPI", ["median_days_to_chemotherapy", "pct_chemo_over_90d", "median_days_to_radiation",
                                  "new_diagnoses", "mean_estimated_cost_usd"], format_func=lambda s: s.replace("_", " "))
e = kpi[kpi.entity == entity].sort_values("year_of_diagnosis")
ea = alerts[(alerts.entity == entity) & (alerts.kpi == measure)]
fig = go.Figure(go.Scatter(x=e.year_of_diagnosis, y=e[measure], mode="lines+markers", name=measure.replace("_", " "),
                           line=dict(color=BLUE, width=2.5), marker=dict(size=9, line=RING),
                           hovertemplate="%{x}: <b>%{y:,.1f}</b><extra></extra>"))
if len(ea):
    fig.add_trace(go.Scatter(x=ea.period.astype(int), y=ea.current_value, mode="markers", name="alert",
                             marker=dict(size=18, symbol="diamond", line=RING,
                                         color=[STATUS["critical"] if s == "high" else STATUS["serious"] for s in ea.severity]),
                             text=ea.message, hovertemplate="%{text}<extra></extra>"))
fig.update_layout(height=380, title=f"{measure.replace('_', ' ')} · {entity} (◆ = alert)", hovermode="x unified")
show(fig, key="trend")
mod = e[["year_of_diagnosis", "surgery_patients", "chemotherapy_patients", "radiation_patients", "endocrine_patients"]]
fig = go.Figure()
for col, name in (("surgery_patients", "Surgery"), ("chemotherapy_patients", "Chemotherapy"),
                  ("radiation_patients", "Radiation"), ("endocrine_patients", "Endocrine")):
    fig.add_trace(go.Bar(x=mod.year_of_diagnosis, y=mod[col], name=name, marker=dict(color=MODALITY_COLORS[name], line=RING)))
fig.update_layout(barmode="stack", height=320, bargap=0.25, title=f"Patients by modality and diagnosis year · {entity}")
show(fig, key="mod")

section("Alert feed", STATUS["critical"], "🚨")
f = st.columns(3)
sev = f[0].multiselect("Severity", ["high", "medium"], default=["high", "medium"])
kp = f[1].multiselect("KPI", sorted(alerts.kpi.unique()))
ent = f[2].multiselect("Entity", sorted(alerts.entity.unique()))
a = alerts[alerts.severity.isin(sev)]
a = a[a.kpi.isin(kp)] if kp else a
a = a[a.entity.isin(ent)] if ent else a
for r in a.sort_values(["period", "severity"], ascending=[False, True]).head(20).itertuples():
    st.markdown(f"{'🔴 **High**' if r.severity == 'high' else '🟠 **Medium**'} · `{r.period}` · {r.message}")
table(a, f"All {len(a)} alerts")
note("Alert rule: |change vs trailing 3-year median| ≥ 25%, current n ≥ 8, and robust z ≥ 2. Volume alerts in TCGA "
     "mostly reflect study accrual waves, not clinical demand.", YELLOW)
footer()
