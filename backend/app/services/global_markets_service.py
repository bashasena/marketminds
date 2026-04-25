"""Global indices, GIFT proxy, and commodities via yfinance."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass

import yfinance as yf

from app.services.nifty_indices_history import fetch_last_close_and_pct_change
from app.services.yahoo_chart_bars import chart_last_and_pct

logger = logging.getLogger(__name__)

# Yahoo often throttles or returns empty from Docker; cap wait per symbol so the request can finish.
_YF_PER_SYMBOL_SEC = 14.0
_NIFTYINDICES_GIFT_SEC = 20.0


@dataclass
class TickerBar:
    symbol: str
    label: str
    last: float | None
    pct_change: float | None
    currency: str | None = None


def _last_and_pct(symbol: str) -> tuple[float | None, float | None]:
    a = chart_last_and_pct(symbol)
    if a is not None and a[0] is not None:
        return a
    t = yf.Ticker(symbol)
    hist = t.history(period="8d", interval="1d")
    if hist is None or hist.empty:
        return (None, None)
    last = float(hist["Close"].iloc[-1])
    if len(hist) >= 2:
        prev = float(hist["Close"].iloc[-2])
        pct = (last - prev) / prev * 100.0 if prev else None
    else:
        pct = None
    return last, pct


def _fetch_gift_niftyindices_fallback() -> tuple[float | None, float | None, str]:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fetch_last_close_and_pct_change, "NIFTY 50")
        try:
            a, b = fut.result(timeout=_NIFTYINDICES_GIFT_SEC)
            return a, b, "GIFT proxy (Nifty EOD via niftyindices)"
        except (FutureTimeout, Exception) as e:
            if not isinstance(e, FutureTimeout):
                logger.debug("niftyindices gift fallback: %s", e)
            return None, None, "GIFT Nifty (proxy)"


def fetch_global_cues(
    gift_symbol: str,
    us_index_symbol: str,
    gold_fut: str,
    usd_inr: str,
    crude_symbol: str,
    *,
    allow_niftyindices_gift_fallback: bool = True,
) -> dict[str, TickerBar]:
    # Low concurrency: Yahoo chart (used first) can return 429 if too many parallel GETs.
    yf_args = (gift_symbol, us_index_symbol, gold_fut, usd_inr, crude_symbol)
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_last_and_pct, s) for s in yf_args]
        results = []
        for f in futs:
            try:
                results.append(f.result(timeout=_YF_PER_SYMBOL_SEC))
            except (FutureTimeout, Exception) as e:
                if not isinstance(e, FutureTimeout):
                    logger.debug("parallel yf batch: %s", e)
                results.append((None, None))
    (gift_last, gift_pct) = results[0]
    (us_last, us_pct) = results[1]
    (gold_usd, gold_pct) = results[2]
    (inr, _) = results[3]
    (crude, crude_pct) = results[4]

    gift_label = "GIFT Nifty (proxy)"
    if gift_last is None and allow_niftyindices_gift_fallback:
        gift_last, gift_pct, gift_label = _fetch_gift_niftyindices_fallback()

    gold_inr_per_10g: float | None = None
    if gold_usd and inr:
        # Approx COMEX USD/oz to INR per 10g: (USD/oz) * INR/USD / 31.1035 * 10
        gold_inr_per_10g = gold_usd * inr / 31.1035 * 10.0

    return {
        "gift_nifty": TickerBar(
            symbol=gift_symbol,
            label=gift_label,
            last=gift_last,
            pct_change=gift_pct,
        ),
        "us_index": TickerBar(
            symbol=us_index_symbol,
            label="NASDAQ" if "IXIC" in us_index_symbol else "US Index",
            last=us_last,
            pct_change=us_pct,
        ),
        "gold_usd_oz": TickerBar(
            symbol=gold_fut,
            label="Gold (COMEX USD/oz)",
            last=gold_usd,
            pct_change=gold_pct,
            currency="USD",
        ),
        "gold_inr_est_10g": TickerBar(
            symbol="derived",
            label="Gold est. (INR / 10g)",
            last=gold_inr_per_10g,
            pct_change=None,
            currency="INR",
        ),
        "crude_wti": TickerBar(
            symbol=crude_symbol,
            label="Crude WTI",
            last=crude,
            pct_change=crude_pct,
            currency="USD",
        ),
        "usd_inr": TickerBar(
            symbol=usd_inr,
            label="USD/INR",
            last=inr,
            pct_change=None,
            currency="INR",
        ),
    }


def fetch_global_cues_usd(
    dow_symbol: str,
    us_index_symbol: str,
    gold_fut: str,
    crude_symbol: str,
    dollar_index_symbol: str,
) -> dict[str, TickerBar]:
    """
    US dashboard strip: all USD-quoted (spot/futures) — no Nifty/GIFT, no INR pair, no INR gold.
    """
    yf_args = (dow_symbol, us_index_symbol, gold_fut, crude_symbol, dollar_index_symbol)
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_last_and_pct, s) for s in yf_args]
        results: list[tuple[float | None, float | None]] = []
        for f in futs:
            try:
                results.append(f.result(timeout=_YF_PER_SYMBOL_SEC))
            except (FutureTimeout, Exception) as e:
                if not isinstance(e, FutureTimeout):
                    logger.debug("parallel usd global: %s", e)
                results.append((None, None))
    (dow_last, dow_pct) = results[0]
    (us_last, us_pct) = results[1]
    (gold_usd, gold_pct) = results[2]
    (crude, crude_pct) = results[3]
    (dxy_last, dxy_pct) = results[4]

    us_lbl = "NASDAQ" if "IXIC" in us_index_symbol else "US index"
    dxy_lbl = "Dollar index (ICE)"
    if "UUP" in dollar_index_symbol.upper():
        dxy_lbl = "USD strength (UUP proxy)"

    return {
        "dow": TickerBar(
            symbol=dow_symbol,
            label="Dow Jones",
            last=dow_last,
            pct_change=dow_pct,
            currency="USD",
        ),
        "us_index": TickerBar(
            symbol=us_index_symbol,
            label=us_lbl,
            last=us_last,
            pct_change=us_pct,
            currency="USD",
        ),
        "gold_usd_oz": TickerBar(
            symbol=gold_fut,
            label="Gold (COMEX USD/oz)",
            last=gold_usd,
            pct_change=gold_pct,
            currency="USD",
        ),
        "crude_wti": TickerBar(
            symbol=crude_symbol,
            label="Crude WTI (USD/bbl)",
            last=crude,
            pct_change=crude_pct,
            currency="USD",
        ),
        "dollar_index": TickerBar(
            symbol=dollar_index_symbol,
            label=dxy_lbl,
            last=dxy_last,
            pct_change=dxy_pct,
            currency="USD",
        ),
    }
