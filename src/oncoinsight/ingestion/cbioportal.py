"""Extract curated clinical data from the cBioPortal public REST API.

Studies:
* ``brca_tcga_pan_can_atlas_2018`` - TCGA PanCancer Atlas curated outcome endpoints (OS, DSS, DFS, PFS;
  Liu et al., Cell 2018) and PAM50 subtype for the same TCGA-BRCA patients pulled from GDC.
* ``brca_metabric`` - METABRIC (Curtis 2012, Pereira 2016, Rueda 2019): 2,509 patients with tumor size,
  grade, surgery type, treatment flags, overall and relapse-free survival. Used as a second,
  independent cohort for survival and recurrence modelling.

The API returns "long" records (one row per patient x attribute); pivoting to wide happens in the loader.
"""

from __future__ import annotations

from datetime import UTC, datetime

from oncoinsight.common.config import Settings, get_settings
from oncoinsight.common.logging import get_logger
from oncoinsight.common.storage import RawStore, dumps_gz_json, get_raw_store
from oncoinsight.ingestion.gdc import ExtractManifest, new_run_id
from oncoinsight.ingestion.http import ApiClient

log = get_logger(__name__)


def extract_study(study_id: str, run_id: str | None = None, settings: Settings | None = None,
                  store: RawStore | None = None) -> ExtractManifest:
    s = settings or get_settings()
    store = store or get_raw_store(s)
    run_id = run_id or new_run_id()
    manifest = ExtractManifest(f"cbioportal_{study_id}", run_id, "full", datetime.now(UTC).isoformat())
    prefix = f"cbioportal/{study_id}/run_id={run_id}"

    with ApiClient(s.cbioportal_api_url, s.http_timeout_s) as api:
        study = api.get_json(f"/studies/{study_id}")
        store.put_bytes(f"{prefix}/study.json.gz", dumps_gz_json(study))
        attrs = api.get_json(f"/studies/{study_id}/clinical-attributes", {"projection": "SUMMARY"})
        store.put_bytes(f"{prefix}/clinical_attributes.json.gz", dumps_gz_json(attrs))
        for level in ("PATIENT", "SAMPLE"):
            rows = api.get_json(
                f"/studies/{study_id}/clinical-data",
                {"clinicalDataType": level, "projection": "SUMMARY", "pageSize": 1_000_000},
            )
            key = f"{prefix}/clinical_{level.lower()}.json.gz"
            store.put_bytes(key, dumps_gz_json(rows))
            manifest.keys.append(key)
            manifest.record_count += len(rows)
            log.info("cbioportal_extracted", study=study_id, level=level, rows=len(rows))

    store.put_bytes(f"{prefix}/_manifest.json.gz", dumps_gz_json(manifest.__dict__))
    return manifest


def extract_all(run_id: str | None = None, settings: Settings | None = None) -> list[ExtractManifest]:
    s = settings or get_settings()
    run_id = run_id or new_run_id()
    return [extract_study(study, run_id, s) for study in s.cbioportal_studies]
