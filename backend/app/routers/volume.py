"""Volume surge scanner API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.volume_scan_service import _fetch_pcr, _yfin_sym, run_volume_scan, run_watch_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/volume", tags=["volume"])


@router.get("/scan")
def volume_scan(
    market: str = Query("nasdaq", description="nasdaq | sp500 | both"),
    threshold: float = Query(1.5, ge=1.0, le=10.0, description="Volume ratio threshold (e.g. 1.5 = 1.5× avg)"),
    pcr_min: float = Query(0.7, ge=0.0, le=5.0, description="Minimum PCR filter"),
):
    """Scan for volume surges across NASDAQ 100 and S&P 500 using Yahoo Finance chart API."""
    result = run_volume_scan(market=market, vol_threshold=threshold, pcr_min=pcr_min)
    return result


@router.get("/watch")
def volume_watch(
    symbols: str = Query(..., description="Comma-separated list of symbols, e.g. AAPL,MSFT,NVDA"),
):
    """
    Return current volume data for a specific watchlist of symbols.
    No threshold filtering — returns raw ratios so the client can decide when to alert.
    """
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=422, detail="symbols must be a non-empty comma-separated list")
    if len(syms) > 50:
        raise HTTPException(status_code=422, detail="max 50 symbols per watch request")
    return {"results": run_watch_scan(syms)}


@router.get("/pcr/{sym}")
def get_pcr(sym: str):
    """
    Fetch live Put-Call Ratio for a single symbol via Yahoo Finance options chain (yfinance).

    Returns the nearest-expiry OI-based PCR, OI trend, and raw call/put open interest totals.
    This is the same source used by the volume scanner and the watchlist batch job, but
    for a single symbol on demand — useful for the watchlist 'Update PCR' button.

    Source: Yahoo Finance options chain (yfinance) — ~15 min delayed, intraday.
    """
    symbol = sym.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="sym is required")

    # yfinance uses the plain ticker for US stocks (no market suffix needed)
    yfin_symbol = _yfin_sym(symbol, "nasdaq")  # market suffix is a no-op for US stocks
    try:
        pcr, oi_trend = _fetch_pcr(yfin_symbol)

        # Also pull raw OI numbers for transparency
        import yfinance as yf
        from app.services.volume_scan_service import _YF_SESSION
        ticker = yf.Ticker(yfin_symbol, session=_YF_SESSION)
        expirations = ticker.options or []
        call_oi = 0
        put_oi = 0
        nearest_expiry = None
        if expirations:
            nearest_expiry = expirations[0]
            chain = ticker.option_chain(nearest_expiry)
            call_oi = int(chain.calls["openInterest"].sum()) if "openInterest" in chain.calls.columns else 0
            put_oi = int(chain.puts["openInterest"].sum()) if "openInterest" in chain.puts.columns else 0

        return {
            "sym": symbol,
            "pcr": pcr,
            "oiTrend": oi_trend,
            "callOi": call_oi,
            "putOi": put_oi,
            "nearestExpiry": nearest_expiry,
            "source": "yahoo_finance_options",
        }
    except Exception as e:
        logger.warning("PCR fetch failed for %s: %s", symbol, e)
        raise HTTPException(status_code=502, detail=f"Options data unavailable for {symbol}: {e}") from e
