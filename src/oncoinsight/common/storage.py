"""Raw-layer object storage. The same interface is backed by the local filesystem (development/CI)
or S3 / MinIO (docker, cloud). Keys look like S3 keys: ``gdc/tcga_brca/cases/run_id=.../part-0000.json.gz``."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

from oncoinsight.common.config import Settings, get_settings


class RawStore(Protocol):
    def put_bytes(self, key: str, data: bytes) -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def list_keys(self, prefix: str) -> list[str]: ...
    def exists(self, key: str) -> bool: ...
    def uri(self, key: str) -> str: ...


class LocalRawStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise ValueError(f"key escapes raw store root: {key}")
        return p

    def put_bytes(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)  # atomic on POSIX: readers never see half-written files
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file() and not p.name.endswith(".tmp"))

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def uri(self, key: str) -> str:
        return f"file://{self._path(key)}"


class S3RawStore:
    def __init__(self, bucket: str, endpoint_url: str | None, region: str):
        import boto3
        from botocore.exceptions import ClientError

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            if not endpoint_url:  # in AWS the bucket is provisioned by Terraform, never by the app
                raise
            self.client.create_bucket(Bucket=bucket)

    def put_bytes(self, key: str, data: bytes) -> str:
        # encryption comes from the bucket's default (SSE-KMS, see infra/terraform); an explicit SSE header here
        # would override the customer-managed key
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []))
        return sorted(keys)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"


def get_raw_store(settings: Settings | None = None) -> RawStore:
    s = settings or get_settings()
    if s.storage_backend == "s3":
        return S3RawStore(s.s3_bucket, s.s3_endpoint_url, s.s3_region)
    return LocalRawStore(s.data_dir / "raw")


# ---------- helpers for JSON / NDJSON payloads ----------

def dumps_gz_json(obj: object) -> bytes:
    return gzip.compress(json.dumps(obj, separators=(",", ":"), default=str).encode())


def loads_gz_json(data: bytes) -> object:
    return json.loads(gzip.decompress(data))


def dumps_gz_ndjson(rows: Iterable[dict]) -> bytes:
    return gzip.compress("".join(json.dumps(r, separators=(",", ":"), default=str) + "\n" for r in rows).encode())


def iter_gz_ndjson(data: bytes) -> Iterator[dict]:
    for line in gzip.decompress(data).decode().splitlines():
        if line.strip():
            yield json.loads(line)
