# `app/pages/`: dashboard pages

[← dashboard overview](../README.md)

Every page opens with the question it answers and the short answer.

| Section | File | Page | What you can do |
|---|---|---|---|
| Start here | `overview.py` | Overview | The question, headline numbers, the typical patient journey, who the patients are, a glossary |
| | `story.py` | The story in 2 minutes | The problem, the data, the four main findings (in tabs), and the 8 pipeline steps |
| The patient journey | `time_to_treatment.py` | Waiting times | Change what counts as "too long", compare groups, **click a hospital** for its patients, adjusted comparisons |
| | `pathways.py` | Treatment paths | Flow chart from diagnosis to outcome, **click a path tile** for its patients, gaps between steps |
| | `patient_360.py` | One patient's journey | Filter by path / outcome / hospital, random patient, treatment timeline with check-ups |
| Results | `survival.py` | Survival | **Compare any two groups** live (5-year survival, extra months, log-rank), survival by group, adjusted model |
| | `recurrence.py` | Cancer returning | Recurrence by group, an **interactive risk calculator**, model accuracy and calibration |
| | `cost.py` | Cost | Cost by path / stage / tumour type / hospital type, cost vs. outcome, a **what-if simulator** |
| | `equity.py` | Fairness of care | Recommended-treatment rates by age and race with uncertainty, group × measure grid, all tests |
| | `operations.py` | Hospital comparison | Report card, **animated** year-by-year chart, trend explorer with alert markers, alert feed |
| Behind the scenes | `assistant.py` | Ask the data (AI) | Chat with audited queries, example questions, a measure explorer that needs no AI |
| | `data_quality.py` | Data checks | Check results by dataset, what didn't pass, refresh timeline |
| | `lineage.py` | How the data flows | Interactive map of every dbt table; focus any table; view its SQL |
