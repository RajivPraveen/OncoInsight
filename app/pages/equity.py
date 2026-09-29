import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    AGE_COLORS,
    SERIES,
    footer,
    how_to_read,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    show,
    table,
)

page_setup("Fairness of care",
           "Do patients get the treatment guidelines recommend, and as quickly, regardless of age or race?",
           kicker="Results",
           question="Do some groups of patients miss out on recommended treatment?",
           answer="Age is the biggest gap. When guidelines strongly recommend chemotherapy, <b>86%</b> of 40–49 "
                  "year-olds get it but only <b>21%</b> of those 75+. Race differences exist for some treatments but "
                  "are tangled up with which hospital the data came from.")

tests = query("select * from analytics.disparity_tests order by p_value")
kpi_cards([
    {"label": "Comparisons checked", "value": len(tests)},
    {"label": "Clear differences found", "value": int(tests.significant_fdr_05.sum()),
     "sub": "after correcting for running many tests"},
    {"label": "Largest gap", "value": "Age 75+", "sub": "chemo when recommended: 21% vs. 86%"},
])

rates = query("select * from analytics.disparity_rates where n >= 11")
section("Who gets the recommended treatment?",
        blurb="Each measure only counts patients for whom the treatment is recommended.")
c = st.columns([2, 2])
FAM = {"Chemotherapy when indicated": "Chemotherapy, when strongly recommended",
       "HER2-targeted therapy": "HER2-targeted drugs, for HER2+ tumours",
       "Endocrine therapy": "Hormone therapy, for HR+ tumours",
       "Radiation therapy": "Radiation", "Chemotherapy started > 90 days": "Chemotherapy started after 90 days"}
fam = c[0].selectbox("Treatment", rates.test_family.unique(), format_func=lambda f: FAM.get(f, f))
dim = c[1].radio("Compare by", rates[rates.test_family == fam].group_type.unique().tolist(), horizontal=True,
                 format_func=lambda s: {"race_main": "Race", "age_group": "Age group"}.get(s, s))
r = rates[(rates.test_family == fam) & (rates.group_type == dim)]
if dim == "age_group":
    r = r.set_index("group_value").reindex([a for a in AGE_COLORS if a in set(r.group_value)]).reset_index()
    colors = [AGE_COLORS[g] for g in r.group_value]
else:
    colors = SERIES[: len(r)]
fig = go.Figure(go.Bar(x=r.group_value, y=r.rate * 100, marker=dict(color=colors, line=RING),
                       error_y=dict(type="data", symmetric=False, array=(r.ci_upper - r.rate) * 100,
                                    arrayminus=(r.rate - r.ci_lower) * 100, color="#8b9099", thickness=1.5),
                       text=[f"{v:.0%}" for v in r.rate], textposition="outside", customdata=r.n,
                       hovertemplate="%{x}: <b>%{y:.0f}%</b> (%{customdata} patients)<extra></extra>"))
t = tests[(tests.test_family == fam) & (tests.group_type == dim)]
fig.update_layout(height=420, bargap=0.45, yaxis=dict(range=[0, 112], title="% of patients"),
                  title=f"{FAM.get(fam, fam)} · {r.population.iloc[0] if len(r) else ''}")
show(fig, key="rates")
if len(t):
    clear = bool(t.significant_fdr_05.iloc[0])
    st.markdown(f"**Is the difference real?** {'Yes, the groups clearly differ' if clear else 'Not clearly - it could be chance'} "
                f"(adjusted p = {t.p_value_fdr.iloc[0]:.2g}).")
how_to_read("each bar is the share of a group who got the treatment. The thin lines show the uncertainty: when they "
            "overlap a lot, the groups may not really differ.")

section("Every group, every measure", blurb="One grid to spot where a group stands out from the rest.")
dis = query("select * from marts.mart_disparities where n_patients >= 11 and group_value <> 'Not reported'")
gt = st.radio("Groups", dis.group_type.unique().tolist(), horizontal=True, key="hm_gt",
              format_func=lambda s: s.replace("_", " ").capitalize())
d = dis[dis.group_type == gt].set_index("group_value")
measures = {"pct_chemo_when_indicated": "% got chemo when recommended", "pct_her2_targeted_among_her2_pos": "% HER2+ got HER2 drugs",
            "pct_endocrine_among_hr_pos": "% HR+ got hormone therapy", "pct_radiation": "% got radiation",
            "median_days_to_chemotherapy": "Typical days to chemo", "pct_chemo_over_90d": "% chemo after 90 days",
            "pct_stage_iii_iv": "% advanced cancer", "crude_mortality_pct": "% died"}
m = d[list(measures)]
z = (m - m.mean()) / m.std(ddof=0).replace(0, 1)
fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=list(measures.values()), y=list(m.index), text=m.round(1).to_numpy(),
                           texttemplate="%{text}", colorscale=[[0, "#2a5285"], [0.5, "#f1f0ed"], [1, "#d0643c"]],
                           zmid=0, xgap=3, ygap=3, colorbar=dict(title="vs. other<br>groups", tickvals=[-2, 0, 2], ticktext=["lower", "average", "higher"]),
                           hovertemplate="%{y}<br>%{x}: <b>%{text}</b><extra></extra>"))
fig.update_layout(height=150 + 40 * len(m), xaxis=dict(tickangle=-25), yaxis=dict(autorange="reversed"), margin=dict(t=20))
show(fig, key="heat")
how_to_read("each number is the actual value for that group. Colour shows how it compares with the other groups: "
            "<b>orange</b> = higher, <b>blue</b> = lower, grey = about average.")
note("<b>Read with care.</b> Race is self-reported and often missing at some non-US hospitals. A small group with 0% "
     "(e.g. 0 of 14 HER2+ Asian patients recorded as getting HER2 drugs) is more likely missing data than missing "
     "care. These results show where to look, not what caused a gap.")

section("All statistical tests", blurb="For analysts: every comparison, with its raw and adjusted p-values.")
st.dataframe(tests[["test_family", "population", "group_type", "method", "statistic", "p_value", "p_value_fdr",
                    "significant_fdr_05", "n"]].style.format({"p_value": "{:.2g}", "p_value_fdr": "{:.2g}", "statistic": "{:.2f}"}, na_rep="—")
             .apply(lambda s: ["background-color: #f6e3e3" if v else "" for v in s], subset=["significant_fdr_05"]),
             use_container_width=True, hide_index=True)
table(dis, "Full table of group measures")
footer()
