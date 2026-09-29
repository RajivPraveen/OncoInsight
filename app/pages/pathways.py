import plotly.graph_objects as go
import streamlit as st
from charts import pathway_treemap, sankey
from theme import (
    BLUE,
    MODALITY_COLORS,
    apply_filters,
    cohort_filters,
    fmt_usd,
    footer,
    how_to_read,
    kpi_cards,
    page_setup,
    patients,
    pills,
    plain,
    query,
    section,
    selected_points,
    show,
    small_cohort_guard,
    table,
)

page_setup("Treatment paths",
           "Which treatments patients receive, in what order, and how they do afterwards.",
           kicker="The patient journey",
           question="What sequence of treatments do patients actually go through?",
           answer="Almost everyone starts with surgery. The most common follow-ups are radiation, chemotherapy and "
                  "hormone therapy, in different orders. About half of patients go through <b>three or more</b> "
                  "types of treatment.")
f = cohort_filters()
cohort = apply_filters(patients(), f)
if not small_cohort_guard(len(cohort)):
    st.stop()
steps = apply_filters(query("select * from marts.mart_patient_pathway_steps"), f)

top = cohort.pathway.value_counts()
kpi_cards([
    {"label": "Different treatment paths", "value": f"{len(top)}", "sub": f"the top 5 cover {top.head(5).sum() / len(cohort):.0%} of patients"},
    {"label": "Most common path", "value": plain(top.index[0]).replace("Chemotherapy", "Chemo"),
     "sub": f"{top.iloc[0]} patients"},
    {"label": "Had 3 or more treatment types", "value": f"{(cohort.n_pathway_steps >= 3).mean():.0%}", "sub": "of patients"},
    {"label": "Chemo before surgery", "value": f"{cohort.neoadjuvant_chemotherapy.mean():.1%}", "sub": "to shrink the tumour first"},
])

section("How patients flow from diagnosis to outcome",
        blurb="Every band is a group of patients moving from one step to the next. Thicker = more patients.")
pills({plain(k): v for k, v in MODALITY_COLORS.items()})
c = st.columns([1, 1, 3])
max_steps = c[0].slider("Steps to show", 2, 5, 4)
min_n = c[1].slider("Hide groups smaller than", 1, 30, 5)
show(sankey(steps, cohort, max_steps, min_n), key="sankey")
how_to_read("read left to right. Everyone starts at <b>Diagnosis</b>, passes through each treatment in the order "
            "it started (1., 2., 3. ...), and ends in an outcome on the right. Hover a band to see how many patients.")

section("Compare the paths", blurb="Each tile is one treatment path. Bigger = more patients. Click a tile to see who is on it.")
pw_all = cohort.groupby("pathway").agg(
    n_patients=("patient_id", "size"), crude_recurrence_pct=("any_progression_or_recurrence", lambda s: 100 * s.mean()),
    crude_mortality_pct=("os_event", lambda s: 100 * s.mean()),
    median_estimated_cost_usd=("total_estimated_cost_usd", "median"),
    median_days_to_first_adjuvant=("days_to_first_adjuvant_treatment", "median"),
    mean_age=("age_at_diagnosis", "mean")).reset_index()
pw = pw_all[pw_all.n_patients >= 10]
METRICS = {"crude_recurrence_pct": "% whose cancer came back", "crude_mortality_pct": "% who died",
           "median_estimated_cost_usd": "Typical cost ($)", "median_days_to_first_adjuvant": "Days to first treatment after surgery",
           "mean_age": "Average age"}
metric = st.radio("Shade tiles by", list(METRICS), horizontal=True, format_func=METRICS.get)
event = show(pathway_treemap(pw, metric, METRICS[metric]), key="treemap", select=True)
how_to_read("darker tiles have a higher value for the measure you picked. Outcomes are not adjusted for stage, so "
            "paths used for more advanced cancer will look worse.")
by_label = {plain(x): x for x in pw.pathway}
clicked = [by_label[pt.get("label")] for pt in selected_points(event) if pt.get("label") in by_label]
chosen = clicked[0] if clicked else None
if chosen:
    sub = cohort[cohort.pathway == chosen]
    st.markdown(f"#### {plain(chosen)}")
    kpi_cards([
        {"label": "Patients", "value": len(sub), "sub": f"{len(sub) / len(cohort):.0%} of those shown"},
        {"label": "Typical age", "value": f"{sub.age_at_diagnosis.median():.0f}"},
        {"label": "Advanced cancer (stage III–IV)", "value": f"{sub.stage_major.isin(['III', 'IV']).mean():.0%}"},
        {"label": "Typical cost", "value": fmt_usd(sub.total_estimated_cost_usd.median())},
        {"label": "Cancer came back", "value": f"{sub.any_progression_or_recurrence.mean():.0%}"},
    ])
    table(sub[["patient_barcode", "age_at_diagnosis", "stage_group", "receptor_subtype", "hospital_name",
               "days_to_chemotherapy", "os_months", "os_event", "total_estimated_cost_usd"]], f"Patients on {chosen}")
else:
    st.caption("Click a tile above to see the patients on that path.")

section("How long between steps?", blurb="The gap from the end of one treatment to the start of the next.")
gaps = steps[steps.days_since_previous_end.notna() & steps.previous_group.notna()]
gaps = gaps[gaps.days_since_previous_end.between(-30, 400)]
gaps["transition"] = gaps.previous_group + " → " + gaps.pathway_group
common = gaps.transition.value_counts()
common = common[common >= 15].index[:8]
fig = go.Figure()
for t in common:
    v = gaps.loc[gaps.transition == t, "days_since_previous_end"]
    col = MODALITY_COLORS.get(t.split(" → ")[1], BLUE)
    fig.add_trace(go.Box(x=v, name=f"{plain(t)} ({len(v)} patients)", marker_color=col, line_color=col, boxpoints=False,
                         fillcolor="rgba(0,0,0,0)", hovertemplate="median %{median} days<extra></extra>"))
fig.update_layout(height=120 + 46 * len(common), showlegend=False, xaxis_title="days between the end of one step and the start of the next",
                  margin=dict(t=30))
show(fig, key="gaps")
how_to_read("the box covers the middle half of patients and the line inside is the typical gap. Colour = the "
            "treatment being started.")
table(pw_all.sort_values("n_patients", ascending=False), "Summary of every path")
footer()
