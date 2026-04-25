"""India VIX level and day change via yfinance."""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from app.services.nifty_indices_history import fetch_index_daily_rows


@dataclass
class VixReading:
    last: float | None
    prev_close: float | None
    pct_change: float | None


def _vix_from_niftyindices() -> VixReading | None:
    rows = fetch_index_daily_rows("INDIA VIX", day_span=20)
    if len(rows) < 1:
        return None
    try:
        last = float(str(rows[-1].get("CLOSE", "")).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if len(rows) < 2:
        return VixReading(last=last, prev_close=None, pct_change=None)
    try:
        prev = float(str(rows[-2].get("CLOSE", "")).replace(",", ""))
    except (TypeError, ValueError):
        return VixReading(last=last, prev_close=None, pct_change=None)
    pct = (last - prev) / prev * 100.0 if prev else None
    return VixReading(last=last, prev_close=prev, pct_change=pct)


def fetch_india_vix(symbol: str = "^INDIAVIX") -> VixReading:
    t = yf.Ticker(symbol)
    hist = t.history(period="5d", interval="1d")
    if hist is not None and not hist.empty:
        last = float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            pct = (last - prev) / prev * 100.0 if prev else None
        else:
            prev = None
            pct = None
        return VixReading(last=last, prev_close=prev, pct_change=pct)
    alt = _vix_from_niftyindices()
    if alt is not None:
        return alt
    return VixReading(last=None, prev_close=None, pct_change=None)
