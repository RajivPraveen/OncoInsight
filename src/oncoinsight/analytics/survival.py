"""Survival analytics: Kaplan-Meier curves, log-rank tests and Cox proportional hazards models.

TCGA-BRCA uses the PanCancer Clinical Data Resource endpoints (OS / DSS / PFI). METABRIC (OS / DSS / RFS,
median follow-up ~10 years) is used as an independent, larger cohort. All results are associations in
observational data - they describe the cohorts and are not causal treatment-effect estimates.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test, proportional_hazard_test

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

TIME_GRID = np.arange(0, 241, 3)  # months, 0-20 years
MIN_GROUP_N = 15

TCGA_ENDPOINTS = {"OS": ("os_months", "os_event"), "DSS": ("dss_months", "dss_event"), "PFI": ("pfs_months", "pfs_event")}
TCGA_STRATIFIERS = ["stage_major", "receptor_subtype", "pam50_subtype", "pathway_group", "chemo_timing_group",
                    "race_ethnicity", "age_group", "site_type"]
METABRIC_ENDPOINTS = {"OS": ("os_months", "os_event"), "DSS": ("os_months", "dss_event"), "RFS": ("rfs_months", "rfs_event")}
METABRIC_STRATIFIERS = ["tumor_stage", "receptor_subtype", "pam50_claudin_subtype", "treatment_combination",
                        "age_group", "tumor_grade"]


def _clean(df: pd.DataFrame, t: str, e: str, group: str | None = None) -> pd.DataFrame:
    cols = [t, e] + ([group] if group else [])
    d = df[cols].dropna().copy()
    d[t] = d[t].astype(float)
    d[e] = d[e].astype(int)
    d = d[d[t] >= 0]
    if group:
        d[group] = d[group].astype(str)
        d = d[~d[group].isin(["Unknown", "Not reported", "nan", "None"])]
    return d


def km_by_group(df: pd.DataFrame, cohort: str, endpoint: str, t: str, e: str, group: str
                ) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    d = _clean(df, t, e, group)
    counts = d[group].value_counts()
    keep = counts[counts >= MIN_GROUP_N].index
    d = d[d[group].isin(keep)]
    curves, summaries = [], []
    for g, sub in d.groupby(group):
        kmf = KaplanMeierFitter(label=str(g)).fit(sub[t], sub[e])
        grid = TIME_GRID[sub[t].max() >= TIME_GRID]
        sf = kmf.survival_function_at_times(grid).to_numpy()
        ci = kmf.confidence_interval_survival_function_.reindex(kmf.survival_function_.index)
        ci_at = ci.reindex(ci.index.union(grid)).ffill().loc[grid]
        at_risk = [(sub[t] >= x).sum() for x in grid]
        curves.append(pd.DataFrame({
            "cohort": cohort, "endpoint": endpoint, "stratifier": group, "group_value": str(g),
            "time_months": grid, "survival": sf, "ci_lower": ci_at.iloc[:, 0].to_numpy(),
            "ci_upper": ci_at.iloc[:, 1].to_numpy(), "at_risk": at_risk}))

        def at(month: float) -> tuple[float | None, float | None, float | None]:
            if sub[t].max() < month:
                return None, None, None
            s = float(kmf.survival_function_at_times(month).iloc[0])
            c = ci.reindex(ci.index.union([month])).ffill().loc[month]
            return s, float(c.iloc[0]), float(c.iloc[1])

        s5, l5, u5 = at(60)
        s10, l10, u10 = at(120)
        med = kmf.median_survival_time_
        summaries.append({
            "cohort": cohort, "endpoint": endpoint, "stratifier": group, "group_value": str(g),
            "n": len(sub), "events": int(sub[e].sum()),
            "median_survival_months": None if np.isinf(med) else float(med),
            "survival_5y": s5, "survival_5y_ci_lower": l5, "survival_5y_ci_upper": u5,
            "survival_10y": s10, "survival_10y_ci_lower": l10, "survival_10y_ci_upper": u10,
        })
    test = None
    if d[group].nunique() >= 2:
        r = multivariate_logrank_test(d[t], d[group], d[e])
        test = {"cohort": cohort, "endpoint": endpoint, "stratifier": group, "n_groups": int(d[group].nunique()),
                "n": len(d), "test_statistic": float(r.test_statistic), "degrees_of_freedom": int(r.degrees_of_freedom),
                "p_value": float(r.p_value)}
    return (pd.concat(curves, ignore_index=True) if curves else pd.DataFrame(), pd.DataFrame(summaries), test)


def run_km(tcga: pd.DataFrame, metabric: pd.DataFrame) -> dict[str, pd.DataFrame]:
    curves, summaries, tests = [], [], []
    plan = [("TCGA-BRCA", tcga, TCGA_ENDPOINTS, TCGA_STRATIFIERS),
            ("METABRIC", metabric, METABRIC_ENDPOINTS, METABRIC_STRATIFIERS)]
    for cohort, df, endpoints, strats in plan:
        for ep, (t, e) in endpoints.items():
            for g in strats:
                c, s, test = km_by_group(df, cohort, ep, t, e, g)
                curves.append(c)
                summaries.append(s)
                if test:
                    tests.append(test)
    return {"km_curves": pd.concat(curves, ignore_index=True), "km_summary": pd.concat(summaries, ignore_index=True),
            "logrank_tests": pd.DataFrame(tests)}


# ------------------------------------------------------------------ Cox models
def _dummies(df: pd.DataFrame, col: str, reference: str, prefix: str) -> pd.DataFrame:
    d = pd.get_dummies(df[col].astype(str), prefix=prefix, prefix_sep=": ", dtype=float)
    ref = f"{prefix}: {reference}"
    return d.drop(columns=[ref]) if ref in d.columns else d


def tcga_design(df: pd.DataFrame, endpoint: str = "OS") -> pd.DataFrame:
    t, e = TCGA_ENDPOINTS[endpoint]
    # Progression/recurrence endpoints exclude stage IV: disease is already metastatic at diagnosis.
    stages = ["I", "II", "III"] if endpoint == "PFI" else ["I", "II", "III", "IV"]
    d = df[(df["stage_major"].isin(stages)) & (df["receptor_subtype"] != "Unknown")].copy()
    d = d.dropna(subset=[t, e, "age_at_diagnosis"])
    X = pd.DataFrame({"duration": d[t].astype(float), "event": d[e].astype(int),
                      "Age (per 10 years)": d["age_at_diagnosis"].astype(float) / 10})
    X = X.join(_dummies(d, "stage_major", "I", "Stage")).join(_dummies(d, "receptor_subtype", "HR+/HER2-", "Subtype"))
    for flag, label in (("received_chemotherapy", "Received chemotherapy"), ("received_radiation", "Received radiation"),
                        ("received_endocrine", "Received endocrine therapy")):
        X[label] = d[flag].astype(float)
    return X[X["duration"] > 0]


def tcga_chemo_timing_design(df: pd.DataFrame) -> pd.DataFrame:
    """Among adjuvant chemotherapy recipients: is starting > 90 days after diagnosis associated with OS?"""
    d = df[df["days_to_chemotherapy"].between(0, 730) & df["stage_major"].isin(["I", "II", "III"])
           & (df["receptor_subtype"] != "Unknown")].copy()
    d = d.dropna(subset=["os_months", "os_event", "age_at_diagnosis"])
    X = pd.DataFrame({"duration": d["os_months"].astype(float), "event": d["os_event"].astype(int),
                      "Chemotherapy started > 90 days": d["chemo_delayed_over_90d"].astype(float),
                      "Age (per 10 years)": d["age_at_diagnosis"].astype(float) / 10})
    X = X.join(_dummies(d, "stage_major", "I", "Stage")).join(_dummies(d, "receptor_subtype", "HR+/HER2-", "Subtype"))
    return X[X["duration"] > 0]


def metabric_design(df: pd.DataFrame, endpoint: str = "OS") -> pd.DataFrame:
    t, e = METABRIC_ENDPOINTS[endpoint]
    d = df[df["receptor_subtype"] != "Unknown"].dropna(
        subset=[t, e, "age_at_diagnosis", "tumor_size_mm", "tumor_grade", "lymph_nodes_positive"]).copy()
    d = d[d["breast_surgery"].isin(["MASTECTOMY", "BREAST CONSERVING"])]
    X = pd.DataFrame({
        "duration": d[t].astype(float), "event": d[e].astype(int),
        "Age (per 10 years)": d["age_at_diagnosis"].astype(float) / 10,
        "Tumour size (per 10 mm)": d["tumor_size_mm"].astype(float) / 10,
        "Positive lymph nodes (log1p)": np.log1p(d["lymph_nodes_positive"].astype(float)),
        "Mastectomy (vs breast-conserving)": (d["breast_surgery"] == "MASTECTOMY").astype(float),
        "Received chemotherapy": d["received_chemotherapy"].astype(float),
        "Received radiotherapy": d["received_radiotherapy"].astype(float),
        "Received endocrine therapy": d["received_hormone_therapy"].astype(float),
    })
    d["tumor_grade"] = d["tumor_grade"].astype(int).astype(str)
    X = X.join(_dummies(d, "tumor_grade", "1", "Grade")).join(_dummies(d, "receptor_subtype", "HR+/HER2-", "Subtype"))
    return X[X["duration"] > 0]


MIN_EPV = 2    # below this many events per covariate a Cox model is not fitted at all
CAUTION_EPV = 10  # conventional events-per-variable guideline (Peduzzi et al. 1995); below it results are flagged


def fit_cox(model_name: str, X: pd.DataFrame, penalizer: float = 0.01) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fit a penalised Cox model. Never raises for statistical reasons: models with too few events or that fail
    to converge are recorded with a status and no coefficients, so one weak model cannot block the pipeline."""
    # drop constant columns (e.g. a subtype absent from a small subset)
    X = X.loc[:, (X.nunique() > 1) | X.columns.isin(["duration", "event"])]
    n_cov = X.shape[1] - 2
    events = int(X["event"].sum())
    epv = events / max(n_cov, 1)
    fit = {"model": model_name, "n": int(len(X)), "events": events, "n_covariates": n_cov, "events_per_variable": epv,
           "penalizer": penalizer, "concordance": None, "log_likelihood_ratio_p": None, "aic_partial": None,
           "status": "fitted", "caution": "low events-per-variable" if epv < CAUTION_EPV else None}
    empty = pd.DataFrame()
    if epv < MIN_EPV:
        fit["status"] = "insufficient_events"
        log.warning("cox_model_skipped", model=model_name, events=events, covariates=n_cov)
        return empty, empty, fit
    cph = CoxPHFitter(penalizer=penalizer)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cph.fit(X, duration_col="duration", event_col="event")
        llr = cph.log_likelihood_ratio_test()
    except Exception as exc:  # lifelines ConvergenceError / singular matrix
        fit["status"] = "not_converged"
        log.warning("cox_model_failed", model=model_name, error=str(exc)[:200])
        return empty, empty, fit
    if llr.test_statistic < 0:  # fitted model worse than null -> optimiser did not converge; do not publish
        fit["status"] = "not_converged"
        log.warning("cox_model_failed", model=model_name, error="negative likelihood-ratio statistic")
        return empty, empty, fit
    s = cph.summary
    coefs = pd.DataFrame({
        "model": model_name, "covariate": s.index, "hazard_ratio": s["exp(coef)"].to_numpy(),
        "ci_lower": s["exp(coef) lower 95%"].to_numpy(), "ci_upper": s["exp(coef) upper 95%"].to_numpy(),
        "p_value": s["p"].to_numpy(), "coef": s["coef"].to_numpy(), "se": s["se(coef)"].to_numpy()})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ph = proportional_hazard_test(cph, X, time_transform="rank")
        ph_df = pd.DataFrame({"model": model_name, "covariate": ph.summary.index,
                              "test_statistic": ph.summary["test_statistic"].to_numpy(),
                              "p_value": ph.summary["p"].to_numpy()})
        ph_df["ph_assumption_ok"] = ph_df["p_value"] > 0.05
    except Exception as exc:  # pragma: no cover - diagnostics must not break the pipeline
        log.warning("ph_test_failed", model=model_name, error=str(exc))
        ph_df = empty
    fit.update(concordance=float(cph.concordance_index_), log_likelihood_ratio_p=float(llr.p_value),
               aic_partial=float(cph.AIC_partial_))
    log.info("cox_model_fitted", **fit)
    return coefs, ph_df, fit


def run_cox(tcga: pd.DataFrame, metabric: pd.DataFrame) -> dict[str, pd.DataFrame]:
    specs = [
        ("TCGA OS ~ age + stage + subtype + treatment", tcga_design(tcga, "OS")),
        ("TCGA PFI ~ age + stage + subtype + treatment", tcga_design(tcga, "PFI")),
        ("TCGA OS ~ chemo timing (adjuvant chemo recipients)", tcga_chemo_timing_design(tcga)),
        ("METABRIC OS ~ clinical + treatment", metabric_design(metabric, "OS")),
        ("METABRIC DSS ~ clinical + treatment", metabric_design(metabric, "DSS")),
        ("METABRIC RFS ~ clinical + treatment", metabric_design(metabric, "RFS")),
    ]
    coefs, phs, fits = [], [], []
    for name, X in specs:
        c, p, f = fit_cox(name, X)
        coefs.append(c)
        phs.append(p)
        fits.append(f)
    return {"cox_coefficients": pd.concat(coefs, ignore_index=True),
            "cox_ph_tests": pd.concat(phs, ignore_index=True), "cox_model_fit": pd.DataFrame(fits)}
