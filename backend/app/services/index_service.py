"""Nifty 50 index OHLC, breadth, and top movers from NSE."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import yfinance as yf

from app.services.nse_client import get_nse_client

logger = logging.getLogger(__name__)


@dataclass
class ConstituentMove:
    symbol: str
    pct_change: float
    last_price: float | None


@dataclass
class IndexSnapshot:
    index_name: str
    as_of: date | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    pct_change: float | None
    advances: int
    declines: int
    unchanged: int
    top_gainers: list[ConstituentMove]
    top_losers: list[ConstituentMove]
    raw_index_meta: dict[str, Any]


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_nse_datetime_to_date(raw: str) -> date | None:
    s = raw.strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%y %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    for fmt in ("%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(s[:11], fmt).date()
        except ValueError:
            continue
    return None


def fetch_nifty50_snapshot(index_name: str = "NIFTY 50", top_n: int = 5) -> IndexSnapshot:
    """Fetch Nifty 50 index stats and constituent breadth from NSE equity-stockIndices API."""
    nse = get_nse_client()
    data = nse.get_json("/api/equity-stockIndices", params={"index": index_name})
    meta = data.get("metadata", {}) or {}
    market_data = data.get("data", []) or []

    last = _safe_float(meta.get("last"))
    o = _safe_float(meta.get("open"))
    h = _safe_float(meta.get("high"))
    l = _safe_float(meta.get("low"))
    pc = _safe_float(meta.get("previousClose"))
    pct = None
    if last is not None and pc not in (None, 0):
        pct = (last - pc) / pc * 100.0

    advances = declines = unchanged = 0
    moves: list[ConstituentMove] = []
    for row in market_data:
        sym = row.get("symbol") or row.get("meta", {}).get("symbol")
        if not sym:
            continue
        pchange = _safe_float(row.get("pChange"))
        lp = _safe_float(row.get("lastPrice"))
        if pchange is None:
            continue
        moves.append(ConstituentMove(symbol=str(sym), pct_change=pchange, last_price=lp))
        if pchange > 0.0001:
            advances += 1
        elif pchange < -0.0001:
            declines += 1
        else:
            unchanged += 1

    moves_sorted = sorted(moves, key=lambda m: m.pct_change, reverse=True)
    gainers = moves_sorted[:top_n]
    losers = sorted(moves, key=lambda m: m.pct_change)[:top_n]

    as_of: date | None = None
    for key in ("time", "lastUpdateTime", "varDate"):
        raw = meta.get(key)
        if isinstance(raw, str) and raw.strip():
            as_of = _parse_nse_datetime_to_date(raw)
            if as_of is not None:
                break
    if as_of is None:
        as_of = date.today()

    return IndexSnapshot(
        index_name=index_name,
        as_of=as_of,
        open=o,
        high=h,
        low=l,
        close=last,
        pct_change=pct,
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        top_gainers=gainers,
        top_losers=losers,
        raw_index_meta=dict(meta),
    )


def fetch_nifty50_yfinance_fallback(yfin_symbol: str, top_n: int = 5) -> IndexSnapshot:
    """Last-resort index OHLC / % change when NSE JSON is blocked or unavailable."""
    del top_n
    t = yf.Ticker(yfin_symbol)
    hist = t.history(period="8d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        return IndexSnapshot(
            index_name="NIFTY 50",
            as_of=date.today(),
            open=None,
            high=None,
            low=None,
            close=None,
            pct_change=None,
            advances=0,
            declines=0,
            unchanged=0,
            top_gainers=[],
            top_losers=[],
            raw_index_meta={"source": "yfinance", "note": "no_history"},
        )
    row = hist.iloc[-1]
    last = float(row["Close"])
    o = float(row["Open"])
    h = float(row["High"])
    l = float(row["Low"])
    pct = None
    if len(hist) >= 2:
        pc = float(hist["Close"].iloc[-2])
        if pc:
            pct = (last - pc) / pc * 100.0
    ts = hist.index[-1]
    as_of = ts.date() if hasattr(ts, "date") else date.today()
    return IndexSnapshot(
        index_name="NIFTY 50 (Yahoo Finance)",
        as_of=as_of,
        open=o,
        high=h,
        low=l,
        close=last,
        pct_change=pct,
        advances=0,
        declines=0,
        unchanged=0,
        top_gainers=[],
        top_losers=[],
        raw_index_meta={"source": "yfinance", "symbol": yfin_symbol},
    )


def fetch_nifty50_snapshot_resilient(
    index_name: str,
    yfin_symbol: str,
    top_n: int = 5,
) -> tuple[IndexSnapshot, str | None]:
    """Try NSE constituents API; on failure use yfinance for headline index only."""
    try:
        return fetch_nifty50_snapshot(index_name, top_n=top_n), None
    except Exception as e:
        logger.warning("NSE equity index unavailable (%s); using yfinance fallback", e)
        return fetch_nifty50_yfinance_fallback(yfin_symbol, top_n=top_n), str(e)
