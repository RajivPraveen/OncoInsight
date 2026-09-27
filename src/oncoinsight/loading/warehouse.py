"""Idempotent, incremental loads into the Postgres ``raw`` schema.

Each load COPYs a Polars frame into a temp table, then upserts on ``id``. A row is only rewritten (and
its ``_loaded_at`` bumped) when its ``record_hash`` changed, which is what dbt incremental models key on.
Full-refresh loads additionally soft-delete rows that disappeared from the source (``_is_deleted``)."""

from __future__ import annotations

import io
from dataclasses import dataclass

import polars as pl
from psycopg import sql

from oncoinsight.common.config import Settings
from oncoinsight.common.db import connect
from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

PG_TYPES = {pl.Int64: "bigint", pl.Int32: "integer", pl.Float64: "double precision", pl.Boolean: "boolean",
            pl.Utf8: "text", pl.String: "text"}
JSON_COLUMNS = {"resource"}


@dataclass
class LoadResult:
    table: str
    rows_in: int
    rows_changed: int
    rows_soft_deleted: int = 0


def _pg_type(col: str, dtype: pl.DataType) -> str:
    if col in JSON_COLUMNS:
        return "jsonb"
    return PG_TYPES.get(dtype.base_type() if hasattr(dtype, "base_type") else dtype, "text")


def _ensure_table(conn, schema: str, table: str, df: pl.DataFrame, key: str) -> None:
    cols = [sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL(_pg_type(c, t))) for c, t in df.schema.items()]
    conn.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(schema)))
    conn.execute(sql.SQL(
        "create table if not exists {}.{} ({}, _loaded_at timestamptz not null default now(), "
        "_is_deleted boolean not null default false, primary key ({}))"
    ).format(sql.Identifier(schema), sql.Identifier(table), sql.SQL(", ").join(cols), sql.Identifier(key)))
    # schema evolution: add any new source columns
    existing = {r[0] for r in conn.execute(
        "select column_name from information_schema.columns where table_schema=%s and table_name=%s", (schema, table))}
    for c, t in df.schema.items():
        if c not in existing:
            log.info("schema_evolution_add_column", table=f"{schema}.{table}", column=c)
            conn.execute(sql.SQL("alter table {}.{} add column {} {}").format(
                sql.Identifier(schema), sql.Identifier(table), sql.Identifier(c), sql.SQL(_pg_type(c, t))))


def upsert_frame(df: pl.DataFrame, table: str, schema: str = "raw", key: str = "id", full_refresh: bool = False,
                 scope_filter: tuple[str, str] | None = None, settings: Settings | None = None) -> LoadResult:
    """Upsert ``df`` into ``schema.table``.

    ``scope_filter`` (column, value) limits soft-deletes to one source partition, e.g. one cBioPortal study.
    """
    if df.is_empty():
        return LoadResult(table, 0, 0)
    if "record_hash" not in df.columns:
        raise ValueError("frames must carry a record_hash column for change detection")
    cols = df.columns
    buf = io.StringIO()
    df.write_csv(buf, include_header=False, null_value="\\N", quote_style="necessary")
    buf.seek(0)

    tgt = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
    updates = sql.SQL(", ").join(
        sql.SQL("{c} = excluded.{c}").format(c=sql.Identifier(c)) for c in cols if c != key)

    with connect(settings) as conn:
        _ensure_table(conn, schema, table, df, key)
        conn.execute(sql.SQL("create temp table _stage (like {} including defaults) on commit drop").format(tgt))
        with conn.cursor().copy(sql.SQL("copy _stage ({}) from stdin with (format csv, null '\\N')").format(col_list)) as cp:
            while chunk := buf.read(1 << 20):
                cp.write(chunk)
        changed = conn.execute(sql.SQL(
            "insert into {tgt} ({cols}) select {cols} from _stage "
            "on conflict ({key}) do update set {updates}, _loaded_at = now(), _is_deleted = false "
            "where {tgt}.record_hash is distinct from excluded.record_hash or {tgt}._is_deleted"
        ).format(tgt=tgt, cols=col_list, key=sql.Identifier(key), updates=updates)).rowcount
        deleted = 0
        if full_refresh:
            where = sql.SQL("")
            params: tuple = ()
            if scope_filter:
                where = sql.SQL(" and {} = %s").format(sql.Identifier(scope_filter[0]))
                params = (scope_filter[1],)
            deleted = conn.execute(sql.SQL(
                "update {tgt} t set _is_deleted = true, _loaded_at = now() where not t._is_deleted "
                "and not exists (select 1 from _stage s where s.{key} = t.{key})"
            ).format(tgt=tgt, key=sql.Identifier(key)) + where, params).rowcount
        conn.commit()
    log.info("upsert_complete", table=f"{schema}.{table}", rows_in=df.height, rows_changed=changed, soft_deleted=deleted)
    return LoadResult(table, df.height, changed, deleted)
