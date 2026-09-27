"""Pipeline steps shared by the CLI (``python -m oncoinsight.pipeline``) and the Dagster assets.

    extract (GDC, cBioPortal) -> raw JSON (local / S3)
      -> FHIR R4 mapping + schema validation -> FHIR NDJSON bulk files (raw store)
      -> Polars flatten -> Great Expectations gate -> incremental upsert into Postgres ``raw``
      -> dbt build (staging -> intermediate -> core star schema -> marts, with tests)
      -> Python analytics (survival, Cox, recurrence models, disparities) -> ``analytics`` schema
      -> KPI monitoring / alerts -> ``ops.kpi_alerts``
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from oncoinsight.common.config import PROJECT_ROOT, Settings, get_settings
from oncoinsight.common.db import ensure_ops_schema, get_watermark, log_run, set_watermark
from oncoinsight.common.logging import get_logger
from oncoinsight.common.storage import (
    dumps_gz_json,
    dumps_gz_ndjson,
    get_raw_store,
    iter_gz_ndjson,
    loads_gz_json,
)
from oncoinsight.fhir.flatten import flatten
from oncoinsight.fhir.gdc_to_fhir import map_cases
from oncoinsight.fhir.validate import validate_resources
from oncoinsight.ingestion import cbioportal, gdc
from oncoinsight.loading.cbioportal_transform import pivot_clinical
from oncoinsight.loading.warehouse import upsert_frame
from oncoinsight.quality.expectations import enforce, persist_results, validate_frame

log = get_logger(__name__)
logging.getLogger("great_expectations").setLevel(logging.ERROR)

DBT_DIR = PROJECT_ROOT / "dbt" / "oncoinsight"


def _latest_run_prefix(store, prefix: str) -> str:
    runs = sorted({k.split("run_id=")[1].split("/")[0] for k in store.list_keys(prefix) if "run_id=" in k})
    if not runs:
        raise FileNotFoundError(f"no extracted runs under {prefix}")
    return f"{prefix}/run_id={runs[-1]}"


# ------------------------------------------------------------------ extract
def extract_gdc(mode: str = "full", settings: Settings | None = None) -> gdc.ExtractManifest:
    s = settings or get_settings()
    since = get_watermark(gdc.SOURCE, s) if mode == "incremental" else None
    manifest = gdc.extract_cases(since=since, settings=s)
    return manifest


def extract_cbioportal(settings: Settings | None = None) -> list[gdc.ExtractManifest]:
    return cbioportal.extract_all(settings=settings)


# ------------------------------------------------------------------ FHIR
def build_fhir(run_id: str | None = None, settings: Settings | None = None) -> dict:
    """Map an extracted GDC run into FHIR R4 NDJSON bulk files (one file per resource type)."""
    s = settings or get_settings()
    store = get_raw_store(s)
    base = f"gdc/{s.gdc_project_id.lower()}/cases"
    prefix = f"{base}/run_id={run_id}" if run_id else _latest_run_prefix(store, base)
    run_id = prefix.split("run_id=")[1]
    cases: list[dict] = []
    for key in store.list_keys(prefix):
        if key.endswith(".json.gz") and "/part-" in key:
            cases.extend(loads_gz_json(store.get_bytes(key)))
    report = validate_resources(map_cases(cases))
    fhir_prefix = f"fhir/{s.gdc_project_id.lower()}/run_id={run_id}"
    for rtype, items in report.valid.items():
        store.put_bytes(f"{fhir_prefix}/{rtype}.ndjson.gz", dumps_gz_ndjson(items))
    if report.quarantined:
        store.put_bytes(f"quarantine/{fhir_prefix}/invalid.ndjson.gz", dumps_gz_ndjson(report.quarantined))
        log.warning("fhir_resources_quarantined", count=len(report.quarantined))
    summary = {"run_id": run_id, "cases": len(cases), "resources": report.counts,
               "quarantined": len(report.quarantined), "prefix": fhir_prefix}
    store.put_bytes(f"{fhir_prefix}/_manifest.json.gz", dumps_gz_json(summary))
    log.info("fhir_build_complete", **{k: v for k, v in summary.items() if k != "resources"}, resources=report.counts)
    return summary


# ------------------------------------------------------------------ load
def load_fhir(run_id: str | None = None, full_refresh: bool = True, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    store = get_raw_store(s)
    ensure_ops_schema(s)
    base = f"fhir/{s.gdc_project_id.lower()}"
    prefix = f"{base}/run_id={run_id}" if run_id else _latest_run_prefix(store, base)
    run_id = prefix.split("run_id=")[1]
    started = datetime.now(UTC)
    resources: dict[str, list[dict]] = {}
    for key in store.list_keys(prefix):
        if key.endswith(".ndjson.gz"):
            rtype = Path(key).name.split(".")[0]
            resources[rtype] = list(iter_gz_ndjson(store.get_bytes(key)))
    frames = flatten(resources, source_run_id=run_id)

    # Quality gate: validate every frame before anything is written.
    results = [r for name, df in frames.items() for r in validate_frame(name, df)]
    persist_results(run_id, results, s)
    try:
        enforce(results)
    except Exception as exc:
        log_run(f"load_fhir:{run_id}", "load_fhir", "failed_dq", started, details={"error": str(exc)}, settings=s)
        raise

    out = {}
    for name, df in frames.items():
        res = upsert_frame(df, name, full_refresh=full_refresh, settings=s)
        out[name] = res.__dict__
    changed = sum(v["rows_changed"] for v in out.values())
    log_run(f"load_fhir:{run_id}", "load_fhir", "success", started, rows_in=sum(v["rows_in"] for v in out.values()),
            rows_changed=changed, details=out, settings=s)
    # advance the incremental watermark only after a successful load
    manifest_key = f"gdc/{s.gdc_project_id.lower()}/cases/run_id={run_id}/_manifest.json.gz"
    if store.exists(manifest_key):
        m = loads_gz_json(store.get_bytes(manifest_key))
        if m.get("max_updated_datetime"):
            set_watermark(gdc.SOURCE, m["max_updated_datetime"], s)
    return out


def load_cbioportal(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    store = get_raw_store(s)
    ensure_ops_schema(s)
    out = {}
    for study in s.cbioportal_studies:
        prefix = _latest_run_prefix(store, f"cbioportal/{study}")
        run_id = prefix.split("run_id=")[1]
        started = datetime.now(UTC)
        frames = {}
        for level in ("patient", "sample"):
            rows = loads_gz_json(store.get_bytes(f"{prefix}/clinical_{level}.json.gz"))
            frames[f"cbio_{study}_{level}"] = pivot_clinical(rows, level, run_id)
        results = [r for name, df in frames.items() for r in validate_frame(name, df)]
        persist_results(run_id, results, s)
        enforce(results)
        for name, df in frames.items():
            out[name] = upsert_frame(df, name, full_refresh=True, settings=s).__dict__
        log_run(f"load_cbioportal:{study}:{run_id}", "load_cbioportal", "success", started,
                rows_in=sum(frames[n].height for n in frames), details={n: out[n] for n in frames}, settings=s)
    return out


# ------------------------------------------------------------------ dbt
def run_dbt(command: str = "build", select: str | None = None, full_refresh: bool = False) -> None:
    args = ["dbt", command, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if command in ("build", "run", "seed") and full_refresh:
        args.append("--full-refresh")
    if select:
        args += ["--select", select]
    log.info("dbt_invoke", args=" ".join(args))
    subprocess.run(args, check=True, cwd=DBT_DIR)


def run_all(mode: str = "full", skip_extract: bool = False) -> None:
    s = get_settings()
    ensure_ops_schema(s)
    if not skip_extract:
        extract_gdc(mode, s)
        extract_cbioportal(s)
    build_fhir(settings=s)
    load_fhir(full_refresh=(mode == "full"), settings=s)
    load_cbioportal(s)
    run_dbt("deps")
    run_dbt("build")
    from oncoinsight.analytics.run import run_analytics
    from oncoinsight.monitoring.kpi_monitor import run_monitoring

    run_analytics(s)
    run_monitoring(s)


def main() -> None:
    p = argparse.ArgumentParser(description="OncoInsight pipeline")
    p.add_argument("step", choices=["all", "extract", "fhir", "load", "dbt", "analytics", "monitor"])
    p.add_argument("--mode", choices=["full", "incremental"], default="full")
    p.add_argument("--skip-extract", action="store_true")
    a = p.parse_args()
    s = get_settings()
    if a.step == "all":
        run_all(a.mode, a.skip_extract)
    elif a.step == "extract":
        extract_gdc(a.mode, s)
        extract_cbioportal(s)
    elif a.step == "fhir":
        build_fhir(settings=s)
    elif a.step == "load":
        load_fhir(full_refresh=(a.mode == "full"), settings=s)
        load_cbioportal(s)
    elif a.step == "dbt":
        run_dbt("build")
    elif a.step == "analytics":
        from oncoinsight.analytics.run import run_analytics
        run_analytics(s)
    elif a.step == "monitor":
        from oncoinsight.monitoring.kpi_monitor import run_monitoring
        run_monitoring(s)


if __name__ == "__main__":
    pl.Config.set_tbl_rows(20)
    main()
