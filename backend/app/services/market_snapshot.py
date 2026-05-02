"""Orchestrates all data sources into a single JSON-serializable snapshot."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.composite_sentiment import compute_composite
from app.services.fii_dii_service import fetch_fii_dii
from app.services.global_markets_service import TickerBar, fetch_global_cues
from app.services.index_service import fetch_nifty50_snapshot_resilient
from app.services.narrative_service import (
    dashboard_title,
    fii_note,
    global_note,
    index_narrative,
    pivot_note,
)
from app.services.options_service import (
    enrich_options_with_history,
    fetch_nifty_options_snapshot,
    options_snapshot_to_api_dict,
)
from app.services.technical_levels import build_pivot_from_yfinance_or_niftyindices
from app.services.vix_service import fetch_india_vix
from app.services.x_sentiment_service import build_x_sentiment_report

logger = logging.getLogger(__name__)


def _bar_dict(b) -> dict[str, Any]:
    return {"symbol": b.symbol, "label": b.label, "last": b.last, "pct_change": b.pct_change, "currency": b.currency}


def build_snapshot(settings: Settings | None = None, db: Session | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    data_warnings: list[str] = []

    idx, idx_err = fetch_nifty50_snapshot_resilient(
        settings.primary_index,
        settings.yfin_nifty_symbol,
        top_n=5,
    )
    if idx_err:
        data_warnings.append(f"nifty_breadth_nse: {idx_err}")

    pivots = build_pivot_from_yfinance_or_niftyindices(
        settings.yfin_nifty_symbol,
        niftyindices_index_name=settings.primary_index,
    )
    vix = fetch_india_vix(settings.yfin_vix_symbol)
    fii = fetch_fii_dii()
    opts = fetch_nifty_options_snapshot(settings.nifty_options_symbol, ref_date=idx.as_of or date.today())
    opts = enrich_options_with_history(db, "in_nifty", opts, record_tick=db is not None)
    if opts.pcr_oi is None and (opts.total_call_oi + opts.total_put_oi) == 0:
        data_warnings.append(
            "nifty_options: no OI/PCR — NSE returned an empty option chain (typical if the API host is "
            "outside India, blocked, or session rejected). Run the backend from an Indian network or VPN, "
            "or verify the NSE option-chain API returns a non-empty 'records' object from the same host."
        )
    try:
        globals_map = fetch_global_cues(
            settings.yfin_gift_symbol,
            settings.yfin_us_index_symbol,
            settings.yfin_gold_futures,
            settings.yfin_usd_inr,
            settings.yfin_crude_symbol,
        )
    except Exception as e:
        logger.warning("Global / commodity yfinance fetch failed: %s", e)
        data_warnings.append(f"global_markets: {e}")
        stub = TickerBar(symbol="-", label="Unavailable", last=None, pct_change=None)
        globals_map = {k: stub for k in ("gift_nifty", "us_index", "gold_usd_oz", "gold_inr_est_10g", "crude_wti", "usd_inr")}
    x_rep = build_x_sentiment_report(
        settings.x_bearer_token,
        settings.x_list_id,
        settings.x_tweet_lookback_hours,
        settings.x_max_tweets,
        settings.finbert_model,
    )
    composite = compute_composite(
        idx.pct_change,
        vix.last,
        vix.pct_change,
        opts.pcr_oi,
        fii.fii_net_crores,
        x_rep.aggregate_score_0_100,
    )

    spot = idx.close or opts.spot
    pivot_val = pivots.pivot if pivots else None

    payload: dict[str, Any] = {
        "snapshot_date": str(idx.as_of or date.today()),
        "generated_at_utc": None,
        "header": {
            "title": dashboard_title(composite, idx.pct_change),
            "date": str(idx.as_of or date.today()),
        },
        "index": {
            "name": idx.index_name,
            "open": idx.open,
            "high": idx.high,
            "low": idx.low,
            "close": idx.close,
            "pct_change": idx.pct_change,
            "advances": idx.advances,
            "declines": idx.declines,
            "unchanged": idx.unchanged,
            "narrative": index_narrative(
                idx.pct_change, idx.high, idx.low, idx.close, index_name=idx.index_name or "Nifty 50"
            ),
        },
        "breadth": {
            "advances": idx.advances,
            "declines": idx.declines,
            "unchanged": idx.unchanged,
        },
        "top_movers": {
            "gainers": [asdict(g) for g in idx.top_gainers],
            "losers": [asdict(l) for l in idx.top_losers],
        },
        "technical": {
            "pivot": pivot_val,
            "s1": pivots.s1 if pivots else None,
            "s2": pivots.s2 if pivots else None,
            "r1": pivots.r1 if pivots else None,
            "r2": pivots.r2 if pivots else None,
            "prev_ohlc": (
                {
                    "o": pivots.prev_open,
                    "h": pivots.prev_high,
                    "l": pivots.prev_low,
                    "c": pivots.prev_close,
                }
                if pivots
                else None
            ),
            "note": pivot_note(spot, pivot_val),
        },
        "vix": {"level": vix.last, "pct_change": vix.pct_change},
        "fii_dii": {
            "as_of": str(fii.as_of_date) if fii.as_of_date else None,
            "fii_net_crores": fii.fii_net_crores,
            "dii_net_crores": fii.dii_net_crores,
            "note": fii_note(fii.fii_net_crores, fii.dii_net_crores),
        },
        "options": options_snapshot_to_api_dict(opts),
        "global": {k: _bar_dict(v) for k, v in globals_map.items()},
        "global_note": global_note(
            globals_map["gift_nifty"].pct_change,
            globals_map["us_index"].pct_change,
        ),
        "composite": {
            "score_0_100": composite.score_0_100,
            "label": composite.label,
            "components": composite.components,
            "weights": composite.weights,
            "explanation": composite.explanation,
        },
        "x_sentiment_summary": {
            "aggregate_0_100": x_rep.aggregate_score_0_100,
            "tweet_count": x_rep.tweet_count,
            "model": x_rep.model_used,
            "error": x_rep.error,
        },
        "meta": {
            "market_id": "in_nifty",
            "yfin_nifty": settings.yfin_nifty_symbol,
            "data_warnings": list(data_warnings),
            "ui": {
                "index_title": "Nifty 50",
                "index_subtitle": "Cash index",
                "breadth_subtitle": "Nifty 50 constituents",
                "movers_subtitle": "Nifty 50",
                "vix_line": "India VIX",
                "fii_title": "FII / DII (cash)",
            },
        },
    }
    if x_rep.error:
        payload["meta"]["data_warnings"].append(x_rep.error)

    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    return payload


def x_sentiment_detail(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    rep = build_x_sentiment_report(
        settings.x_bearer_token,
        settings.x_list_id,
        settings.x_tweet_lookback_hours,
        settings.x_max_tweets,
        settings.finbert_model,
    )
    return {
        "list_id": rep.list_id,
        "tweet_count": rep.tweet_count,
        "aggregate_0_100": rep.aggregate_score_0_100,
        "per_ticker": rep.per_ticker,
        "model": rep.model_used,
        "error": rep.error,
        "samples": [
            {
                "tweet_id": t.tweet_id,
                "text": t.text,
                "score_0_100": t.score_0_100,
                "label": t.label,
                "tickers": t.tickers,
            }
            for t in rep.samples
        ],
    }
