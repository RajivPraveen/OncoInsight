"""Equity and time-to-treatment statistics.

* Group comparisons: Kruskal-Wallis / Mann-Whitney U (time to chemotherapy), chi-square or Fisher exact
  (proportions), Wilson 95% CIs, Benjamini-Hochberg FDR correction across the family of tests.
* Delay drivers: multivariable logistic regression (chemo > 90 days) and median (quantile) regression of
  days-to-chemotherapy on case mix, demographics and site type.
* Hospital benchmarking: case-mix-adjusted observed/expected ratio of chemo > 90 days per treating site.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

MAIN_RACES = ["White", "Black or African American", "Asian"]


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson")
    return float(lo), float(hi)


def _prop_test(df: pd.DataFrame, group: str, outcome: str, label: str, population: str) -> tuple[dict, list[dict]]:
    d = df[[group, outcome]].dropna()
    d = d[d[outcome].isin([True, False, 0, 1])]
    # string labels: a list of booleans would be interpreted by pandas as a column mask
    table = (pd.crosstab(d[group], d[outcome].astype(bool).map({False: "no", True: "yes"}))
             .reindex(columns=["no", "yes"], fill_value=0))
    rows = []
    for g, r in table.iterrows():
        n, k = int(r.sum()), int(r["yes"])
        lo, hi = wilson(k, n)
        rows.append({"test_family": label, "population": population, "group_type": group, "group_value": g,
                     "n": n, "events": k, "rate": k / n if n else np.nan, "ci_lower": lo, "ci_upper": hi})
    if table.shape[0] < 2:
        return {}, rows
    counts = table.to_numpy()
    if counts.shape == (2, 2) and (counts < 5).any():
        _, p = stats.fisher_exact(counts)
        method, stat, dof = "Fisher exact", np.nan, 1
    else:
        stat, p, dof, _ = stats.chi2_contingency(counts)
        method = "Chi-square"
    return ({"test_family": label, "population": population, "group_type": group, "method": method,
             "statistic": float(stat) if not np.isnan(stat) else None, "dof": int(dof), "p_value": float(p),
             "n": int(table.to_numpy().sum()), "n_groups": int(table.shape[0])}, rows)


def group_tests(p360: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = p360.copy()
    df["race_main"] = df["race"].where(df["race"].isin(MAIN_RACES))
    adj = df[df["days_to_chemotherapy"].between(0, 730)]
    tests, rates = [], []

    # continuous: days to adjuvant chemotherapy
    for group in ("race_main", "age_group", "stage_major", "receptor_subtype", "site_type"):
        d = adj[[group, "days_to_chemotherapy"]].dropna()
        d = d[~d[group].isin(["Unknown", "Not reported"])]
        samples = [s["days_to_chemotherapy"].to_numpy() for _, s in d.groupby(group) if len(s) >= 10]
        if len(samples) >= 2:
            h, p = stats.kruskal(*samples)
            tests.append({"test_family": "Days to adjuvant chemotherapy", "population": "Adjuvant chemo recipients",
                          "group_type": group, "method": "Kruskal-Wallis", "statistic": float(h),
                          "dof": len(samples) - 1, "p_value": float(p), "n": int(sum(map(len, samples))),
                          "n_groups": len(samples)})
    b = adj.loc[adj["race_main"] == "Black or African American", "days_to_chemotherapy"]
    w = adj.loc[adj["race_main"] == "White", "days_to_chemotherapy"]
    if len(b) >= 10 and len(w) >= 10:
        u, p = stats.mannwhitneyu(b, w, alternative="two-sided")
        tests.append({"test_family": "Days to adjuvant chemotherapy", "population": "Black vs White patients",
                      "group_type": "race_main", "method": "Mann-Whitney U", "statistic": float(u), "dof": None,
                      "p_value": float(p), "n": int(len(b) + len(w)), "n_groups": 2,
                      "effect_median_diff_days": float(b.median() - w.median())})

    # proportions
    indicated = df[df["receptor_subtype"].isin(["Triple negative", "HR-/HER2+", "HR+/HER2+"]) & df["stage_major"].isin(["II", "III"])]
    plan = [
        (adj, "race_main", "chemo_delayed_over_90d", "Chemotherapy started > 90 days", "Adjuvant chemo recipients"),
        (adj, "age_group", "chemo_delayed_over_90d", "Chemotherapy started > 90 days", "Adjuvant chemo recipients"),
        (indicated, "age_group", "received_chemotherapy", "Chemotherapy when indicated", "TNBC/HER2+ stage II-III"),
        (indicated, "race_main", "received_chemotherapy", "Chemotherapy when indicated", "TNBC/HER2+ stage II-III"),
        (df[df["her2_status"] == "Positive"], "race_main", "received_her2_targeted", "HER2-targeted therapy", "HER2-positive"),
        (df[df["her2_status"] == "Positive"], "age_group", "received_her2_targeted", "HER2-targeted therapy", "HER2-positive"),
        (df[df["hr_status"] == "Positive"], "race_main", "received_endocrine", "Endocrine therapy", "HR-positive"),
        (df[df["hr_status"] == "Positive"], "age_group", "received_endocrine", "Endocrine therapy", "HR-positive"),
        (df, "race_main", "received_radiation", "Radiation therapy", "All patients"),
    ]
    for data, group, outcome, label, pop in plan:
        d = data[~data[group].isin(["Unknown", "Not reported"])]
        t, r = _prop_test(d, group, outcome, label, pop)
        if t:
            tests.append(t)
        rates.extend(r)

    tests_df = pd.DataFrame(tests)
    if not tests_df.empty:
        tests_df["p_value_fdr"] = multipletests(tests_df["p_value"], method="fdr_bh")[1]
        tests_df["significant_fdr_05"] = tests_df["p_value_fdr"] < 0.05
    return {"disparity_tests": tests_df, "disparity_rates": pd.DataFrame(rates)}


def _or_table(res, model: str, n: int) -> pd.DataFrame:
    ci = res.conf_int()
    out = pd.DataFrame({"model": model, "term": res.params.index, "estimate": np.exp(res.params.values),
                        "ci_lower": np.exp(ci[0].values), "ci_upper": np.exp(ci[1].values),
                        "p_value": res.pvalues.values, "n": n, "estimate_type": "odds_ratio"})
    return out[out["term"] != "Intercept"]


def delay_drivers(p360: pd.DataFrame) -> pd.DataFrame:
    d = p360[p360["days_to_chemotherapy"].between(0, 730)].copy()
    d = d[d["stage_major"].isin(["I", "II", "III"]) & (d["receptor_subtype"] != "Unknown")]
    d["race_main"] = np.where(d["race"].isin(MAIN_RACES), d["race"], "Other/Not reported")
    d["delayed"] = d["chemo_delayed_over_90d"].astype(int)
    d["age10"] = d["age_at_diagnosis"] / 10
    d = d.dropna(subset=["age10"])
    formula_rhs = ("age10 + C(stage_major, Treatment('I')) + C(receptor_subtype, Treatment('HR+/HER2-')) "
                   "+ C(race_main, Treatment('White')) + C(site_type, Treatment('Academic medical center'))")
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logit = smf.logit(f"delayed ~ {formula_rhs}", data=d).fit(disp=False, maxiter=200)
        out.append(_or_table(logit, "Logistic: chemo > 90 days", len(d)))
        qr = smf.quantreg(f"days_to_chemotherapy ~ {formula_rhs}", data=d).fit(q=0.5, max_iter=5000)
    ci = qr.conf_int()
    out.append(pd.DataFrame({"model": "Median regression: days to chemo", "term": qr.params.index,
                             "estimate": qr.params.values, "ci_lower": ci[0].values, "ci_upper": ci[1].values,
                             "p_value": qr.pvalues.values, "n": len(d), "estimate_type": "median_difference_days"}))
    res = pd.concat(out, ignore_index=True)
    res["term"] = (res["term"].str.replace(r"C\((\w+), Treatment\('([^']+)'\)\)\[T\.([^\]]+)\]", r"\1: \3 (vs \2)", regex=True)
                   .str.replace("age10", "Age (per 10 years)"))
    log.info("delay_drivers_fitted", n=len(d), logit_pseudo_r2=round(float(logit.prsquared), 3))
    return res


def hospital_risk_adjusted(p360: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    """Observed vs case-mix-expected share of adjuvant chemo started > 90 days, per treating site."""
    d = p360[p360["days_to_chemotherapy"].between(0, 730) & p360["is_treating_facility"].fillna(False)].copy()
    d = d[d["stage_major"].isin(["I", "II", "III"])].dropna(subset=["age_at_diagnosis"])
    d["delayed"] = d["chemo_delayed_over_90d"].astype(int)
    X = pd.get_dummies(d[["stage_major", "receptor_subtype", "age_group"]], drop_first=True, dtype=float)
    X = sm.add_constant(X)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = sm.GLM(d["delayed"], X, family=sm.families.Binomial()).fit()
    d["expected"] = m.predict(X)
    g = d.groupby("hospital_name").agg(n=("delayed", "size"), observed=("delayed", "sum"), expected=("expected", "sum"),
                                       site_type=("site_type", "first")).reset_index()
    g = g[g["n"] >= min_n].copy()
    g["oe_ratio"] = g["observed"] / g["expected"]
    # exact Poisson CI on the observed count, scaled by expected (standard O/E funnel approach)
    g["oe_ci_lower"] = stats.chi2.ppf(0.025, 2 * g["observed"]) / 2 / g["expected"]
    g["oe_ci_upper"] = stats.chi2.ppf(0.975, 2 * (g["observed"] + 1)) / 2 / g["expected"]
    g["oe_ci_lower"] = g["oe_ci_lower"].fillna(0)
    g["observed_rate"] = g["observed"] / g["n"]
    g["expected_rate"] = g["expected"] / g["n"]
    g["network_rate"] = d["delayed"].mean()
    g["flag"] = np.select([g["oe_ci_lower"] > 1, g["oe_ci_upper"] < 1], ["Worse than expected", "Better than expected"],
                          "As expected")
    return g.sort_values("oe_ratio", ascending=False)
