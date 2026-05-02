"""Snapshot API routes."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.jobs.snapshot_job import run_snapshot_pipeline
from app.models.snapshot import DailySnapshot
from app.repositories.snapshot_repo import (
    get_latest_snapshot,
    get_snapshot_for_date,
    list_recent_snapshots,
    upsert_daily_snapshot,
    upsert_fii_dii_flow,
)
from app.services.composite_sentiment import compute_composite
from app.services.market_snapshot import build_snapshot
from app.services.narrative_service import dashboard_title
from app.services.options_service import (
    enrich_options_with_history,
    options_from_nse_option_chain_payload,
    options_snapshot_to_api_dict,
)
from app.services.us_market_snapshot import build_us_snapshot
from app.services.us_nasdaq_market_snapshot import build_us_nasdaq_snapshot

router = APIRouter(prefix="/snapshot", tags=["snapshot"])
IST = ZoneInfo("Asia/Kolkata")
VALID_MARKETS = frozenset({"in_nifty", "us_broad", "usa_nasdaq"})


def _row_for_stored_read(db: Session, market: str) -> DailySnapshot | None:
    """Same row selection as ``GET /snapshot/today?live=false`` (today IST, else latest)."""
    today_ist = datetime.now(IST).date()
    row = get_snapshot_for_date(db, today_ist, market)
    if row is None:
        row = get_latest_snapshot(db, market)
    return row


@router.get("/today")
def snapshot_today(
    market: str = Query("in_nifty", description="in_nifty | us_broad (S&P) | usa_nasdaq (NASDAQ)"),
    live: bool = Query(False, description="Force recompute from upstream sources"),
    persist: bool = Query(False, description="When true, save freshly built snapshot to DB"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    if not live:
        row = _row_for_stored_read(db, market)
        if row is not None:
            return row.payload
        # Do not run builders for normal reads — avoids slow fetches and nginx timeouts.
        raise HTTPException(status_code=404, detail="no_stored_snapshot")
    if market == "in_nifty":
        payload = build_snapshot(get_settings(), db=db)
    elif market == "us_broad":
        payload = build_us_snapshot(get_settings(), db=db)
    else:
        payload = build_us_nasdaq_snapshot(get_settings(), db=db)
    if persist:
        snap_date = date.fromisoformat(str(payload["snapshot_date"]))
        comp = payload.get("composite", {}).get("score_0_100")
        idx = payload.get("index", {})
        upsert_daily_snapshot(
            db,
            snap_date,
            payload,
            float(comp) if comp is not None else None,
            float(idx["close"]) if idx.get("close") is not None else None,
            float(idx["pct_change"]) if idx.get("pct_change") is not None else None,
            market_id=market,
        )
        fii = payload.get("fii_dii", {})
        if market == "in_nifty" and fii.get("as_of"):
            fd = date.fromisoformat(str(fii["as_of"]))
            upsert_fii_dii_flow(
                db,
                fd,
                float(fii["fii_net_crores"]) if fii.get("fii_net_crores") is not None else None,
                float(fii["dii_net_crores"]) if fii.get("dii_net_crores") is not None else None,
            )
    return payload


@router.get("/history")
def snapshot_history(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list_recent_snapshots(db, days)
    return {
        "days": days,
        "count": len(rows),
        "items": [
            {
                "snapshot_date": str(r.snapshot_date),
                "composite_sentiment": r.composite_sentiment,
                "nifty_close": r.nifty_close,
                "nifty_pct_change": r.nifty_pct_change,
                "payload": r.payload,
            }
            for r in rows
        ],
    }


@router.post("/refresh")
def snapshot_refresh(
    market: str = Query("in_nifty", description="in_nifty | us_broad | usa_nasdaq"),
) -> dict[str, Any]:
    """Manual / hook trigger: rebuild and persist."""
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    payload = run_snapshot_pipeline(persist=True, market=market)
    return {"ok": True, "snapshot_date": payload.get("snapshot_date"), "market": market}


_INGEST_REQUIRED = ("snapshot_date", "header", "index", "options", "composite")


@router.post("/ingest")
def snapshot_ingest(
    market: str = Query("in_nifty", description="Target market id in DB"),
    persist: bool = Query(True, description="Save as the daily snapshot row for snapshot_date"),
    body: dict[str, Any] = Body(..., description="Full dashboard snapshot JSON"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Load a snapshot you saved elsewhere (e.g. ``GET /snapshot/today?live=true`` from a machine
    where NSE works, or a hand-edited JSON file). Persists to PostgreSQL when ``persist=true``.
    """
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    missing = [k for k in _INGEST_REQUIRED if k not in body]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing keys: {missing}")
    snap_date = date.fromisoformat(str(body["snapshot_date"]))
    comp = body.get("composite", {}).get("score_0_100")
    idx = body.get("index", {})
    if persist:
        upsert_daily_snapshot(
            db,
            snap_date,
            body,
            float(comp) if comp is not None else None,
            float(idx["close"]) if idx.get("close") is not None else None,
            float(idx["pct_change"]) if idx.get("pct_change") is not None else None,
            market_id=market,
        )
        fii = body.get("fii_dii", {})
        if market == "in_nifty" and fii.get("as_of"):
            fd = date.fromisoformat(str(fii["as_of"]))
            upsert_fii_dii_flow(
                db,
                fd,
                float(fii["fii_net_crores"]) if fii.get("fii_net_crores") is not None else None,
                float(fii["dii_net_crores"]) if fii.get("dii_net_crores") is not None else None,
            )
    return body


@router.post("/options/from-nse-json")
def snapshot_options_from_nse_json(
    market: str = Query("in_nifty", description="Which stored snapshot row to patch"),
    symbol: str = Query("NIFTY", description="Index symbol as in the JSON (e.g. NIFTY, BANKNIFTY)"),
    persist: bool = Query(
        False,
        description="If true, merge options into latest DB snapshot for this market and recompute composite",
    ),
    ref: Optional[str] = Query(
        None,
        description="ISO date (YYYY-MM-DD) for picking nearest expiry; default today (IST)",
    ),
    body: dict[str, Any] = Body(
        ...,
        description="Raw NSE response: full object with `records`, or the `records` object alone",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Feed a **manually downloaded** NSE option-chain JSON (same shape as
    ``/api/option-chain-indices``). Save the response from browser DevTools on a machine
    where NSE returns data, then POST the file here.

    With ``persist=true``, updates **only** the ``options`` block on the **latest** stored
    snapshot and recomputes **composite** + header title.
    """
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    try:
        ref_d = date.fromisoformat(ref) if ref else datetime.now(IST).date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"bad ref date: {e}") from e
    try:
        opts = options_from_nse_option_chain_payload(body, symbol=symbol, ref_date=ref_d)
        opts = enrich_options_with_history(db, market, opts, record_tick=True)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    opt_dict = options_snapshot_to_api_dict(opts)
    out: dict[str, Any] = {"options": opt_dict, "symbol": symbol, "ref_date": str(ref_d)}
    if not persist:
        return out
    row = _row_for_stored_read(db, market)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="no_stored_snapshot: run a live refresh or POST /snapshot/ingest first",
        )
    p = deepcopy(row.payload)
    p["options"] = opt_dict
    # Drop stale "nifty_options" line items from a prior live build now that OI/PCR is populated from a file
    pcr = opt_dict.get("pcr_oi")
    oi_sum = (opt_dict.get("call_oi_total") or 0) + (opt_dict.get("put_oi_total") or 0)
    if pcr is not None or oi_sum > 0:
        meta = dict(p.get("meta") or {})
        prev = list(meta.get("data_warnings") or [])
        meta["data_warnings"] = [w for w in prev if not (isinstance(w, str) and w.strip().startswith("nifty_options:"))]
        p["meta"] = meta
    idx = p.get("index") or {}
    vix = p.get("vix") or {}
    fii = p.get("fii_dii") or {}
    xsum = p.get("x_sentiment_summary") or {}
    c = compute_composite(
        idx.get("pct_change"),
        vix.get("level"),
        vix.get("pct_change"),
        opt_dict.get("pcr_oi"),
        fii.get("fii_net_crores"),
        xsum.get("aggregate_0_100"),
    )
    p["composite"] = {
        "score_0_100": c.score_0_100,
        "label": c.label,
        "components": c.components,
        "weights": c.weights,
        "explanation": c.explanation,
    }
    hdr = dict(p.get("header") or {})
    hdr["title"] = dashboard_title(c, idx.get("pct_change"))
    p["header"] = hdr
    p["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    snap_date = date.fromisoformat(str(p.get("snapshot_date", row.snapshot_date)))
    upsert_daily_snapshot(
        db,
        snap_date,
        p,
        float(c.score_0_100),
        float(idx["close"]) if idx.get("close") is not None else None,
        float(idx["pct_change"]) if idx.get("pct_change") is not None else None,
        market_id=market,
    )
    return {
        "ok": True,
        "options": opt_dict,
        "patched_snapshot_date": str(snap_date),
        "market": market,
    }
