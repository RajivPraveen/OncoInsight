import pandas as pd
import streamlit as st
from theme import footer, note, page_setup, section

from oncoinsight.assistant.agent import ask
from oncoinsight.assistant.semantic import MetricRequest, SemanticError, load_layer, run_metric
from oncoinsight.common.config import get_settings

settings = get_settings()
page_setup("Ask the data",
           "Type a question in plain English. An AI assistant (Claude) looks up the answer in the database and shows "
           "you exactly which queries it ran, so you can check its work.",
           kicker="Behind the scenes")
enabled = settings.anthropic_api_key is not None and bool(settings.anthropic_api_key.get_secret_value())

c = st.columns(3)
with c[0]:
    n_metrics = sum(len(m["metrics"]) for m in load_layer()["models"].values())
    note(f"<b>Agreed definitions.</b> It uses {n_metrics} pre-defined measures, so its numbers match the rest of the "
         "dashboard.")
with c[1]:
    note("<b>Read-only.</b> Any query it writes is checked first. It can only read finished tables, never change or "
         "delete anything.")
with c[2]:
    note("<b>Privacy-safe.</b> Groups smaller than 11 patients are hidden, and every query has a time limit.")

examples = [
    "Show me Stage III patients receiving chemotherapy and compare their treatment completion rates across hospitals.",
    "Why did chemotherapy delays increase in the latest alerts? Which sites drive it?",
    "Which patient groups wait longest from diagnosis to chemotherapy?",
    "How does 5-year overall survival differ by receptor subtype in TCGA and METABRIC?",
    "What is the estimated cost of the most common treatment pathways?",
]
section("Ask a question")
if not enabled:
    st.info("The AI assistant needs an Anthropic API key (`ANTHROPIC_API_KEY` in `.env`). The measure explorer below "
            "works without it.")
else:
    st.session_state.setdefault("history", [])
    cols = st.columns(len(examples))
    clicked = None
    for col, q in zip(cols, examples, strict=True):
        if col.button(q[:42] + "…", help=q, use_container_width=True):
            clicked = q
    question = st.chat_input("Ask about waiting times, treatments, survival, cost or fairness") or clicked
    for turn in st.session_state.history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Looking it up…"):
            try:
                result = ask(question)
                st.markdown(result.answer)
                for i, q in enumerate(result.queries, 1):
                    with st.expander(f"Query {i}: {q.tool}{' - ' + q.purpose if q.purpose else ''}{' (error)' if q.error else ''}"):
                        st.code(q.sql, language="sql")
                        if q.error:
                            st.error(q.error)
                        elif q.rows:
                            st.dataframe(pd.DataFrame(q.rows), use_container_width=True, hide_index=True)
                st.caption(f"model {result.model} · tokens in {result.usage['input_tokens']:,} (cache read "
                           f"{result.usage['cache_read_input_tokens']:,}) · out {result.usage['output_tokens']:,}")
                st.session_state.history += [{"role": "user", "content": question},
                                             {"role": "assistant", "content": result.answer}]
            except Exception as exc:  # surface API/config errors in the UI
                st.error(f"Assistant error: {exc}")

section("Explore a measure yourself", blurb="No AI needed: pick a measure and how to split it.")
layer = load_layer()
mc = st.columns(4)
model_name = mc[0].selectbox("Topic", list(layer["models"]))
model = layer["models"][model_name]
metric = mc[1].selectbox("Measure", list(model["metrics"]), format_func=lambda m: m.replace("_", " ").capitalize())
dims = mc[2].multiselect("Split by (up to 3)", list(model["dimensions"]), max_selections=3,
                         default=["stage_major"] if "stage_major" in model["dimensions"] else [])
filt_dim = mc[3].selectbox("Only include", [""] + list(model["dimensions"]))
filters = []
if filt_dim:
    filters.append({"dimension": filt_dim, "operator": "=", "value": st.text_input(f"{filt_dim} equals")})
st.caption(model["metrics"][metric]["description"])
try:
    q, rows = run_metric(MetricRequest(metric=metric, dimensions=dims, filters=[x for x in filters if x["value"] != ""]), settings)
    df = pd.DataFrame(rows)
    if dims and len(df) and df.value.notna().any():
        import plotly.express as px
        from charts import RING
        from theme import SERIES, show

        fig = px.bar(df, x=dims[0], y="value", color=dims[1] if len(dims) > 1 else None, barmode="group",
                     color_discrete_sequence=SERIES, hover_data=["n"], text_auto=".1f")
        fig.update_traces(marker_line=RING)
        fig.update_layout(height=360, title=f"{metric.replace('_', ' ')} by {', '.join(dims)}", bargap=0.35)
        show(fig, key="metric_chart")
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.expander("See the SQL"):
        st.code(q.sql, language="sql")
except SemanticError as exc:
    st.error(str(exc))
footer()
