import json
from pathlib import Path

import streamlit as st
from charts import LAYER_COLOR, lineage_graph
from theme import BLUE, ORANGE, VIOLET, footer, kpi_cards, note, page_setup, pills, section, show

page_setup("Data lineage", "Trace any table back to the source APIs and forward to the dashboards that use it. "
           "Generated live from the dbt manifest, so it can't drift from the code.", kicker="Platform")
MANIFEST = Path(__file__).resolve().parents[2] / "dbt" / "oncoinsight" / "target" / "manifest.json"
if not MANIFEST.exists():
    st.warning("dbt manifest not found - run `dbt parse` in dbt/oncoinsight.")
    st.stop()
m = json.loads(MANIFEST.read_text())
models = {k: v for k, v in m["nodes"].items() if v["resource_type"] == "model"}
tests = [v for v in m["nodes"].values() if v["resource_type"] == "test"]
kpi_cards([
    {"label": "dbt models", "value": len(models), "color": BLUE, "icon": "🧱"},
    {"label": "Sources", "value": len(m["sources"]), "color": VIOLET, "icon": "🔌"},
    {"label": "Data tests", "value": len(tests), "color": ORANGE, "icon": "✅"},
    {"label": "Seeds", "value": sum(v["resource_type"] == "seed" for v in m["nodes"].values()), "color": "#eda100", "icon": "🌱"},
])
section("Explore the graph", BLUE, "🧬")
pills({k.title(): v for k, v in LAYER_COLOR.items()})
choices = ["(whole project)"] + sorted(v["name"] for v in models.values())
focus_name = st.selectbox("Focus on a model (shows its full upstream and downstream lineage)", choices,
                          index=choices.index("mart_patient_360") if "mart_patient_360" in choices else 0)
focus = next((k for k, v in models.items() if v["name"] == focus_name), None)
show(lineage_graph(MANIFEST, focus), key="lineage")
if focus:
    node = models[focus]
    st.markdown(f"**{node['name']}** · materialized as `{node['config'].get('materialized')}` in schema `{node['schema']}`")
    if node.get("description"):
        st.caption(node["description"])
    with st.expander("Compiled SQL source"):
        st.code(node.get("raw_code", ""), language="sql")
note("Upstream of the dbt graph: <b>GDC & cBioPortal APIs → raw JSON (S3) → FHIR R4 NDJSON → Great Expectations → "
     "raw tables</b>. Downstream: this dashboard, the FastAPI service, Power BI and the AI assistant (declared as dbt "
     "exposures).", VIOLET)
footer()
