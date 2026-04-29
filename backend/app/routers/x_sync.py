"""
X (Twitter) List sentiment only — not combined with Yahoo / NSE snapshot builders.
Optional persist patches the latest stored snapshot for a market and recomputes composite.
"""

from __future__ import annotations

import copy
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.repositories.snapshot_repo import get_latest_snapshot, upsert_daily_snapshot
from app.services.composite_sentiment import CompositeResult, compute_composite
from app.services.narrative_service import dashboard_title
from app.services.x_sentiment_service import XSentimentReport, build_x_sentiment_report
from app.routers.snapshot import VALID_MARKETS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/x", tags=["x"])


def _x_summary_dict(rep: XSentimentReport) -> dict[str, Any]:
    return {
        "aggregate_0_100": rep.aggregate_score_0_100,
        "tweet_count": rep.tweet_count,
        "model": rep.model_used,
        "error": rep.error,
    }


def _apply_x_to_stored_payload(
    payload: dict[str, Any], x_rep: XSentimentReport
) -> tuple[dict[str, Any], CompositeResult]:
    p = copy.deepcopy(payload)
    p["x_sentiment_summary"] = _x_summary_dict(x_rep)
    idx = p.get("index") or {}
    vix = p.get("vix") or {}
    opt = p.get("options") or {}
    fii = p.get("fii_dii") or {}
    c = compute_composite(
        idx.get("pct_change"),
        vix.get("level"),
        vix.get("pct_change"),
        opt.get("pcr_oi"),
        fii.get("fii_net_crores"),
        x_rep.aggregate_score_0_100,
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
    return p, c


@router.post("/sync")
def x_sync_only(
    market: Optional[str] = Query(
        None,
        description="When persist=true, which market's latest DB row to patch (in_nifty | us_broad | usa_nasdaq)",
    ),
    persist: bool = Query(
        False,
        description="If true, merge X into the latest stored snapshot for `market` and re-save; requires market",
    ),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Calls the X List API and FinBERT (or fallback) only — no Yahoo, no NSE index fetch.
    """
    x_rep = build_x_sentiment_report(
        settings.x_bearer_token,
        settings.x_list_id,
        settings.x_tweet_lookback_hours,
        settings.x_max_tweets,
        settings.finbert_model,
    )
    summary = _x_summary_dict(x_rep)

    out: dict[str, Any] = {
        "ok": True,
        "x_only": True,
        "x_sentiment_summary": summary,
        "persisted": False,
        "message": "X / List sentiment only; full snapshot (prices) unchanged.",
    }

    if not persist:
        return out

    if not market or market not in VALID_MARKETS:
        raise HTTPException(
            status_code=400,
            detail="persist=true requires market= one of: " + ", ".join(sorted(VALID_MARKETS)),
        )

    row = get_latest_snapshot(db, market)
    if row is None:
        out["message"] = "No stored snapshot to patch. Run a full 'Refresh live & save' for this market first."
        return out

    new_payload, comp = _apply_x_to_stored_payload(row.payload, x_rep)
    snap_date = date.fromisoformat(str(new_payload.get("snapshot_date", row.snapshot_date)))
    idx = new_payload.get("index") or {}
    upsert_daily_snapshot(
        db,
        snap_date,
        new_payload,
        float(comp.score_0_100) if comp.score_0_100 is not None else None,
        float(idx["close"]) if idx.get("close") is not None else None,
        float(idx["pct_change"]) if idx.get("pct_change") is not None else None,
        market_id=market,
    )
    out["persisted"] = True
    out["message"] = f"Patched latest stored snapshot for {market} (snapshot_date={snap_date}) with new X data and composite."
    out["snapshot_date"] = str(snap_date)
    return out
