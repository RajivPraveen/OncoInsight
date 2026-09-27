# OncoInsight developer commands. `make help` lists them.
.DEFAULT_GOAL := help
DBT = cd dbt/oncoinsight && uv run --project ../.. dbt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python deps and pre-commit hooks
	uv sync && cp -n .env.example .env || true
	uv run pre-commit install || true

up: ## Start Postgres + S3 (SeaweedFS)
	docker compose up -d postgres s3

pipeline: ## Full pipeline on live public data (extract -> FHIR -> GX -> load -> dbt -> analytics -> alerts)
	uv run python -m oncoinsight.pipeline all

incremental: ## Incremental refresh (GDC watermark)
	uv run python -m oncoinsight.pipeline all --mode incremental

offline: ## Pipeline on committed real-data fixtures (no network)
	uv run python scripts/load_fixtures.py && uv run python -m oncoinsight.pipeline all --skip-extract

dbt: ## dbt build (models + tests)
	$(DBT) build --profiles-dir .

docs: ## Generate dbt docs + data dictionary
	$(DBT) docs generate --profiles-dir . && cd ../.. && uv run python scripts/gen_data_dictionary.py

dashboard: ## Run the Streamlit dashboard on :8503
	uv run streamlit run app/Home.py --server.port 8503

api: ## Run the FastAPI service on :8011
	uv run uvicorn oncoinsight.api.main:app --port 8011 --reload

stack: ## Build and start the full containerised stack (Dagster :3001, API :8010, dashboard :8502)
	docker compose up -d --build

test: ## Unit + integration tests
	uv run pytest -o addopts="" -q

lint: ## Ruff lint
	uv run ruff check .

readme-assets: ## Regenerate README charts and dashboard screenshots
	uv run python scripts/make_readme_assets.py

powerbi: ## Export Power BI model tables to Parquet
	uv run python scripts/export_powerbi.py

clean: ## Remove build artefacts
	rm -rf dbt/oncoinsight/target dbt/oncoinsight/logs .pytest_cache .ruff_cache
