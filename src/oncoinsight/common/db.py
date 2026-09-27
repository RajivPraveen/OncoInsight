"""Warehouse connection helpers and the operational (``ops``) schema used for run logging,
watermarks, and data-quality results."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from oncoinsight.common.config import Settings, get_settings

OPS_DDL = """
create schema if not exists raw;
create schema if not exists ops;
create schema if not exists analytics;

create table if not exists ops.pipeline_runs (
    run_id        text primary key,
    pipeline      text not null,
    status        text not null,
    started_at    timestamptz not null,
    finished_at   timestamptz,
    rows_in       integer,
    rows_changed  integer,
    details       jsonb
);

create table if not exists ops.ingestion_watermarks (
    source        text primary key,
    watermark     text not null,
    updated_at    timestamptz not null default now()
);

create table if not exists ops.dq_results (
    run_id        text not null,
    checked_at    timestamptz not null,
    dataset       text not null,
    expectation   text not null,
    column_name   text,
    severity      text not null,
    success       boolean not null,
    observed      jsonb,
    primary key (run_id, dataset, expectation, column_name)
);

create table if not exists ops.kpi_alerts (
    alert_id      text primary key,
    detected_at   timestamptz not null,
    kpi           text not null,
    entity_type   text not null,
    entity        text not null,
    period        text not null,
    current_value double precision,
    baseline_value double precision,
    pct_change    double precision,
    robust_z      double precision,
    n_current     integer,
    severity      text not null,
    message       text not null
);
"""


def engine(settings: Settings | None = None, readonly: bool = False) -> Engine:
    s = settings or get_settings()
    return create_engine(s.sqlalchemy_url(readonly), pool_pre_ping=True)


@contextlib.contextmanager
def connect(settings: Settings | None = None, readonly: bool = False) -> Iterator[psycopg.Connection]:
    s = settings or get_settings()
    with psycopg.connect(s.dsn(readonly), autocommit=False) as conn:
        yield conn


def ensure_ops_schema(settings: Settings | None = None) -> None:
    with connect(settings) as conn:
        conn.execute(OPS_DDL)
        conn.commit()


def _decimals_to_float(df: pd.DataFrame) -> pd.DataFrame:
    """Postgres NUMERIC arrives as decimal.Decimal objects; convert those columns to float64."""
    for col in df.columns[df.dtypes == "object"]:
        first = df[col].dropna()
        if not first.empty and isinstance(first.iloc[0], Decimal):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


def read_sql(sql: str, params: dict | None = None, settings: Settings | None = None, readonly: bool = False) -> pd.DataFrame:
    with engine(settings, readonly).connect() as c:
        return _decimals_to_float(pd.read_sql_query(sql, c, params=params))


def write_frame(df: pd.DataFrame, table: str, schema: str = "analytics", settings: Settings | None = None) -> int:
    """Replace an analytics output table atomically (Python-produced results such as KM curves)."""
    eng = engine(settings)
    with eng.begin() as c:
        df.to_sql(table, c, schema=schema, if_exists="replace", index=False, method="multi", chunksize=2000)
    return len(df)


def log_run(run_id: str, pipeline: str, status: str, started_at: datetime, rows_in: int | None = None,
            rows_changed: int | None = None, details: dict | None = None, settings: Settings | None = None) -> None:
    with connect(settings) as conn:
        conn.execute(
            """insert into ops.pipeline_runs (run_id, pipeline, status, started_at, finished_at, rows_in, rows_changed, details)
               values (%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (run_id) do update set status=excluded.status, finished_at=excluded.finished_at,
                 rows_in=excluded.rows_in, rows_changed=excluded.rows_changed, details=excluded.details""",
            (run_id, pipeline, status, started_at, datetime.now(UTC), rows_in, rows_changed,
             json.dumps(details or {}, default=str)),
        )
        conn.commit()


def get_watermark(source: str, settings: Settings | None = None) -> str | None:
    with connect(settings) as conn:
        row = conn.execute("select watermark from ops.ingestion_watermarks where source=%s", (source,)).fetchone()
        return row[0] if row else None


def set_watermark(source: str, watermark: str, settings: Settings | None = None) -> None:
    with connect(settings) as conn:
        conn.execute(
            """insert into ops.ingestion_watermarks (source, watermark, updated_at) values (%s,%s,now())
               on conflict (source) do update set watermark=excluded.watermark, updated_at=now()""",
            (source, watermark),
        )
        conn.commit()
