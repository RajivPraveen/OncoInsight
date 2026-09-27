# One image for every Python service (Dagster webserver/daemon, API, dashboard, pipeline CLI).
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" DAGSTER_HOME=/opt/dagster/home

# libgomp1: OpenMP runtime for XGBoost; curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY dagster_project ./dagster_project
COPY dbt ./dbt
COPY app ./app
COPY scripts ./scripts
COPY tests/fixtures ./tests/fixtures
RUN uv sync --frozen --no-dev

# pre-build the dbt manifest so Dagster can load dbt assets without a warehouse connection
RUN cd dbt/oncoinsight && dbt parse --profiles-dir . --target dev >/dev/null
COPY docker/dagster /opt/dagster/home

RUN useradd --create-home --uid 1000 onco && mkdir -p /app/data && chown -R onco /app /opt/dagster/home
USER onco
EXPOSE 3000 8000 8501
CMD ["python", "-m", "oncoinsight.pipeline", "all"]
