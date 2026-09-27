# `models/staging`: typed, cleaned views over the raw layer

[← dbt project](../../README.md)

One view per source table. Staging only renames, casts, standardises and filters `_is_deleted` rows. No business
logic lives here.

| Model | Source | Notes |
|---|---|---|
| `fhir/stg_fhir__patients` | `raw.fhir_patient` | demographics, vital status, age (TCGA caps ages > 89), site |
| `fhir/stg_fhir__organizations` | `raw.fhir_organization` | joins `ref_site_classification` to flag biorepositories vs treating facilities |
| `fhir/stg_fhir__conditions` | `raw.fhir_condition` | ICD-10, ICD-O-3 histology groups, AJCC stage group → major stage |
| `fhir/stg_fhir__observations` | `raw.fhir_observation` | staging/TNM, lymph nodes, ER/PR/HER2, disease status, recurrence events |
| `fhir/stg_fhir__procedures` | `raw.fhir_procedure` | surgery and radiation; `is_delivered` from FHIR status |
| `fhir/stg_fhir__medications` | `raw.fhir_medication` | MedicationAdministration + MedicationStatement; normalised `agent_key` |
| `fhir/stg_fhir__encounters` | `raw.fhir_encounter` | follow-up and last-contact visits |
| `registry/stg_registry__tcga_pancan_patients` | cBioPortal PanCancer Atlas | curated OS / DSS / PFI / DFI endpoints, PAM50 subtype (safe numeric casts) |
| `registry/stg_registry__metabric_patients` | cBioPortal METABRIC | patient + sample attributes joined (tumour size, grade, receptor status, treatments, OS/RFS) |

`sources.yml` documents all 11 raw sources, with source-level uniqueness tests and freshness thresholds on `_loaded_at`.
