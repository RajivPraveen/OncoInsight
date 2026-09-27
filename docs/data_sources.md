# Data sources, FHIR mapping & lineage

## Sources

| Feed | Endpoint | Records (Sept 2026 pull) | Refresh |
|---|---|---|---|
| TCGA-BRCA clinical | `POST https://api.gdc.cancer.gov/cases` (project `TCGA-BRCA`) | 1,098 cases; 1,342 diagnoses; 4,948 treatments; 3,367 follow-ups; 3,300+ molecular tests | daily incremental, weekly full |
| TCGA PanCancer curated clinical | `GET https://www.cbioportal.org/api/studies/brca_tcga_pan_can_atlas_2018/clinical-data` | 1,084 patients × 41 attributes | weekly full |
| METABRIC | `GET https://www.cbioportal.org/api/studies/brca_metabric/clinical-data` | 2,509 patients × 24 patient + 12 sample attributes | weekly full |
| CMS / Medicaid reference prices | RVU26D, Oct-2026 ASP file, NADAC 2026-09-23 | 35 prices | versioned dbt seed |

All clinical feeds are de-identified, open-access research data: no authentication or data-use certification is
required for the fields used. Please cite the original studies (see README).

## GDC → FHIR R4 mapping

| GDC entity / field | FHIR resource | Key elements |
|---|---|---|
| case + demographic | `Patient` | identifier (TCGA barcode), gender, birth year, US Core race/ethnicity (OMB codes), deceased, extensions: age at diagnosis, age obfuscated, days to death, vital status |
| tissue_source_site | `Organization` | identifier (TSS code), name → managingOrganization / performer / serviceProvider |
| diagnosis | `Condition` | ICD-10 code, ICD-O-3 morphology extension, laterality, AJCC stage summary (LOINC 21902-2), primary flag, year of diagnosis |
| AJCC T/N/M, stage group | `Observation` | LOINC 21899-0 / 21900-6 / 21901-4 / 21902-2 |
| pathology_details | `Observation` | LOINC 21893-3 (nodes positive), 21894-1 (nodes examined) |
| molecular_tests ESR1/PGR/ERBB2 | `Observation` (laboratory) | LOINC 16112-5 ER, 16113-3 PR, 48676-1 HER2; method IHC/FISH |
| treatment (surgery, radiation) | `Procedure` | status (completed / in-progress / not-done / unknown), performedPeriod, fractions, dose, intent, margin, outcome, reasonReference → Condition |
| treatment (drugs) with dates | `MedicationAdministration` | medication (agent), effectivePeriod, cycles, dose, route, intent, outcome |
| treatment (drugs) without dates | `MedicationStatement` | same, `effective[x]` absent (FHIR requires it on MedicationAdministration) |
| follow_up | `Encounter` (AMB) + `Observation` | disease status (LOINC 97509-4); recurrence events with type/site/day |

Every time-bearing resource carries the exact `days-from-diagnosis` / `days-to-treatment-start` extensions. The
anchored ISO dates (day 0 = 1 July of the diagnosis year) exist for FHIR conformance and calendar views only.

**Validation.** The latest full run: 24,313 resources, 0 quarantined. `fhir.resources` enforces structure,
cardinality and datatypes. Code value sets (e.g. `status`) are additionally enforced as critical Great Expectations checks.

## Lineage (dbt)

```
raw.fhir_patient ─► stg_fhir__patients ─► dim_patient ─┐
raw.fhir_condition ─► stg_fhir__conditions ─► int_primary_diagnosis ─► fact_diagnosis
raw.fhir_observation ─► stg_fhir__observations ─► int_biomarker_status / int_follow_up
raw.fhir_procedure + raw.fhir_medication ─► stg_* ─► int_treatment_events (+ ref_agent_catalog)
      ─► int_pathway_steps ─► int_patient_pathway
      ─► int_estimated_cost_lines (+ ref_cms_reference_prices, ref_procedure_cost_rules)
raw.cbio_*_patient ─► stg_registry__* ─► fact_outcome / mart_metabric_cohort
core.* ─► mart_patient_360 ─► mart_treatment_pathways, mart_pathway_transitions, mart_treatment_delay,
          mart_delay_by_hospital, mart_survival, mart_recurrence(_summary), mart_cost_analysis,
          mart_kpi_annual, mart_disparities, mart_treatment_adherence
```

Generate the interactive lineage graph with `cd dbt/oncoinsight && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .`.
