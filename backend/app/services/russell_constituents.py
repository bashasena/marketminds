"""Russell 2000 (IWM) constituent list — bundled CSV + optional live refresh."""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_BUNDLED_CSV = Path(__file__).resolve().parent.parent / "data" / "russell_2000_components.csv"
_GITHUB_CSV = "https://raw.githubusercontent.com/ikoniaris/Russell2000/master/russell_2000_components.csv"
_BULLISHBEARS_URL = "https://bullishbears.com/russell-2000-stocks-list/"

_CACHE: list[tuple[str, str]] | None = None
_CACHE_AT: float = 0.0
_CACHE_TTL_SEC = 24 * 3600

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _normalize_tickers(df: pd.DataFrame) -> list[tuple[str, str]]:
    sym_col = None
    name_col = None
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in ("ticker", "symbol"):
            sym_col = c
        if cl == "name":
            name_col = c
    if sym_col is None:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        sym = str(row[sym_col]).strip().upper()
        if not sym or sym in ("NAN", "—", "-"):
            continue
        if sym in seen:
            continue
        seen.add(sym)
        name = str(row[name_col]).strip() if name_col is not None else sym
        if not name or name.lower() == "nan":
            name = sym
        out.append((sym, name))
    return out


def _load_bundled() -> list[tuple[str, str]]:
    if not _BUNDLED_CSV.is_file():
        return []
    df = pd.read_csv(_BUNDLED_CSV)
    stocks = _normalize_tickers(df)
    logger.info("Russell 2000: loaded %d symbols from bundled CSV", len(stocks))
    return stocks


def _fetch_bullishbears() -> list[tuple[str, str]]:
    tables = pd.read_html(_BULLISHBEARS_URL, storage_options=_HEADERS)
    for table in tables:
        if "Symbol" in table.columns and "Name" in table.columns and len(table) > 100:
            stocks = _normalize_tickers(table)
            if len(stocks) > 500:
                logger.info("Russell 2000: loaded %d symbols from bullishbears", len(stocks))
                return stocks
    return []


def _fetch_github() -> list[tuple[str, str]]:
    r = requests.get(_GITHUB_CSV, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    stocks = _normalize_tickers(df)
    logger.info("Russell 2000: loaded %d symbols from GitHub CSV", len(stocks))
    return stocks


def get_russell_2000_stocks(*, force_refresh: bool = False) -> list[tuple[str, str]]:
    """
    Return (ticker, name) pairs for Russell 2000 / IWM universe.
    Tries live bullishbears list, then GitHub CSV, then bundled file.
    """
    global _CACHE, _CACHE_AT
    now = time.time()
    if not force_refresh and _CACHE is not None and (now - _CACHE_AT) < _CACHE_TTL_SEC:
        return _CACHE

    stocks: list[tuple[str, str]] = []
    for loader in (_fetch_bullishbears, _fetch_github, _load_bundled):
        try:
            stocks = loader()
            if len(stocks) >= 500:
                break
        except Exception as e:
            logger.warning("Russell 2000 loader %s failed: %s", loader.__name__, e)

    if not stocks:
        raise RuntimeError("Could not load Russell 2000 constituents")

    _CACHE = stocks
    _CACHE_AT = now
    return stocks
