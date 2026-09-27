# `tests`: singular reconciliation tests

[← dbt project](../README.md)

These guard end-to-end correctness beyond per-column tests. Each returns the rows that violate its rule, so a
failure points straight at the problem.

| Test | Guarantees |
|---|---|
| `assert_pathway_edges_conserve_patients` | Every patient leaves the Sankey's Diagnosis node exactly once |
| `assert_cost_lines_reconcile_to_patient_360` | Patient-level cost equals the sum of its cost lines to the cent |
| `assert_biomarker_subtype_consistent` | "Triple negative" never coexists with any positive receptor |
| `assert_no_staging_patient_loss` | Every non-deleted raw FHIR patient reaches the Patient 360 mart |
