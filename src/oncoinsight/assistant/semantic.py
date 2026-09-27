"""Compile governed metric requests (metric + dimensions + filters) into parameterised SQL."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

LAYER_PATH = Path(__file__).with_name("semantic_layer.yml")
OPERATORS = {"=": "=", "!=": "<>", ">": ">", ">=": ">=", "<": "<", "<=": "<=", "in": "in", "not in": "not in"}


class MetricFilter(BaseModel):
    dimension: str
    operator: str = Field("=", description="One of =, !=, >, >=, <, <=, in, not in")
    value: str | int | float | bool | list[str | int | float | bool]


class MetricRequest(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: list[MetricFilter] = Field(default_factory=list)
    order_by_metric_desc: bool = True
    limit: int = 100


@dataclass
class CompiledQuery:
    sql: str
    params: dict = field(default_factory=dict)
    model: str = ""
    description: str = ""


class SemanticError(ValueError):
    pass


@lru_cache
def load_layer() -> dict:
    return yaml.safe_load(LAYER_PATH.read_text())


def find_metric(metric: str) -> tuple[str, dict, dict]:
    for model_name, model in load_layer()["models"].items():
        if metric in model["metrics"]:
            return model_name, model, model["metrics"][metric]
    raise SemanticError(f"Unknown metric '{metric}'. Available: {', '.join(all_metrics())}")


def all_metrics() -> list[str]:
    return [m for model in load_layer()["models"].values() for m in model["metrics"]]


def compile_metric(req: MetricRequest) -> CompiledQuery:
    model_name, model, metric = find_metric(req.metric)
    allowed = model["dimensions"]
    for d in [*req.dimensions, *(f.dimension for f in req.filters)]:
        if d not in allowed:
            raise SemanticError(f"Dimension '{d}' is not available for metric '{req.metric}' (model {model_name}). "
                                f"Allowed: {', '.join(allowed)}")
    if len(req.dimensions) > 3:
        raise SemanticError("At most 3 dimensions per query")

    params: dict = {}
    where = []
    for i, f in enumerate(req.filters):
        op = OPERATORS.get(f.operator.lower())
        if not op:
            raise SemanticError(f"Unsupported operator '{f.operator}'")
        col = f'"{f.dimension}"'
        if op in ("in", "not in"):
            values = f.value if isinstance(f.value, list) else [f.value]
            names = []
            for j, v in enumerate(values):
                params[f"f{i}_{j}"] = v
                names.append(f"%(f{i}_{j})s")
            where.append(f"{col} {op} ({', '.join(names)})")
        else:
            params[f"f{i}"] = f.value
            where.append(f"{col} {op} %(f{i})s")

    dims = [f'"{d}"' for d in req.dimensions]
    n_expr = metric.get("n_expression", model["count_expression"])
    select = [*dims, f"{metric['expression']} as value", f"{n_expr} as n"]
    sql = f"select {', '.join(select)} from {model['table']}"
    if where:
        sql += " where " + " and ".join(where)
    if dims:
        sql += " group by " + ", ".join(dims)
        sql += f" order by value {'desc' if req.order_by_metric_desc else 'asc'} nulls last"
    sql += f" limit {max(1, min(int(req.limit), 500))}"
    return CompiledQuery(sql=sql, params=params, model=model_name, description=metric["description"])


def run_metric(req: MetricRequest, settings=None) -> tuple[CompiledQuery, list[dict]]:
    """Execute a governed metric on the read-only role and apply small-cell suppression."""
    from oncoinsight.common.db import connect

    q = compile_metric(req)
    threshold = load_layer()["small_cell_threshold"]
    with connect(settings, readonly=True) as conn:
        cur = conn.execute(q.sql, q.params)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    for r in rows:
        v = r.get("value")
        r["value"] = float(v) if v is not None else None
        n = r.get("n")
        r["n"] = int(n) if n is not None else None
        if req.metric not in ("patients", "treated_patients", "new_diagnoses") and r["n"] is not None and r["n"] < threshold:
            r["value"] = None
            r["suppressed"] = f"n<{threshold}"
    return q, rows
