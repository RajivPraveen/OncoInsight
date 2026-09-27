"""Generate docs/data_dictionary.md from the live warehouse + dbt manifest descriptions.

    uv run python scripts/gen_data_dictionary.py
"""

from __future__ import annotations

import json
from pathlib import Path

from oncoinsight.common.db import read_sql

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dbt" / "oncoinsight" / "target" / "manifest.json"
SCHEMAS = ["core", "marts", "analytics", "ops", "ref"]


def main() -> None:
    docs: dict[str, dict] = {}
    if MANIFEST.exists():
        for node in json.loads(MANIFEST.read_text())["nodes"].values():
            if node["resource_type"] in ("model", "seed"):
                docs[f"{node['schema']}.{node['name']}"] = {
                    "description": node.get("description", ""),
                    "columns": {c: v.get("description", "") for c, v in node.get("columns", {}).items()}}
    cols = read_sql("""select table_schema, table_name, column_name, data_type, ordinal_position
                       from information_schema.columns where table_schema = any(%(s)s)
                       order by table_schema, table_name, ordinal_position""", {"s": SCHEMAS})
    counts = read_sql("""select schemaname as table_schema, relname as table_name, n_live_tup as approx_rows
                         from pg_stat_user_tables where schemaname = any(%(s)s)""", {"s": SCHEMAS})
    rows = {(r.table_schema, r.table_name): r.approx_rows for r in counts.itertuples()}
    out = ["# Data dictionary", "",
           "Generated from the live warehouse (`scripts/gen_data_dictionary.py`) with dbt model descriptions. "
           "Grain and business rules for each metric are in [metric_definitions.md](metric_definitions.md).", ""]
    for schema in SCHEMAS:
        tables = cols[cols.table_schema == schema].table_name.unique()
        if not len(tables):
            continue
        out += [f"## `{schema}`", ""]
        for t in tables:
            meta = docs.get(f"{schema}.{t}", {})
            out += [f"### `{schema}.{t}`", ""]
            if meta.get("description"):
                out += [meta["description"].strip(), ""]
            out += [f"Approx. rows: {rows.get((schema, t), 'n/a'):,}" if isinstance(rows.get((schema, t)), int)
                    else "Approx. rows: n/a", "", "| Column | Type | Description |", "|---|---|---|"]
            for c in cols[(cols.table_schema == schema) & (cols.table_name == t)].itertuples():
                desc = meta.get("columns", {}).get(c.column_name, "").replace("|", "/").replace("\n", " ")
                out.append(f"| `{c.column_name}` | {c.data_type} | {desc} |")
            out.append("")
    (ROOT / "docs" / "data_dictionary.md").write_text("\n".join(out))
    print(f"wrote data dictionary for {cols.groupby(['table_schema', 'table_name']).ngroups} tables")


if __name__ == "__main__":
    main()
