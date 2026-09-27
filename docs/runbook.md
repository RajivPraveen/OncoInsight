# Operations runbook

## Schedules

| Job | When | What |
|---|---|---|
| `daily_incremental_refresh` | 06:00 UTC | GDC cases updated since the watermark, cBioPortal, FHIR, load, `dbt build`, analytics, KPI alerts |
| `weekly_full_reconciliation` | Sun 03:00 UTC | full GDC pull, soft-deletes, `dbt build --full-refresh` |

Local equivalent:

```bash
uv run python -m oncoinsight.pipeline all --mode incremental
```

## Failure handling

| Symptom | Where to look | Action |
|---|---|---|
| Extract step failed after retries | Dagster run logs; the GDC/cBioPortal status pages | Re-execute the failed step. Watermarks only advance after a successful load, so nothing is lost |
| `DataQualityError` (critical expectation) | `ops.dq_results where not success and severity='critical'`; Data Quality page | Inspect `observed.partial_unexpected_list`. Fix the mapping or quarantine, then re-run `load`. Nothing was written |
| FHIR resources quarantined | raw store `quarantine/fhir/...invalid.ndjson.gz` | Fix the mapper, re-run `fhir` + `load` |
| dbt test failure | Dagster asset checks / `dbt build` output | `dbt test --select <model>`; failing rows via `dbt test --store-failures` |
| Cox model `status != 'fitted'` | `analytics.cox_model_fit` | Expected for small subsets. Investigate if it happens on the full cohort |
| Step hangs after analytics | loky worker pool | Fixed by `_shutdown_worker_pools()`. If it recurs, check for new `n_jobs=-1` usage |
| KPI alert | `ops.kpi_alerts`, Operations page, webhook | Triage by direction/severity. Use the assistant ("why did X change?") to decompose by site/stage/subtype |

## Backfill / replay

The raw layer is immutable and run-partitioned. To rebuild from any earlier extract:

```bash
uv run python -c "from oncoinsight.pipeline import build_fhir, load_fhir; build_fhir('<run_id>'); load_fhir('<run_id>')"
```

Then rebuild the dbt models:

```bash
cd dbt/oncoinsight && uv run dbt build --profiles-dir . --full-refresh
```

## Secrets & access

- Secrets come only from the environment (`.env` locally, AWS Secrets Manager in ECS). `.env` is git-ignored.
- BI, API and assistant use the read-only `onco_reader` role. Rotate its password in Secrets Manager and in the
  `WAREHOUSE_READER_PASSWORD` variable.
- The optional alert webhook is set via `ONCO_ALERT_WEBHOOK_URL`.
