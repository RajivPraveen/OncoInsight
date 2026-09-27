import plotly.graph_objects as go
import streamlit as st
from charts import RING, delay_distribution, forest
from theme import (
    BLUE,
    INK_2,
    MAGENTA,
    ORANGE,
    STATUS,
    apply_filters,
    cohort_filters,
    footer,
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

page_setup("Time to treatment", "Where do delays happen, who waits longest, and which sites differ even after "
           "adjusting for case mix? Move the threshold slider to redefine a 'delay' and every number recomputes.",
           kicker="Care journey · operations")
f = cohort_filters()
delay = apply_filters(query("select * from marts.mart_treatment_delay"), f)
if not small_cohort_guard(delay.patient_id.nunique()):
    st.stop()

c = st.columns([2, 2, 3])
interval = c[0].selectbox("Interval", sorted(delay.interval_name.unique()),
                          index=sorted(delay.interval_name.unique()).index("Diagnosis → Chemotherapy"))
threshold = c[1].slider("Delay threshold (days)", 30, 180, 90, step=5,
                        help="90 days = threshold associated with worse survival for adjuvant chemotherapy")
d = delay[delay.interval_name == interval]
over = (d.interval_days > threshold).mean()
kpi_cards([
    {"label": "Patients with this interval", "value": f"{len(d):,}", "color": BLUE, "icon": "👥"},
    {"label": "Median", "value": f"{d.interval_days.median():.0f} days", "sub": f"IQR {d.interval_days.quantile(.25):.0f}–{d.interval_days.quantile(.75):.0f}", "color": ORANGE, "icon": "⏱️"},
    {"label": f"Over {threshold} days", "value": f"{over:.1%}", "sub": f"{int((d.interval_days > threshold).sum())} patients",
     "color": STATUS["critical"] if over > 0.2 else STATUS["good"], "icon": "⚠️"},
    {"label": "90th percentile", "value": f"{d.interval_days.quantile(.9):.0f} days", "sub": "tail of the distribution", "color": MAGENTA, "icon": "📏"},
])

section("Who waits longest?", ORANGE, "👥")
dim = st.radio("Compare by", ["stage_major", "receptor_subtype", "age_group", "race_ethnicity", "site_type"],
               horizontal=True, format_func=lambda s: s.replace("_", " ").replace("major", "").title())
show(delay_distribution(d, dim, threshold, f"{interval}: distribution by {dim.replace('_', ' ')} (box = IQR)"), key="violin")

section("Site benchmark - click a site to see its patients", BLUE, "🏥")
b = d[d.is_benchmarkable]
site = (b.groupby("hospital_name").interval_days.agg(n="size", median="median",
                                                     p25=lambda s: s.quantile(.25), p75=lambda s: s.quantile(.75),
                                                     over=lambda s: 100 * (s > threshold).mean()).reset_index())
site = site[site.n >= 10].sort_values("median")
network = d.interval_days.median()
fig = go.Figure()
for r in site.itertuples():
    fig.add_shape(type="line", x0=r.p25, x1=r.p75, y0=r.hospital_name, y1=r.hospital_name, line=dict(color="#c3c2b7", width=3))
col = [STATUS["critical"] if m > network * 1.2 else (BLUE if m < network * 0.85 else "#6da7ec") for m in site["median"]]
fig.add_trace(go.Scatter(x=site["median"], y=site.hospital_name, mode="markers", marker=dict(size=14, color=col, line=RING),
                         customdata=site[["n", "p25", "p75", "over"]],
                         hovertemplate="<b>%{y}</b><br>median %{x:.0f} days (IQR %{customdata[1]:.0f}–%{customdata[2]:.0f})"
                                       f"<br>%{{customdata[3]:.0f}}% over {threshold} d · n=%{{customdata[0]}}<extra></extra>"))
fig.add_vline(x=network, line_color=INK_2, line_width=1, annotation_text=f"network median {network:.0f} d")
fig.update_layout(height=140 + 38 * len(site), showlegend=False, xaxis_title="days",
                  title="Site median (dot) and interquartile range - red = >20% slower than the network")
ev = show(fig, key="site_dots", select=True)
picked = [pt.get("y") for pt in selected_points(ev)]
if picked:
    st.markdown(f"#### 🔍 {picked[0]}: patients for {interval}")
    table(b[b.hospital_name == picked[0]][["patient_id", "interval_days", "stage_major", "receptor_subtype", "age_group",
                                          "race_ethnicity", "year_of_diagnosis"]].sort_values("interval_days", ascending=False),
          f"{picked[0]} patients")

tab1, tab2, tab3 = st.tabs(["🧮 Case-mix-adjusted (O/E)", "📊 Adjusted delay drivers", "🌡️ Heatmap: site × interval"])
with tab1:
    ra = query("select * from analytics.hospital_risk_adjusted_delay").rename(columns={"hospital_name": "site"})
    show(forest(ra, "site", "oe_ratio", "oe_ci_lower", "oe_ci_upper", p=None, ref=1, log=False,
                title="Observed ÷ expected chemo > 90 days (logistic model: stage, subtype, age). Red = worse, blue = better",
                xtitle="observed / expected"), key="oe")
    note("A ratio above 1 means more late starts than the site's case mix predicts. If the 95% interval excludes 1, "
         "the site is flagged. Computed on the full cohort with the fixed 90-day definition.", ORANGE)
with tab2:
    dd = query("select * from analytics.delay_drivers where term <> 'Intercept'")
    model = st.radio("Model", dd.model.unique().tolist(), horizontal=True)
    m = dd[dd.model == model]
    is_or = "Logistic" in model
    show(forest(m, "term", "estimate", "ci_lower", "ci_upper", ref=1.0 if is_or else 0.0, log=is_or,
                xtitle="odds ratio" if is_or else "difference in median days",
                title=f"{model} - adjusted for all terms shown (n={int(m.n.iloc[0])})"), key="drivers")
with tab3:
    hm = delay[delay.is_benchmarkable].groupby(["hospital_name", "interval_name"]).interval_days.median().unstack()
    counts = delay[delay.is_benchmarkable].groupby("hospital_name").patient_id.nunique()
    hm = hm.loc[counts[counts >= 20].index]
    net = delay.groupby("interval_name").interval_days.median()
    rel = (hm - net) / net
    fig = go.Figure(go.Heatmap(z=rel.to_numpy() * 100, x=rel.columns, y=rel.index, zmid=0, zmin=-60, zmax=60,
                               colorscale=[[0, "#1c5cab"], [0.5, "#f0efec"], [1, "#d03b3b"]], xgap=3, ygap=3,
                               text=hm.round(0).to_numpy(), texttemplate="%{text}",
                               colorbar=dict(title="% vs network"),
                               hovertemplate="%{y}<br>%{x}<br>median <b>%{text}</b> days (%{z:+.0f}% vs network)<extra></extra>"))
    fig.update_layout(height=150 + 34 * len(rel), title="Median days by site and interval - red = slower than network, blue = faster",
                      xaxis=dict(tickangle=-30), yaxis=dict(autorange="reversed"))
    show(fig, key="heat")
table(d, f"{interval} intervals")
footer()
