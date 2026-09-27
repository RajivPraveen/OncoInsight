import plotly.graph_objects as go
import streamlit as st
from charts import RING, forest, km_from_table
from theme import (
    AQUA,
    BLUE,
    GREEN,
    INK_2,
    MAGENTA,
    MODALITY_COLORS,
    ORANGE,
    RED,
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
    step,
)

page_setup("Why OncoInsight exists",
           "Cancer care is a journey of many hand-offs. Every hand-off can add delay, and delay, variation and "
           "inequity are hard to see unless the whole journey is measured. This page explains the problem, the "
           "data, what the platform does, and what it found.",
           kicker="The story", chips=["Problem", "Data", "Pipeline", "Findings", "How to explore"])

# ------------------------------------------------------------------ 1. the problem
section("1 · The problem", RED, "🎯")
c1, c2 = st.columns([1.2, 1])
with c1:
    st.markdown("""
Breast cancer is the most commonly diagnosed cancer in women. Treatment is **multimodal**: surgery, then often
chemotherapy, radiation, endocrine (hormone) therapy and HER2-targeted drugs, delivered by different teams over
months. An oncology network's leadership keeps asking the same questions:

- ⏱️ **How long** do patients wait from diagnosis to treatment, and where are the bottlenecks?
- 🔀 **Which pathways** do patients actually follow, and what do they cost?
- 📈 **How do outcomes differ** by stage, tumour biology and pathway?
- 🏥 **Do hospitals differ** once you account for how sick their patients are?
- ⚖️ **Is care equitable** across age and race?

These are **analytics questions, not a single prediction**. Answering them needs a platform that tracks the whole
journey, not one model.
""")
with c2:
    note("<b>Why delay matters.</b> Starting adjuvant chemotherapy more than <b>90 days</b> after surgery has been "
         "associated with worse survival in large US cohorts (Chavez-MacGregor et al., <i>JAMA Oncology</i> 2016). "
         "That makes time to treatment a KPI a network can act on.", RED)
    note("<b>Why equity matters.</b> Guideline-recommended treatment should not depend on age or race. Measuring "
         "receipt of indicated therapy by group is how you find gaps.", VIOLET)
    note("<b>Why cost matters.</b> Pathways differ a lot in cost (e.g. HER2-targeted antibodies), and value "
         "discussions need cost placed beside outcomes.", AQUA)

# ------------------------------------------------------------------ 2. the journey
section("2 · The patient journey we measure", ORANGE, "🧭")
stages = [("🩺 Diagnosis", "day 0", INK_2), ("🔪 Surgery", "≈ day 0", MODALITY_COLORS["Surgery"]),
          ("💉 Chemotherapy", "median day 65", MODALITY_COLORS["Chemotherapy"]),
          ("💊 Endocrine", "median day 170", MODALITY_COLORS["Endocrine"]),
          ("☢️ Radiation", "median day 182", MODALITY_COLORS["Radiation"]), ("📅 Follow-up", "years 1–10+", BLUE),
          ("🎯 Outcome", "recurrence · survival", STATUS["critical"])]
xs = list(range(len(stages)))
fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=[0] * len(xs), mode="lines", line=dict(color="#e1e0d9", width=10), hoverinfo="skip"))
fig.add_trace(go.Scatter(x=xs, y=[0] * len(xs), mode="markers+text", text=[st_[0] for st_ in stages],
                         textposition="top center", textfont=dict(size=14, color="#0b0b0b"),
                         marker=dict(size=30, color=[st_[2] for st_ in stages], line=RING),
                         customdata=[st_[1] for st_ in stages], hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
for x, st_ in zip(xs, stages, strict=True):
    fig.add_annotation(x=x, y=-0.5, text=st_[1], showarrow=False, font=dict(size=12, color=INK_2))
fig.update_layout(height=230, showlegend=False, title="A typical journey through this cohort (hover each stop)",
                  yaxis=dict(visible=False, range=[-1, 1]), xaxis=dict(visible=False, range=[-0.5, len(xs) - 0.5]))
show(fig, key="journey")

# ------------------------------------------------------------------ 3. the data
section("3 · Real data, not synthetic", BLUE, "🗄️")
counts = query("""select (select count(*) from core.dim_patient) patients, (select count(*) from core.fact_treatment) treatments,
                  (select count(*) from core.fact_observation) observations, (select count(*) from core.fact_encounter) encounters,
                  (select count(*) from marts.mart_metabric_cohort) metabric, (select count(*) from core.dim_hospital) sites""").iloc[0]
kpi_cards([
    {"label": "TCGA-BRCA patients", "value": f"{counts.patients:,}", "sub": "NCI Genomic Data Commons API", "color": BLUE, "icon": "🧑‍🤝‍🧑"},
    {"label": "Treatment records", "value": f"{counts.treatments:,}", "sub": "surgery · radiation · 65 drug agents", "color": ORANGE, "icon": "💊"},
    {"label": "Clinical observations", "value": f"{counts.observations:,}", "sub": "stage, TNM, ER/PR/HER2, status", "color": AQUA, "icon": "🔬"},
    {"label": "Follow-up encounters", "value": f"{counts.encounters:,}", "sub": "visits and last contact", "color": YELLOW, "icon": "📅"},
    {"label": "METABRIC patients", "value": f"{counts.metabric:,}", "sub": "independent validation cohort", "color": MAGENTA, "icon": "🧪"},
    {"label": "Contributing sites", "value": f"{counts.sites}", "sub": "hospitals and biorepositories", "color": GREEN, "icon": "🏥"},
])
st.markdown("")
note("Real data is messy, and handling that is part of the point: undated treatments, sites that are tissue biobanks "
     "rather than hospitals, ages over 89 obfuscated, drug classes mislabelled at source, surgery type missing. "
     "Things no public dataset contains (readmissions, claims, insurance) are <b>documented as out of scope, not "
     "invented</b>.", BLUE)

# ------------------------------------------------------------------ 4. what the platform does
section("4 · What happens every time the pipeline runs", GREEN, "⚙️")
runs = query("select pipeline, max(finished_at) last_run, count(*) runs from ops.pipeline_runs group by 1")
dq = query("""select count(*) total, count(*) filter (where success) passed from (select distinct on (dataset, expectation,
              column_name) success from ops.dq_results order by dataset, expectation, column_name, checked_at desc) d""").iloc[0]
cols = st.columns(2)
steps = [
    ("Extract", "Pull every TCGA-BRCA case from the GDC API and curated outcomes from cBioPortal, with retries and "
     "incremental watermarks. Raw JSON lands in S3, immutable and partitioned by run.", BLUE),
    ("Standardise to FHIR R4", "Map each case to Patient, Condition, Observation, Procedure, MedicationAdministration and "
     "Encounter resources (mCODE-style, LOINC/ICD codes) and validate every one against the FHIR schema.", ORANGE),
    ("Quality gate", f"Great Expectations checks every batch <i>before</i> loading. Critical failures block the load. "
     f"Latest run: <b>{dq.passed}/{dq.total}</b> expectations passing.", AQUA),
    ("Load incrementally", "Hash-based upserts into Postgres: only changed records are rewritten, and deletions are "
     "soft-deleted. A re-run changes 0 rows.", YELLOW),
    ("Model with dbt", "Staging → business logic → star schema (dims + incremental facts) → 14 analysis marts, "
     "guarded by 98 tests including referential integrity.", MAGENTA),
    ("Analyse", "Kaplan-Meier, Cox models, recurrence ML, disparity tests with FDR control, and case-mix-adjusted hospital "
     "benchmarking are written back to the warehouse.", GREEN),
    ("Monitor & alert", "KPIs are compared with a trailing baseline. Unusual moves become alerts (and optional "
     "webhooks).", VIOLET),
    ("Serve", "This dashboard, a REST API, a Power BI model, and an AI assistant that can only run governed, "
     "read-only queries.", RED),
]
for i, (t, d, c) in enumerate(steps):
    with cols[i % 2]:
        step(i + 1, t, d, c)
st.caption("Orchestrated by Dagster: daily incremental + weekly full reconciliation, with retries and failure alerts. "
           "Last runs: " + ", ".join(f"{r.pipeline} {str(r.last_run)[:16]}" for r in runs.itertuples()))

# ------------------------------------------------------------------ 5. findings
section("5 · What we found", MAGENTA, "💡")
t1, t2, t3, t4 = st.tabs(["⏱️ Delays vary by site", "📈 Stage drives survival", "⚖️ Age gap in chemo", "🔁 What predicts progression"])
with t1:
    ra = query("select * from analytics.hospital_risk_adjusted_delay")
    ra = ra.rename(columns={"hospital_name": "site"})
    show(forest(ra, "site", "oe_ratio", "oe_ci_lower", "oe_ci_upper", p=None, ref=1, log=False,
                title="Observed ÷ expected chemo delays (> 90 days), adjusted for stage, subtype and age",
                xtitle="observed / expected (1 = as expected)"), key="f_oe")
    note("After case-mix adjustment, one site has <b>~2.6×</b> the expected share of late chemotherapy starts, "
         "while another has none. That points to process differences worth a closer look, not patient mix.", ORANGE)
with t2:
    curves = query("select * from analytics.km_curves where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    summ = query("select * from analytics.km_summary where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    show(km_from_table(curves, summ, "stage_major", "Overall survival by AJCC stage (TCGA-BRCA)"), key="f_km")
    note("5-year overall survival falls from about <b>91%</b> (stage I) to <b>27%</b> (stage IV). This is why stage "
         "is adjusted for in every comparison.", BLUE)
with t3:
    r = query("select group_value, n, rate, ci_lower, ci_upper from analytics.disparity_rates "
              "where test_family='Chemotherapy when indicated' and group_type='age_group' order by group_value")
    order = ["<40", "40-49", "50-64", "65-74", "75+"]
    r = r.set_index("group_value").reindex([o for o in order if o in set(r.group_value)]).reset_index()
    fig = go.Figure(go.Bar(x=r.group_value, y=r.rate * 100, marker=dict(color="#2a78d6", line=RING),
                           error_y=dict(type="data", symmetric=False, array=(r.ci_upper - r.rate) * 100,
                                        arrayminus=(r.rate - r.ci_lower) * 100, color="#898781", thickness=1.5),
                           text=[f"{v:.0%}" for v in r.rate], textposition="outside", customdata=r.n,
                           hovertemplate="%{x}: <b>%{y:.1f}%</b> (n=%{customdata})<extra></extra>"))
    fig.update_layout(height=380, yaxis=dict(range=[0, 110], title="% receiving chemotherapy"), bargap=0.4,
                      title="Chemotherapy receipt when strongly indicated (TNBC / HER2+, stage II–III), 95% CI")
    show(fig, key="f_age")
    note("Receipt drops from <b>86%</b> (age 40–49) to <b>21%</b> (75+). Some of this reflects appropriate "
         "individualisation for frailty; the size of the gap makes it a question to review.", VIOLET)
with t4:
    co = query("select * from analytics.cox_coefficients where model like %(m)s", {"m": "TCGA PFI%"})
    show(forest(co, "covariate", "hazard_ratio", "ci_lower", "ci_upper", title="Progression-free interval: adjusted hazard ratios "
                "(red = higher risk, blue = lower, grey = not significant)"), key="f_pfi")
    note("Stage III (HR ≈ 3.7) and triple-negative biology (HR ≈ 2.7) carry the highest adjusted risk of "
         "progression. These are associations in observational data, not causal effects.", MAGENTA)

# ------------------------------------------------------------------ 6. how to explore
section("6 · Explore it yourself", VIOLET, "🧑‍💻")
e = st.columns(4)
e[0].page_link("pages/pathways.py", label="Click through the pathways", icon="🔀")
e[1].page_link("pages/survival.py", label="Build two cohorts and compare survival", icon="📈")
e[2].page_link("pages/cost.py", label="Run a cost what-if scenario", icon="💵")
e[3].page_link("pages/assistant.py", label="Ask the AI assistant", icon="🤖")
footer()
