"""Stage the committed fixtures into the raw store as if they were an extraction run (offline CI / demos).

    uv run python scripts/load_fixtures.py && uv run python -m oncoinsight.pipeline all --skip-extract
"""

from __future__ import annotations

from pathlib import Path

from oncoinsight.common.config import get_settings
from oncoinsight.common.storage import dumps_gz_json, get_raw_store, loads_gz_json

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
RUN_ID = "20000101T000000Z-fixture"


def main() -> None:
    s = get_settings()
    store = get_raw_store(s)
    cases = loads_gz_json((FIXTURES / "gdc_cases.json.gz").read_bytes())
    base = f"gdc/{s.gdc_project_id.lower()}/cases/run_id={RUN_ID}"
    store.put_bytes(f"{base}/part-0000.json.gz", dumps_gz_json(cases))
    store.put_bytes(f"{base}/_manifest.json.gz", dumps_gz_json({"source": "fixture", "run_id": RUN_ID,
                                                                "record_count": len(cases)}))
    for study in s.cbioportal_studies:
        for lvl in ("patient", "sample"):
            data = (FIXTURES / f"cbio_{study}_{lvl}.json.gz").read_bytes()
            store.put_bytes(f"cbioportal/{study}/run_id={RUN_ID}/clinical_{lvl}.json.gz", data)
    print(f"staged {len(cases)} fixture cases as run {RUN_ID}")


if __name__ == "__main__":
    main()
