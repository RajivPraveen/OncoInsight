# Assumptions & limitations

Read these before quoting any number from the platform.

## Data

- **Research cohorts, not a health system.** TCGA-BRCA patients were enrolled for tumour sequencing between 1988 and
  2013 (mostly 2006–2011). Volumes by year reflect study accrual, not clinical demand, so volume alerts in the KPI
  monitor mostly reflect accrual waves.
- **"Hospitals" are TCGA tissue source sites.** Ten of the 40 are commercial biorepositories or research institutes
  (for example Indivumed, Asterand, ILSBio). They procured tissue but did not deliver the care. They are classified
  in `ref_site_classification` (a manual classification from public knowledge) and excluded from benchmarking.
- **Index date.** TCGA's day 0 is the initial pathologic diagnosis, usually the surgical specimen date, so
  "diagnosis → treatment" intervals are effectively surgery → adjuvant therapy. Biopsy-to-surgery time is not
  observable. Undated delivered surgeries are placed at day 0 (`start_day_imputed`).
- **Undated treatments.** 537 drug records have no dates (FHIR `MedicationStatement`). They count toward
  "received" flags but cannot enter pathway sequences or intervals (`pathway_is_complete`).
- **Calendar dates are anchored** at 1 July of the diagnosis year. Month/quarter views would be artefacts, so
  operational KPIs use diagnosis year.
- **Not available in any public patient-level oncology dataset:** readmissions, missed or cancelled appointments,
  insurance, income, claims, provider (physician) identifiers. The platform does not fabricate them.
  Treatment-completion signals (cycles vs standard, endocrine duration, reported outcome) replace adherence
  metrics. Reference-priced costs replace claims.
- **Race/ethnicity** are patient-reported, missing for about 9%, and missingness is concentrated at non-US sites. The
  Asian group is small and comes largely from sites with sparse treatment capture (e.g. 0 of 14 HER2+ Asian patients
  have recorded HER2-targeted therapy). Treat these as data-capture signals before equity conclusions.
- **Ages > 89** are obfuscated by TCGA.

## Methods

- All comparisons are **observational associations**. Treatment indicators in Cox models are confounded by
  indication (sicker patients get more treatment). They are not treatment-effect estimates, and the platform never
  claims one pathway is medically better.
- Cox models use a small ridge penalty (0.01), report Schoenfeld proportional-hazards tests, and record
  events-per-variable. Models under 10 EPV are flagged. The chemo-timing model has 27 events (EPV 3.9), so its
  HR is imprecise.
- Recurrence models are trained on METABRIC (UK/Canada, 1977–2005 diagnoses, pre-trastuzumab era). The API/dashboard
  scorer is a cohort-level demonstration and **not for clinical decisions**.
- Multiple comparisons in the equity analysis are FDR-corrected (Benjamini-Hochberg). Group tests are unadjusted.
  Adjusted associations are in `analytics.delay_drivers`.
- **Costs are estimates**: 2026 Medicare national rates applied to utilisation from earlier eras, standard BSA/weight
  dosing, blended surgery type, no facility fees. Use them for relative comparison across pathways, not budgeting.

## Platform

- Local S3 uses SeaweedFS because MinIO no longer publishes public container images. Production targets AWS S3
  (Terraform).
- The Terraform has been `validate`d but not applied to an AWS account.
- Power BI Desktop is Windows-only, so no `.pbix` is committed. `powerbi/` contains the model design, DAX measures,
  theme and connection steps.
- XGBoost needs an OpenMP runtime. On macOS without `libomp`, the pipeline automatically uses scikit-learn
  HistGradientBoosting. The Docker image includes XGBoost's runtime.
