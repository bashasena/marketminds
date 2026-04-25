"""
Yahoo Finance v8 chart API (JSON) — often works when yfinance Ticker.history() is empty
from Docker / cloud IPs because it is a single GET with browser-like headers.

Falls back to the chart block `meta` (regularMarketPrice, day high/low) when
`indicators.quote` is empty, which can happen in some network / anti-bot setups.
"""

from __future__ import annotations

import logging
import math
import os
import random
import threading
import time
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_CHART_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# query2 often answers 200 when query1 returns 429 for the same IP (Yahoo’s edge varies by host).
_CHART_HOSTS = (
    "https://query2.finance.yahoo.com",
    "https://query1.finance.yahoo.com",
)

# Space out chart requests: Yahoo often returns 429 (rate limit) if many parallel hits occur.
_yahoo_lock = threading.Lock()
_last_yahoo_at = 0.0
_YAHOO_MIN_INTERVAL = max(0.0, float(os.environ.get("YAHOO_CHART_MIN_INTERVAL", "0.25")))

def _throttle_yahoo() -> None:
    global _last_yahoo_at
    if _YAHOO_MIN_INTERVAL <= 0:
        return
    with _yahoo_lock:
        now = time.monotonic()
        wait = _last_yahoo_at + _YAHOO_MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last_yahoo_at = time.monotonic()


def _quote_ref(symbol: str) -> str:
    """Referer for Yahoo; path uses raw symbol, e.g. AAPL, %5EGSPC, GC%3DF."""
    safe = symbol.replace("=", "%3D")
    return f"https://finance.yahoo.com/quote/{safe}"


def _chart_request_headers(symbol: str) -> dict[str, str]:
    return {
        "User-Agent": _CHART_UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://finance.yahoo.com",
        "Referer": _quote_ref(quote(symbol, safe="")),
    }


def _http_get_json_chart(
    base: str,
    sym: str,
    range_: str,
    interval: str,
    header_symbol: str,
    timeout: float,
) -> dict[str, Any] | None:
    """One GET; retries on 429 with backoff. Returns JSON body or None."""
    url = f"{base}/v8/finance/chart/{sym}"
    max_attempts = 4
    for attempt in range(max_attempts):
        _throttle_yahoo()
        try:
            with httpx.Client(
                timeout=timeout,
                headers=_chart_request_headers(header_symbol),
                follow_redirects=True,
            ) as c:
                r = c.get(
                    url,
                    params={"range": range_, "interval": interval, "includePrePost": "false"},
                )
        except Exception as e:
            logger.debug("yahoo chart get %s %s: %s", base, header_symbol, e)
            if attempt < max_attempts - 1:
                time.sleep(0.4 * (2**attempt) + random.uniform(0, 0.2))
            continue

        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            try:
                wait_s = float(ra) if ra else (1.0 * (2**attempt) + random.uniform(0.3, 1.2))
            except (TypeError, ValueError):
                wait_s = 1.0 * (2**attempt) + random.uniform(0.3, 1.2)
            logger.warning(
                "Yahoo rate limit 429 for %s (%s) — retry in %.1fs (attempt %s/%s)",
                header_symbol,
                base,
                wait_s,
                attempt + 1,
                max_attempts,
            )
            time.sleep(wait_s)
            continue
        if r.status_code != 200:
            logger.debug("yahoo chart %s: HTTP %s", header_symbol, r.status_code)
            if attempt < max_attempts - 1 and r.status_code in (500, 502, 503, 504):
                time.sleep(0.5 * (2**attempt))
                continue
            return None
        try:
            return r.json()
        except Exception as e:
            logger.debug("yahoo chart json %s: %s", header_symbol, e)
            return None
    return None


def _get_chart_block(symbol: str, range_: str, interval: str, timeout: float = 25.0) -> dict[str, Any] | None:
    """
    Return first `chart.result[0]` block, or None.
    Tries query2 first, then query1 (either host can rate-limit or work depending on IP). 429 handling with backoff.
    """
    sym = quote(symbol, safe="")
    last_err: str | None = None
    for base in _CHART_HOSTS:
        data = _http_get_json_chart(base, sym, range_, interval, symbol, timeout)
        if data is None:
            last_err = "http_or_json"
            continue
        c_err = (data.get("chart") or {}).get("error")
        if c_err:
            last_err = str(c_err)
            logger.debug("yahoo chart err body %s: %s", symbol, c_err)
            continue
        r0 = (data.get("chart") or {}).get("result")
        if not r0 or not isinstance(r0, list) or not r0[0]:
            last_err = "empty result"
            continue
        return r0[0]
    if last_err:
        logger.info("yahoo chart all hosts failed for %s: %s", symbol, last_err)
    return None


def _fget(arr: list[Any] | None, i: int) -> float | None:
    if not arr or i >= len(arr):
        return None
    v = arr[i]
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ohlc_from_block(block: dict[str, Any]) -> list[dict[str, Any]]:
    ts = block.get("timestamp") or []
    ind = (block.get("indicators") or {}).get("quote")
    if not ind or not isinstance(ind, list) or not ind[0]:
        return []
    q = ind[0]
    oa, ha, la, ca = q.get("open"), q.get("high"), q.get("low"), q.get("close")

    out: list[dict[str, Any]] = []
    for i, tsec in enumerate(ts):
        c = _fget(ca, i)
        if c is None:
            continue
        o, h, l_ = _fget(oa, i), _fget(ha, i), _fget(la, i)
        if o is None:
            o = c
        if h is None:
            h = c
        if l_ is None:
            l_ = c
        d = datetime.fromtimestamp(int(tsec), tz=timezone.utc).date()
        out.append({"d": d, "o": o, "h": h, "l": l_, "c": c})
    return out


def _spot_ohlc_from_block_meta(block: dict[str, Any], symbol: str) -> tuple[float, float, float, float, float | None, date, str] | None:
    """
    When daily quote arrays are empty, use `meta` spot fields (ETF / index all support this).
    Returns (o, h, l, c, pct_vs_prev, as_of, symbol).
    """
    m = block.get("meta") or {}
    c = m.get("regularMarketPrice")
    if c is None:
        return None
    c = float(c)
    prev = m.get("chartPreviousClose")
    o_raw = m.get("regularMarketOpen")
    o = float(o_raw) if o_raw is not None else (float(prev) if prev is not None else c)
    h = m.get("regularMarketDayHigh")
    l_ = m.get("regularMarketDayLow")
    hi = float(h) if h is not None else c
    lo = float(l_) if l_ is not None else c
    t = m.get("regularMarketTime")
    as_d = (
        datetime.fromtimestamp(int(t), tz=timezone.utc).date() if t is not None else date.today()
    )
    pct = None
    if prev is not None and float(prev) != 0.0:
        pct = (c - float(prev)) / float(prev) * 100.0
    return o, hi, lo, c, pct, as_d, symbol


def fetch_chart_daily_ohlc(
    symbol: str,
    range_: str = "3mo",
    timeout: float = 25.0,
) -> list[dict[str, Any]]:
    """
    Returns oldest-first list of {d, o, h, l, c} for last valid closes.
    Tries requested range, then 1mo, then 5d.
    """
    for rng in (range_, "1mo", "5d"):
        block = _get_chart_block(symbol, range_=rng, interval="1d", timeout=timeout)
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if rows:
            return rows
    return []


def chart_headline_combined(
    symbol: str,
) -> tuple[float | None, float | None, float | None, float | None, float | None, date | None, str, str] | None:
    """
    Daily bar row if present; else `meta` spot. Returns
    (o, h, l, last_close, pct_1d, as_of, symbol, mode) with mode in ('bars', 'meta').
    """
    for rng in ("3mo", "1mo", "5d"):
        block = _get_chart_block(symbol, range_=rng, interval="1d")
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if len(rows) >= 1:
            last = rows[-1]
            c2 = last["c"]
            o, h, l_ = last["o"], last["h"], last["l"]
            as_of = last["d"]
            pct = None
            if len(rows) >= 2:
                pc = rows[-2].get("c")
                if pc and c2 is not None:
                    pct = (c2 - float(pc)) / float(pc) * 100.0
            return o, h, l_, c2, pct, as_of, symbol, "bars"
        sp = _spot_ohlc_from_block_meta(block, symbol)
        if sp is not None:
            o, h, l_, c, pct, as_d, sym = sp
            return o, h, l_, c, pct, as_d, sym, "meta"
    return None


def chart_headline_last_row(
    symbol: str,
) -> tuple[float | None, float | None, float | None, float | None, float | None, date | None, str] | None:
    """Backward-compatible: bars or meta, without mode flag (drops mode)."""
    r = chart_headline_combined(symbol)
    if r is None:
        return None
    o, h, l_, c, pct, d, sym, _mode = r
    return o, h, l_, c, pct, d, sym


def chart_one_day_pct_change(symbol: str) -> float | None:
    for rng in ("1mo", "5d", "1d"):
        block = _get_chart_block(symbol, range_=rng, interval="1d")
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if len(rows) >= 2:
            c0, c1 = rows[-1].get("c"), rows[-2].get("c")
            if c0 is not None and c1 is not None and c1:
                return (c0 - c1) / c1 * 100.0
        sp = _spot_ohlc_from_block_meta(block, symbol)
        if sp is not None:
            _o, _h, _l, _c, pct, _d, _s = sp
            if pct is not None:
                return pct
    return None


def chart_prior_session_ohlc(symbol: str) -> tuple[float, float, float, float] | None:
    for rng in ("1mo", "3mo"):
        block = _get_chart_block(symbol, range_=rng, interval="1d")
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if len(rows) < 2:
            continue
        bar = rows[-2]
        o, h, l_, c = bar.get("o"), bar.get("h"), bar.get("l"), bar.get("c")
        if c is None or o is None or h is None or l_ is None:
            continue
        return (float(o), float(h), float(l_), float(c))
    return None


def chart_vix_reading(symbol: str) -> tuple[float | None, float | None, float | None] | None:
    """(last, prev_close, pct) or None."""
    for rng in ("1mo", "5d"):
        block = _get_chart_block(symbol, range_=rng, interval="1d")
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if len(rows) >= 2:
            last = float(rows[-1]["c"])
            prev = float(rows[-2]["c"])
            pct = (last - prev) / prev * 100.0 if prev else None
            return last, prev, pct
        if len(rows) == 1:
            return float(rows[-1]["c"]), None, None
        sp = _spot_ohlc_from_block_meta(block, symbol)
        if sp is not None:
            _o, _h, _l, c, pct, _d, _sym = sp
            prev2 = (block.get("meta") or {}).get("chartPreviousClose")
            prev3 = float(prev2) if prev2 is not None else None
            return float(c), prev3, pct
    return None


def chart_last_and_pct(symbol: str) -> tuple[float | None, float | None] | None:
    """Last price and 1D % for global tiles."""
    p = chart_one_day_pct_change(symbol)
    for rng in ("1mo", "5d", "1d"):
        block = _get_chart_block(symbol, range_=rng, interval="1d")
        if block is None:
            continue
        rows = _ohlc_from_block(block)
        if rows:
            c0f = float(rows[-1]["c"])
            if p is not None:
                return c0f, p
            if len(rows) >= 2 and rows[-2].get("c"):
                a = float(rows[-1]["c"])
                b = float(rows[-2]["c"])
                return a, (a - b) / b * 100.0
            return c0f, p
        sp = _spot_ohlc_from_block_meta(block, symbol)
        if sp is not None:
            _o, _h, _l, c, pct, _d, _sym = sp
            if c is not None:
                return float(c), pct
    return None
