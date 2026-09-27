import pandas as pd
import pytest

from oncoinsight.common.storage import LocalRawStore, dumps_gz_ndjson, iter_gz_ndjson
from oncoinsight.monitoring.kpi_monitor import detect


def _kpis(values, n=30):
    years = range(2005, 2005 + len(values))
    return pd.DataFrame({"entity_type": "Hospital", "entity": "Hospital B", "year_of_diagnosis": list(years),
                         "median_days_to_chemotherapy": values, "n_timed_chemotherapy": n,
                         "pct_chemo_over_90d": 20.0, "median_days_to_radiation": 60.0, "radiation_patients": n,
                         "new_diagnoses": n, "mean_estimated_cost_usd": 15000.0})


def test_alert_fires_on_large_sustained_jump():
    alerts = detect(_kpis([19, 20, 19, 28]), pct_threshold=0.25, min_n=8)
    a = alerts[alerts.kpi == "median_days_to_chemotherapy"].iloc[0]
    assert a.period == "2008" and a.direction == "worse"
    assert a["pct_change"] == pytest.approx((28 - 19) / 19)
    assert "Hospital B" in a.message and "+47%" in a.message


def test_no_alert_below_threshold_or_small_n():
    assert detect(_kpis([19, 20, 19, 21]), 0.25, 8).empty
    assert detect(_kpis([19, 20, 19, 40], n=3), 0.25, 8).empty


def test_local_store_roundtrip_and_path_safety(tmp_path):
    store = LocalRawStore(tmp_path)
    store.put_bytes("a/b/x.ndjson.gz", dumps_gz_ndjson([{"id": 1}, {"id": 2}]))
    assert [r["id"] for r in iter_gz_ndjson(store.get_bytes("a/b/x.ndjson.gz"))] == [1, 2]
    assert store.list_keys("a") == ["a/b/x.ndjson.gz"]
    with pytest.raises(ValueError):
        store.put_bytes("../../escape.txt", b"x")
