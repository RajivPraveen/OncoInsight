# `scripts/`: developer utilities

[← back to project README](../README.md)

| Script | Purpose | Command |
|---|---|---|
| `make_fixtures.py` | Build the deterministic real-data test sample from the latest full extract | `uv run python scripts/make_fixtures.py` |
| `load_fixtures.py` | Stage fixtures into the raw store for an offline run (used by CI) | `make offline` |
| `make_readme_assets.py` | Render README charts with the dashboard's own figure factories (kaleido) and capture real dashboard screenshots (Playwright + local Chrome) into `docs/images/` | `make readme-assets` |
| `gen_data_dictionary.py` | Generate `docs/data_dictionary.md` from the live warehouse columns and dbt descriptions | `make docs` |
| `export_powerbi.py` | Export the Power BI model tables to Parquet for offline report building | `make powerbi` |
