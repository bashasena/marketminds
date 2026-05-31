"""Volume surge scanner API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.volume_scan_service import run_volume_scan, run_watch_scan

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
