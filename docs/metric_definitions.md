# Metric definitions

Governed metrics are defined once in [`src/oncoinsight/assistant/semantic_layer.yml`](../src/oncoinsight/assistant/semantic_layer.yml)
and reused by the API (`/metrics/query`), the dashboard metric explorer and the AI assistant. Groups with
fewer than **11** patients are suppressed.

| Metric | Definition | Population / notes |
|---|---|---|
| Days to chemotherapy | first delivered chemotherapy start day − index diagnosis day | adjuvant starts only (0–730 days); negative = neoadjuvant |
| % chemotherapy > 90 days | share of adjuvant chemo starts with interval > 90 days | threshold from Chavez-MacGregor et al., JAMA Oncol 2016 |
| Days to radiation / endocrine | first delivered start day of the modality | 0–730 days |
| Chemo end → radiation | first radiation start − last chemo end | patients whose radiation followed chemo |
| Treatment pathway | ordered list of first-start days of each modality group (Surgery, Chemotherapy, HER2-targeted, Radiation, Endocrine, Other systemic) | ties broken by clinical order; undated delivered treatments reported via `pathway_is_complete = false` |
| Receptor subtype | HR+ = ER+ or PR+; HER2 by ISH if available, else IHC (equivocal IHC without ISH → Unknown) | HR+/HER2−, HR+/HER2+, HR−/HER2+, Triple negative |
| Chemotherapy when indicated | received chemotherapy among triple-negative or HER2+ patients, stage II–III | guideline-concordance proxy |
| HER2-targeted among HER2+ | received trastuzumab/lapatinib among HER2-positive | era effect: adjuvant trastuzumab approved 2006 |
| Crude mortality / recurrence % | events ÷ patients, not time-adjusted | use KM/Cox for comparisons |
| OS / DSS / PFI | TCGA PanCancer CDR endpoints (months), event indicator | PFI excludes stage IV in models |
| 5-year relapse (METABRIC) | RFS event ≤ 60 months; patients censored < 60 months without event excluded | model label |
| Standard-cycle completion % | reported cycles ≥ standard regimen length for that agent (`ref_agent_catalog`) | cycle-based regimens with reported cycles |
| Estimated cost | Σ(units × CMS 2026 unit price) across drug, administration, radiation and surgery cost lines | see Cost section below |
| RMST (cohort lab) | restricted mean survival time up to a chosen horizon (36/60/120 months); the difference is extra event-free months for cohort A vs B | interpretable without proportional hazards |
| O/E delay ratio | observed ÷ expected count of chemo > 90 days, expected from logistic model on stage, subtype, age group | treating sites with ≥ 20 patients; exact Poisson 95% CI |

## Cost model

- **Drugs**: units per administration from standard dosing at BSA 1.8 m² / 70 kg (in `ref_agent_catalog`) ×
  administrations. Administrations = reported cycles (capped at 36), otherwise the standard course length. Oral
  daily agents use the observed therapy days, otherwise 5 years.
- **Administration**: CPT 96413 once per infusion day. Concurrent same-day agents (e.g. AC) share one administration.
- **Radiation**: 77263 planning + 77412 per fraction + 77427 per 5 fractions. Uses observed fractions, otherwise 25.
- **Surgery**: surgeon fee blended 50/50 lumpectomy (19301) / mastectomy (19303) + axillary staging (38525 + 38900),
  because TCGA does not report surgery type. A re-excision is priced as a lumpectomy only.
- **Excluded**: hospital facility fees (OPPS Addendum B requires accepting an AMA licence; see
  cost_reference_sources.md), imaging, labs, inpatient stays, supportive drugs without a retrieved price.
- `used_default_quantity` marks every line that relied on a default rather than observed utilisation.

## KPI monitoring rule

For each entity (network + benchmarkable site) × KPI × diagnosis year: baseline = median of the prior 3 years.
The monitor alerts when |Δ%| ≥ 25%, n ≥ 8, and the robust z-score (MAD × 1.4826) is ≥ 2 (or the spread cannot be
estimated). Severity is *high* when |Δ%| ≥ 50%. Thresholds are env-configurable (`ONCO_KPI_ALERT_*`).

## Cost what-if scenarios

Implemented in `oncoinsight.analytics.cost_scenarios.reprice` and applied to every cost line of the current cohort:

| Lever | Effect |
|---|---|
| Hypofractionation (toggle + fractions) | caps CPT 77412 delivery units at N fractions and 77427 management at ceil(N/5) per course |
| Trastuzumab biosimilar discount % | reduces the J9355 unit price |
| Other drug price change % | scales all other drug unit prices |
| Physician fee schedule change % | scales every CPT (PFS) unit price |

Baseline and scenario use the same unrounded `units × unit_price` formula, so untouched levers change nothing.
