import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    INK_2,
    MODALITY_COLORS,
    STATUS,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    kpi_cards,
    page_setup,
    patients,
    pills,
    plain,
    query,
    section,
    show,
    table,
)

page_setup("One patient's journey",
           "Pick any patient to see their diagnosis, every treatment on a timeline, their check-ups, what happened "
           "to them, and what their care cost. All patients are real and de-identified.",
           kicker="The patient journey")
f = cohort_filters()
cohort = apply_filters(patients(), f)

section("Find a patient")
c = st.columns([1.2, 1.2, 1.2, 2])
path_sel = c[0].selectbox("Treatment path", ["Any"] + cohort.pathway.value_counts().index.tolist())
outcome_sel = c[1].selectbox("Outcome", ["Any", "Deceased", "Recurrence / progression", "No event recorded"])
site_sel = c[2].selectbox("Hospital", ["Any"] + sorted(cohort.hospital_name.dropna().unique()))
pool = cohort
if path_sel != "Any":
    pool = pool[pool.pathway == path_sel]
if outcome_sel == "Deceased":
    pool = pool[pool.os_event == 1]
elif outcome_sel == "Recurrence / progression":
    pool = pool[pool.any_progression_or_recurrence]
elif outcome_sel == "No event recorded":
    pool = pool[(pool.os_event == 0) & ~pool.any_progression_or_recurrence]
if site_sel != "Any":
    pool = pool[pool.hospital_name == site_sel]
if pool.empty:
    st.info("No patients match - loosen the filters.")
    st.stop()
if c[3].button("Show me a random patient", icon=":material/shuffle:"):
    st.session_state["p360_pick"] = pool.sample(1).patient_barcode.iloc[0]
options = pool.patient_barcode.sort_values().tolist()
pick = st.session_state.get("p360_pick")
barcode = c[3].selectbox(f"Patient ID ({len(options):,} match)", options,
                         index=options.index(pick) if pick in options else 0)
p = cohort[cohort.patient_barcode == barcode].iloc[0]

event = "Deceased" if p.os_event == 1 else ("Recurrence / progression" if p.any_progression_or_recurrence else "No event recorded")
ev_color = {"Deceased": STATUS["critical"], "Recurrence / progression": STATUS["serious"]}.get(event, STATUS["good"])
kpi_cards([
    {"label": "Patient", "value": p.patient_barcode, "sub": f"{p.gender}, age {p.age_at_diagnosis:.0f} · {p.race}"},
    {"label": "Cancer stage", "value": p.stage_group, "sub": f"{p.histology_group}"},
    {"label": "Tumour type", "value": p.receptor_subtype, "sub": f"ER {p.er_status} · PR {p.pr_status} · HER2 {p.her2_status}"},
    {"label": "What happened", "value": event, "sub": f"followed for {p.os_months:.0f} months"},
    {"label": "Estimated cost of care", "value": fmt_usd(p.total_estimated_cost_usd), "sub": p.hospital_name},
])

section("Treatment timeline", blurb="Day 0 is the day of diagnosis. Hover any bar for dates and cost.")
pills({plain(k): v for k, v in MODALITY_COLORS.items() if k in (p.pathway or "")})
tx = query("""select pathway_modality, pathway_group, treatment_name, start_day, end_day, status, treatment_intent,
                     treatment_outcome, number_of_cycles, number_of_fractions, estimated_cost_usd, start_day_imputed
              from core.fact_treatment where patient_id = %(p)s order by start_day nulls last""", {"p": p.patient_id})
dated = tx[tx.start_day.notna() & tx.pathway_group.notna() & tx.status.isin(["completed", "in-progress", "active"])]
enc = query("select days_from_diagnosis, timepoint from core.fact_encounter where patient_id=%(p)s", {"p": p.patient_id})
if len(dated):
    fig = go.Figure()
    for grp, g in dated.groupby("pathway_group", sort=False):
        end = g.end_day.fillna(g.start_day + 1)
        fig.add_trace(go.Bar(y=g.treatment_name, x=(end - g.start_day).clip(lower=4), base=g.start_day, orientation="h",
                             name=plain(grp), marker=dict(color=MODALITY_COLORS.get(grp), line=RING),
                             customdata=pd.concat([g.start_day, end, g.estimated_cost_usd], axis=1),
                             hovertemplate="<b>%{y}</b><br>day %{customdata[0]:.0f} → %{customdata[1]:.0f}"
                                           "<br>est. $%{customdata[2]:,.0f}<extra>" + grp + "</extra>"))
    if len(enc):
        fig.add_trace(go.Scatter(x=enc.days_from_diagnosis, y=["Check-ups"] * len(enc), mode="markers",
                                 name="Check-up", marker=dict(size=10, color=INK_2, symbol="diamond", line=RING),
                                 text=enc.timepoint, hovertemplate="%{text} · day %{x}<extra></extra>"))
    if pd.notna(p.days_to_recurrence):
        fig.add_vline(x=p.days_to_recurrence, line_color=STATUS["critical"], line_width=2,
                      annotation_text="cancer came back", annotation_font_color=STATUS["critical"])
    fig.add_vline(x=0, line_color="#4b5563", line_width=1, annotation_text="diagnosis")
    fig.update_layout(height=140 + 38 * (dated.treatment_name.nunique() + 1), barmode="overlay", bargap=0.35,
                      xaxis_title="days since diagnosis", margin=dict(t=40))
    show(fig, key="timeline")
else:
    st.info("This patient has no dated treatments (undated records are listed below).")
if not p.pathway_is_complete:
    st.caption("Some of this patient's treatments have no date in the source data, so the timeline may be missing steps.")
table(tx, "All treatment records for this patient")

section("All patients matching the filters")
table(cohort[["patient_barcode", "age_at_diagnosis", "stage_group", "receptor_subtype", "hospital_name", "pathway",
              "days_to_chemotherapy", "os_months", "os_event", "total_estimated_cost_usd"]], "Patient list")
footer()
