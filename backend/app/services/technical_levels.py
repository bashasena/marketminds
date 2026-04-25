"""Classic daily pivot levels from prior session OHLC."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass

import yfinance as yf

from app.services.nifty_indices_history import fetch_prior_session_ohlc_for_pivot
from app.services.yahoo_chart_bars import chart_prior_session_ohlc

_YF_PIVOT_SEC = 16.0


@dataclass
class PivotLevels:
    pivot: float
    s1: float
    s2: float
    r1: float
    r2: float
    prev_open: float
    prev_high: float
    prev_low: float
    prev_close: float


def compute_pivot_levels(prev_o: float, prev_h: float, prev_l: float, prev_c: float) -> PivotLevels:
    """Classic pivot (floor trader) formula using previous regular session OHLC."""
    pp = (prev_h + prev_l + prev_c) / 3.0
    r1 = 2.0 * pp - prev_l
    s1 = 2.0 * pp - prev_h
    r2 = pp + (prev_h - prev_l)
    s2 = pp - (prev_h - prev_l)
    return PivotLevels(
        pivot=pp,
        s1=s1,
        s2=s2,
        r1=r1,
        r2=r2,
        prev_open=prev_o,
        prev_high=prev_h,
        prev_low=prev_l,
        prev_close=prev_c,
    )


def _fetch_prior_day_ohlc_yfinance_inner(symbol: str) -> tuple[float, float, float, float] | None:
    """Return (open, high, low, close) for the last fully completed daily bar (not today)."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="10d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty or len(hist) < 2:
        return None
    row = hist.iloc[-2]
    return float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])


def fetch_prior_day_ohlc_yfinance(symbol: str) -> tuple[float, float, float, float] | None:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_fetch_prior_day_ohlc_yfinance_inner, symbol)
        try:
            return fut.result(timeout=_YF_PIVOT_SEC)
        except FutureTimeout:
            return None
        except Exception:
            return None


def build_pivot_from_yfinance(symbol: str) -> PivotLevels | None:
    ohlc = fetch_prior_day_ohlc_yfinance(symbol)
    if ohlc is None:
        return None
    o, h, l, c = ohlc
    return compute_pivot_levels(o, h, l, c)


def build_pivot_from_yahoo_chart_api(symbol: str) -> PivotLevels | None:
    """Yahoo v8 JSON daily bars; used when yfinance history is empty."""
    ohlc = chart_prior_session_ohlc(symbol)
    if ohlc is None:
        return None
    o, h, l, c = ohlc
    return compute_pivot_levels(o, h, l, c)


def build_pivot_from_yfinance_or_niftyindices(
    yfinance_symbol: str,
    niftyindices_index_name: str = "NIFTY 50",
) -> PivotLevels | None:
    """Prefer Yahoo daily bars; if empty (common in Docker), use niftyindices.com EOD OHLC."""
    pl0 = build_pivot_from_yahoo_chart_api(yfinance_symbol)
    if pl0 is not None:
        return pl0
    pl = build_pivot_from_yfinance(yfinance_symbol)
    if pl is not None:
        return pl
    ohlc = fetch_prior_session_ohlc_for_pivot(niftyindices_index_name)
    if ohlc is None:
        return None
    o, h, l, c = ohlc
    return compute_pivot_levels(o, h, l, c)
