"""Pre-load data-quality gate built on Great Expectations (GX Core 1.x).

Every raw frame is validated BEFORE it is written to the warehouse. Expectations are tagged:
* ``critical`` - schema / key / domain violations that would corrupt downstream models. Any failure
  raises :class:`DataQualityError` and the load for that run is aborted.
* ``warning``  - plausibility checks (e.g. treatment end before start). Failures are recorded in
  ``ops.dq_results`` and surfaced on the dashboard, but do not block the pipeline.

Cross-table referential integrity is enforced after load by dbt ``relationships`` tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd
import polars as pl

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

FHIR_EVENT_STATUS = ["completed", "in-progress", "not-done", "unknown", "active", "not-taken", "stopped",
                     "on-hold", "entered-in-error", "intended", "preparation"]
MODALITIES = ["surgery", "radiation", "chemotherapy", "hormone_therapy", "targeted_therapy", "immunotherapy",
              "bisphosphonate", "ancillary", "pharmaceutical_nos"]
STAGES = ["Stage 0", "Stage I", "Stage IA", "Stage IB", "Stage II", "Stage IIA", "Stage IIB", "Stage III",
          "Stage IIIA", "Stage IIIB", "Stage IIIC", "Stage IV", "Stage X"]


class DataQualityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Check:
    expectation: gxe.Expectation
    severity: str  # critical | warning


def _c(e: gxe.Expectation) -> Check:
    return Check(e, "critical")


def _w(e: gxe.Expectation) -> Check:
    return Check(e, "warning")


def _key_checks(key: str = "id") -> list[Check]:
    return [_c(gxe.ExpectColumnValuesToNotBeNull(column=key)), _c(gxe.ExpectColumnValuesToBeUnique(column=key)),
            _c(gxe.ExpectColumnValuesToNotBeNull(column="record_hash"))]


def _treatment_checks() -> list[Check]:
    return [
        *_key_checks(),
        _c(gxe.ExpectColumnValuesToNotBeNull(column="patient_id")),
        _c(gxe.ExpectColumnValuesToBeInSet(column="status", value_set=FHIR_EVENT_STATUS)),
        _c(gxe.ExpectColumnValuesToBeInSet(column="modality", value_set=MODALITIES)),
        _w(gxe.ExpectColumnPairValuesAToBeGreaterThanB(column_A="days_to_treatment_end", column_B="days_to_treatment_start",
                                                       or_equal=True, ignore_row_if="either_value_is_missing")),
        _w(gxe.ExpectColumnValuesToBeBetween(column="days_to_treatment_start", min_value=-3650, max_value=7300)),
    ]


SUITES: dict[str, list[Check]] = {
    "fhir_patient": [
        *_key_checks(),
        _c(gxe.ExpectColumnValuesToNotBeNull(column="gdc_barcode")),
        _c(gxe.ExpectColumnValuesToMatchRegex(column="gdc_barcode", regex=r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}$")),
        _c(gxe.ExpectColumnValuesToBeInSet(column="gender", value_set=["female", "male", "unknown"])),
        _w(gxe.ExpectColumnValuesToBeInSet(column="vital_status", value_set=["Alive", "Dead"])),
        _w(gxe.ExpectColumnValuesToBeBetween(column="age_at_diagnosis_years", min_value=18, max_value=90)),
        _w(gxe.ExpectColumnValuesToBeBetween(column="days_to_death", min_value=0, max_value=15000)),
        _w(gxe.ExpectTableRowCountToBeBetween(min_value=900, max_value=5000)),
    ],
    "fhir_organization": [*_key_checks(), _c(gxe.ExpectColumnValuesToNotBeNull(column="name"))],
    "fhir_condition": [
        *_key_checks(),
        _c(gxe.ExpectColumnValuesToNotBeNull(column="patient_id")),
        _w(gxe.ExpectColumnValuesToMatchRegex(column="icd10_code", regex=r"^(C50|D05)")),
        _w(gxe.ExpectColumnValuesToBeInSet(column="stage_group", value_set=STAGES)),
        _w(gxe.ExpectColumnValuesToBeBetween(column="year_of_diagnosis", min_value=1970, max_value=2030)),
    ],
    "fhir_observation": [
        *_key_checks(),
        _c(gxe.ExpectColumnValuesToNotBeNull(column="patient_id")),
        _c(gxe.ExpectColumnValuesToNotBeNull(column="code")),
        _w(gxe.ExpectColumnValuesToBeInSet(column="biomarker", value_set=["ER", "PR", "HER2"])),
        _w(gxe.ExpectColumnValuesToBeBetween(column="value_integer", min_value=0, max_value=100)),
    ],
    "fhir_procedure": [*_treatment_checks(),
                       _w(gxe.ExpectColumnValuesToBeBetween(column="number_of_fractions", min_value=1, max_value=60))],
    "fhir_medication": [*_treatment_checks(),
                        _c(gxe.ExpectColumnValuesToBeInSet(column="fhir_resource_type",
                                                           value_set=["MedicationAdministration", "MedicationStatement"]))],
    "fhir_encounter": [*_key_checks(), _c(gxe.ExpectColumnValuesToNotBeNull(column="patient_id")),
                       _w(gxe.ExpectColumnValuesToBeBetween(column="days_from_diagnosis", min_value=-365, max_value=10000))],
    "cbio_brca_tcga_pan_can_atlas_2018_patient": [
        *_key_checks(), _c(gxe.ExpectColumnValuesToBeUnique(column="patient_id")),
        _c(gxe.ExpectColumnToExist(column="os_months")), _c(gxe.ExpectColumnToExist(column="os_status")),
        _w(gxe.ExpectColumnValuesToMatchRegex(column="os_status", regex=r"^[01]:")),
    ],
    "cbio_brca_metabric_patient": [
        *_key_checks(), _c(gxe.ExpectColumnValuesToBeUnique(column="patient_id")),
        _c(gxe.ExpectColumnToExist(column="os_months")), _c(gxe.ExpectColumnToExist(column="rfs_status")),
        _w(gxe.ExpectColumnValuesToMatchRegex(column="rfs_status", regex=r"^[01]:")),
        _w(gxe.ExpectTableRowCountToBeBetween(min_value=2000, max_value=3000)),
    ],
    "cbio_brca_tcga_pan_can_atlas_2018_sample": [*_key_checks("id")],
    "cbio_brca_metabric_sample": [*_key_checks("id")],
}


@dataclass
class DQResult:
    dataset: str
    expectation: str
    column: str | None
    severity: str
    success: bool
    observed: dict


def validate_frame(name: str, df: pl.DataFrame, context: gx.AbstractDataContext | None = None) -> list[DQResult]:
    checks = SUITES.get(name)
    if not checks:
        log.warning("no_expectation_suite", dataset=name)
        return []
    ctx = context or gx.get_context(mode="ephemeral")
    pdf: pd.DataFrame = df.drop([c for c in ("resource",) if c in df.columns]).to_pandas()
    source = ctx.data_sources.add_or_update_pandas(name=f"src_{name}")
    asset = source.add_dataframe_asset(name=name)
    batch = asset.add_batch_definition_whole_dataframe(f"{name}_batch").get_batch(batch_parameters={"dataframe": pdf})

    results: list[DQResult] = []
    for chk in checks:
        exp = chk.expectation
        r = batch.validate(exp)
        col = getattr(exp, "column", None) or getattr(exp, "column_A", None)
        observed = {k: v for k, v in (r.result or {}).items()
                    if k in ("element_count", "unexpected_count", "unexpected_percent", "observed_value",
                             "partial_unexpected_list", "missing_count")}
        results.append(DQResult(name, exp.expectation_type, col, chk.severity, bool(r.success),
                                json.loads(json.dumps(observed, default=str))))
    return results


def enforce(results: list[DQResult]) -> None:
    failed = [r for r in results if r.severity == "critical" and not r.success]
    for r in results:
        if not r.success:
            (log.error if r.severity == "critical" else log.warning)(
                "dq_expectation_failed", dataset=r.dataset, expectation=r.expectation, column=r.column,
                severity=r.severity, observed=r.observed)
    if failed:
        summary = ", ".join(f"{r.dataset}.{r.column}:{r.expectation}" for r in failed)
        raise DataQualityError(f"{len(failed)} critical expectation(s) failed: {summary}")


def persist_results(run_id: str, results: list[DQResult], settings=None) -> None:
    from oncoinsight.common.db import connect

    now = datetime.now(UTC)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """insert into ops.dq_results (run_id, checked_at, dataset, expectation, column_name, severity, success, observed)
                   values (%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (run_id, dataset, expectation, column_name) do update
                   set success=excluded.success, observed=excluded.observed, checked_at=excluded.checked_at""",
                [(run_id, now, r.dataset, r.expectation, r.column or "", r.severity, r.success, json.dumps(r.observed))
                 for r in results])
        conn.commit()
