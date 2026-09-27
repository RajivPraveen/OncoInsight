# `macros`: reusable SQL

[← dbt project](../README.md)

| File | Macros |
|---|---|
| `generate_schema_name.sql` | Uses custom schema names verbatim (`stg`, `int`, `core`, `marts`, `ref`) instead of dbt's `<target>_<custom>` prefixing |
| `helpers.sql` | `safe_numeric` (casts registry text, nulls tokens like `[Not Available]`), `status_event` (`"1:DECEASED"` → 1), `stage_major`, `age_group`, `incremental_loaded_at` (incremental filter on `_loaded_at`), `grant_reader_usage` (idempotent grants for the read-only role) |
| `generic_tests.sql` | In-repo generic tests: `expression_is_true`, `non_negative`, `within_range`, `row_count_between` (no dbt_utils dependency, so builds work offline) |
