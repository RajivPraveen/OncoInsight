import plotly.graph_objects as go
import streamlit as st
from charts import pathway_treemap, sankey
from theme import (
    AQUA,
    BLUE,
    MAGENTA,
    MODALITY_COLORS,
    ORANGE,
    VIOLET,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    kpi_cards,
    note,
    page_setup,
    patients,
    pills,
    query,
    section,
    selected_points,
    show,
    small_cohort_guard,
    table,
)

page_setup("Treatment pathways", "Which sequences of surgery, chemotherapy, radiation, endocrine and HER2-targeted "
           "therapy do patients follow? How long do they take, what do they cost, and how do patients do afterwards?",
           kicker="Care journey")
f = cohort_filters()
cohort = apply_filters(patients(), f)
if not small_cohort_guard(len(cohort)):
    st.stop()
steps = apply_filters(query("select * from marts.mart_patient_pathway_steps"), f)

top = cohort.pathway.value_counts()
kpi_cards([
    {"label": "Distinct pathways", "value": f"{len(top)}", "sub": f"top 5 cover {top.head(5).sum() / len(cohort):.0%}", "color": BLUE, "icon": "🔀"},
    {"label": "Most common", "value": top.index[0].replace("Surgery", "S").replace("Chemotherapy", "Chemo")
     .replace("Radiation", "RT").replace("Endocrine", "Endo"), "sub": f"{top.iloc[0]} patients", "color": ORANGE, "icon": "🥇"},
    {"label": "Multimodal (3+ steps)", "value": f"{(cohort.n_pathway_steps >= 3).mean():.0%}", "sub": "of patients", "color": AQUA, "icon": "🧩"},
    {"label": "Neoadjuvant chemo", "value": f"{cohort.neoadjuvant_chemotherapy.mean():.1%}", "sub": "chemo before surgery", "color": MAGENTA, "icon": "↩️"},
])

section("The journey, animated by volume", ORANGE, "🌊")
pills(MODALITY_COLORS)
c = st.columns([1, 1, 3])
max_steps = c[0].slider("Steps shown", 2, 5, 4)
min_n = c[1].slider("Hide flows smaller than", 1, 30, 5)
show(sankey(steps, cohort, max_steps, min_n), key="sankey")
note("Read left to right: every patient starts at <b>Diagnosis</b>, flows through the first dated start of each "
     "modality, and ends in an outcome. Link colour = the step the patient is leaving. Hover any band for counts.", ORANGE)

section("Pathway explorer - click a tile to drill in", BLUE, "🗺️")
pw_all = cohort.groupby("pathway").agg(
    n_patients=("patient_id", "size"), crude_recurrence_pct=("any_progression_or_recurrence", lambda s: 100 * s.mean()),
    crude_mortality_pct=("os_event", lambda s: 100 * s.mean()),
    median_estimated_cost_usd=("total_estimated_cost_usd", "median"),
    median_days_to_first_adjuvant=("days_to_first_adjuvant_treatment", "median"),
    mean_age=("age_at_diagnosis", "mean")).reset_index()
pw = pw_all[pw_all.n_patients >= 10]
metric = st.radio("Colour tiles by", ["crude_recurrence_pct", "crude_mortality_pct", "median_estimated_cost_usd",
                                      "median_days_to_first_adjuvant", "mean_age"], horizontal=True,
                  format_func=lambda m: m.replace("_", " ").replace("pct", "%"))
event = show(pathway_treemap(pw, metric), key="treemap", select=True)
clicked = [pt.get("label") for pt in selected_points(event) if pt.get("label") in set(pw.pathway)]
chosen = clicked[0] if clicked else None
if chosen:
    sub = cohort[cohort.pathway == chosen]
    st.markdown(f"#### 🔍 {chosen}")
    kpi_cards([
        {"label": "Patients", "value": len(sub), "sub": f"{len(sub) / len(cohort):.1%} of cohort", "color": BLUE, "icon": "👥"},
        {"label": "Median age", "value": f"{sub.age_at_diagnosis.median():.0f}", "color": ORANGE, "icon": "🎂"},
        {"label": "Stage III–IV", "value": f"{sub.stage_major.isin(['III', 'IV']).mean():.0%}", "color": AQUA, "icon": "📊"},
        {"label": "Median est. cost", "value": fmt_usd(sub.total_estimated_cost_usd.median()), "color": MAGENTA, "icon": "💵"},
        {"label": "Crude recurrence", "value": f"{sub.any_progression_or_recurrence.mean():.0%}", "color": VIOLET, "icon": "🔁"},
    ])
    table(sub[["patient_barcode", "age_at_diagnosis", "stage_group", "receptor_subtype", "hospital_name",
               "days_to_chemotherapy", "os_months", "os_event", "total_estimated_cost_usd"]], f"Patients on {chosen}")
else:
    st.caption("👆 Click a pathway tile to see its patients and profile.")

section("How long between steps?", AQUA, "⏳")
gaps = steps[steps.days_since_previous_end.notna() & steps.previous_group.notna()]
gaps = gaps[gaps.days_since_previous_end.between(-30, 400)]
gaps["transition"] = gaps.previous_group + " → " + gaps.pathway_group
common = gaps.transition.value_counts()
common = common[common >= 15].index[:8]
fig = go.Figure()
for t in common:
    v = gaps.loc[gaps.transition == t, "days_since_previous_end"]
    col = MODALITY_COLORS.get(t.split(" → ")[1], BLUE)
    fig.add_trace(go.Box(x=v, name=f"{t} (n={len(v)})", marker_color=col, line_color=col, boxpoints=False,
                         fillcolor="rgba(0,0,0,0)", hovertemplate="median %{median} days<extra></extra>"))
fig.update_layout(height=120 + 46 * len(common), showlegend=False, xaxis_title="days from end of previous step to next start",
                  title="Gap between consecutive modalities (box = interquartile range; colour = next modality)")
show(fig, key="gaps")
table(pw_all.sort_values("n_patients", ascending=False), "Pathway summary for the cohort")
footer()
