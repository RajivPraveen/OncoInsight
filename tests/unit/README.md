# `tests/unit/`: unit tests (no database needed)

[← tests](../README.md)

| File | Verifies |
|---|---|
| `test_fhir.py` | R4B validity of every generated resource, quarantine, date anchoring, coding, flattening and hashing |
| `test_quality_and_transform.py` | The quality gate passes clean data and blocks bad batches; the cBioPortal pivot |
| `test_assistant.py` | Semantic-layer SQL compilation and injection safety, SQL guard, agent tool loop with a mocked model |
| `test_monitoring_and_storage.py` | KPI alert rules and raw-store safety |
| `test_cohorts_and_charts.py` | Cohort survival comparison and RMST, Sankey conservation, forest colouring, lineage, filters, cost simulator |
