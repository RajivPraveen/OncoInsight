"""On-the-fly cohort survival comparison (used by the dashboard Cohort Lab and ``POST /survival/compare``).

For any two patient cohorts: Kaplan-Meier curves with 95% CIs, numbers at risk, median survival, survival at
fixed horizons, restricted mean survival time (RMST) at a horizon with the RMST difference, and a log-rank test.
RMST is reported because it stays interpretable when hazards are not proportional and when medians are not
reached (common in breast cancer, where most patients survive past follow-up).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from lifelines.utils import restricted_mean_survival_time

MIN_N = 11


@dataclass
class CohortCurve:
    label: str
    n: int
    events: int
    timeline: list[float] = field(default_factory=list)
    survival: list[float] = field(default_factory=list)
    ci_lower: list[float] = field(default_factory=list)
    ci_upper: list[float] = field(default_factory=list)
    at_risk: list[int] = field(default_factory=list)
    median_months: float | None = None
    survival_at: dict[int, float | None] = field(default_factory=dict)
    rmst: float | None = None


@dataclass
class CohortComparison:
    endpoint: str
    horizon_months: int
    a: CohortCurve
    b: CohortCurve
    logrank_p: float | None
    logrank_statistic: float | None
    rmst_difference: float | None  # A - B, months


def _curve(df: pd.DataFrame, t: str, e: str, label: str, horizon: int, grid: np.ndarray) -> CohortCurve:
    d = df[[t, e]].dropna()
    d = d[d[t] >= 0]
    c = CohortCurve(label=label, n=len(d), events=int(d[e].sum()) if len(d) else 0)
    if len(d) < MIN_N:
        return c
    kmf = KaplanMeierFitter().fit(d[t], d[e])
    g = grid[grid <= d[t].max()]
    ci = kmf.confidence_interval_survival_function_
    ci_g = ci.reindex(ci.index.union(g)).ffill().loc[g]
    c.timeline = g.tolist()
    c.survival = kmf.survival_function_at_times(g).round(4).tolist()
    c.ci_lower = ci_g.iloc[:, 0].round(4).tolist()
    c.ci_upper = ci_g.iloc[:, 1].round(4).tolist()
    c.at_risk = [int((d[t] >= x).sum()) for x in g]
    med = kmf.median_survival_time_
    c.median_months = None if np.isinf(med) else float(med)
    for h in (12, 36, 60, 120):
        c.survival_at[h] = float(kmf.survival_function_at_times(h).iloc[0]) if d[t].max() >= h else None
    if d[t].max() >= horizon:
        c.rmst = float(restricted_mean_survival_time(kmf, t=horizon))
    return c


def compare_cohorts(a: pd.DataFrame, b: pd.DataFrame, t: str = "os_months", e: str = "os_event",
                    label_a: str = "Cohort A", label_b: str = "Cohort B", horizon: int = 60,
                    endpoint: str = "OS") -> CohortComparison:
    grid = np.arange(0, 241, 1.0)
    ca, cb = _curve(a, t, e, label_a, horizon, grid), _curve(b, t, e, label_b, horizon, grid)
    p = stat = None
    if ca.n >= MIN_N and cb.n >= MIN_N:
        da, db = a[[t, e]].dropna(), b[[t, e]].dropna()
        r = logrank_test(da[t], db[t], da[e], db[e])
        p, stat = float(r.p_value), float(r.test_statistic)
    diff = ca.rmst - cb.rmst if ca.rmst is not None and cb.rmst is not None else None
    return CohortComparison(endpoint, horizon, ca, cb, p, stat, diff)


def filter_frame(df: pd.DataFrame, filters: dict[str, list]) -> pd.DataFrame:
    """Apply {column: [allowed values]} filters (only for columns present; empty lists ignored)."""
    out = df
    for col, values in (filters or {}).items():
        if values and col in out.columns:
            out = out[out[col].isin(values)]
    return out
