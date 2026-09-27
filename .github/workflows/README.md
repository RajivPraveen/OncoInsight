# `.github/workflows/`: continuous integration

[← back to project README](../../README.md)

`ci.yml` runs on every push to `main` and on every pull request:

| Job | What it proves |
|---|---|
| `lint-and-unit` | `ruff` passes, and all unit tests pass without a database |
| `pipeline-integration` | The **entire pipeline works end to end offline** on the committed real-data fixtures against a fresh Postgres 16 service: create roles → stage fixtures → FHIR build + validation → quality gate → incremental load → `dbt seed` + `dbt build` (models + tests) → analytics → KPI monitor → API / role / reconciliation integration tests. It uploads the dbt docs artifacts |
| `docker-build` | The production image builds (with a GitHub Actions layer cache) |
| `terraform` | `terraform fmt -check` and `terraform validate` pass |
