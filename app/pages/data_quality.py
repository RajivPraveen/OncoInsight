import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    STATUS,
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

page_setup("Data checks",
           "Before any data reaches this dashboard it goes through automatic checks: are required fields filled in, "
           "are values in a sensible range, do records link up correctly? This page shows what passed and what didn't.",
           kicker="Behind the scenes")

dq = query("""select distinct on (dataset, expectation, column_name) dataset, expectation, column_name, severity, success,
                     observed, checked_at from ops.dq_results order by dataset, expectation, column_name, checked_at desc""")
runs = query("select run_id, pipeline, status, started_at, finished_at, rows_in, rows_changed from ops.pipeline_runs order by started_at desc limit 200")
kpi_cards([
    {"label": "Checks run", "value": len(dq)},
    {"label": "Passing", "value": f"{dq.success.mean():.0%}"},
    {"label": "Serious failures", "value": int(((dq.severity == "critical") & ~dq.success).sum()), "sub": "these would stop the load"},
    {"label": "Warnings", "value": int(((dq.severity == "warning") & ~dq.success).sum()), "sub": "logged, but not blocking"},
    {"label": "Data refreshes logged", "value": len(runs)},
])

section("Checks by dataset")
agg = dq.assign(state=dq.apply(lambda r: "passed" if r.success else f"failed ({r.severity})", axis=1)) \
    .groupby(["dataset", "state"]).size().unstack(fill_value=0)
fig = go.Figure()
for state, color in (("passed", STATUS["good"]), ("failed (warning)", STATUS["warning"]), ("failed (critical)", STATUS["critical"])):  # status colours
    if state in agg:
        fig.add_trace(go.Bar(y=agg.index, x=agg[state], name=state, orientation="h", marker=dict(color=color, line=RING),
                             hovertemplate="%{y}: <b>%{x}</b> " + state + "<extra></extra>"))
fig.update_layout(barmode="stack", height=120 + 34 * len(agg), bargap=0.35, xaxis_title="number of checks", margin=dict(t=40))
show(fig, key="dq")
how_to_read("each bar is one source table. Green = checks passed, amber = warnings, red = serious failures.")

fails = dq[~dq.success]
if len(fails):
    section("What didn't pass", blurb="Real quirks in the source data. They are kept and flagged, not silently dropped.")
    for r in fails.itertuples():
        obs = r.observed if isinstance(r.observed, dict) else {}
        st.markdown(f"**{'Serious' if r.severity == 'critical' else 'Warning'}** · `{r.dataset}.{r.column_name}` · {r.expectation.replace('_', ' ')} · "
                    f"**{obs.get('unexpected_count', '—')}** unexpected ({(obs.get('unexpected_percent') or 0):.2f}%) · "
                    f"sample `{obs.get('partial_unexpected_list', [])[:5]}`")
    note("For example: radiation courses recorded with more than 60 sessions, or treatments dated more than 20 years "
         "after diagnosis. Unusual, but real, so they are flagged rather than deleted.")

section("Data refreshes over time")
if len(runs):
    fig = go.Figure()
    for pipe, g in runs.groupby("pipeline"):
        fig.add_trace(go.Scatter(x=g.started_at, y=[pipe] * len(g), mode="markers", name=pipe,
                                 marker=dict(size=13, line=RING, color=[STATUS["good"] if s == "success" else STATUS["critical"] for s in g.status]),
                                 customdata=g[["status", "rows_in", "rows_changed"]],
                                 hovertemplate="%{x}<br>%{customdata[0]} · rows in %{customdata[1]} · changed %{customdata[2]}<extra></extra>"))
    fig.update_layout(height=280, showlegend=False, margin=dict(t=20))
    show(fig, key="runs")
    how_to_read("each dot is one refresh (green = succeeded). Hover to see how many rows changed; re-running on the "
                "same data changes almost nothing, which is the point.")
wm = query("select * from ops.ingestion_watermarks")
st.caption("Last update fetched from each source: " + "; ".join(f"{r.source} = {r.watermark}" for r in wm.itertuples()))
table(dq, "All check results")
table(runs, "All data refreshes")
footer()
