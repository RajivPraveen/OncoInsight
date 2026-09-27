"""Automated oncology KPI monitoring.

For every entity (network + benchmarkable hospital) and KPI, each diagnosis-year value is compared with a
trailing baseline (median of the previous ``BASELINE_YEARS`` years). An alert fires when
  * the relative change exceeds ``kpi_alert_pct_change`` (default 25%), and
  * the current period has at least ``kpi_alert_min_n`` patients, and
  * the value is unusual relative to the entity's own history (robust z-score from the MAD >= 2), or the
    history is too short to estimate spread.
Severity is ``high`` when the change is at least twice the threshold. Alerts are written to
``ops.kpi_alerts``; an optional webhook (``ONCO_ALERT_WEBHOOK_URL``) receives the latest-period alerts.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from oncoinsight.common.config import Settings, get_settings
from oncoinsight.common.db import connect, ensure_ops_schema, read_sql, write_frame
from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

BASELINE_YEARS = 3


@dataclass(frozen=True)
class KPI:
    column: str
    label: str
    n_column: str
    higher_is_worse: bool
    unit: str


KPIS = [
    KPI("median_days_to_chemotherapy", "Median diagnosis-to-chemotherapy time", "n_timed_chemotherapy", True, "days"),
    KPI("pct_chemo_over_90d", "Chemotherapy started > 90 days", "n_timed_chemotherapy", True, "%"),
    KPI("median_days_to_radiation", "Median diagnosis-to-radiation time", "radiation_patients", True, "days"),
    KPI("new_diagnoses", "New diagnoses", "new_diagnoses", False, "patients"),
    KPI("mean_estimated_cost_usd", "Mean estimated treatment cost", "new_diagnoses", True, "USD"),
]


def detect(kpi_df: pd.DataFrame, pct_threshold: float, min_n: int) -> pd.DataFrame:
    alerts = []
    for (etype, entity), g in kpi_df.groupby(["entity_type", "entity"]):
        g = g.sort_values("year_of_diagnosis")
        for k in KPIS:
            cols = list(dict.fromkeys(["year_of_diagnosis", k.column, k.n_column]))  # value and n may coincide
            series = g[cols].dropna(subset=[k.column])
            for i in range(BASELINE_YEARS, len(series)):
                cur = series.iloc[i]
                hist = series.iloc[i - BASELINE_YEARS:i][k.column].astype(float)
                base = float(hist.median())
                n_cur = int(cur[k.n_column]) if pd.notna(cur[k.n_column]) else 0
                if base == 0 or n_cur < min_n:
                    continue
                value = float(cur[k.column])
                pct = (value - base) / abs(base)
                mad = float(np.median(np.abs(hist - base))) * 1.4826
                z = (value - base) / mad if mad > 0 else np.nan
                unusual = np.isnan(z) or abs(z) >= 2
                if abs(pct) < pct_threshold or not unusual:
                    continue
                worse = (pct > 0) == k.higher_is_worse
                severity = "high" if abs(pct) >= 2 * pct_threshold else "medium"
                direction = "increased" if pct > 0 else "decreased"
                period = str(int(cur["year_of_diagnosis"]))
                msg = (f"{entity}: {k.label} {direction} from {base:,.1f} to {value:,.1f} {k.unit} "
                       f"({pct:+.0%}) vs the prior {BASELINE_YEARS}-year median (n={n_cur}, diagnosis year {period}).")
                alerts.append({
                    "alert_id": hashlib.md5(f"{etype}|{entity}|{k.column}|{period}".encode()).hexdigest(),
                    "kpi": k.column, "kpi_label": k.label, "entity_type": etype, "entity": entity, "period": period,
                    "current_value": value, "baseline_value": base, "pct_change": pct,
                    "robust_z": None if np.isnan(z) else float(z), "n_current": n_cur,
                    "severity": severity, "direction": "worse" if worse else "better", "message": msg})
    return pd.DataFrame(alerts)


def _notify(alerts: pd.DataFrame) -> None:
    url = os.getenv("ONCO_ALERT_WEBHOOK_URL")
    if not url or alerts.empty:
        return
    import httpx

    text = "\n".join(f"[{r.severity.upper()}] {r.message}" for r in alerts.itertuples())
    try:
        httpx.post(url, json={"text": f"OncoInsight KPI alerts\n{text}"}, timeout=10).raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("alert_webhook_failed", error=str(exc))


def run_monitoring(settings: Settings | None = None) -> pd.DataFrame:
    s = settings or get_settings()
    ensure_ops_schema(s)
    kpis = read_sql("select * from marts.mart_kpi_annual", settings=s)
    alerts = detect(kpis, s.kpi_alert_pct_change, s.kpi_alert_min_n)
    now = datetime.now(UTC)
    with connect(s) as conn:
        conn.execute("delete from ops.kpi_alerts")
        if not alerts.empty:
            with conn.cursor() as cur:
                cur.executemany(
                    """insert into ops.kpi_alerts (alert_id, detected_at, kpi, entity_type, entity, period, current_value,
                       baseline_value, pct_change, robust_z, n_current, severity, message)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [(r.alert_id, now, r.kpi, r.entity_type, r.entity, r.period, r.current_value, r.baseline_value,
                      r.pct_change, r.robust_z, r.n_current, r.severity, r.message) for r in alerts.itertuples()])
        conn.commit()
    if not alerts.empty:
        write_frame(alerts, "kpi_alerts_detail", settings=s)
        latest = alerts[alerts["period"] == alerts["period"].max()]
        _notify(latest)
    log.info("kpi_monitoring_complete", alerts=len(alerts),
             high=int((alerts["severity"] == "high").sum()) if not alerts.empty else 0)
    return alerts
