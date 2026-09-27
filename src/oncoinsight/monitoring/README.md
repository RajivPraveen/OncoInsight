# `monitoring/`: automated KPI anomaly detection

[← package overview](../README.md)

`kpi_monitor.py` scans `marts.mart_kpi_annual` for the network and every benchmarkable site and raises alerts such as:

> *Christiana Healthcare: Median diagnosis-to-radiation time increased from 140.5 to 220.0 days (+57%) vs the prior 3-year median (n=9, diagnosis year 2012).* (a real alert from this warehouse)

**Rule** (thresholds configurable via `ONCO_KPI_ALERT_*`):

1. Baseline = median of the previous 3 diagnosis years.
2. |change| ≥ 25%, **and** current n ≥ 8, **and** robust z-score (MAD × 1.4826) ≥ 2, or the history is too short to
   estimate spread.
3. Severity **high** when |change| ≥ 50%; each alert records whether the move is worse or better for that KPI.

KPIs monitored: median days to chemotherapy, % of chemo starts > 90 days, median days to radiation, new diagnoses, and
mean estimated cost. Alerts go to `ops.kpi_alerts` (and `analytics.kpi_alerts_detail`), and an optional webhook
(`ONCO_ALERT_WEBHOOK_URL`) receives the latest period's alerts.
