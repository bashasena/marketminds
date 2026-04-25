"""Lightweight NSE India HTTP client (session + headers)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Origin": NSE_BASE,
    "Referer": NSE_BASE + "/",
}


def _retryable_nse(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(
        exc,
        (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError),
    )


class NSEClient:
    """Maintains cookies by hitting the landing page before API calls."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True)
            self._warm_session()
        return self._client

    def _warm_session(self) -> None:
        assert self._client is not None
        for path, params in (
            ("/api/marketStatus", None),
            ("/api/equity-stockIndices", {"index": "NIFTY 50"}),
            ("/", None),
        ):
            try:
                r = self._client.get(NSE_BASE + path, params=params)
                if r.status_code < 400:
                    return
                logger.debug("NSE warm %s -> %s", path, r.status_code)
            except Exception as e:
                logger.debug("NSE warm %s failed: %s", path, e)
        logger.warning("NSE session warm-up did not get a 2xx/3xx response; API calls may still fail.")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @retry(
        retry=retry_if_exception(_retryable_nse),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def get_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        client = self._ensure_client()
        url = NSE_BASE + path if path.startswith("/") else f"{NSE_BASE}/{path}"
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


_nse_singleton: NSEClient | None = None


def get_nse_client() -> NSEClient:
    global _nse_singleton
    if _nse_singleton is None:
        _nse_singleton = NSEClient()
    return _nse_singleton
