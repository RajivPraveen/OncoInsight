# `staging/fhir/`: FHIR staging views

[← staging](../README.md)

Seven views, one per flattened FHIR table (`raw.fhir_*`): patients, organizations, conditions, observations,
procedures, medications (MedicationAdministration + MedicationStatement) and encounters. They rename columns to
analytics-friendly names, cast types, derive simple flags (`is_delivered`, `stage_major`, `histology_group`) and drop
soft-deleted rows. Clinical logic lives in [`../../intermediate`](../../intermediate/).
