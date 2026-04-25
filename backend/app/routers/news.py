"""Market news feed (RSS-backed)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services.news_feed_service import NEWS_RSS_BY_MARKET, fetch_market_news

router = APIRouter(prefix="/news", tags=["news"])


@router.get("")
def market_news(
    market: str = Query("in_nifty", description="Market id: in_nifty | us_broad"),
    limit: int = Query(12, ge=1, le=30),
) -> dict[str, Any]:
    if market not in NEWS_RSS_BY_MARKET:
        return {
            "market": market,
            "items": [],
            "error": f"unsupported market {market!r}; use one of: {', '.join(sorted(NEWS_RSS_BY_MARKET))}",
        }
    items, err = fetch_market_news(market, limit=limit)
    return {"market": market, "items": items, "error": err}
