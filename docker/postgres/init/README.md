# `docker/postgres/init/`: warehouse bootstrap

[← docker](../../README.md)

`01_roles.sh` runs once when the Postgres volume is first created (and in CI). It:

1. creates the `dagster` database for orchestration metadata;
2. creates the curated schemas (`raw`, `ops`, `analytics`, `marts`);
3. creates the **`onco_reader`** role used by the API, dashboard, Power BI and AI assistant. The role is read-only by
   default, has a 30 s statement timeout, and has `SELECT` via default privileges on curated schemas only (never raw
   or staging).
