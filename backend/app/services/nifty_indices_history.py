"""NIFTY indices historical OHLC via niftyindices.com (works when Yahoo Finance blocks yfinance)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_HIST_URL = "https://niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": "https://niftyindices.com",
    "Referer": "https://niftyindices.com/reports/historical-data",
}


def _cinfo_payload(index_name: str, start: str, end: str) -> dict[str, str]:
    cinfo = (
        "{'name':'"
        + index_name
        + "','startDate':'"
        + start
        + "','endDate':'"
        + end
        + "','indexName':'"
        + index_name
        + "'}"
    )
    return {"cinfo": cinfo}


def _parse_row_date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fetch_index_daily_rows(index_name: str, day_span: int = 35) -> list[dict[str, Any]]:
    """Return sorted rows (oldest first) from niftyindices historical table."""
    end = date.today()
    start = end - timedelta(days=max(14, day_span))
    start_s = start.strftime("%d-%b-%Y")
    end_s = end.strftime("%d-%b-%Y")
    try:
        # Tighter than before so a hung upstream does not keep /snapshot over nginx's old 60s budget alone.
        with httpx.Client(timeout=22.0, follow_redirects=True) as client:
            r = client.post(_HIST_URL, headers=_HEADERS, json=_cinfo_payload(index_name, start_s, end_s))
            r.raise_for_status()
            payload = r.json()
        raw = payload.get("d")
        if raw is None:
            return []
        rows = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(rows, list):
            return []
    except Exception as e:
        logger.warning("niftyindices history failed for %s: %s", index_name, e)
        return []

    parsed: list[tuple[date, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ds = row.get("HistoricalDate") or row.get("HISTORICAL_DATE")
        if not ds:
            continue
        d = _parse_row_date(str(ds))
        if d is None:
            continue
        parsed.append((d, row))
    parsed.sort(key=lambda x: x[0])
    return [r for _, r in parsed]


def fetch_last_close_and_pct_change(index_name: str) -> tuple[float | None, float | None]:
    """Latest close and % vs prior row (niftyindices daily series)."""
    rows = fetch_index_daily_rows(index_name, day_span=40)
    if len(rows) < 1:
        return None, None
    last = rows[-1]
    try:
        c_last = float(str(last.get("CLOSE", "")).replace(",", ""))
    except (TypeError, ValueError):
        return None, None
    if len(rows) < 2:
        return c_last, None
    prev = rows[-2]
    try:
        c_prev = float(str(prev.get("CLOSE", "")).replace(",", ""))
    except (TypeError, ValueError):
        return c_last, None
    pct = (c_last - c_prev) / c_prev * 100.0 if c_prev else None
    return c_last, pct


def fetch_prior_session_ohlc_for_pivot(index_name: str) -> tuple[float, float, float, float] | None:
    """
    OHLC of the most recent completed daily bar in the series (for classic pivots).
    Uses niftyindices daily EOD rows (last row = last completed session).
    """
    rows = fetch_index_daily_rows(index_name, day_span=40)
    if not rows:
        return None
    last = rows[-1]
    try:
        o = float(str(last.get("OPEN", "")).replace(",", ""))
        h = float(str(last.get("HIGH", "")).replace(",", ""))
        l = float(str(last.get("LOW", "")).replace(",", ""))
        c = float(str(last.get("CLOSE", "")).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return o, h, l, c
