import plotly.graph_objects as go
import streamlit as st
from charts import delay_distribution, forest
from theme import (
    BLUE,
    INK_2,
    STATUS,
    apply_filters,
    cohort_filters,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    selected_points,
    show,
    small_cohort_guard,
    table,
)

page_setup("Waiting times",
           "How long patients wait between diagnosis and each treatment, who waits longest, and which hospitals are "
           "slower than they should be.",
           kicker="The patient journey",
           question="How long do patients wait to start treatment, and is any hospital slower than its patients' "
                    "needs would explain?",
           answer="The typical wait for chemotherapy is about <b>65 days</b>, but <b>1 in 4</b> patients wait more "
                  "than 90. After allowing for how sick each hospital's patients were, one hospital has "
                  "<b>2.6×</b> the expected number of late starts.")
f = cohort_filters()
delay = apply_filters(query("select * from marts.mart_treatment_delay"), f)
if not small_cohort_guard(delay.patient_id.nunique()):
    st.stop()

INTERVAL_NAMES = {"Diagnosis → Chemotherapy": "Diagnosis to chemotherapy",
                  "Diagnosis → Radiation": "Diagnosis to radiation",
                  "Diagnosis → Endocrine therapy": "Diagnosis to hormone therapy",
                  "Diagnosis → First adjuvant treatment": "Diagnosis to first treatment after surgery",
                  "Chemotherapy end → Radiation": "End of chemotherapy to radiation"}
c = st.columns([2, 2, 3])
options = sorted(delay.interval_name.unique())
interval = c[0].selectbox("Which wait?", options, index=options.index("Diagnosis → Chemotherapy"),
                          format_func=lambda s: INTERVAL_NAMES.get(s, s))
threshold = c[1].slider("Count a wait as 'too long' after (days)", 30, 180, 90, step=5,
                        help="90 days is the point research links to worse survival for chemotherapy")
label = INTERVAL_NAMES.get(interval, interval).lower()
d = delay[delay.interval_name == interval]
over = (d.interval_days > threshold).mean()
kpi_cards([
    {"label": "Patients with this wait", "value": f"{len(d):,}"},
    {"label": "Typical wait", "value": f"{d.interval_days.median():.0f} days",
     "sub": f"half wait between {d.interval_days.quantile(.25):.0f} and {d.interval_days.quantile(.75):.0f} days"},
    {"label": f"Waited more than {threshold} days", "value": f"{over:.0%}",
     "sub": f"{int((d.interval_days > threshold).sum())} patients"},
    {"label": "The slowest 10% waited over", "value": f"{d.interval_days.quantile(.9):.0f} days"},
])

section("Who waits longest?", blurb="Pick a way to split patients into groups and compare their waits.")
dims = {"stage_major": "Cancer stage", "receptor_subtype": "Tumour type", "age_group": "Age group",
        "race_ethnicity": "Race / ethnicity", "site_type": "Hospital type"}
dim = st.radio("Compare by", list(dims), horizontal=True, format_func=dims.get)
show(delay_distribution(d, dim, threshold, f"Days from {label}, by {dims[dim].lower()}"), key="violin")
how_to_read("each shape shows how waits are spread for one group: wider = more patients waited that long. "
            f"The box marks the middle half of patients and the line inside is the typical wait. The red line is "
            f"your {threshold}-day mark.")

section("Hospital by hospital", blurb="Click a hospital's dot to see its patients.")
b = d[d.is_benchmarkable]
site = (b.groupby("hospital_name").interval_days.agg(n="size", median="median",
                                                     p25=lambda s: s.quantile(.25), p75=lambda s: s.quantile(.75),
                                                     over=lambda s: 100 * (s > threshold).mean()).reset_index())
site = site[site.n >= 10].sort_values("median")
network = d.interval_days.median()
fig = go.Figure()
for r in site.itertuples():
    fig.add_shape(type="line", x0=r.p25, x1=r.p75, y0=r.hospital_name, y1=r.hospital_name, line=dict(color="#d4d2cc", width=3))
col = [STATUS["critical"] if m > network * 1.2 else (BLUE if m < network * 0.85 else "#93b1d6") for m in site["median"]]
fig.add_trace(go.Scatter(x=site["median"], y=site.hospital_name, mode="markers", marker=dict(size=13, color=col, line=dict(color="#ffffff", width=2)),
                         customdata=site[["n", "p25", "p75", "over"]],
                         hovertemplate="<b>%{y}</b><br>typical wait %{x:.0f} days (middle half %{customdata[1]:.0f}–%{customdata[2]:.0f})"
                                       f"<br>%{{customdata[3]:.0f}}% waited over {threshold} days · %{{customdata[0]}} patients<extra></extra>"))
fig.add_vline(x=network, line_color=INK_2, line_width=1, annotation_text=f"all hospitals: {network:.0f} days")
fig.update_layout(height=140 + 38 * len(site), showlegend=False, xaxis_title="days", margin=dict(t=30))
ev = show(fig, key="site_dots", select=True)
how_to_read("the dot is each hospital's typical wait; the grey bar covers the middle half of its patients. "
            "<b>Red</b> = more than 20% slower than all hospitals combined, dark blue = noticeably faster.")
picked = [pt.get("y") for pt in selected_points(ev)]
if picked:
    st.markdown(f"#### {picked[0]}: patients and their wait")
    table(b[b.hospital_name == picked[0]][["patient_id", "interval_days", "stage_major", "receptor_subtype", "age_group",
                                          "race_ethnicity", "year_of_diagnosis"]].sort_values("interval_days", ascending=False),
          f"{picked[0]} patients")

section("A fair comparison", blurb="Some hospitals treat sicker patients. These views adjust for that.")
tab1, tab2, tab3 = st.tabs(["Late starts vs. expected", "What drives longer waits", "Every hospital, every wait"])
with tab1:
    ra = query("select * from analytics.hospital_risk_adjusted_delay").rename(columns={"hospital_name": "site"})
    show(forest(ra, "site", "oe_ratio", "oe_ci_lower", "oe_ci_upper", p=None, ref=1, log=False,
                title="Chemotherapy started after 90 days: actual ÷ expected, given each hospital's patients",
                xtitle="actual ÷ expected  (1 = as expected)"), key="oe")
    how_to_read("a model predicts how many late starts each hospital <i>should</i> have from its patients' stage, "
                "tumour type and age. Above 1 = more late starts than expected. <b>Red</b> means the whole "
                "uncertainty range is above 1, so the hospital is clearly worse.")
    note("Uses all patients and the fixed 90-day definition, so it doesn't change with the filters above.")
with tab2:
    dd = query("select * from analytics.delay_drivers where term <> 'Intercept'")
    model_names = {m: ("Chance of waiting over 90 days" if "Logistic" in m else "Extra days of waiting")
                   for m in dd.model.unique()}
    model = st.radio("Show", dd.model.unique().tolist(), horizontal=True, format_func=model_names.get)
    m = dd[dd.model == model].copy()
    m["term"] = (m.term.str.replace("receptor_subtype: ", "Tumour type: ").str.replace("stage_major: ", "Stage ")
                 .str.replace("site_type: ", "Hospital type: ").str.replace("race_main: ", "Race: "))
    is_or = "Logistic" in model
    show(forest(m, "term", "estimate", "ci_lower", "ci_upper", ref=1.0 if is_or else 0.0, log=is_or,
                xtitle="how many times more likely (1 = no difference)" if is_or else "extra days compared with the baseline group",
                title=f"{model_names[model]}, holding the other factors equal ({int(m.n.iloc[0])} patients)"), key="drivers")
    how_to_read("each row compares a group with the baseline in brackets. Right of the line = longer waits "
                "(<b>red</b> if clear), left = shorter (<b>blue</b>), grey = no clear difference.")
with tab3:
    hm = delay[delay.is_benchmarkable].groupby(["hospital_name", "interval_name"]).interval_days.median().unstack()
    counts = delay[delay.is_benchmarkable].groupby("hospital_name").patient_id.nunique()
    hm = hm.loc[counts[counts >= 20].index]
    net = delay.groupby("interval_name").interval_days.median()
    rel = (hm - net) / net
    rel.columns = [INTERVAL_NAMES.get(x, x) for x in rel.columns]
    fig = go.Figure(go.Heatmap(z=rel.to_numpy() * 100, x=rel.columns, y=rel.index, zmid=0, zmin=-60, zmax=60,
                               colorscale=[[0, "#2a5285"], [0.5, "#f1f0ed"], [1, "#b83c3c"]], xgap=3, ygap=3,
                               text=hm.round(0).to_numpy(), texttemplate="%{text}",
                               colorbar=dict(title="vs. all<br>hospitals", ticksuffix="%"),
                               hovertemplate="%{y}<br>%{x}<br>typical <b>%{text}</b> days (%{z:+.0f}% vs. all hospitals)<extra></extra>"))
    fig.update_layout(height=150 + 34 * len(rel), xaxis=dict(tickangle=-20), yaxis=dict(autorange="reversed"),
                      margin=dict(t=30))
    show(fig, key="heat")
    how_to_read("each number is a hospital's typical wait in days. <b>Red</b> = slower than all hospitals combined, "
                "<b>blue</b> = faster, grey = about the same.")
table(d, f"{INTERVAL_NAMES.get(interval, interval)} waits")
footer()
