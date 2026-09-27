"""Runs every Python analytics module against the dbt marts and writes results to the ``analytics`` schema."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd

from oncoinsight.analytics import disparities, recurrence, survival
from oncoinsight.common.config import Settings, get_settings
from oncoinsight.common.db import ensure_ops_schema, log_run, read_sql, write_frame
from oncoinsight.common.logging import get_logger

log = get_logger(__name__)
logging.getLogger("lifelines").setLevel(logging.ERROR)


def load_inputs(s: Settings) -> dict[str, pd.DataFrame]:
    return {
        "tcga": read_sql("select * from marts.mart_survival", settings=s),
        "metabric": read_sql("select * from marts.mart_metabric_cohort", settings=s),
        "p360": read_sql("select * from marts.mart_patient_360", settings=s),
    }


def run_analytics(settings: Settings | None = None) -> dict[str, int]:
    s = settings or get_settings()
    ensure_ops_schema(s)
    started = datetime.now(UTC)
    data = load_inputs(s)
    outputs: dict[str, pd.DataFrame] = {}
    outputs.update(survival.run_km(data["tcga"], data["metabric"]))
    outputs.update(survival.run_cox(data["tcga"], data["metabric"]))
    outputs.update(recurrence.run_recurrence_models(data["metabric"], model_dir=s.data_dir / "models"))
    outputs.update(disparities.group_tests(data["p360"]))
    outputs["delay_drivers"] = disparities.delay_drivers(data["p360"])
    outputs["hospital_risk_adjusted_delay"] = disparities.hospital_risk_adjusted(data["p360"])

    written = {}
    for name, df in outputs.items():
        df = df.copy()
        df["computed_at"] = started
        written[name] = write_frame(df, name, schema="analytics", settings=s)
    log_run(f"analytics:{started:%Y%m%dT%H%M%S}", "analytics", "success", started, rows_in=len(data["p360"]),
            details=written, settings=s)
    log.info("analytics_complete", tables=written)
    _shutdown_worker_pools()
    return written


def _shutdown_worker_pools() -> None:
    """scikit-learn (n_jobs=-1) leaves a reusable loky process pool alive; terminate it so orchestrator step
    subprocesses (Dagster multiprocess executor) can exit."""
    from joblib.externals.loky import get_reusable_executor

    get_reusable_executor().shutdown(wait=True, kill_workers=True)


if __name__ == "__main__":
    run_analytics()
