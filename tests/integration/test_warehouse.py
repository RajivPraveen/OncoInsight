"""Integration tests against a built warehouse (local docker stack or the CI Postgres service)."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import warehouse_available

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not warehouse_available(), reason="warehouse not built / not reachable")]


@pytest.fixture(scope="module")
def client():
    from oncoinsight.api.main import app

    return TestClient(app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["patients"] > 0


def test_core_endpoints(client):
    for path in ["/kpis/summary", "/pathways", "/pathways/transitions", "/delays/hospitals", "/costs",
                 "/survival/km?stratifier=stage_major", "/survival/cox", "/recurrence/summary", "/disparities",
                 "/alerts", "/data-quality", "/metrics", "/pipeline/runs"]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.text[:200])


def test_metric_query_endpoint(client):
    r = client.post("/metrics/query", json={"metric": "median_days_to_chemotherapy", "dimensions": ["stage_major"]})
    assert r.status_code == 200 and r.json()["rows"]


def test_reader_role_cannot_see_raw_or_write():
    import psycopg

    from oncoinsight.common.config import get_settings

    dsn = get_settings().dsn(readonly=True)
    with psycopg.connect(dsn) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select * from raw.fhir_patient limit 1")
    with psycopg.connect(dsn) as conn, pytest.raises(
            (psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege)):
        conn.execute("delete from marts.mart_patient_360")


def test_cost_lines_reconcile(client):
    from oncoinsight.common.db import read_sql

    d = read_sql("""select (select round(sum(total_estimated_cost_usd)::numeric, 0) from marts.mart_patient_360) a,
                           (select round(sum(estimated_amount_usd)::numeric, 0) from core.fact_estimated_cost) b""")
    assert float(d.a[0]) == pytest.approx(float(d.b[0]), abs=1)


def test_survival_compare_endpoint(client):
    r = client.post("/survival/compare", json={"a": {"label": "TNBC", "receptor_subtype": ["Triple negative"]},
                                               "b": {"label": "HR+/HER2-", "receptor_subtype": ["HR+/HER2-"]}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["a"]["n"] >= 11 and body["logrank_p"] is not None and "x-request-id" in r.headers


def test_api_key_enforced_when_configured(client, monkeypatch):
    from pydantic import SecretStr

    from oncoinsight.common import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "api_key", SecretStr("s3cret"))
    assert client.get("/pathways").status_code == 401
    assert client.get("/pathways", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert client.get("/health").status_code == 200  # health stays open for load balancers
