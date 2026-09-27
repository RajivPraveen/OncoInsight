"""Central configuration. All settings come from environment variables (or a local .env file);
nothing secret is hardcoded. See .env.example for the full list."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- environment ---
    env: Literal["local", "ci", "docker", "prod"] = Field("local", alias="ONCO_ENV")
    data_dir: Path = Field(PROJECT_ROOT / "data", alias="ONCO_DATA_DIR")

    # --- raw storage (local filesystem or S3 / MinIO) ---
    storage_backend: Literal["local", "s3"] = Field("local", alias="ONCO_STORAGE_BACKEND")
    s3_bucket: str = Field("oncoinsight-raw", alias="ONCO_S3_BUCKET")
    s3_endpoint_url: str | None = Field(None, alias="ONCO_S3_ENDPOINT_URL")
    s3_region: str = Field("us-east-1", alias="AWS_REGION")

    # --- source APIs (all public, no credentials required) ---
    gdc_api_url: str = Field("https://api.gdc.cancer.gov", alias="GDC_API_URL")
    gdc_project_id: str = Field("TCGA-BRCA", alias="GDC_PROJECT_ID")
    cbioportal_api_url: str = Field("https://www.cbioportal.org/api", alias="CBIOPORTAL_API_URL")
    cbioportal_studies: list[str] = Field(
        default=["brca_tcga_pan_can_atlas_2018", "brca_metabric"], alias="CBIOPORTAL_STUDIES"
    )
    http_timeout_s: float = Field(120.0, alias="ONCO_HTTP_TIMEOUT_S")

    # --- warehouse ---
    pg_host: str = Field("localhost", alias="WAREHOUSE_HOST")
    pg_port: int = Field(5433, alias="WAREHOUSE_PORT")
    pg_db: str = Field("oncoinsight", alias="WAREHOUSE_DB")
    pg_user: str = Field("oncoinsight", alias="WAREHOUSE_USER")
    pg_password: SecretStr = Field(SecretStr("oncoinsight"), alias="WAREHOUSE_PASSWORD")
    # read-only role used by the API and the AI assistant
    pg_reader_user: str = Field("onco_reader", alias="WAREHOUSE_READER_USER")
    pg_reader_password: SecretStr = Field(SecretStr("onco_reader"), alias="WAREHOUSE_READER_PASSWORD")

    # --- API security (optional): when set, every endpoint except /health and docs requires X-API-Key ---
    api_key: SecretStr | None = Field(None, alias="ONCO_API_KEY")

    # --- AI assistant ---
    anthropic_api_key: SecretStr | None = Field(None, alias="ANTHROPIC_API_KEY")
    assistant_model: str = Field("claude-opus-5", alias="ONCO_ASSISTANT_MODEL")
    assistant_max_rows: int = Field(500, alias="ONCO_ASSISTANT_MAX_ROWS")

    # --- monitoring thresholds ---
    kpi_alert_pct_change: float = Field(0.25, alias="ONCO_KPI_ALERT_PCT_CHANGE")
    kpi_alert_min_n: int = Field(8, alias="ONCO_KPI_ALERT_MIN_N")

    def dsn(self, readonly: bool = False) -> str:
        user = self.pg_reader_user if readonly else self.pg_user
        pwd = (self.pg_reader_password if readonly else self.pg_password).get_secret_value()
        return f"postgresql://{user}:{pwd}@{self.pg_host}:{self.pg_port}/{self.pg_db}"

    def sqlalchemy_url(self, readonly: bool = False) -> str:
        return self.dsn(readonly).replace("postgresql://", "postgresql+psycopg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
