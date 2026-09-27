# `analytics/`: statistics, machine learning and scenario modelling

[← package overview](../README.md)

Reads the dbt marts and writes results back to the `analytics` schema, so every statistic is versioned, queryable data
used by the dashboard, API and Power BI.

| File | Methods | Output tables |
|---|---|---|
| `survival.py` | Kaplan-Meier with 95% CIs and numbers at risk (OS / DSS / PFI for TCGA; OS / DSS / RFS for METABRIC) across stage, subtype, PAM50, pathway, chemo timing, race/ethnicity and age; multivariate log-rank; six penalised Cox PH models with Schoenfeld tests and events-per-variable checks | `km_curves`, `km_summary`, `logrank_tests`, `cox_coefficients`, `cox_ph_tests`, `cox_model_fit` |
| `cohorts.py` | Live comparison of any two cohorts: KM curves, survival at 1/3/5/10 years, **restricted mean survival time** and its difference, log-rank | used by the Cohort Lab and `POST /survival/compare` |
| `recurrence.py` | 5-year relapse models on METABRIC (logistic regression, random forest, XGBoost with a HistGradientBoosting fallback), 5-fold CV + hold-out, calibration, permutation importance; best model saved for scoring | `recurrence_model_metrics`, `recurrence_model_calibration`, `recurrence_feature_importance` |
| `disparities.py` | Wilson CIs, χ² / Fisher, Kruskal-Wallis / Mann-Whitney, Benjamini-Hochberg FDR; adjusted delay drivers (logistic + median regression); case-mix-adjusted **observed ÷ expected** delay per site with exact Poisson CIs | `disparity_tests`, `disparity_rates`, `delay_drivers`, `hospital_risk_adjusted_delay` |
| `cost_scenarios.py` | Line-level re-pricing for what-if levers: hypofractionation, trastuzumab biosimilar discount, drug price change, fee-schedule change. An unchanged scenario is exactly $0 | used by the Cost page |
| `run.py` | Runs everything, writes outputs, logs the run, and shuts down joblib worker pools so orchestrator subprocesses exit cleanly | n/a |

**Robustness:** Cox models never crash the pipeline. Models with too few events are skipped, non-converged models are
recorded with a status, and models under 10 events per covariate are flagged "interpret with caution".

**Interpretation:** all results are observational associations. Treatment indicators are confounded by indication and
are not treatment-effect estimates.
