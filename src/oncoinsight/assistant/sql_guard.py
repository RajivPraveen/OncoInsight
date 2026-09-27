"""Validate LLM-written SQL before it touches the warehouse.

Defense in depth: (1) this static check - a single read-only SELECT over allow-listed curated tables, no
dangerous functions, bounded LIMIT; (2) execution on the ``onco_reader`` role, which is read-only
(default_transaction_read_only), has a 30 s statement timeout, and cannot see raw/staging schemas.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from oncoinsight.assistant.semantic import load_layer

BLOCKED_FUNCTIONS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import", "lo_export",
                     "dblink", "dblink_exec", "set_config", "pg_terminate_backend", "pg_cancel_backend",
                     "current_setting", "pg_stat_file", "copy"}
MAX_LIMIT = 500


class UnsafeSQLError(ValueError):
    pass


def allowed_tables() -> set[str]:
    return {t.lower() for t in load_layer()["tables_for_sql"]}


def validate_sql(sql: str, max_limit: int = MAX_LIMIT) -> str:
    """Return a normalised, LIMIT-bounded SQL string or raise UnsafeSQLError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSQLError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeSQLError("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeSQLError("Only SELECT queries are allowed")
    for node_type in (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command,
                      exp.Merge, exp.TruncateTable, exp.Grant):
        if tree.find(node_type) is not None:
            raise UnsafeSQLError(f"{node_type.__name__} statements are not allowed")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    allowed = allowed_tables()
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = (table.db or "").lower()
        if not schema and name in cte_names:
            continue
        full = f"{schema}.{name}" if schema else name
        if full not in allowed:
            raise UnsafeSQLError(f"Table '{full}' is not in the allow-list. Use schema-qualified curated tables: "
                                 + ", ".join(sorted(allowed)))

    for fn in tree.find_all(exp.Func):
        fname = (fn.sql_name() if not isinstance(fn, exp.Anonymous) else fn.name).lower()
        if fname in BLOCKED_FUNCTIONS:
            raise UnsafeSQLError(f"Function '{fname}' is not allowed")

    # enforce an outer LIMIT
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(max_limit)
    else:
        try:
            value = int(limit.expression.name)
        except (AttributeError, ValueError):
            value = max_limit + 1
        if value > max_limit:
            tree = tree.limit(max_limit)
    return tree.sql(dialect="postgres")
