"""Dagster orchestration for OncoInsight.

Asset graph:
    gdc_cases_raw ─► fhir_bulk_export ─► raw FHIR tables (fhir/*) ─┐
    cbioportal_raw ───────────────────► raw registry tables ──────┤─► dbt models (+ dbt tests as asset checks)
                                                                   └─► analytics_results ─► kpi_alerts
Schedules: daily incremental refresh (06:00 UTC) and weekly full reconciliation (Sunday 03:00 UTC).
"""


import os

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    Backoff,
    Config,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    RunFailureSensorContext,
    ScheduleDefinition,
    asset,
    define_asset_job,
    multi_asset,
    run_failure_sensor,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets, get_asset_key_for_model

from oncoinsight import pipeline
from oncoinsight.common.config import PROJECT_ROOT, get_settings

DBT_PROJECT_DIR = PROJECT_ROOT / "dbt" / "oncoinsight"
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()

API_RETRY = RetryPolicy(max_retries=3, delay=30, backoff=Backoff.EXPONENTIAL)

FHIR_TABLES = ["fhir_patient", "fhir_organization", "fhir_condition", "fhir_observation", "fhir_procedure",
               "fhir_medication", "fhir_encounter"]
REGISTRY_TABLES = ["cbio_brca_tcga_pan_can_atlas_2018_patient", "cbio_brca_tcga_pan_can_atlas_2018_sample",
                   "cbio_brca_metabric_patient", "cbio_brca_metabric_sample"]


class ExtractConfig(Config):
    mode: str = "incremental"  # "incremental" | "full"


# ------------------------------------------------------------------ extraction
@asset(group_name="ingestion", retry_policy=API_RETRY, compute_kind="python",
       description="TCGA-BRCA clinical cases from the NCI GDC API, landed as gzipped JSON in the raw store.")
def gdc_cases_raw(context: AssetExecutionContext, config: ExtractConfig) -> MaterializeResult:
    m = pipeline.extract_gdc(config.mode)
    return MaterializeResult(metadata={"run_id": m.run_id, "mode": m.mode, "records": m.record_count,
                                       "max_updated_datetime": m.max_updated_datetime or "",
                                       "files": MetadataValue.json(m.keys)})


@asset(group_name="ingestion", retry_policy=API_RETRY, compute_kind="python",
       description="cBioPortal clinical data: TCGA PanCancer Atlas curated endpoints and METABRIC.")
def cbioportal_raw(context: AssetExecutionContext) -> MaterializeResult:
    ms = pipeline.extract_cbioportal()
    return MaterializeResult(metadata={m.source: m.record_count for m in ms})


@asset(group_name="interoperability", deps=[gdc_cases_raw], compute_kind="fhir",
       description="FHIR R4 NDJSON bulk export (mCODE-style) generated and schema-validated from the GDC extract.")
def fhir_bulk_export(context: AssetExecutionContext) -> MaterializeResult:
    summary = pipeline.build_fhir()
    return MaterializeResult(metadata={"run_id": summary["run_id"], "cases": summary["cases"],
                                       "quarantined": summary["quarantined"],
                                       "resources": MetadataValue.json(summary["resources"])})


# ------------------------------------------------------------------ warehouse raw layer
@multi_asset(
    group_name="warehouse_raw", compute_kind="postgres",
    specs=[AssetSpec(AssetKey(["fhir", t]), deps=[fhir_bulk_export], description=f"raw.{t} (quality-gated upsert)")
           for t in FHIR_TABLES],
)
def raw_fhir_tables(context: AssetExecutionContext):
    full = context.run.tags.get("oncoinsight/full_refresh") == "true"
    results = pipeline.load_fhir(full_refresh=full)
    for t in FHIR_TABLES:
        r = results.get(t, {})
        yield MaterializeResult(asset_key=AssetKey(["fhir", t]),
                                metadata={"rows_in": r.get("rows_in", 0), "rows_changed": r.get("rows_changed", 0),
                                          "rows_soft_deleted": r.get("rows_soft_deleted", 0)})


@multi_asset(
    group_name="warehouse_raw", compute_kind="postgres",
    specs=[AssetSpec(AssetKey(["registry", t]), deps=[cbioportal_raw], description=f"raw.{t}") for t in REGISTRY_TABLES],
)
def raw_registry_tables(context: AssetExecutionContext):
    results = pipeline.load_cbioportal()
    for t in REGISTRY_TABLES:
        r = results.get(t, {})
        yield MaterializeResult(asset_key=AssetKey(["registry", t]),
                                metadata={"rows_in": r.get("rows_in", 0), "rows_changed": r.get("rows_changed", 0)})


# ------------------------------------------------------------------ dbt
@dbt_assets(manifest=dbt_project.manifest_path, project=dbt_project)
def oncoinsight_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    args = ["build"]
    if context.run.tags.get("oncoinsight/full_refresh") == "true":
        args.append("--full-refresh")
    yield from dbt.cli(args, context=context).stream()


# ------------------------------------------------------------------ analytics & monitoring
@asset(group_name="analytics", compute_kind="python",
       deps=[get_asset_key_for_model([oncoinsight_dbt], m) for m in
             ("mart_survival", "mart_patient_360", "mart_metabric_cohort")],
       description="Kaplan-Meier, Cox PH, recurrence models, disparity tests, risk-adjusted benchmarking.")
def analytics_results(context: AssetExecutionContext) -> MaterializeResult:
    written = pipeline_analytics()
    return MaterializeResult(metadata={k: v for k, v in written.items()})


def pipeline_analytics() -> dict[str, int]:
    from oncoinsight.analytics.run import run_analytics

    return run_analytics(get_settings())


@asset(group_name="monitoring", compute_kind="python",
       deps=[get_asset_key_for_model([oncoinsight_dbt], "mart_kpi_annual"), analytics_results],
       description="KPI anomaly detection vs trailing baseline; alerts to ops.kpi_alerts (+ optional webhook).")
def kpi_alerts(context: AssetExecutionContext) -> MaterializeResult:
    from oncoinsight.monitoring.kpi_monitor import run_monitoring

    alerts = run_monitoring(get_settings())
    high = int((alerts["severity"] == "high").sum()) if not alerts.empty else 0
    latest = alerts[alerts["period"] == alerts["period"].max()]["message"].tolist() if not alerts.empty else []
    return MaterializeResult(metadata={"alerts": len(alerts), "high_severity": high,
                                       "latest_period_alerts": MetadataValue.md("\n".join(f"- {m}" for m in latest))})


# ------------------------------------------------------------------ jobs, schedules, sensors
all_assets = AssetSelection.all()
daily_refresh = define_asset_job("daily_incremental_refresh", selection=all_assets,
                                 config={"ops": {"gdc_cases_raw": {"config": {"mode": "incremental"}}}})
weekly_full = define_asset_job("weekly_full_reconciliation", selection=all_assets,
                               tags={"oncoinsight/full_refresh": "true"},
                               config={"ops": {"gdc_cases_raw": {"config": {"mode": "full"}}}})

schedules = [
    ScheduleDefinition(job=daily_refresh, cron_schedule="0 6 * * *", execution_timezone="UTC",
                       default_status=DefaultScheduleStatus.RUNNING),
    ScheduleDefinition(job=weekly_full, cron_schedule="0 3 * * 0", execution_timezone="UTC",
                       default_status=DefaultScheduleStatus.RUNNING),
]


@run_failure_sensor(monitored_jobs=[daily_refresh, weekly_full])
def notify_on_failure(context: RunFailureSensorContext) -> None:
    msg = f"OncoInsight pipeline run {context.dagster_run.run_id} ({context.dagster_run.job_name}) failed: " \
          f"{context.failure_event.message}"
    context.log.error(msg)
    url = os.getenv("ONCO_ALERT_WEBHOOK_URL")
    if url:
        import httpx

        httpx.post(url, json={"text": msg}, timeout=10)


defs = Definitions(
    assets=[gdc_cases_raw, cbioportal_raw, fhir_bulk_export, raw_fhir_tables, raw_registry_tables, oncoinsight_dbt,
            analytics_results, kpi_alerts],
    jobs=[daily_refresh, weekly_full],
    schedules=schedules,
    sensors=[notify_on_failure],
    resources={"dbt": DbtCliResource(project_dir=dbt_project, profiles_dir=str(DBT_PROJECT_DIR))},
)
