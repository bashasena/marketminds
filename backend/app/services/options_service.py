"""Nifty index options: PCR and OI walls from NSE option chain."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from app.services.narrative_service import options_note

from app.services.nse_client import NSE_BASE, get_nse_client, reset_nse_client

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
    max_call_oi: float
    max_put_oi: float
    spot: float | None
    raw_expiry_dates: list[str]


def _pick_nearest_expiry(dates: list[str], ref: date) -> str | None:
    if not dates:
        return None
    parsed: list[tuple[date, str]] = []
    for d in dates:
        try:
            parsed.append((_parse_nse_expiry(d), d))
        except Exception:
            continue
    if not parsed:
        return dates[0]
    parsed.sort(key=lambda x: abs((x[0] - ref).days))
    return parsed[0][1]


def _parse_nse_expiry(s: str) -> date:
    """NSE returns e.g. ``25-Apr-2025`` (12 chars) — do not truncate the year."""
    from datetime import datetime

    t = (s or "").strip()
    for fmt, need in (("%d-%b-%Y", 12), ("%d-%B-%Y", 12), ("%d-%m-%Y", 10), ("%Y-%m-%d", 10)):
        if len(t) >= need:
            try:
                return datetime.strptime(t[:need], fmt).date()
            except ValueError:
                continue
    raise ValueError(f"unparseable NSE expiry: {s!r}")


def _option_chain_non_empty(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    rec = data.get("records")
    if not isinstance(rec, dict):
        return False
    return bool(rec.get("data") or rec.get("expiryDates"))


def _leg_oi(leg: Mapping[str, Any] | None) -> float:
    if not leg:
        return 0.0
    v: Any = leg.get("openInterest")
    if v is None:
        v = leg.get("open_interest")
    if isinstance(v, str):
        v = v.replace(",", "").strip()
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _same_nse_expiry(a: str | None, b: str | None) -> bool:
    """NSE may mix case (e.g. ``25-Apr-2025`` vs ``25-APR-2025``) between ``expiryDates`` and each row."""
    if not a or not b:
        return True
    sa, sb = str(a).strip(), str(b).strip()
    if sa == sb:
        return True
    if sa.lower() == sb.lower():
        return True
    try:
        return _parse_nse_expiry(sa) == _parse_nse_expiry(sb)
    except Exception:
        return False


def options_from_nse_option_chain_payload(
    data: dict[str, Any],
    *,
    symbol: str = "NIFTY",
    ref_date: date | None = None,
) -> OptionsSnapshot:
    """
    Build PCR / OI walls from a saved NSE JSON response (same shape as
    ``/api/option-chain-indices``). You can paste the body from browser DevTools
    or a file downloaded from a machine where NSE returns data.
    """
    ref = ref_date or date.today()
    if not isinstance(data, dict):
        raise TypeError("payload must be a JSON object")
    body = data
    if "records" not in body and ("data" in body or "expiryDates" in body or "underlyingValue" in body):
        body = {"records": body}
    records = body.get("records", {}) or {}
    if not isinstance(records, dict):
        records = {}
    exp_dates = [str(x) for x in (records.get("expiryDates") or [])]
    expiry = _pick_nearest_expiry(exp_dates, ref)
    total_ce_oi = 0.0
    total_pe_oi = 0.0
    max_ce_strike: float | None = None
    max_ce_val = 0.0
    max_pe_strike: float | None = None
    max_pe_val = 0.0
    spot = None
    underlying = records.get("underlyingValue")
    if underlying is not None:
        try:
            spot = float(underlying)
        except (TypeError, ValueError):
            spot = None

    rows = list(records.get("data", []) or [])
    if not rows and exp_dates:
        logger.warning("NSE option chain (pasted payload): no rows for %s (expir=%s)", symbol, expiry)
    for row in rows:
        ed = row.get("expiryDate") or row.get("expiryDates")
        if not ed and row.get("CE"):
            ed = (row.get("CE") or {}).get("expiryDate")
        if expiry and ed and not _same_nse_expiry(str(expiry), str(ed)):
            continue
        ce = row.get("CE") or {}
        pe = row.get("PE") or {}
        strike = row.get("strikePrice")
        try:
            k = float(strike)
        except (TypeError, ValueError):
            continue
        ce_oi = _leg_oi(ce)
        pe_oi = _leg_oi(pe)
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi
        if ce_oi > max_ce_val:
            max_ce_val = ce_oi
            max_ce_strike = k
        if pe_oi > max_pe_val:
            max_pe_val = pe_oi
            max_pe_strike = k

    if max_ce_val <= 0:
        max_ce_strike = None
    if max_pe_val <= 0:
        max_pe_strike = None

    pcr = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else None
    return OptionsSnapshot(
        symbol=symbol,
        expiry=str(expiry) if expiry else None,
        pcr_oi=pcr,
        total_call_oi=total_ce_oi,
        total_put_oi=total_pe_oi,
        max_call_oi_strike=max_ce_strike,
        max_put_oi_strike=max_pe_strike,
        max_call_oi=float(max_ce_val),
        max_put_oi=float(max_pe_val),
        spot=spot,
        raw_expiry_dates=exp_dates[:8],
    )


def fetch_nifty_options_snapshot(symbol: str = "NIFTY", ref_date: date | None = None) -> OptionsSnapshot:
    ref = ref_date or date.today()
    try:
        nse = get_nse_client()
        data = nse.get_json(
            "/api/option-chain-indices",
            params={"symbol": symbol},
            extra_headers={"Referer": f"{NSE_BASE}/option-chain"},
        )
        if not _option_chain_non_empty(data):
            reset_nse_client()
            nse = get_nse_client()
            data = nse.get_json(
                "/api/option-chain-indices",
                params={"symbol": symbol},
                extra_headers={"Referer": f"{NSE_BASE}/option-chain"},
            )
            if not _option_chain_non_empty(data):
                logger.warning(
                    "NSE option-chain-indices for %s returned an empty payload twice "
                    "(common outside India, bot filtering, or off-hours; options stay blank)",
                    symbol,
                )
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
            max_call_oi=0.0,
            max_put_oi=0.0,
            spot=None,
            raw_expiry_dates=[],
        )
    return options_from_nse_option_chain_payload(data, symbol=symbol, ref_date=ref)


def options_snapshot_to_api_dict(opts: OptionsSnapshot) -> dict[str, Any]:
    """Single place for the ``options`` object shape in snapshot JSON."""
    return {
        "symbol": opts.symbol,
        "expiry": opts.expiry,
        "pcr_oi": opts.pcr_oi,
        "call_oi_total": opts.total_call_oi,
        "put_oi_total": opts.total_put_oi,
        "resistance_strike_call_oi": opts.max_call_oi_strike,
        "support_strike_put_oi": opts.max_put_oi_strike,
        "call_wall_oi": opts.max_call_oi,
        "put_wall_oi": opts.max_put_oi,
        "note": options_note(
            opts.pcr_oi,
            opts.max_put_oi_strike,
            opts.max_call_oi_strike,
            opts.max_put_oi,
            opts.max_call_oi,
        ),
    }
