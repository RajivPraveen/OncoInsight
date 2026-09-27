# `staging/registry/`: registry staging views

[← staging](../README.md)

| Model | Source | Provides |
|---|---|---|
| `stg_registry__tcga_pancan_patients` | cBioPortal `brca_tcga_pan_can_atlas_2018` | Curated OS / DSS / PFI / DFI months and events (TCGA Clinical Data Resource), PAM50 subtype, neoadjuvant history |
| `stg_registry__metabric_patients` | cBioPortal `brca_metabric` | 2,509-patient validation cohort: tumour size, grade, stage, ER/PR/HER2, surgery type, treatment flags, OS / DSS / RFS |

Registry values arrive as text, so `safe_numeric` and `status_event` macros cast them safely.
