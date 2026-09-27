"""OncoInsight REST API (FastAPI). Serves curated marts and analytics results over the read-only role.

Run: ``uvicorn oncoinsight.api.main:app --port 8010`` - interactive docs at /docs.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from oncoinsight import __version__
from oncoinsight.assistant.semantic import MetricRequest, SemanticError, all_metrics, load_layer, run_metric
from oncoinsight.common.config import get_settings
from oncoinsight.common.db import read_sql
from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="OncoInsight API",
    version=__version__,
    description="Breast cancer treatment pathways & outcomes analytics on real public data (TCGA-BRCA, METABRIC). "
                "De-identified research data; observational associations only; not for clinical decision-making.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_and_audit(request: Request, call_next):
    """Optional API-key auth (ONCO_API_KEY) + request id + structured access log with latency."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    expected = get_settings().api_key
    if expected is not None and expected.get_secret_value() and request.url.path not in OPEN_PATHS:
        supplied = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(supplied, expected.get_secret_value()):
            return JSONResponse({"detail": "invalid or missing X-API-Key"}, status_code=401,
                                headers={"x-request-id": request_id})
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["x-request-id"] = request_id
    log.info("api_request", method=request.method, path=request.url.path, status=response.status_code,
             duration_ms=ms, request_id=request_id)
    return response


def q(sql: str, params: dict | None = None) -> list[dict]:
    df = read_sql(sql, params, readonly=True)
    return json.loads(df.to_json(orient="records", date_format="iso"))


# ------------------------------------------------------------------ health / ops
@app.get("/health", tags=["ops"])
def health() -> dict:
    try:
        n = q("select count(*) as n from marts.mart_patient_360")[0]["n"]
        return {"status": "ok", "patients": n, "version": __version__}
    except Exception as exc:
        raise HTTPException(503, f"warehouse unavailable: {exc}") from exc


@app.get("/pipeline/runs", tags=["ops"])
def pipeline_runs(limit: int = Query(20, le=200)) -> list[dict]:
    return q("select run_id, pipeline, status, started_at, finished_at, rows_in, rows_changed from ops.pipeline_runs "
             "order by started_at desc limit %(limit)s", {"limit": limit})


@app.get("/data-quality", tags=["ops"])
def data_quality() -> list[dict]:
    return q("""select distinct on (dataset, expectation, column_name) dataset, expectation, column_name, severity,
                success, observed, checked_at from ops.dq_results
                order by dataset, expectation, column_name, checked_at desc""")


# ------------------------------------------------------------------ KPIs & alerts
@app.get("/kpis/summary", tags=["kpis"])
def kpi_summary() -> dict:
    row = q("""select count(*) as patients, count(distinct hospital_id) as sites,
                  round(avg(received_chemotherapy::int) * 100, 1) as pct_chemotherapy,
                  percentile_cont(0.5) within group (order by days_to_chemotherapy)
                      filter (where days_to_chemotherapy between 0 and 730) as median_days_to_chemotherapy,
                  round(100.0 * avg(chemo_delayed_over_90d::int) filter (where days_to_chemotherapy between 0 and 730), 1) as pct_chemo_over_90d,
                  round(100.0 * avg(os_event), 1) as crude_mortality_pct,
                  round(100.0 * avg(any_progression_or_recurrence::int), 1) as crude_recurrence_pct,
                  round(avg(total_estimated_cost_usd)) as mean_estimated_cost_usd
               from marts.mart_patient_360""")[0]
    row["open_high_alerts"] = q("select count(*) as n from ops.kpi_alerts where severity = 'high'")[0]["n"]
    return row


@app.get("/kpis/annual", tags=["kpis"])
def kpis_annual(entity: str = "All sites") -> list[dict]:
    return q("select * from marts.mart_kpi_annual where entity = %(e)s order by year_of_diagnosis", {"e": entity})


@app.get("/alerts", tags=["kpis"])
def alerts(severity: Literal["high", "medium"] | None = None, period: str | None = None,
           limit: int = Query(100, le=1000)) -> list[dict]:
    sql = "select * from ops.kpi_alerts where true"
    params: dict = {"limit": limit}
    if severity:
        sql += " and severity = %(sev)s"
        params["sev"] = severity
    if period:
        sql += " and period = %(period)s"
        params["period"] = period
    return q(sql + " order by period desc, severity, abs(pct_change) desc limit %(limit)s", params)


# ------------------------------------------------------------------ pathways, delays, cost
@app.get("/pathways", tags=["pathways"])
def pathways() -> list[dict]:
    return q("select * from marts.mart_treatment_pathways order by n_patients desc")


@app.get("/pathways/transitions", tags=["pathways"])
def pathway_transitions(min_patients: int = 5) -> list[dict]:
    return q("select * from marts.mart_pathway_transitions where n_patients >= %(m)s order by source_step, n_patients desc",
             {"m": min_patients})


@app.get("/delays/hospitals", tags=["delays"])
def delays_by_hospital(interval: str = "Diagnosis → Chemotherapy") -> list[dict]:
    return q("select * from marts.mart_delay_by_hospital where interval_name = %(i)s and is_reportable "
             "order by median_days desc", {"i": interval})


@app.get("/delays/risk-adjusted", tags=["delays"])
def delays_risk_adjusted() -> list[dict]:
    return q("select * from analytics.hospital_risk_adjusted_delay order by oe_ratio desc")


@app.get("/delays/drivers", tags=["delays"])
def delay_drivers() -> list[dict]:
    return q("select model, term, estimate, ci_lower, ci_upper, p_value, n, estimate_type from analytics.delay_drivers")


@app.get("/costs", tags=["cost"])
def costs(dimension: str | None = None) -> list[dict]:
    if dimension:
        return q("select * from marts.mart_cost_analysis where dimension = %(d)s order by mean_cost_usd desc", {"d": dimension})
    return q("select * from marts.mart_cost_analysis order by dimension, mean_cost_usd desc")


# ------------------------------------------------------------------ outcomes
@app.get("/survival/km", tags=["outcomes"])
def km(cohort: Literal["TCGA-BRCA", "METABRIC"] = "TCGA-BRCA", endpoint: str = "OS",
       stratifier: str = "stage_major") -> dict:
    curves = q("select group_value, time_months, survival, ci_lower, ci_upper, at_risk from analytics.km_curves "
               "where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s order by group_value, time_months",
               {"c": cohort, "e": endpoint, "s": stratifier})
    if not curves:
        raise HTTPException(404, "no curves for that cohort/endpoint/stratifier")
    summary = q("select * from analytics.km_summary where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s",
                {"c": cohort, "e": endpoint, "s": stratifier})
    test = q("select * from analytics.logrank_tests where cohort=%(c)s and endpoint=%(e)s and stratifier=%(s)s",
             {"c": cohort, "e": endpoint, "s": stratifier})
    return {"curves": curves, "summary": summary, "logrank": test[0] if test else None}


class CohortSpec(BaseModel):
    label: str = "Cohort"
    stage_major: list[str] = []
    receptor_subtype: list[str] = []
    age_group: list[str] = []
    chemo_timing_group: list[str] = []
    pathway_group: list[str] = []
    received_chemotherapy: list[bool] = []
    received_radiation: list[bool] = []


class CompareRequest(BaseModel):
    a: CohortSpec
    b: CohortSpec
    endpoint: Literal["OS", "DSS", "PFI"] = "OS"
    horizon_months: int = Field(60, ge=12, le=180)


@app.post("/survival/compare", tags=["outcomes"])
def survival_compare(req: CompareRequest) -> dict:
    """Live Kaplan-Meier comparison of two cohorts: curves, 5-year survival, RMST difference and log-rank test."""
    from dataclasses import asdict

    from oncoinsight.analytics.cohorts import compare_cohorts, filter_frame

    cols = {"OS": ("os_months", "os_event"), "DSS": ("dss_months", "dss_event"), "PFI": ("pfs_months", "pfs_event")}
    t, e = cols[req.endpoint]
    surv = read_sql("select * from marts.mart_survival", readonly=True)
    fa = {k: v for k, v in req.a.model_dump().items() if k != "label"}
    fb = {k: v for k, v in req.b.model_dump().items() if k != "label"}
    comp = compare_cohorts(filter_frame(surv, fa), filter_frame(surv, fb), t, e, req.a.label, req.b.label,
                           req.horizon_months, req.endpoint)
    if comp.a.n < 11 or comp.b.n < 11:
        raise HTTPException(422, f"each cohort needs >= 11 patients (got {comp.a.n} and {comp.b.n})")
    return asdict(comp)


@app.get("/survival/cox", tags=["outcomes"])
def cox(model: str | None = None) -> dict:
    fits = q("select * from analytics.cox_model_fit")
    coefs = q("select * from analytics.cox_coefficients" + (" where model = %(m)s" if model else ""),
              {"m": model} if model else None)
    return {"models": fits, "coefficients": coefs}


@app.get("/recurrence/summary", tags=["outcomes"])
def recurrence_summary(factor: str | None = None) -> list[dict]:
    if factor:
        return q("select * from marts.mart_recurrence_summary where factor = %(f)s", {"f": factor})
    return q("select * from marts.mart_recurrence_summary order by factor, factor_value")


@app.get("/recurrence/models", tags=["outcomes"])
def recurrence_models() -> dict:
    return {"metrics": q("select * from analytics.recurrence_model_metrics"),
            "feature_importance": q("select * from analytics.recurrence_feature_importance order by importance_mean desc")}


class RecurrenceRiskInput(BaseModel):
    age_at_diagnosis: float = Field(..., ge=18, le=100)
    tumor_size_mm: float = Field(..., gt=0, le=200)
    tumor_grade: int = Field(..., ge=1, le=3)
    lymph_nodes_positive: int = Field(..., ge=0, le=60)
    receptor_subtype: Literal["HR+/HER2-", "HR+/HER2+", "HR-/HER2+", "Triple negative"]
    pam50_claudin_subtype: str | None = None
    menopausal_state: Literal["Pre", "Post"] | None = None
    breast_surgery: Literal["MASTECTOMY", "BREAST CONSERVING"] | None = None
    received_chemotherapy: bool = False
    received_hormone_therapy: bool = False
    received_radiotherapy: bool = False


@lru_cache
def _risk_model():
    import joblib

    path = get_settings().data_dir / "models" / "recurrence_5y_model.joblib"
    if not path.exists():
        raise HTTPException(503, "recurrence model not trained yet - run the analytics step")
    meta = json.loads(path.with_suffix(".json").read_text())
    return joblib.load(path), meta


@app.post("/predict/recurrence-risk", tags=["outcomes"])
def predict_recurrence(inp: RecurrenceRiskInput) -> dict:
    """Cohort-level 5-year relapse risk estimate from the METABRIC-trained model (demonstration only)."""
    model, meta = _risk_model()
    row = pd.DataFrame([inp.model_dump()])[meta["features"]]
    row[meta["binary"]] = row[meta["binary"]].astype(float)  # model was trained on 0/1 floats
    p = float(model.predict_proba(row)[0, 1])
    return {"five_year_relapse_probability": round(p, 3), "model": meta["model"],
            "holdout_roc_auc": round(meta["holdout_roc_auc"], 3), "training_cohort": meta["training_cohort"],
            "disclaimer": meta["intended_use"]}


# ------------------------------------------------------------------ equity & patients
@app.get("/disparities", tags=["equity"])
def disparities(group_type: str | None = None) -> dict:
    groups = q("select * from marts.mart_disparities" + (" where group_type = %(g)s" if group_type else "") +
               " order by group_type, n_patients desc", {"g": group_type} if group_type else None)
    return {"groups": [g for g in groups if g["n_patients"] >= load_layer()["small_cell_threshold"]],
            "tests": q("select * from analytics.disparity_tests order by p_value")}


@app.get("/patients/{barcode}", tags=["patients"])
def patient_360(barcode: str) -> dict:
    rows = q("select * from marts.mart_patient_360 where patient_barcode = %(b)s", {"b": barcode.upper()})
    if not rows:
        raise HTTPException(404, "patient not found")
    return rows[0]


# ------------------------------------------------------------------ semantic layer & assistant
@app.get("/metrics", tags=["semantic layer"])
def list_metrics() -> dict:
    layer = load_layer()
    return {name: {"table": m["table"], "dimensions": list(m["dimensions"]), "metrics":
                   {k: v["description"] for k, v in m["metrics"].items()}} for name, m in layer["models"].items()}


@app.post("/metrics/query", tags=["semantic layer"])
def query_metric(req: MetricRequest) -> dict:
    try:
        compiled, rows = run_metric(req)
    except SemanticError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"metric": req.metric, "description": compiled.description, "sql": compiled.sql, "rows": rows,
            "available_metrics": None if rows else all_metrics()}


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


@app.post("/assistant/ask", tags=["assistant"])
def assistant_ask(req: AskRequest) -> dict:
    from oncoinsight.assistant.agent import ask

    try:
        a = ask(req.question)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"answer": a.answer, "model": a.model, "stop_reason": a.stop_reason, "usage": a.usage,
            "queries": [q.__dict__ for q in a.queries]}
