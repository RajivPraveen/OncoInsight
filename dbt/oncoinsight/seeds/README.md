# `seeds`: versioned reference data (schema `ref`)

[← dbt project](../README.md)

| Seed | Rows | Contents |
|---|---|---|
| `ref_cms_reference_prices.csv` | 35 | 2026 CMS national prices: Physician Fee Schedule RVU26D (surgeon, radiation, chemo administration), Oct-2026 ASP Part B drug payment limits, NADAC oral-drug acquisition costs. Each row records HCPCS code, billing unit, price basis, source file and URL. Provenance is in [`docs/cost_reference_sources.md`](../../../docs/cost_reference_sources.md) |
| `ref_agent_catalog.csv` | 65 | Raw GDC agent names → canonical agent, drug class, pathway modality, route, price, standard dosing (BSA 1.8 m² / 70 kg) and course length |
| `ref_procedure_cost_rules.csv` | 8 | How radiation (planning + per-fraction delivery + weekly management), surgery (blended lumpectomy/mastectomy + axillary staging) and chemo administration are priced |
| `ref_ajcc_stage.csv` | 14 | AJCC stage group → major stage and sort order |
| `ref_site_classification.csv` | 40 | Tissue source site → academic / cancer center / community / military / **biorepository**, and whether it is a treating facility |

Changing a price or dosing assumption is a reviewed, version-controlled CSV edit followed by `dbt build`.
