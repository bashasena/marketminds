"""X (Twitter) List sentiment: fetch tweets, FinBERT scoring, ticker aggregation."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(
    r"\b(NIFTY|BANKNIFTY|FINNIFTY|SENSEX|RELIANCE|TCS|HDFCBANK|INFY|ICICIBANK|SBIN|LT)\b",
    re.IGNORECASE,
)


@dataclass
class TweetSentiment:
    tweet_id: str
    text: str
    score_0_100: float
    label: str
    tickers: list[str]


@dataclass
class XSentimentReport:
    list_id: str | None
    tweet_count: int
    aggregate_score_0_100: float
    per_ticker: dict[str, float]
    samples: list[TweetSentiment]
    model_used: str
    error: str | None = None


_finbert_pipe = None


def _get_finbert_pipeline(model_name: str):
    global _finbert_pipe
    if os.environ.get("DISABLE_FINBERT", "").lower() in ("1", "true", "yes"):
        return None
    if _finbert_pipe is None:
        try:
            from transformers import pipeline

            _finbert_pipe = pipeline("sentiment-analysis", model=model_name, tokenizer=model_name)
        except Exception as e:
            logger.warning("FinBERT unavailable, using lexical fallback: %s", e)
            _finbert_pipe = False
    return _finbert_pipe if _finbert_pipe is not False else None


def _lexical_sentiment(text: str) -> tuple[float, str]:
    t = text.upper()
    pos = sum(t.count(w) for w in ("BULL", "LONG", "BUY", "UPSIDE", "BREAKOUT", "RALLY"))
    neg = sum(t.count(w) for w in ("BEAR", "SHORT", "SELL", "DOWN", "CRASH", "GAP DOWN"))
    raw = 50.0 + (pos - neg) * 8.0
    raw = max(0.0, min(100.0, raw))
    label = "neutral"
    if raw >= 60:
        label = "positive"
    elif raw <= 40:
        label = "negative"
    return raw, label


def _finbert_score(text: str, model_name: str) -> tuple[float, str]:
    pipe = _get_finbert_pipeline(model_name)
    if pipe is None:
        return _lexical_sentiment(text)
    try:
        out = pipe(text[:512])[0]
        lab = str(out.get("label", "")).lower()
        score = float(out.get("score", 0.5))
        if lab == "positive":
            s = 50 + score * 50
        elif lab == "negative":
            s = 50 - score * 50
        else:
            s = 50.0
        s = max(0.0, min(100.0, s))
        return s, lab
    except Exception as e:
        logger.debug("FinBERT inference failed: %s", e)
        return _lexical_sentiment(text)


def fetch_list_tweets(bearer: str, list_id: str, max_results: int = 100) -> list[dict[str, Any]]:
    url = f"https://api.twitter.com/2/lists/{list_id}/tweets"
    headers = {"Authorization": f"Bearer {bearer}"}
    params = {
        "max_results": min(max_results, 100),
        "tweet.fields": "created_at,lang,referenced_tweets",
    }
    tweets: list[dict[str, Any]] = []
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        tweets.extend(data.get("data", []) or [])
    return tweets


def build_x_sentiment_report(
    bearer: str | None,
    list_id: str | None,
    lookback_hours: int,
    max_tweets: int,
    model_name: str,
) -> XSentimentReport:
    if not bearer or not list_id:
        return XSentimentReport(
            list_id=list_id,
            tweet_count=0,
            aggregate_score_0_100=50.0,
            per_ticker={},
            samples=[],
            model_used="none",
            error="XBEARER_TOKEN or X_LIST_ID not configured",
        )
    try:
        tweets = fetch_list_tweets(bearer, list_id, max_results=max_tweets)
    except Exception as e:
        logger.warning("X API list fetch failed: %s", e)
        return XSentimentReport(
            list_id=list_id,
            tweet_count=0,
            aggregate_score_0_100=50.0,
            per_ticker={},
            samples=[],
            model_used=model_name,
            error=str(e),
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    scored: list[TweetSentiment] = []
    ticker_scores: dict[str, list[float]] = {}
    for tw in tweets:
        created = tw.get("created_at")
        if created:
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except ValueError:
                pass
        text = tw.get("text") or ""
        tid = str(tw.get("id"))
        s, lab = _finbert_score(text, model_name)
        tickers = sorted({m.group(1).upper() for m in TICKER_RE.finditer(text)})
        scored.append(TweetSentiment(tweet_id=tid, text=text, score_0_100=s, label=lab, tickers=tickers))
        for tk in tickers:
            ticker_scores.setdefault(tk, []).append(s)

    if not scored:
        agg = 50.0
    else:
        agg = sum(t.score_0_100 for t in scored) / len(scored)
    per_ticker = {k: sum(v) / len(v) for k, v in ticker_scores.items()}
    pipe = _get_finbert_pipeline(model_name)
    model_used = model_name if pipe else "lexical-fallback"
    return XSentimentReport(
        list_id=list_id,
        tweet_count=len(scored),
        aggregate_score_0_100=round(agg, 2),
        per_ticker={k: round(v, 2) for k, v in sorted(per_ticker.items(), key=lambda x: -len(ticker_scores[x[0]]))},
        samples=scored[:15],
        model_used=model_used,
        error=None,
    )
