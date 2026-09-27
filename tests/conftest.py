import os
from pathlib import Path

import pytest

from oncoinsight.common.storage import loads_gz_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def gdc_cases() -> list[dict]:
    return loads_gz_json((FIXTURES / "gdc_cases.json.gz").read_bytes())


@pytest.fixture(scope="session")
def metabric_patient_rows() -> list[dict]:
    return loads_gz_json((FIXTURES / "cbio_brca_metabric_patient.json.gz").read_bytes())


def warehouse_available() -> bool:
    if os.getenv("ONCO_SKIP_INTEGRATION") == "1":
        return False
    try:
        import psycopg

        from oncoinsight.common.config import get_settings

        with psycopg.connect(get_settings().dsn(), connect_timeout=2) as c:
            return c.execute("select to_regclass('marts.mart_patient_360')").fetchone()[0] is not None
    except Exception:
        return False
