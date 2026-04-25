"""Nifty index options: PCR and OI walls from NSE option chain."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.nse_client import get_nse_client

logger = logging.getLogger(__name__)


@dataclass
class OptionsSnapshot:
    symbol: str
    expiry: str | None
    pcr_oi: float | None
    total_call_oi: float
    total_put_oi: float
    max_call_oi_strike: float | None
    max_put_oi_strike: float | None
    spot: float | None
    raw_expiry_dates: list[str]


def _pick_nearest_expiry(dates: list[str], ref: date) -> str | None:
    if not dates:
        return None
    parsed: list[tuple[date, str]] = []
    for d in dates:
        try:
            parsed.append((datetime_parse(d), d))
        except Exception:
            continue
    if not parsed:
        return dates[0]
    parsed.sort(key=lambda x: abs((x[0] - ref).days))
    return parsed[0][1]


def datetime_parse(s: str) -> date:
    from datetime import datetime

    return datetime.strptime(s[:10], "%d-%b-%Y").date()


def fetch_nifty_options_snapshot(symbol: str = "NIFTY", ref_date: date | None = None) -> OptionsSnapshot:
    ref = ref_date or date.today()
    try:
        nse = get_nse_client()
        data = nse.get_json("/api/option-chain-indices", params={"symbol": symbol})
    except Exception as e:
        logger.warning("NSE option chain unavailable for %s: %s", symbol, e)
        return OptionsSnapshot(
            symbol=symbol,
            expiry=None,
            pcr_oi=None,
            total_call_oi=0.0,
            total_put_oi=0.0,
            max_call_oi_strike=None,
            max_put_oi_strike=None,
            spot=None,
            raw_expiry_dates=[],
        )
    records = data.get("records", {}) or {}
    exp_dates = records.get("expiryDates") or []
    expiry = _pick_nearest_expiry(exp_dates, ref)
    total_ce_oi = 0.0
    total_pe_oi = 0.0
    max_ce_strike: float | None = None
    max_ce_val = -1.0
    max_pe_strike: float | None = None
    max_pe_val = -1.0
    spot = None
    underlying = records.get("underlyingValue")
    if underlying is not None:
        try:
            spot = float(underlying)
        except (TypeError, ValueError):
            spot = None

    for row in records.get("data", []) or []:
        ed = row.get("expiryDate")
        if expiry and ed and str(ed) != str(expiry):
            continue
        ce = row.get("CE") or {}
        pe = row.get("PE") or {}
        strike = row.get("strikePrice")
        try:
            k = float(strike)
        except (TypeError, ValueError):
            continue
        ce_oi = float(ce.get("openInterest") or 0)
        pe_oi = float(pe.get("openInterest") or 0)
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi
        if ce_oi > max_ce_val:
            max_ce_val = ce_oi
            max_ce_strike = k
        if pe_oi > max_pe_val:
            max_pe_val = pe_oi
            max_pe_strike = k

    pcr = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else None
    return OptionsSnapshot(
        symbol=symbol,
        expiry=str(expiry) if expiry else None,
        pcr_oi=pcr,
        total_call_oi=total_ce_oi,
        total_put_oi=total_pe_oi,
        max_call_oi_strike=max_ce_strike,
        max_put_oi_strike=max_pe_strike,
        spot=spot,
        raw_expiry_dates=[str(x) for x in exp_dates[:8]],
    )
