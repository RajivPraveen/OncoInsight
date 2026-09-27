# `app/pages/`: dashboard pages

[← dashboard overview](../README.md)

| Section | File | Page | What you can do |
|---|---|---|---|
| Start here | `overview.py` | 🏠 Overview | Colour-coded KPIs, subtype → stage → first-treatment sunburst, modality mix, median start days, world map |
| | `story.py` | 📖 Why OncoInsight? | The project story: the problem, the patient journey, the real data, the 8 pipeline steps with live pass rates, and findings in tabs |
| Care journey | `patient_360.py` | 🧑‍⚕️ Patient 360 | Filter by pathway / outcome / site, 🎲 random patient, treatment timeline with follow-up markers and recurrence line |
| | `pathways.py` | 🔀 Treatment pathways | Cohort-filtered Sankey (depth + minimum-flow sliders), **click-to-drill treemap**, gaps between modalities |
| | `time_to_treatment.py` | ⏱️ Time to treatment | **Delay-threshold slider**, violins by group, **clickable site benchmark**, O/E, delay drivers, site × interval heatmap |
| Outcomes & value | `survival.py` | 📈 Survival & cohort lab | **Build two cohorts** and compare KM / 5-year survival / RMST / log-rank live; precomputed curves; Cox forest plots with PH diagnostics |
| | `recurrence.py` | 🔁 Recurrence & risk | Rates by factor, model calibration and importance, **interactive risk gauge** |
| | `cost.py` | 💵 Cost & what-if | Cost by pathway / stage / subtype / site, value map, **4-lever scenario simulator** with a cost bridge |
| | `equity.py` | ⚖️ Equity | Guideline-concordance by group with Wilson CIs, group × measure heatmap, FDR-highlighted tests |
| Operations & platform | `operations.py` | 🏥 Hospital scorecard & alerts | Diverging scorecard, **animated** year-by-year site chart, KPI trend with alert markers, filterable alert feed |
| | `data_quality.py` | 🧪 Data quality | Expectation results by dataset, open findings with samples, pipeline run timeline |
| | `lineage.py` | 🧬 Data lineage | Interactive dbt graph from the manifest; focus any model; view its SQL |
| | `assistant.py` | 🤖 AI analytics assistant | Chat with audited queries, one-click example questions, governed metric explorer with charts |
