# `tests/`: automated tests

[← back to project README](../README.md)

**48 tests** run with `make test`. Unit tests need no database; integration tests run automatically when a built
warehouse is reachable and skip cleanly otherwise (`ONCO_SKIP_INTEGRATION=1` forces the skip).

| File | Covers |
|---|---|
| `unit/test_fhir.py` | Every generated resource is valid R4B; invalid resources are quarantined; date anchoring; treatment classification; US Core race coding; not-given → `not-done`; LOINC biomarkers; flattening and order-independent hashing |
| `unit/test_quality_and_transform.py` | The GX gate passes clean data, **blocks** duplicate keys and bad domain values; cBioPortal long → wide pivot |
| `unit/test_assistant.py` | Parameterised semantic-layer SQL (injection-safe), undeclared dimensions rejected, SQL guard blocks DML / raw tables / `pg_sleep` / multi-statement, agent tool loop with a mocked model (prompt caching, refusal fallback, refusal handling) |
| `unit/test_monitoring_and_storage.py` | KPI alert fires on a +47% jump and not on small or noisy changes; raw-store round trip and path-traversal protection |
| `unit/test_cohorts_and_charts.py` | Cohort comparison detects real differences (RMST sign, log-rank), small cohorts not estimated, Sankey conserves patients, forest-plot significance colouring, lineage traversal, cohort filters, **cost simulator: unchanged scenario = $0** |
| `integration/test_warehouse.py` | Every API endpoint, live cohort comparison, API-key enforcement, the read-only role cannot read raw or write, cost reconciliation |
| [`fixtures/`](fixtures/) | Real-data sample used by unit tests and the offline CI pipeline |
