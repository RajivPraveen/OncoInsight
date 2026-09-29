import plotly.graph_objects as go
import streamlit as st
from charts import RING, forest, km_from_table
from theme import (
    BLUE,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    show,
    step,
)

page_setup("The story in 2 minutes",
           "Why this project exists, what data it uses, what it found, and how it was built.",
           kicker="The story")

# ------------------------------------------------------------------ 1. the problem
section("1 · The problem")
c1, c2 = st.columns([1.2, 1])
with c1:
    st.markdown("""
Breast cancer is the most common cancer in women. Treatment is not one thing but a **series of steps**:
surgery, then often chemotherapy, radiation and years of hormone pills. Each step is run by a different team,
and every hand-off between teams is a chance for the patient to wait.

Waiting matters. Patients who start chemotherapy **more than 90 days** after surgery have worse survival.

So the people running a cancer network need answers to simple questions:

- **How long** do patients wait, and at which step?
- **Which hospitals** are slower than they should be?
- **How do patients do** afterwards, and what does their care **cost**?
- Is care **fair** across age and race?

No single prediction model answers these. You need to track the whole journey for every patient.
""")
with c2:
    note("<b>Why the 90-day mark?</b> A large US study (Chavez-MacGregor et al., <i>JAMA Oncology</i> 2016) found "
         "patients starting chemotherapy more than 90 days after surgery had worse survival. That makes waiting time "
         "something a hospital can measure and fix.")
    note("<b>Why compare fairly?</b> A hospital that treats sicker patients will look slower. OncoInsight adjusts "
         "for each hospital's mix of patients before comparing them, so the comparison is fair.")

# ------------------------------------------------------------------ 2. the data
section("2 · Real patients, not made-up data",
        blurb="Every number comes from public, de-identified research data. No patient is invented.")
counts = query("""select (select count(*) from core.dim_patient) patients, (select count(*) from core.fact_treatment) treatments,
                  (select count(*) from core.fact_encounter) encounters, (select count(*) from marts.mart_metabric_cohort) metabric,
                  (select count(*) from core.dim_hospital) sites""").iloc[0]
kpi_cards([
    {"label": "Patients followed", "value": f"{counts.patients:,}", "sub": "US cancer research study (TCGA)"},
    {"label": "Treatments recorded", "value": f"{counts.treatments:,}", "sub": "surgery, radiation and 65 drugs, with dates"},
    {"label": "Follow-up visits", "value": f"{counts.encounters:,}", "sub": "check-ups after treatment"},
    {"label": "Hospitals", "value": f"{counts.sites}", "sub": "that contributed patients"},
    {"label": "Second patient group", "value": f"{counts.metabric:,}", "sub": "UK/Canada study used to double-check results"},
])

# ------------------------------------------------------------------ 3. findings
section("3 · What we found")
t1, t2, t3, t4 = st.tabs(["Some hospitals are slower", "Stage drives survival", "Older patients get less chemo",
                          "What raises the risk of cancer returning"])
with t1:
    ra = query("select * from analytics.hospital_risk_adjusted_delay")
    ra = ra.rename(columns={"hospital_name": "site"})
    show(forest(ra, "site", "oe_ratio", "oe_ci_lower", "oe_ci_upper", p=None, ref=1, log=False,
                title="Late chemotherapy starts: actual ÷ expected for each hospital's mix of patients",
                xtitle="actual ÷ expected  (1 = as expected, 2 = twice as many)"), key="f_oe")
    how_to_read("each dot is a hospital; the line through it is the range we're 95% confident in. "
                "<b>Red</b> = clearly more late starts than expected, <b>blue</b> = clearly fewer, grey = can't tell.")
    note("After allowing for how sick each hospital's patients were, one hospital has about <b>2.6×</b> the expected "
         "number of late chemotherapy starts, and another has none. That points to a process problem "
         "(referrals, scheduling, capacity), not sicker patients.")
with t2:
    curves = query("select * from analytics.km_curves where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    summ = query("select * from analytics.km_summary where cohort='TCGA-BRCA' and endpoint='OS' and stratifier='stage_major'")
    show(km_from_table(curves, summ, "stage_major", "Share of patients still alive, by cancer stage"), key="f_km")
    how_to_read("each line starts at 100% at diagnosis and steps down when a patient dies. A higher line means "
                "better survival. The shaded band is the uncertainty.")
    note("Five years after diagnosis, about <b>91%</b> of stage I patients are alive, compared with <b>27%</b> "
         "at stage IV. That's why every comparison in this project accounts for stage.")
with t3:
    r = query("select group_value, n, rate, ci_lower, ci_upper from analytics.disparity_rates "
              "where test_family='Chemotherapy when indicated' and group_type='age_group' order by group_value")
    order = ["<40", "40-49", "50-64", "65-74", "75+"]
    r = r.set_index("group_value").reindex([o for o in order if o in set(r.group_value)]).reset_index()
    fig = go.Figure(go.Bar(x=r.group_value, y=r.rate * 100, marker=dict(color=BLUE, line=RING),
                           error_y=dict(type="data", symmetric=False, array=(r.ci_upper - r.rate) * 100,
                                        arrayminus=(r.rate - r.ci_lower) * 100, color="#8b9099", thickness=1.5),
                           text=[f"{v:.0%}" for v in r.rate], textposition="outside", customdata=r.n,
                           hovertemplate="Age %{x}: <b>%{y:.0f}%</b> received chemo (%{customdata} patients)<extra></extra>"))
    fig.update_layout(height=380, yaxis=dict(range=[0, 110], title="% who received chemotherapy"), bargap=0.45,
                      xaxis_title="age group",
                      title="Patients who received chemotherapy when guidelines strongly recommend it")
    show(fig, key="f_age")
    how_to_read("only patients whose tumour type and stage make chemotherapy strongly recommended are counted. "
                "The thin lines show the uncertainty.")
    note("Among patients where guidelines strongly recommend chemotherapy, <b>86%</b> of 40–49 year-olds got it, "
         "but only <b>21%</b> of those aged 75+. Some of this is right (frail patients may not cope with it), "
         "but a gap this large is worth reviewing.")
with t4:
    co = query("select * from analytics.cox_coefficients where model like %(m)s", {"m": "TCGA PFI%"})
    show(forest(co, "covariate", "hazard_ratio", "ci_lower", "ci_upper",
                title="How much each factor raises or lowers the risk of the cancer growing or returning",
                xtitle="risk multiplier  (1 = no effect, 2 = double the risk)"), key="f_pfi")
    how_to_read("each factor is compared with a baseline patient, holding the other factors equal. Right of the line "
                "= higher risk (<b>red</b>), left = lower (<b>blue</b>), grey = no clear effect.")
    note("Stage III cancer carries about <b>3.7×</b> the risk, and triple-negative tumours about <b>2.7×</b>. "
         "These are patterns in the data, not proof of cause.")

# ------------------------------------------------------------------ 4. how it's built
section("4 · How it was built", blurb="For the technically curious: what happens every time the data is refreshed.")
with st.expander("Show the 8 steps of the data pipeline"):
    dq = query("""select count(*) total, count(*) filter (where success) passed from (select distinct on (dataset, expectation,
                  column_name) success from ops.dq_results order by dataset, expectation, column_name, checked_at desc) d""").iloc[0]
    cols = st.columns(2)
    steps = [
        ("Collect", "Download every patient record from two public cancer research databases (NCI GDC and cBioPortal). "
         "Only new or changed records are re-downloaded."),
        ("Convert to a hospital standard", "Turn each record into FHIR, the format real hospital systems use to "
         "exchange data, and check every record is valid."),
        ("Check quality", f"Run automatic checks before anything is loaded. Serious problems stop the load. "
         f"Latest run: <b>{dq.passed} of {dq.total}</b> checks passed."),
        ("Load", "Save into a PostgreSQL database. Unchanged records are skipped, so re-running is safe."),
        ("Organise", "Build clean, tested tables (with dbt) so every metric has one agreed definition."),
        ("Analyse", "Run the statistics: survival curves, risk models, fairness tests and fair hospital comparisons."),
        ("Watch for changes", "Compare each measure with previous years and raise an alert if it jumps."),
        ("Share", "Serve the results to this dashboard, an API, Power BI and an AI assistant that can only read."),
    ]
    for i, (t, d) in enumerate(steps):
        with cols[i % 2]:
            step(i + 1, t, d)
    st.caption("Runs automatically on a schedule (Dagster), daily for updates and weekly for a full refresh.")

section("Explore it yourself")
e = st.columns(2)
e[0].page_link("pages/time_to_treatment.py", label="See who waits too long", icon=":material/schedule:")
e[0].page_link("pages/survival.py", label="Compare survival between two groups", icon=":material/monitor_heart:")
e[1].page_link("pages/cost.py", label="Try a cost-saving scenario", icon=":material/payments:")
e[1].page_link("pages/assistant.py", label="Ask the data a question", icon=":material/chat:")
footer()
