# `docker/dagster/`: Dagster instance configuration

[← docker](../README.md)

- `dagster.yaml`: run, event and schedule storage in the Postgres `dagster` database (shared by the webserver and the
  daemon), a queued run coordinator (max 2 concurrent runs), and telemetry disabled.
- `workspace.yaml`: loads the code location from `dagster_project.definitions`.
