# `tests/integration/`: tests against a built warehouse

[← tests](../README.md)

`test_warehouse.py` runs when a built warehouse is reachable (local Docker stack or the CI Postgres service) and
skips otherwise. It checks every REST endpoint, the live cohort comparison, API-key enforcement, that the read-only
role **cannot** read raw tables or write, and that patient-level costs reconcile with cost lines.
