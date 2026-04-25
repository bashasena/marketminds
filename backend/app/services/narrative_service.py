"""Auto-generated headlines and one-line interpretations for the dashboard."""

from __future__ import annotations

from app.services.composite_sentiment import CompositeResult


def dashboard_title(composite: CompositeResult, nifty_pct: float | None) -> str:
    p = nifty_pct or 0.0
    s = composite.score_0_100
    if p >= 0.6 and s >= 62:
        return "Bulls Reclaim Control"
    if p <= -0.6 and s <= 42:
        return "Bears Press Their Advantage"
    if abs(p) < 0.25 and 45 <= s <= 55:
        return "Range-Bound Session"
    if p >= 0.35 and s < 55:
        return "Cautious Green: Tape Up, Mood Mixed"
    if p <= -0.35 and s > 55:
        return "Dip Buyers Lurking"
    if s >= 60:
        return "Constructive Tone Despite the Tape"
    if s <= 40:
        return "Defensive Positioning Dominates"
    return "Balanced Risk-On / Risk-Off"


def index_narrative(
    pct: float | None,
    high: float | None,
    low: float | None,
    close: float | None,
    index_name: str = "Nifty",
) -> str:
    if pct is None or close is None:
        return "Index data unavailable for narrative."
    direction = "higher" if pct > 0 else "lower" if pct < 0 else "flat"
    rng = ""
    if high and low:
        rng = f" Day range {low:,.0f}–{high:,.0f}."
    return f"{index_name} finished {direction} by {abs(pct):.2f}% at {close:,.2f}.{rng}"


def pivot_note(close: float | None, pivot: float | None) -> str:
    if close is None or pivot is None:
        return "Awaiting reliable spot vs pivot for positioning read."
    if close > pivot * 1.001:
        return "Trading above pivot confirms short-term bullish momentum vs prior balance."
    if close < pivot * 0.999:
        return "Below pivot: intraday bias leans fragile; watch reclaim for longs."
    return "Around pivot: equilibrium zone — breaks either side may trend."


def fii_note(fii: float | None, dii: float | None) -> str:
    if fii is None and dii is None:
        return "FII/DII flow data not available."
    parts = []
    if fii is not None:
        parts.append(f"FII net {'bought' if fii >= 0 else 'sold'} ~{abs(fii):,.0f} cr")
    if dii is not None:
        parts.append(f"DII net {'bought' if dii >= 0 else 'sold'} ~{abs(dii):,.0f} cr")
    return "; ".join(parts) + "."


def options_note(pcr: float | None, put_wall: float | None, call_wall: float | None) -> str:
    if pcr is None:
        return "Options skew unavailable."
    skew = "elevated put interest" if pcr > 1.1 else "call-heavy OI" if pcr < 0.85 else "balanced OI"
    walls = ""
    if put_wall and call_wall:
        walls = f" Max put OI {put_wall:,.0f} vs max call OI {call_wall:,.0f}."
    return f"PCR (OI) at {pcr:.2f} suggests {skew}.{walls}"


def global_note(gift_pct: float | None, us_pct: float | None) -> str:
    g = f"GIFT proxy {gift_pct:+.2f}% " if gift_pct is not None else ""
    u = f"US tech {us_pct:+.2f}%." if us_pct is not None else ""
    if not g and not u:
        return "Global cues unavailable."
    return (g + u).strip()
