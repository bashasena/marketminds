"""S&P 500–style headline index + mega-cap sample breadth / movers (Yahoo Finance, chart API fallback)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date
from typing import Any

import yfinance as yf

from app.services.index_service import ConstituentMove, IndexSnapshot
from app.services.yahoo_chart_bars import (
    chart_headline_combined,
    chart_one_day_pct_change,
)

logger = logging.getLogger(__name__)

# Liquid S&P 500 names (sample; not full index membership).
_US_SAMPLE = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "JPM",
    "V",
    "JNJ",
    "WMT",
    "UNH",
    "XOM",
    "MA",
    "PG",
    "AVGO",
    "HD",
    "MRK",
    "COST",
    "ABBV",
    "PEP",
    "CSCO",
    "ADBE",
    "NFLX",
]

_YF_SEC = 12.0
_HEADLINE_TIMEOUT = 18.0

# Yahoo often returns empty ^GSPC from Docker; ETFs usually work as the same spot proxy.
_HEADLINE_SYMBOLS = ("^GSPC", "SPY", "IVV", "VOO")

# NASDAQ Composite + liquid proxies; separate sample (tech-heavy) for breadth.
_NASDAQ_HEADLINE_SYMBOLS = ("^IXIC", "QQQ", "QQQM")
_NASDAQ_SAMPLE = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "AVGO",
    "COST",
    "NFLX",
    "AMD",
    "ADBE",
    "PYPL",
    "CSCO",
    "INTC",
    "QCOM",
    "AMAT",
    "MU",
    "LRCX",
    "ISRG",
    "GILD",
    "MRVL",
    "ADI",
    "SNPS",
]


def _hist_last_row(symbol: str):
    """Return (open, high, low, close, pct, as_of_date) or None."""
    t = yf.Ticker(symbol)
    for auto_adj in (False, True):
        for period in ("1mo", "3mo"):
            hist = t.history(period=period, interval="1d", auto_adjust=auto_adj)
            if hist is None or hist.empty:
                continue
            if len(hist) < 1:
                continue
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
            return o, h, l, last, pct, as_of, symbol
    return None


def underlying_last_for_options_chain(symbol: str) -> float | None:
    """
    Last close for an ETF that matches option-chain strikes (e.g. SPY, QQQ).

    Broad cash indices (^GSPC ~5000, ^IXIC ~24000) must **not** be used for ATM selection — they are on a
    different scale than OPRA strikes (~400–600), which collapses ATM to an extreme chain strike and breaks PCR.
    """
    ch = chart_headline_combined(symbol)
    if ch is not None:
        _o, _h, _l, last, _pct, _as_of, _used, _mode = ch
        return float(last)
    got = _hist_last_row(symbol)
    if got is None:
        return None
    _o, _h, _l, last, _pct, _as_of, _symbol = got
    return float(last)


def _us_headline_chain(
    symbols: tuple[str, ...],
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    date | None,
    str,
    str,
]:
    """
    Yahoo v8 chart, then yfinance, for a tuple of tickers in order.
    ohlc_source: yahoo_bars | yahoo_meta | yfinance | "".
    """
    for sym in symbols:
        ch = chart_headline_combined(sym)
        if ch is not None:
            o, h, l, last, pct, as_of, used, mode = ch
            src = "yahoo_bars" if mode == "bars" else "yahoo_meta"
            return o, h, l, last, pct, as_of, used, src
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_hist_last_row, sym)
            try:
                got = fut.result(timeout=_HEADLINE_TIMEOUT)
            except (FutureTimeout, Exception) as e:
                logger.debug("US headline %s: %s", sym, e)
                got = None
        if got is not None:
            o, h, l, last, pct, as_of, used = got
            return o, h, l, last, pct, as_of, used, "yfinance"
    return None, None, None, None, None, None, "", ""


def _one_pct_change(sym: str) -> tuple[str, float | None]:
    p = chart_one_day_pct_change(sym)
    if p is not None:
        return sym, p
    try:
        t = yf.Ticker(sym)
        for auto_adj in (False, True):
            hist = t.history(period="1mo", interval="1d", auto_adjust=auto_adj)
            if hist is None or hist.empty or len(hist) < 2:
                continue
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            if not prev:
                continue
            return sym, (last - prev) / prev * 100.0
    except Exception as e:
        logger.debug("us sample yf %s: %s", sym, e)
    return sym, None


def _order_book_style_snapshot(
    top_n: int,
    headline_symbols: tuple[str, ...],
    sample: list[str],
    display_name: str,
    primary_symbol: str,
    breadth_key: str,
) -> IndexSnapshot:
    g_open, g_high, g_low, g_last, g_pct, as_of, head_sym, ohlc_src = _us_headline_chain(headline_symbols)
    moves: list[ConstituentMove] = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_one_pct_change, s) for s in sample]
        for f in futs:
            try:
                sym, p = f.result(timeout=_YF_SEC + 2)
            except (FutureTimeout, Exception):
                continue
            if p is not None:
                moves.append(ConstituentMove(symbol=sym, pct_change=p, last_price=None))

    idx_name = display_name
    if head_sym and head_sym != primary_symbol:
        idx_name = f"{display_name} (via {head_sym})"

    advances = declines = unchanged = 0
    for m in moves:
        if m.pct_change > 0.0001:
            advances += 1
        elif m.pct_change < -0.0001:
            declines += 1
        else:
            unchanged += 1

    moves_sorted = sorted(moves, key=lambda m: m.pct_change, reverse=True)
    gainers = moves_sorted[:top_n] if moves_sorted else []
    losers = sorted(moves, key=lambda m: m.pct_change)[:top_n] if moves else []

    if ohlc_src:
        src = ohlc_src
    else:
        src = "unavailable" if g_last is None else "yfinance"
    return IndexSnapshot(
        index_name=idx_name,
        as_of=as_of or date.today(),
        open=g_open,
        high=g_high,
        low=g_low,
        close=g_last,
        pct_change=g_pct,
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        top_gainers=gainers,
        top_losers=losers,
        raw_index_meta={
            "source": src,
            "headline": head_sym or primary_symbol,
            "breadth": breadth_key,
            "n": str(len(moves)),
        },
    )


def fetch_sp500_style_snapshot(top_n: int = 5) -> IndexSnapshot:
    return _order_book_style_snapshot(
        top_n,
        _HEADLINE_SYMBOLS,
        _US_SAMPLE,
        "S&P 500",
        "^GSPC",
        "us_mega_cap_sample",
    )


def fetch_nasdaq_style_snapshot(top_n: int = 5) -> IndexSnapshot:
    return _order_book_style_snapshot(
        top_n,
        _NASDAQ_HEADLINE_SYMBOLS,
        _NASDAQ_SAMPLE,
        "NASDAQ Composite",
        "^IXIC",
        "us_nasdaq_tech_sample",
    )
