"""Global indices, GIFT proxy, and commodities via yfinance."""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from app.services.nifty_indices_history import fetch_last_close_and_pct_change


@dataclass
class TickerBar:
    symbol: str
    label: str
    last: float | None
    pct_change: float | None
    currency: str | None = None


def _last_and_pct(symbol: str) -> tuple[float | None, float | None]:
    t = yf.Ticker(symbol)
    hist = t.history(period="8d", interval="1d")
    if hist is None or hist.empty:
        return None, None
    last = float(hist["Close"].iloc[-1])
    if len(hist) >= 2:
        prev = float(hist["Close"].iloc[-2])
        pct = (last - prev) / prev * 100.0 if prev else None
    else:
        pct = None
    return last, pct


def fetch_global_cues(
    gift_symbol: str,
    us_index_symbol: str,
    gold_fut: str,
    usd_inr: str,
    crude_symbol: str,
) -> dict[str, TickerBar]:
    gift_last, gift_pct = _last_and_pct(gift_symbol)
    gift_label = "GIFT Nifty (proxy)"
    if gift_last is None:
        # Yahoo often fails from Docker; NIFTY EOD from niftyindices.com is a usable spot proxy
        gift_last, gift_pct = fetch_last_close_and_pct_change("NIFTY 50")
        gift_label = "GIFT proxy (Nifty EOD via niftyindices)"
    us_last, us_pct = _last_and_pct(us_index_symbol)
    gold_usd, gold_pct = _last_and_pct(gold_fut)
    inr, _ = _last_and_pct(usd_inr)
    crude, crude_pct = _last_and_pct(crude_symbol)

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
