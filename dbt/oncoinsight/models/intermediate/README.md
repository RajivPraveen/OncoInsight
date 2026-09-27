# `models/intermediate`: clinical business logic

[← dbt project](../../README.md)

| Model | Logic |
|---|---|
| `int_primary_diagnosis` | One index primary breast cancer per patient, plus pathologic T / N / M categories and lymph-node counts |
| `int_biomarker_status` | ER / PR / HER2 resolution following ASCO/CAP logic (**FISH overrides IHC** for HER2; equivocal without ISH stays equivocal) → `HR+/HER2-`, `HR+/HER2+`, `HR-/HER2+`, `Triple negative` |
| `int_treatment_events` | Unified surgery / radiation / systemic timeline for the index cancer; agent normalisation via `ref_agent_catalog` (fixes source mislabels such as trastuzumab recorded as "chemotherapy"); undated delivered surgery placed at day 0 and flagged |
| `int_pathway_steps` | First dated start of each modality group, ordered into steps, with gaps since the previous step |
| `int_patient_pathway` | Pathway string (e.g. `Surgery → Chemotherapy → Radiation → Endocrine`), received-modality flags, key start days, neoadjuvant flag, and `pathway_is_complete` (false when a delivered treatment is undated) |
| `int_follow_up` | Follow-up visit counts, last contact, last disease status, first recurrence (day, type, site) |
| `int_estimated_cost_lines` | Reference-price micro-costing: CMS 2026 prices × observed cycles / fractions / therapy days (standard-regimen defaults otherwise); concurrent same-day infusions share one administration fee; every line flags whether a default was used |
