# `fhir/`: GDC → FHIR R4 interoperability layer

[← package overview](../README.md)

The warehouse ingests the clinical feed **only as FHIR**, the way EHR data arrives through Bulk FHIR exports. That
keeps source-specific quirks out of the models and proves the pipeline would work on a hospital feed.

| File | What it does |
|---|---|
| `gdc_to_fhir.py` | mCODE-style mapping of each GDC case (details below) |
| `validate.py` | Validates **every** resource against the FHIR R4B schema (`fhir.resources`); invalid resources are quarantined with the error, never silently dropped |
| `flatten.py` | Polars flattening into one typed table per resource family, keeping the full resource JSON and a SHA-256 `record_hash` for change detection |

## Mapping

| GDC entity | FHIR resource | Coding |
|---|---|---|
| case + demographic | `Patient` | US Core race / ethnicity (OMB codes), TCGA barcode identifier |
| tissue source site | `Organization` | TSS code; linked as managing organisation / performer |
| diagnosis | `Condition` | ICD-10, ICD-O-3 morphology, AJCC stage summary |
| stage / T / N / M | `Observation` | LOINC 21902-2, 21899-0, 21900-6, 21901-4 |
| lymph nodes | `Observation` | LOINC 21893-3 (positive), 21894-1 (examined) |
| ER / PR / HER2 tests | `Observation` | LOINC 16112-5, 16113-3, 48676-1 (method IHC / FISH) |
| surgery, radiation | `Procedure` | status, performed period, fractions, dose, intent, margin |
| dated drug therapy | `MedicationAdministration` | agent, effective period, cycles, dose, route |
| undated drug therapy | `MedicationStatement` | `effective[x]` is mandatory on MedicationAdministration, so undated records use this resource |
| follow-ups | `Encounter` + disease-status / recurrence `Observation`s | LOINC 97509-4 |

**Dates:** TCGA publishes only day offsets and the diagnosis year. FHIR dates are anchored at 1 July of that year,
while the exact offsets travel in extensions and drive every interval calculation downstream.

**Latest run:** 1,098 cases → 24,313 resources, 0 quarantined.
