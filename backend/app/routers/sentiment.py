"""Sentiment drill-down routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.services.market_snapshot import x_sentiment_detail

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/x")
def sentiment_x() -> dict[str, Any]:
    return x_sentiment_detail(get_settings())
