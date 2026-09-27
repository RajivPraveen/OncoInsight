import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    AGE_COLORS,
    BLUE,
    MAGENTA,
    ORANGE,
    SERIES,
    VIOLET,
    footer,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    show,
    table,
)

page_setup("Equity & disparities", "Does access to guideline-indicated treatment, or time to treatment, differ by "
           "age, race, ethnicity or site type? Every comparison shows 95% intervals and FDR-corrected tests.",
           kicker="Outcomes & value", chips=["Wilson 95% CIs", "Chi-square / Fisher / Kruskal-Wallis", "Benjamini-Hochberg FDR"])

tests = query("select * from analytics.disparity_tests order by p_value")
kpi_cards([
    {"label": "Tests run", "value": len(tests), "color": BLUE, "icon": "🧮"},
    {"label": "Significant after FDR", "value": int(tests.significant_fdr_05.sum()), "sub": "q < 0.05", "color": MAGENTA, "icon": "❗"},
    {"label": "Largest gap", "value": "Age ≥ 75", "sub": "chemo when indicated: 21% vs 86%", "color": ORANGE, "icon": "👵"},
])

rates = query("select * from analytics.disparity_rates where n >= 11")
section("Guideline-concordance by group", VIOLET, "⚖️")
c = st.columns([2, 2])
fam = c[0].selectbox("Measure", rates.test_family.unique())
dim = c[1].radio("Stratify by", rates[rates.test_family == fam].group_type.unique().tolist(), horizontal=True,
                 format_func=lambda s: {"race_main": "Race", "age_group": "Age group"}.get(s, s))
r = rates[(rates.test_family == fam) & (rates.group_type == dim)]
if dim == "age_group":
    r = r.set_index("group_value").reindex([a for a in AGE_COLORS if a in set(r.group_value)]).reset_index()
    colors = [AGE_COLORS[g] for g in r.group_value]
else:
    colors = SERIES[: len(r)]
fig = go.Figure(go.Bar(x=r.group_value, y=r.rate * 100, marker=dict(color=colors, line=RING),
                       error_y=dict(type="data", symmetric=False, array=(r.ci_upper - r.rate) * 100,
                                    arrayminus=(r.rate - r.ci_lower) * 100, color="#898781", thickness=1.5),
                       text=[f"{v:.0%}" for v in r.rate], textposition="outside", customdata=r.n,
                       hovertemplate="%{x}: <b>%{y:.1f}%</b> (n=%{customdata})<extra></extra>"))
t = tests[(tests.test_family == fam) & (tests.group_type == dim)]
sub = f"{t.method.iloc[0]} p = {t.p_value.iloc[0]:.2g}, FDR q = {t.p_value_fdr.iloc[0]:.2g}" if len(t) else ""
fig.update_layout(height=420, bargap=0.4, yaxis=dict(range=[0, 112], title="%"),
                  title=f"{fam} - {r.population.iloc[0] if len(r) else ''} · {sub}")
show(fig, key="rates")

section("Equity heatmap: every group × every measure", BLUE, "🌡️")
dis = query("select * from marts.mart_disparities where n_patients >= 11 and group_value <> 'Not reported'")
gt = st.radio("Groups", dis.group_type.unique().tolist(), horizontal=True, key="hm_gt")
d = dis[dis.group_type == gt].set_index("group_value")
measures = {"pct_chemo_when_indicated": "Chemo when indicated %", "pct_her2_targeted_among_her2_pos": "HER2-targeted | HER2+ %",
            "pct_endocrine_among_hr_pos": "Endocrine | HR+ %", "pct_radiation": "Radiation %",
            "median_days_to_chemotherapy": "Median days to chemo", "pct_chemo_over_90d": "Chemo > 90 d %",
            "pct_stage_iii_iv": "Stage III–IV %", "crude_mortality_pct": "Crude mortality %"}
m = d[list(measures)]
z = (m - m.mean()) / m.std(ddof=0).replace(0, 1)
fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=list(measures.values()), y=list(m.index), text=m.round(1).to_numpy(),
                           texttemplate="%{text}", colorscale=[[0, "#1c5cab"], [0.5, "#f0efec"], [1, "#eb6834"]],
                           zmid=0, xgap=3, ygap=3, colorbar=dict(title="vs group mean", tickvals=[-2, 0, 2], ticktext=["lower", "avg", "higher"]),
                           hovertemplate="%{y}<br>%{x}: <b>%{text}</b><extra></extra>"))
fig.update_layout(height=150 + 40 * len(m), xaxis=dict(tickangle=-30), yaxis=dict(autorange="reversed"),
                  title="Cell = value; colour = relative to the other groups (neutral grey = average)")
show(fig, key="heat")
note("Race is patient-reported, and missingness is concentrated at non-US biorepository sites. Small groups (e.g. "
     "0 of 14 HER2+ Asian patients with recorded HER2 therapy) are more likely data-capture gaps than care gaps. "
     "Significant differences show where to investigate, not what caused them.", ORANGE)

section("All statistical tests", MAGENTA, "🧮")
st.dataframe(tests[["test_family", "population", "group_type", "method", "statistic", "p_value", "p_value_fdr",
                    "significant_fdr_05", "n"]].style.format({"p_value": "{:.2g}", "p_value_fdr": "{:.2g}", "statistic": "{:.2f}"}, na_rep="—")
             .apply(lambda s: ["background-color: #fbe3e3" if v else "" for v in s], subset=["significant_fdr_05"]),
             use_container_width=True, hide_index=True)
table(dis, "Full disparities mart")
footer()
