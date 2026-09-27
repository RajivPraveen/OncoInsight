import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    AQUA,
    BLUE,
    GREEN,
    MAGENTA,
    ORANGE,
    STATUS,
    footer,
    kpi_cards,
    note,
    page_setup,
    query,
    section,
    show,
    table,
)

page_setup("Data quality", "Every batch is validated before it enters the warehouse (Great Expectations) and again "
           "after modelling (dbt tests). Here is what passed, what warned, and what the pipeline has done recently.",
           kicker="Platform")

dq = query("""select distinct on (dataset, expectation, column_name) dataset, expectation, column_name, severity, success,
                     observed, checked_at from ops.dq_results order by dataset, expectation, column_name, checked_at desc""")
runs = query("select run_id, pipeline, status, started_at, finished_at, rows_in, rows_changed from ops.pipeline_runs order by started_at desc limit 200")
kpi_cards([
    {"label": "Expectations (latest)", "value": len(dq), "color": BLUE, "icon": "🧪"},
    {"label": "Passing", "value": f"{dq.success.mean():.0%}", "color": STATUS["good"], "icon": "✅"},
    {"label": "Critical failures", "value": int(((dq.severity == "critical") & ~dq.success).sum()), "sub": "would block the load",
     "color": STATUS["critical"], "icon": "⛔"},
    {"label": "Warnings", "value": int(((dq.severity == "warning") & ~dq.success).sum()), "sub": "recorded, not blocking",
     "color": STATUS["warning"], "icon": "⚠️"},
    {"label": "Pipeline runs logged", "value": len(runs), "color": AQUA, "icon": "🔁"},
])

section("Expectations by dataset", GREEN, "📦")
agg = dq.assign(state=dq.apply(lambda r: "passed" if r.success else f"failed ({r.severity})", axis=1)) \
    .groupby(["dataset", "state"]).size().unstack(fill_value=0)
fig = go.Figure()
for state, color in (("passed", STATUS["good"]), ("failed (warning)", STATUS["warning"]), ("failed (critical)", STATUS["critical"])):
    if state in agg:
        fig.add_trace(go.Bar(y=agg.index, x=agg[state], name=state, orientation="h", marker=dict(color=color, line=RING),
                             hovertemplate="%{y}: <b>%{x}</b> " + state + "<extra></extra>"))
fig.update_layout(barmode="stack", height=120 + 34 * len(agg), bargap=0.35, title="Latest result per expectation")
show(fig, key="dq")

fails = dq[~dq.success]
if len(fails):
    section("Open findings", ORANGE, "🔎")
    for r in fails.itertuples():
        obs = r.observed if isinstance(r.observed, dict) else {}
        icon = "⛔" if r.severity == "critical" else "⚠️"
        st.markdown(f"{icon} **{r.severity.title()}** · `{r.dataset}.{r.column_name}` · {r.expectation.replace('_', ' ')} · "
                    f"**{obs.get('unexpected_count', '—')}** unexpected ({(obs.get('unexpected_percent') or 0):.2f}%) · "
                    f"sample `{obs.get('partial_unexpected_list', [])[:5]}`")
    note("These are genuine quirks in the source data (e.g. radiation courses reported with more than 60 fractions, "
         "treatment offsets beyond 20 years). They are kept and flagged rather than silently dropped.", ORANGE)

section("Pipeline activity", MAGENTA, "🔁")
if len(runs):
    fig = go.Figure()
    for pipe, g in runs.groupby("pipeline"):
        fig.add_trace(go.Scatter(x=g.started_at, y=[pipe] * len(g), mode="markers", name=pipe,
                                 marker=dict(size=13, line=RING, color=[STATUS["good"] if s == "success" else STATUS["critical"] for s in g.status]),
                                 customdata=g[["status", "rows_in", "rows_changed"]],
                                 hovertemplate="%{x}<br>%{customdata[0]} · rows in %{customdata[1]} · changed %{customdata[2]}<extra></extra>"))
    fig.update_layout(height=280, showlegend=False, title="Runs over time (green = success) - note re-runs change ~0 rows")
    show(fig, key="runs")
wm = query("select * from ops.ingestion_watermarks")
st.caption("Incremental watermarks: " + "; ".join(f"{r.source} = {r.watermark}" for r in wm.itertuples()))
table(dq, "All expectation results")
table(runs, "Pipeline runs")
footer()
