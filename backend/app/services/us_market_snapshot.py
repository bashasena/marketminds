"""US broad-market snapshot (S&P 500 headline, VIX, pivots, global panel) — Yahoo Finance–first."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.services.composite_sentiment import compute_composite
from app.services.fii_dii_service import FiiDiiSnapshot
from app.services.global_markets_service import TickerBar, fetch_global_cues_usd
from app.services.market_snapshot import _bar_dict
from app.services.narrative_service import (
    dashboard_title,
    global_note,
    index_narrative,
    options_note,
    pivot_note,
)
from app.services.options_service import fetch_nifty_options_snapshot
from app.services.technical_levels import (
    build_pivot_from_yahoo_chart_api,
    build_pivot_from_yfinance,
)
from app.services.us_index_service import fetch_sp500_style_snapshot
from app.services.vix_service import fetch_vix_reading
from app.services.x_sentiment_service import build_x_sentiment_report

logger = logging.getLogger(__name__)


def _us_fii_note() -> str:
    return "FII / DII is an India (NSE) series in ₹ crore — omitted in the US (USD) snapshot."


def _us_global_note() -> str:
    return "US session strip: Dow, NASDAQ, COMEX gold, WTI, ICE dollar index — all USD-quoted (no India spot or rupee crosses in this view)."


def build_us_snapshot(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    data_warnings: list[str] = []

    idx = fetch_sp500_style_snapshot(top_n=5)
    if idx.close is None:
        data_warnings.append(
            "us_gspc: headline index unavailable (^GSPC, SPY, IVV, VOO) — allow outbound HTTPS to "
            "query1.finance.yahoo.com and query2.finance.yahoo.com (Yahoo v8 chart + yfinance both failed)"
        )

    pivot_sym = (idx.raw_index_meta or {}).get("headline") or "^GSPC"
    pivot_candidates: list[str] = []
    for s in (str(pivot_sym), "^GSPC", "SPY", "IVV"):
        if s and s not in pivot_candidates:
            pivot_candidates.append(s)
    pivots = None
    for s in pivot_candidates:
        pivots = build_pivot_from_yahoo_chart_api(s)
        if pivots is not None:
            break
    if pivots is None:
        for s in pivot_candidates:
            pivots = build_pivot_from_yfinance(s)
            if pivots is not None:
                break
    vix = fetch_vix_reading("^VIX")
    if vix.last is None:
        vix = fetch_vix_reading("VIXY")
    fii_india = FiiDiiSnapshot(as_of_date=None, fii_net_crores=None, dii_net_crores=None, raw=[])
    opts = fetch_nifty_options_snapshot("SPY", ref_date=idx.as_of or date.today())
    try:
        globals_map = fetch_global_cues_usd(
            settings.yfin_us_dow_symbol,
            settings.yfin_us_index_symbol,
            settings.yfin_gold_futures,
            settings.yfin_crude_symbol,
            settings.yfin_dollar_index_symbol,
        )
    except Exception as e:
        logger.warning("Global fetch (US snapshot): %s", e)
        data_warnings.append(f"global_markets: {e}")
        stub = TickerBar(symbol="-", label="Unavailable", last=None, pct_change=None, currency="USD")
        globals_map = {k: stub for k in ("dow", "us_index", "gold_usd_oz", "crude_wti", "dollar_index")}

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
        None,
        x_rep.aggregate_score_0_100,
    )

    spot = idx.close or None
    pivot_val = pivots.pivot if pivots else None

    snap_date = idx.as_of or date.today()
    payload: dict[str, Any] = {
        "snapshot_date": str(snap_date),
        "generated_at_utc": None,
        "header": {
            "title": dashboard_title(composite, idx.pct_change),
            "date": str(snap_date),
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
                idx.pct_change,
                idx.high,
                idx.low,
                idx.close,
                index_name="S&P 500",
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
            "as_of": str(fii_india.as_of_date) if fii_india.as_of_date else None,
            "fii_net_crores": fii_india.fii_net_crores,
            "dii_net_crores": fii_india.dii_net_crores,
            "note": _us_fii_note(),
        },
        "options": {
            "symbol": opts.symbol,
            "expiry": opts.expiry,
            "pcr_oi": opts.pcr_oi,
            "call_oi_total": opts.total_call_oi,
            "put_oi_total": opts.total_put_oi,
            "resistance_strike_call_oi": opts.max_call_oi_strike,
            "support_strike_put_oi": opts.max_put_oi_strike,
            "note": options_note(opts.pcr_oi, opts.max_put_oi_strike, opts.max_call_oi_strike)
            or "NSE options chain is India-specific; US options readout not wired.",
        },
        "global": {k: _bar_dict(v) for k, v in globals_map.items()},
        "global_note": _us_global_note(),
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
            "market_id": "us_broad",
            "yfin_sp500": "^GSPC",
            "data_warnings": list(data_warnings),
            "ui": {
                "index_title": "S&P 500",
                "index_subtitle": "Cash / ETF proxy (Yahoo Finance; chart API fallback)",
                "breadth_subtitle": "Mega-cap sample (24 names)",
                "movers_subtitle": "Largest sample moves",
                "vix_line": "Cboe VIX (US)",
                "fii_title": "FII / DII (India only — not used here)",
                "show_fii_card": False,
                "global_subtitle": "US indexes & dollar futures (USD only)",
            },
        },
    }
    # X optional: keep only under x_sentiment_summary.error so the banner is not mixed with data issues
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    return payload
