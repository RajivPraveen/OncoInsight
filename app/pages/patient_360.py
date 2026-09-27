import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    AQUA,
    BLUE,
    MAGENTA,
    MODALITY_COLORS,
    ORANGE,
    STATUS,
    SUBTYPE_COLORS,
    YELLOW,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    kpi_cards,
    page_setup,
    patients,
    pills,
    query,
    section,
    show,
    table,
)

page_setup("Patient 360", "Every patient's journey in one longitudinal view: demographics, tumour biology, "
           "each treatment on a timeline, follow-up, outcome and estimated cost.", kicker="Care journey")
f = cohort_filters()
cohort = apply_filters(patients(), f)

section("Find a patient", BLUE, "🔎")
c = st.columns([1.2, 1.2, 1.2, 2])
path_sel = c[0].selectbox("Pathway", ["Any"] + cohort.pathway.value_counts().index.tolist())
outcome_sel = c[1].selectbox("Outcome", ["Any", "Deceased", "Recurrence / progression", "No event recorded"])
site_sel = c[2].selectbox("Site", ["Any"] + sorted(cohort.hospital_name.dropna().unique()))
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
if c[3].button("🎲 Surprise me with a random patient"):
    st.session_state["p360_pick"] = pool.sample(1).patient_barcode.iloc[0]
options = pool.patient_barcode.sort_values().tolist()
pick = st.session_state.get("p360_pick")
barcode = c[3].selectbox(f"Patient ({len(options):,} match)", options,
                         index=options.index(pick) if pick in options else 0)
p = cohort[cohort.patient_barcode == barcode].iloc[0]

event = "Deceased" if p.os_event == 1 else ("Recurrence / progression" if p.any_progression_or_recurrence else "No event recorded")
ev_color = {"Deceased": STATUS["critical"], "Recurrence / progression": STATUS["serious"]}.get(event, STATUS["good"])
kpi_cards([
    {"label": "Patient", "value": p.patient_barcode, "sub": f"{p.gender}, {p.age_at_diagnosis:.0f} y · {p.race}", "color": BLUE, "icon": "🧑"},
    {"label": "Diagnosis", "value": p.stage_group, "sub": f"{p.t_category}{p.n_category}{p.m_category} · {p.histology_group}", "color": ORANGE, "icon": "🩺"},
    {"label": "Tumour biology", "value": p.receptor_subtype, "sub": f"ER {p.er_status} · PR {p.pr_status} · HER2 {p.her2_status}",
     "color": SUBTYPE_COLORS.get(p.receptor_subtype, BLUE), "icon": "🧬"},
    {"label": "Outcome", "value": event, "sub": f"follow-up {p.os_months:.0f} months", "color": ev_color, "icon": "📍"},
    {"label": "Estimated cost", "value": fmt_usd(p.total_estimated_cost_usd), "sub": p.hospital_name, "color": AQUA, "icon": "💵"},
])

section("Treatment timeline", MAGENTA, "🗓️")
pills({k: v for k, v in MODALITY_COLORS.items() if k in (p.pathway or "")})
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
                             name=grp, marker=dict(color=MODALITY_COLORS.get(grp), line=RING),
                             customdata=pd.concat([g.start_day, end, g.estimated_cost_usd], axis=1),
                             hovertemplate="<b>%{y}</b><br>day %{customdata[0]:.0f} → %{customdata[1]:.0f}"
                                           "<br>est. $%{customdata[2]:,.0f}<extra>" + grp + "</extra>"))
    if len(enc):
        fig.add_trace(go.Scatter(x=enc.days_from_diagnosis, y=["Follow-up visits"] * len(enc), mode="markers",
                                 name="Follow-up", marker=dict(size=10, color=BLUE, symbol="diamond", line=RING),
                                 text=enc.timepoint, hovertemplate="%{text} · day %{x}<extra></extra>"))
    if pd.notna(p.days_to_recurrence):
        fig.add_vline(x=p.days_to_recurrence, line_color=STATUS["critical"], line_width=2,
                      annotation_text="recurrence", annotation_font_color=STATUS["critical"])
    fig.add_vline(x=0, line_color="#52514e", line_width=1, annotation_text="diagnosis")
    fig.update_layout(height=140 + 38 * (dated.treatment_name.nunique() + 1), barmode="overlay", bargap=0.35,
                      xaxis_title="days from index diagnosis", title="Hover any bar for dates and estimated cost")
    show(fig, key="timeline")
else:
    st.info("This patient has no dated treatments (undated records are listed below).")
if not p.pathway_is_complete:
    st.caption("⚠️ Some delivered treatments for this patient are undated, so the pathway may be missing steps.")
table(tx, "All treatment records (FHIR Procedure / MedicationAdministration / MedicationStatement)")

section("Cohort roster", YELLOW, "📋")
table(cohort[["patient_barcode", "age_at_diagnosis", "stage_group", "receptor_subtype", "hospital_name", "pathway",
              "days_to_chemotherapy", "os_months", "os_event", "total_estimated_cost_usd"]], "Patients in the cohort")
footer()
