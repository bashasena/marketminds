"""
ATM-focused option analytics: PCR on ATM±N band, active-strike OI walls,
incremental OI, aggression (volume × ΔOI), and rolling PCR windows.

Designed for index / ETF option chains with discrete strikes (Nifty, SPY, QQQ).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Active strike band width (index / underlying points from ATM strike)
ACTIVE_BAND_POINTS_DEFAULT = 500.0
TOP_VOLUME_STRIKES = 20
ATM_WIDTH_STRIKES = 3  # ATM-3 … ATM+3 → 7 strikes when available
ROLLING_WINDOW_MINUTES = 15


@dataclass(frozen=True)
class StrikeLegs:
    strike: float
    call_oi: float
    put_oi: float
    call_vol: float = 0.0
    put_vol: float = 0.0
    call_oi_chg: float = 0.0
    put_oi_chg: float = 0.0


def unique_sorted_strikes(rows: Sequence[StrikeLegs]) -> list[float]:
    return sorted({r.strike for r in rows})


def get_atm_strike(spot: float | None, strikes: Sequence[float]) -> float | None:
    """Strike nearest to underlying spot (fallback: median strike if spot unknown)."""
    s = [float(x) for x in strikes if x is not None]
    if not s:
        return None
    u = sorted(set(s))
    if spot is None:
        return float(u[len(u) // 2])
    return float(min(u, key=lambda k: abs(k - float(spot))))


def get_atm_band_strikes(sorted_strikes: Sequence[float], atm: float, width: int = ATM_WIDTH_STRIKES) -> list[float]:
    """
    Select up to ``2*width+1`` strikes centered on the strike **nearest** to ``atm``
    in the chain (ATM±width by strike ladder index, not numeric ±width points).
    """
    u = sorted({float(x) for x in sorted_strikes})
    if not u:
        return []
    atm_i = min(range(len(u)), key=lambda i: abs(u[i] - atm))
    lo = max(0, atm_i - width)
    hi = min(len(u) - 1, atm_i + width)
    return u[lo : hi + 1]


def compute_pcr_atm(rows_by_strike: dict[float, StrikeLegs], band_strikes: Sequence[float]) -> float | None:
    """PCR on ATM band only: sum(put OI) / sum(call OI)."""
    ce = 0.0
    pe = 0.0
    for k in band_strikes:
        r = rows_by_strike.get(float(k))
        if not r:
            continue
        ce += max(0.0, r.call_oi)
        pe += max(0.0, r.put_oi)
    if ce <= 0:
        return None
    return pe / ce


def compute_active_strikes(
    rows: Sequence[StrikeLegs],
    atm: float,
    *,
    band_points: float = ACTIVE_BAND_POINTS_DEFAULT,
    top_n_volume: int = TOP_VOLUME_STRIKES,
) -> set[float]:
    """
    Active strikes = {ATM ± band_points} ∪ {top ``top_n_volume`` strikes by (call_vol + put_vol)}.
    """
    active: set[float] = set()
    vol_rank: list[tuple[float, float]] = []
    for r in rows:
        k = float(r.strike)
        if abs(k - atm) <= band_points:
            active.add(k)
        vol_rank.append((k, max(0.0, r.call_vol) + max(0.0, r.put_vol)))
    vol_rank.sort(key=lambda x: x[1], reverse=True)
    for k, _ in vol_rank[:top_n_volume]:
        active.add(float(k))
    return active


def compute_oi_walls(
    rows_by_strike: dict[float, StrikeLegs],
    active_strikes: Iterable[float],
) -> tuple[float | None, float, float | None, float]:
    """Call wall / put wall = max OI strike among **active** strikes only."""
    act = {float(x) for x in active_strikes}
    max_ce_k: float | None = None
    max_ce_v = 0.0
    max_pe_k: float | None = None
    max_pe_v = 0.0
    for k in act:
        r = rows_by_strike.get(k)
        if not r:
            continue
        if r.call_oi > max_ce_v:
            max_ce_v = r.call_oi
            max_ce_k = k
        if r.put_oi > max_pe_v:
            max_pe_v = r.put_oi
            max_pe_k = k
    if max_ce_v <= 0:
        max_ce_k = None
    if max_pe_v <= 0:
        max_pe_k = None
    return max_ce_k, max_ce_v, max_pe_k, max_pe_v


def sum_band_oi(rows_by_strike: dict[float, StrikeLegs], band: Sequence[float]) -> tuple[float, float]:
    ce = 0.0
    pe = 0.0
    for k in band:
        r = rows_by_strike.get(float(k))
        if not r:
            continue
        ce += max(0.0, r.call_oi)
        pe += max(0.0, r.put_oi)
    return ce, pe


def compute_incremental_from_exchange(rows_by_strike: dict[float, StrikeLegs], band: Sequence[float]) -> tuple[float, float]:
    """Sum session ``changeinOpenInterest`` (or equivalent) on the ATM band — intraday incremental."""
    d_ce = 0.0
    d_pe = 0.0
    for k in band:
        r = rows_by_strike.get(float(k))
        if not r:
            continue
        d_ce += float(r.call_oi_chg)
        d_pe += float(r.put_oi_chg)
    return d_ce, d_pe


def compute_aggression(rows_by_strike: dict[float, StrikeLegs], strikes: Sequence[float]) -> tuple[float, float]:
    """
    Aggression = Σ (volume × ΔOI) per side on the given strikes (typically ATM band).
    Uses raw ΔOI (can be negative); volume is non‑negative.
    """
    call_agg = 0.0
    put_agg = 0.0
    for k in strikes:
        r = rows_by_strike.get(float(k))
        if not r:
            continue
        call_agg += max(0.0, r.call_vol) * float(r.call_oi_chg)
        put_agg += max(0.0, r.put_vol) * float(r.put_oi_chg)
    return call_agg, put_agg


def compute_rolling_pcr(
    db: Session | None,
    market_id: str,
    symbol: str,
    expiry: str | None,
    current_atm_put_oi: float,
    current_atm_call_oi: float,
    now: datetime | None = None,
    window_minutes: int = ROLLING_WINDOW_MINUTES,
) -> float | None:
    """
    PCR over **OI added** in the last ``window_minutes`` using stored ATM-band snapshots:

    (put_now - put_anchor) / (call_now - call_anchor)

    where anchor is the oldest tick in ``[now - window, now]`` (or None → no PCR).
    """
    if db is None:
        return None
    from app.repositories.option_oi_repo import get_oldest_tick_since

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    anchor = get_oldest_tick_since(db, market_id, symbol, expiry, window_start, now)
    if anchor is None:
        return None
    d_put = float(current_atm_put_oi) - float(anchor.atm_put_oi)
    d_call = float(current_atm_call_oi) - float(anchor.atm_call_oi)
    if d_call == 0:
        return None
    return d_put / d_call
