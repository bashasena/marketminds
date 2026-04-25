"""Market-scoped headlines via public RSS (Google News search), no API key."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Tuned search queries; swap for dedicated RSS later.
NEWS_RSS_BY_MARKET: dict[str, str] = {
    "in_nifty": "https://news.google.com/rss/search?q=NIFTY+India+stock+market&hl=en-IN&gl=IN&ceid=IN:en",
    "us_broad": "https://news.google.com/rss/search?q=US+stock+market+S%26P+500&hl=en-US&gl=US&ceid=US:en",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
}


def _parse_rss_items(xml_text: str, limit: int) -> list[dict[str, Any]]:
    text = xml_text.lstrip("\ufeff").strip()
    root = ET.fromstring(text)
    out: list[dict[str, Any]] = []
    for item in root.iter("item"):
        if len(out) >= limit:
            break
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
        source: str | None = None
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            if len(parts) == 2 and len(parts[1]) < 80:
                source = parts[1].strip()
                title = parts[0].strip()
        if title and link:
            out.append({"title": title, "url": link, "published_at": pub or None, "source": source})
    return out


def fetch_market_news(market_id: str, limit: int = 12) -> tuple[list[dict[str, Any]], str | None]:
    """
    Returns (items, error_message). Items may be empty on failure.
    """
    url = NEWS_RSS_BY_MARKET.get(market_id)
    if not url:
        return [], f"unknown market: {market_id}"
    try:
        with httpx.Client(timeout=20.0, headers=_HEADERS, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
        items = _parse_rss_items(r.text, max(1, min(limit, 30)))
        return items, None
    except Exception as e:
        logger.warning("news fetch/parse failed for %s: %s", market_id, e)
        return [], str(e)
