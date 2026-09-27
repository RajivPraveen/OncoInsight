"""Create small, deterministic test fixtures from the latest REAL extracts (public open-access data).

    uv run python scripts/make_fixtures.py

Writes tests/fixtures/{gdc_cases.json.gz, cbio_<study>_{patient,sample}.json.gz}: 150 TCGA-BRCA cases with their
matching PanCancer rows, and 300 METABRIC patients. Used by unit tests and the offline CI pipeline run.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from oncoinsight.common.config import get_settings
from oncoinsight.common.storage import dumps_gz_json, get_raw_store, loads_gz_json
from oncoinsight.pipeline import _latest_run_prefix

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
N_TCGA, N_METABRIC = 150, 300


def _pick(ids: list[str], n: int) -> set[str]:
    return set(sorted(ids, key=lambda i: hashlib.md5(i.encode()).hexdigest())[:n])


def main() -> None:
    s = get_settings()
    store = get_raw_store(s)
    OUT.mkdir(parents=True, exist_ok=True)
    base = f"gdc/{s.gdc_project_id.lower()}/cases"
    runs = sorted({k.split("run_id=")[1].split("/")[0] for k in store.list_keys(base)}, reverse=True)
    # latest FULL extract (incremental runs only contain recently updated cases)
    prefix = next(f"{base}/run_id={r}" for r in runs
                  if loads_gz_json(store.get_bytes(f"{base}/run_id={r}/_manifest.json.gz")).get("mode") == "full")
    cases = [c for k in store.list_keys(prefix) if "/part-" in k for c in loads_gz_json(store.get_bytes(k))]
    keep = _pick([c["submitter_id"] for c in cases], N_TCGA)
    sample = [c for c in cases if c["submitter_id"] in keep]
    (OUT / "gdc_cases.json.gz").write_bytes(dumps_gz_json(sample))
    for study in s.cbioportal_studies:
        p = _latest_run_prefix(store, f"cbioportal/{study}")
        rows = {lvl: loads_gz_json(store.get_bytes(f"{p}/clinical_{lvl}.json.gz")) for lvl in ("patient", "sample")}
        ids = keep if study.startswith("brca_tcga") else _pick(sorted({r["patientId"] for r in rows["patient"]}), N_METABRIC)
        for lvl, rs in rows.items():
            (OUT / f"cbio_{study}_{lvl}.json.gz").write_bytes(dumps_gz_json([r for r in rs if r["patientId"] in ids]))
    print(f"wrote fixtures for {len(sample)} TCGA cases to {OUT}")


if __name__ == "__main__":
    main()
