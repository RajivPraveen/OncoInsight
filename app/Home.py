"""OncoInsight dashboard entry point: grouped navigation across 13 pages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="OncoInsight", page_icon="🎗️", layout="wide", initial_sidebar_state="expanded")

P = Path(__file__).parent / "pages"
nav = st.navigation(expanded=True, pages={
    "Start here": [
        st.Page(P / "overview.py", title="Overview", icon="🏠", default=True),
        st.Page(P / "story.py", title="Why OncoInsight?", icon="📖"),
    ],
    "Care journey": [
        st.Page(P / "patient_360.py", title="Patient 360", icon="🧑‍⚕️"),
        st.Page(P / "pathways.py", title="Treatment pathways", icon="🔀"),
        st.Page(P / "time_to_treatment.py", title="Time to treatment", icon="⏱️"),
    ],
    "Outcomes & value": [
        st.Page(P / "survival.py", title="Survival & cohort lab", icon="📈"),
        st.Page(P / "recurrence.py", title="Recurrence & risk", icon="🔁"),
        st.Page(P / "cost.py", title="Cost & what-if", icon="💵"),
        st.Page(P / "equity.py", title="Equity", icon="⚖️"),
    ],
    "Operations & platform": [
        st.Page(P / "operations.py", title="Hospital scorecard & alerts", icon="🏥"),
        st.Page(P / "data_quality.py", title="Data quality", icon="🧪"),
        st.Page(P / "lineage.py", title="Data lineage", icon="🧬"),
        st.Page(P / "assistant.py", title="AI analytics assistant", icon="🤖"),
    ],
})
with st.sidebar:
    st.markdown("### 🎗️ OncoInsight")
    st.caption("Breast cancer treatment & outcomes intelligence · real TCGA-BRCA + METABRIC data")
nav.run()
