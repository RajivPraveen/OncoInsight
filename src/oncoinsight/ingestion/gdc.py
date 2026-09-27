"""Extract TCGA-BRCA clinical records from the NCI Genomic Data Commons (GDC) public API.

Source: https://api.gdc.cancer.gov/cases (open access, no credentials). Each case carries demographics,
diagnoses (stage, TNM, histology), treatments with day offsets relative to diagnosis, follow-ups,
molecular tests (ER/PR/HER2) and the tissue source site (the contributing hospital).

Incremental mode filters on the case-level ``updated_datetime`` using a watermark stored in
``ops.ingestion_watermarks``; full mode re-pulls the project (used for the weekly reconciliation run,
because GDC does not always bump the case timestamp when nested entities change).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from oncoinsight.common.config import Settings, get_settings
from oncoinsight.common.logging import get_logger
from oncoinsight.common.storage import RawStore, dumps_gz_json, get_raw_store
from oncoinsight.ingestion.http import ApiClient

log = get_logger(__name__)

SOURCE = "gdc_tcga_brca"
EXPAND = ",".join([
    "demographic",
    "diagnoses",
    "diagnoses.treatments",
    "diagnoses.pathology_details",
    "follow_ups",
    "follow_ups.molecular_tests",
    "tissue_source_site",
])
PAGE_SIZE = 250


@dataclass
class ExtractManifest:
    source: str
    run_id: str
    mode: str
    extracted_at: str
    record_count: int = 0
    keys: list[str] = field(default_factory=list)
    max_updated_datetime: str | None = None


def _filters(project_id: str, since: str | None) -> dict:
    clauses: list[dict] = [{"op": "=", "content": {"field": "project.project_id", "value": project_id}}]
    if since:
        clauses.append({"op": ">=", "content": {"field": "updated_datetime", "value": since}})
    return {"op": "and", "content": clauses}


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def extract_cases(run_id: str | None = None, since: str | None = None, settings: Settings | None = None,
                  store: RawStore | None = None) -> ExtractManifest:
    s = settings or get_settings()
    store = store or get_raw_store(s)
    run_id = run_id or new_run_id()
    mode = "incremental" if since else "full"
    manifest = ExtractManifest(SOURCE, run_id, mode, datetime.now(UTC).isoformat())
    prefix = f"gdc/{s.gdc_project_id.lower()}/cases/run_id={run_id}"

    with ApiClient(s.gdc_api_url, s.http_timeout_s) as api:
        offset, page = 0, 0
        while True:
            body = {"filters": _filters(s.gdc_project_id, since), "expand": EXPAND, "format": "json",
                    "size": PAGE_SIZE, "from": offset, "sort": "submitter_id:asc"}
            payload = api.post_json("/cases", body)
            hits = payload["data"]["hits"]
            total = payload["data"]["pagination"]["total"]
            if not hits:
                break
            key = f"{prefix}/part-{page:04d}.json.gz"
            store.put_bytes(key, dumps_gz_json(hits))
            manifest.keys.append(key)
            manifest.record_count += len(hits)
            for h in hits:
                u = h.get("updated_datetime")
                if u and (manifest.max_updated_datetime is None or u > manifest.max_updated_datetime):
                    manifest.max_updated_datetime = u
            log.info("gdc_page_extracted", run_id=run_id, page=page, rows=len(hits), total=total)
            offset += len(hits)
            page += 1
            if offset >= total:
                break

    store.put_bytes(f"{prefix}/_manifest.json.gz", dumps_gz_json(manifest.__dict__))
    log.info("gdc_extract_complete", run_id=run_id, mode=mode, records=manifest.record_count)
    return manifest
