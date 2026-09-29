"""OncoInsight dashboard entry point: navigation grouped by the question each page answers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="OncoInsight", page_icon=":material/monitor_heart:", layout="wide",
                   initial_sidebar_state="expanded")

P = Path(__file__).parent / "pages"
nav = st.navigation(expanded=True, pages={
    "Start here": [
        st.Page(P / "overview.py", title="Overview", icon=":material/home:", default=True),
        st.Page(P / "story.py", title="The story in 2 minutes", icon=":material/menu_book:"),
    ],
    "The patient journey": [
        st.Page(P / "time_to_treatment.py", title="Waiting times", icon=":material/schedule:"),
        st.Page(P / "pathways.py", title="Treatment paths", icon=":material/alt_route:"),
        st.Page(P / "patient_360.py", title="One patient's journey", icon=":material/person:"),
    ],
    "Results": [
        st.Page(P / "survival.py", title="Survival", icon=":material/monitor_heart:"),
        st.Page(P / "recurrence.py", title="Cancer returning", icon=":material/autorenew:"),
        st.Page(P / "cost.py", title="Cost", icon=":material/payments:"),
        st.Page(P / "equity.py", title="Fairness of care", icon=":material/balance:"),
        st.Page(P / "operations.py", title="Hospital comparison", icon=":material/local_hospital:"),
    ],
    "Behind the scenes": [
        st.Page(P / "assistant.py", title="Ask the data (AI)", icon=":material/chat:"),
        st.Page(P / "data_quality.py", title="Data checks", icon=":material/fact_check:"),
        st.Page(P / "lineage.py", title="How the data flows", icon=":material/account_tree:"),
    ],
})
with st.sidebar:
    st.markdown("**OncoInsight**")
    st.caption("Where breast cancer patients wait too long for treatment, and what that means for them. "
               "Built on 1,098 real, de-identified patients.")
nav.run()
