# `dagster_project/`: orchestration

[← back to project README](../README.md)

`definitions.py` models the platform as Dagster **software-defined assets**:

```
gdc_cases_raw ──► fhir_bulk_export ──► fhir/* raw tables ──┐
cbioportal_raw ─────────────────────► registry/* raw tables ┴─► dbt models (44) ──► analytics_results ──► kpi_alerts
```

| Feature | Implementation |
|---|---|
| Assets | **65**: extraction, FHIR export, 11 quality-gated raw tables (multi-assets), every dbt model via `dagster-dbt`, analytics, KPI alerts |
| Lineage | dbt sources map onto the raw-table asset keys, so lineage is continuous from the APIs to the marts |
| Data tests | The 98 dbt tests appear as **81 asset checks** (column and singular tests) |
| Reliability | Exponential `RetryPolicy` on API extraction; the incremental watermark only advances after a successful load |
| Jobs & schedules | `daily_incremental_refresh` (06:00 UTC) and `weekly_full_reconciliation` (Sunday 03:00 UTC, dbt `--full-refresh`, soft-deletes), both running by default |
| Alerting | `run_failure_sensor` posts failed runs to `ONCO_ALERT_WEBHOOK_URL` |

## Run it

Dagster UI in Docker at http://localhost:3001:

```bash
make stack
```

Or locally:

```bash
DAGSTER_HOME=$PWD/.dagster_home uv run dagster dev -m dagster_project.definitions
```
