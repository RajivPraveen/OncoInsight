import json
from pathlib import Path

import streamlit as st
from charts import LAYER_COLOR, lineage_graph
from theme import footer, kpi_cards, note, page_setup, pills, section, show

page_setup("How the data flows",
           "A map of every table, from the raw downloads on the left to the finished tables this dashboard reads on the "
           "right. Pick a table to see where its data comes from and what depends on it.",
           kicker="Behind the scenes")
MANIFEST = Path(__file__).resolve().parents[2] / "dbt" / "oncoinsight" / "target" / "manifest.json"
if not MANIFEST.exists():
    st.warning("The data map hasn't been generated yet - run `dbt parse` in dbt/oncoinsight.")
    st.stop()
m = json.loads(MANIFEST.read_text())
models = {k: v for k, v in m["nodes"].items() if v["resource_type"] == "model"}
tests = [v for v in m["nodes"].values() if v["resource_type"] == "test"]
kpi_cards([
    {"label": "Tables built", "value": len(models), "sub": "with dbt"},
    {"label": "Raw data sources", "value": len(m["sources"])},
    {"label": "Automatic tests", "value": len(tests), "sub": "run every time the tables are rebuilt"},
    {"label": "Reference files", "value": sum(v["resource_type"] == "seed" for v in m["nodes"].values()), "sub": "e.g. Medicare prices"},
])
section("Explore the map")
LAYER_NAMES = {"source": "Raw data", "seed": "Reference files", "staging": "Cleaned", "intermediate": "Combined",
               "core": "Core tables", "analytics": "Finished tables"}
pills({LAYER_NAMES.get(k, k.title()): v for k, v in LAYER_COLOR.items()})
choices = ["(whole project)"] + sorted(v["name"] for v in models.values())
focus_name = st.selectbox("Focus on a table (shows everything it comes from and feeds into)", choices,
                          index=choices.index("mart_patient_360") if "mart_patient_360" in choices else 0)
focus = next((k for k, v in models.items() if v["name"] == focus_name), None)
show(lineage_graph(MANIFEST, focus), key="lineage")
if focus:
    node = models[focus]
    st.markdown(f"**{node['name']}** · stored as a `{node['config'].get('materialized')}` in the `{node['schema']}` schema")
    if node.get("description"):
        st.caption(node["description"])
    with st.expander("See the SQL that builds this table"):
        st.code(node.get("raw_code", ""), language="sql")
note("<b>Before this map:</b> data is downloaded from two public cancer databases, converted to FHIR (the hospital "
     "data standard), and checked for quality. <b>After it:</b> the finished tables feed this dashboard, an API, "
     "Power BI and the AI assistant.")
footer()
