import plotly.graph_objects as go
import streamlit as st
from charts import RING
from theme import (
    BLUE,
    INK_2,
    MODALITY_COLORS,
    STAGE_COLORS,
    STATUS,
    SUBTYPE_COLORS,
    apply_filters,
    cohort_filters,
    footer,
    how_to_read,
    kpi_cards,
    page_setup,
    patients,
    section,
    show,
    small_cohort_guard,
)

page_setup(
    "Where do breast cancer patients wait too long?",
    "OncoInsight follows <b>1,098 real breast cancer patients</b> from diagnosis through surgery, chemotherapy, "
    "radiation and hormone therapy. It shows a hospital network where patients wait too long between steps, which "
    "treatments they receive, how they do afterwards, what it costs, and whether care is fair across groups.",
    kicker="OncoInsight · overview",
    question="After a breast cancer diagnosis, how long do patients wait for treatment, and do some hospitals make "
             "them wait longer than their patients' needs would explain?",
    answer="Half of patients start chemotherapy within about <b>2 months</b>. But <b>1 in 4 wait longer than 90 "
           "days</b>, the point research links to worse survival, and one hospital has <b>2.6×</b> more late starts "
           "than expected for its mix of patients.",
)

f = cohort_filters()
p = apply_filters(patients(), f)
if not small_cohort_guard(len(p)):
    st.stop()

timed = p[p.days_to_chemotherapy.between(0, 730)]
kpi_cards([
    {"label": "Patients shown", "value": f"{len(p):,}", "sub": f"treated at {p.hospital_id.nunique()} hospitals"},
    {"label": "Typical wait for chemotherapy", "value": f"{timed.days_to_chemotherapy.median():.0f} days" if len(timed) else "—",
     "sub": f"median, from diagnosis ({len(timed)} patients)"},
    {"label": "Waited more than 90 days", "value": f"{100 * timed.chemo_delayed_over_90d.mean():.0f}%" if len(timed) else "—",
     "sub": "linked to worse survival"},
    {"label": "Cancer came back or grew", "value": f"{100 * p.any_progression_or_recurrence.mean():.0f}%",
     "sub": "during follow-up"},
])

# ------------------------------------------------------------------ the journey
section("What a patient goes through",
        blurb="Breast cancer treatment is a relay between teams. Each hand-off is a chance for delay.")
med = {k: p[c].where(p[c].between(0, 730)).median() for k, c in
       (("Chemotherapy", "days_to_chemotherapy"), ("Endocrine", "days_to_endocrine"), ("Radiation", "days_to_radiation"))}
stops = [("Diagnosis", "day 0", INK_2), ("Surgery", "around day 0", MODALITY_COLORS["Surgery"]),
         ("Chemotherapy", f"typically day {med['Chemotherapy']:.0f}", MODALITY_COLORS["Chemotherapy"]),
         ("Hormone therapy", f"typically day {med['Endocrine']:.0f}", MODALITY_COLORS["Endocrine"]),
         ("Radiation", f"typically day {med['Radiation']:.0f}", MODALITY_COLORS["Radiation"]),
         ("Follow-up", "years 1–10+", BLUE)]
xs = list(range(len(stops)))
fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=[0] * len(xs), mode="lines", line=dict(color="#ecebe7", width=6), hoverinfo="skip"))
fig.add_trace(go.Scatter(x=xs, y=[0] * len(xs), mode="markers+text", text=[s[0] for s in stops],
                         textposition="top center", textfont=dict(size=14, color="#1c1f24"),
                         marker=dict(size=22, color=[s[2] for s in stops], line=RING),
                         customdata=[s[1] for s in stops], hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
for x, s in zip(xs, stops, strict=True):
    fig.add_annotation(x=x, y=-0.55, text=s[1], showarrow=False, font=dict(size=12, color=INK_2))
fig.update_layout(height=190, showlegend=False, margin=dict(t=20, b=10),
                  yaxis=dict(visible=False, range=[-1, 1]), xaxis=dict(visible=False, range=[-0.5, len(xs) - 0.5]))
show(fig, key="journey")
how_to_read("each dot is a step of care; the grey text is the typical (median) day that step starts, counted from "
            "diagnosis. Not every patient has every step.")

left, right = st.columns(2)
with left:
    section("How many patients get each treatment")
    received = {"Surgery": p.received_surgery.mean(), "Chemotherapy": p.received_chemotherapy.mean(),
                "Radiation": p.received_radiation.mean(), "Endocrine": p.received_endocrine.mean(),
                "HER2-targeted": p.received_her2_targeted.mean()}
    names = {"Endocrine": "Hormone therapy", "HER2-targeted": "HER2-targeted drugs"}
    fig = go.Figure(go.Bar(x=[v * 100 for v in received.values()], y=[names.get(k, k) for k in received],
                           orientation="h", marker=dict(color=[MODALITY_COLORS[k] for k in received], line=RING),
                           text=[f"{v:.0%}" for v in received.values()], textposition="outside",
                           hovertemplate="%{y}: <b>%{x:.0f}%</b> of patients<extra></extra>"))
    fig.update_layout(height=280, xaxis=dict(range=[0, 115], title="% of patients", showgrid=False),
                      yaxis=dict(autorange="reversed"), margin=dict(r=40, t=10), bargap=0.4)
    show(fig, key="modalities")
    how_to_read("almost everyone has surgery; about half also have chemotherapy or radiation.")
with right:
    section("How long until each treatment starts")
    fig2 = go.Figure(go.Bar(x=list(med.values()), y=["Chemotherapy", "Hormone therapy", "Radiation"], orientation="h",
                            marker=dict(color=[MODALITY_COLORS[k] for k in med], line=RING),
                            text=[f"{v:.0f} days" for v in med.values()], textposition="inside",
                            insidetextanchor="end", textfont=dict(color="#ffffff"),
                            hovertemplate="%{y}: typically starts on day <b>%{x:.0f}</b><extra></extra>"))
    fig2.add_vline(x=90, line_color=STATUS["critical"], line_width=1, annotation_text="90-day mark",
                   annotation_font_color=STATUS["critical"])
    fig2.update_layout(height=280, yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, 240], title="days after diagnosis",
                       showgrid=False), margin=dict(r=40, t=10), bargap=0.4)
    show(fig2, key="median_start")
    how_to_read("chemotherapy usually starts well before the 90-day mark, but the <b>Waiting times</b> page shows the "
                "quarter of patients who don't.")

left, right = st.columns(2)
with left:
    section("Tumour type", blurb="Tumour type decides which drugs can work.")
    sub = p.receptor_subtype.value_counts().reindex(list(SUBTYPE_COLORS)).dropna()
    fig3 = go.Figure(go.Bar(x=sub.values, y=sub.index, orientation="h",
                            marker=dict(color=[SUBTYPE_COLORS[k] for k in sub.index], line=RING),
                            text=[f"{v:,.0f}" for v in sub.values], textposition="outside",
                            hovertemplate="%{y}: <b>%{x}</b> patients<extra></extra>"))
    fig3.update_layout(height=250, yaxis=dict(autorange="reversed"), xaxis=dict(showgrid=False, title="patients", range=[0, sub.max() * 1.15]),
                       margin=dict(r=40, t=10), bargap=0.4)
    show(fig3, key="subtype")
    how_to_read("<b>HR+</b> tumours respond to hormone therapy, <b>HER2+</b> to HER2-targeted drugs. "
                "<b>Triple negative</b> has neither, so fewer options.")
with right:
    section("Cancer stage", blurb="Stage I is small and local; stage IV has spread.")
    stg = p.stage_major.value_counts().reindex(["I", "II", "III", "IV", "Unknown"]).dropna()
    fig4 = go.Figure(go.Bar(x=[f"Stage {s}" if s != "Unknown" else s for s in stg.index], y=stg.values,
                            marker=dict(color=[STAGE_COLORS[s] for s in stg.index], line=RING),
                            text=[f"{v:,.0f}" for v in stg.values], textposition="outside",
                            hovertemplate="%{x}: <b>%{y}</b> patients<extra></extra>"))
    fig4.update_layout(height=250, yaxis=dict(showgrid=False, title="patients", range=[0, stg.max() * 1.18]),
                       margin=dict(t=10), bargap=0.4)
    show(fig4, key="stage")
    how_to_read("most patients are diagnosed at stage II. Later stages usually need more treatment.")

section("Where to go next")
e = st.columns(2)
e[0].page_link("pages/time_to_treatment.py", label="Waiting times: who waits too long, and where?", icon=":material/schedule:")
e[0].page_link("pages/pathways.py", label="Treatment paths: which treatments, in what order?", icon=":material/alt_route:")
e[1].page_link("pages/survival.py", label="Survival: how do patients do afterwards?", icon=":material/monitor_heart:")
e[1].page_link("pages/cost.py", label="Cost: what does care cost, and what could be saved?", icon=":material/payments:")

with st.expander("New to these terms? A short glossary"):
    st.markdown("""
| Term | Plain meaning |
|---|---|
| **Stage (I–IV)** | How far the cancer has spread. I = small and local, IV = spread to other organs |
| **Chemotherapy** | Drugs that kill fast-growing cells, usually given in cycles after surgery |
| **Hormone therapy** (endocrine) | Pills that block the hormones some tumours need to grow, often taken for years |
| **HER2-targeted drugs** | Drugs such as trastuzumab that attack tumours with extra HER2 protein |
| **HR+ / HER2+ / Triple negative** | Tumour types, based on which receptors the tumour has. They decide which drugs can work |
| **Recurrence** | The cancer coming back after treatment |
| **Median** | The middle value: half of patients are below it, half above |
""")
footer()
