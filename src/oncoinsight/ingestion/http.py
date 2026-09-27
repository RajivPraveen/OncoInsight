"""Shared HTTP client with retry/backoff for the public source APIs."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

RETRYABLE = (httpx.TransportError, httpx.HTTPStatusError)


def _raise_for_retryable(resp: httpx.Response) -> None:
    # 4xx (other than 429) are caller bugs and should fail fast; 5xx / 429 are retried.
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    if resp.status_code >= 400:
        raise ValueError(f"{resp.request.method} {resp.request.url} -> {resp.status_code}: {resp.text[:300]}")


class ApiClient:
    def __init__(self, base_url: str, timeout_s: float = 120.0, user_agent: str = "OncoInsight/1.0 (analytics portfolio)"):
        self.client = httpx.Client(base_url=base_url, timeout=timeout_s, headers={"User-Agent": user_agent},
                                   follow_redirects=True)

    @retry(retry=retry_if_exception_type(RETRYABLE), stop=stop_after_attempt(5),
           wait=wait_exponential(multiplier=2, min=2, max=60), reraise=True)
    def get_json(self, path: str, params: dict | None = None) -> object:
        resp = self.client.get(path, params=params)
        _raise_for_retryable(resp)
        return resp.json()

    @retry(retry=retry_if_exception_type(RETRYABLE), stop=stop_after_attempt(5),
           wait=wait_exponential(multiplier=2, min=2, max=60), reraise=True)
    def post_json(self, path: str, body: dict) -> object:
        resp = self.client.post(path, json=body)
        _raise_for_retryable(resp)
        return resp.json()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
