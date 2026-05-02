"""Nifty / index options: ATM-band PCR, active-strike walls, incremental & aggression (NSE chain)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.services.narrative_service import options_note
from app.services.nse_client import NSE_BASE, get_nse_client, reset_nse_client
from app.services.options_analytics import (
    StrikeLegs,
    compute_active_strikes,
    compute_aggression,
    compute_incremental_from_exchange,
    compute_oi_walls,
    compute_pcr_atm,
    compute_rolling_pcr,
    get_atm_band_strikes,
    get_atm_strike,
    sum_band_oi,
    unique_sorted_strikes,
)
from app.repositories.option_oi_repo import get_latest_tick_before, insert_tick

logger = logging.getLogger(__name__)


@dataclass
class OptionsSnapshot:
    symbol: str
    expiry: str | None
    # Primary PCR = ATM ±3 strikes only (not full-chain totals).
    pcr_oi: float | None
    pcr_15m: float | None = None
    total_call_oi: float = 0.0  # ATM-band sums
    total_put_oi: float = 0.0
    max_call_oi_strike: float | None = None  # active strikes only
    max_put_oi_strike: float | None = None
    max_call_oi: float = 0.0
    max_put_oi: float = 0.0
    spot: float | None = None
    raw_expiry_dates: list[str] = field(default_factory=list)
    atm_strike: float | None = None
    atm_band_strikes: list[float] = field(default_factory=list)
    active_strike_count: int = 0
    call_oi_change: float | None = None
    put_oi_change: float | None = None
    call_aggression: float | None = None
    put_aggression: float | None = None


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


def _leg_vol(leg: Mapping[str, Any] | None) -> float:
    if not leg:
        return 0.0
    v: Any = leg.get("totalTradedVolume") or leg.get("total_traded_volume")
    if isinstance(v, str):
        v = v.replace(",", "").strip()
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _leg_oi_chg(leg: Mapping[str, Any] | None) -> float:
    if not leg:
        return 0.0
    v: Any = leg.get("changeinOpenInterest") or leg.get("change_in_open_interest")
    if isinstance(v, str):
        v = v.replace(",", "").strip()
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _same_nse_expiry(a: str | None, b: str | None) -> bool:
    """NSE may mix case between ``expiryDates`` and each row."""
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


def _empty_snapshot(symbol: str) -> OptionsSnapshot:
    return OptionsSnapshot(
        symbol=symbol,
        expiry=None,
        pcr_oi=None,
        pcr_15m=None,
        total_call_oi=0.0,
        total_put_oi=0.0,
        max_call_oi_strike=None,
        max_put_oi_strike=None,
        max_call_oi=0.0,
        max_put_oi=0.0,
        spot=None,
        raw_expiry_dates=[],
    )


def options_from_nse_option_chain_payload(
    data: dict[str, Any],
    *,
    symbol: str = "NIFTY",
    ref_date: date | None = None,
) -> OptionsSnapshot:
    """
    Build PCR / walls from NSE option-chain JSON using ATM ±3 PCR and active-strike walls only.
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

    spot = None
    underlying = records.get("underlyingValue")
    if underlying is not None:
        try:
            spot = float(underlying)
        except (TypeError, ValueError):
            spot = None

    rows_raw = list(records.get("data", []) or [])
    if not rows_raw and exp_dates:
        logger.warning("NSE option chain (pasted payload): no rows for %s (expir=%s)", symbol, expiry)

    strike_rows: list[StrikeLegs] = []
    for row in rows_raw:
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
        strike_rows.append(
            StrikeLegs(
                strike=k,
                call_oi=_leg_oi(ce),
                put_oi=_leg_oi(pe),
                call_vol=_leg_vol(ce),
                put_vol=_leg_vol(pe),
                call_oi_chg=_leg_oi_chg(ce),
                put_oi_chg=_leg_oi_chg(pe),
            )
        )

    if not strike_rows:
        return OptionsSnapshot(
            symbol=symbol,
            expiry=str(expiry) if expiry else None,
            pcr_oi=None,
            pcr_15m=None,
            total_call_oi=0.0,
            total_put_oi=0.0,
            max_call_oi_strike=None,
            max_put_oi_strike=None,
            max_call_oi=0.0,
            max_put_oi=0.0,
            spot=spot,
            raw_expiry_dates=exp_dates[:8],
        )

    by_k = {r.strike: r for r in strike_rows}
    strikes = unique_sorted_strikes(strike_rows)
    atm = get_atm_strike(spot, strikes)
    if atm is None:
        return _empty_snapshot(symbol)

    band = get_atm_band_strikes(strikes, atm, width=3)
    pcr_atm = compute_pcr_atm(by_k, band)
    ce_band, pe_band = sum_band_oi(by_k, band)
    d_ce, d_pe = compute_incremental_from_exchange(by_k, band)
    call_agg, put_agg = compute_aggression(by_k, band)

    active = compute_active_strikes(strike_rows, atm)
    ce_k, ce_v, pe_k, pe_v = compute_oi_walls(by_k, active)

    return OptionsSnapshot(
        symbol=symbol,
        expiry=str(expiry) if expiry else None,
        pcr_oi=pcr_atm,
        pcr_15m=None,
        total_call_oi=float(ce_band),
        total_put_oi=float(pe_band),
        max_call_oi_strike=ce_k,
        max_put_oi_strike=pe_k,
        max_call_oi=float(ce_v),
        max_put_oi=float(pe_v),
        spot=spot,
        raw_expiry_dates=exp_dates[:8],
        atm_strike=float(atm),
        atm_band_strikes=list(band),
        active_strike_count=len(active),
        call_oi_change=float(d_ce),
        put_oi_change=float(d_pe),
        call_aggression=float(call_agg),
        put_aggression=float(put_agg),
    )


def enrich_options_with_history(
    db: Session | None,
    market_id: str,
    opts: OptionsSnapshot,
    *,
    record_tick: bool = True,
) -> OptionsSnapshot:
    """Attach rolling PCR / tick deltas using persisted ATM-band OI ticks (call after building chain metrics)."""
    if db is None:
        opts.pcr_15m = None
        return opts

    now = datetime.now(timezone.utc)
    ce = float(opts.total_call_oi)
    pe = float(opts.total_put_oi)

    opts.pcr_15m = compute_rolling_pcr(db, market_id, opts.symbol, opts.expiry, pe, ce, now)

    prev = get_latest_tick_before(db, market_id, opts.symbol, opts.expiry, now)
    if opts.call_oi_change is None and prev is not None:
        opts.call_oi_change = ce - float(prev.atm_call_oi)
        opts.put_oi_change = pe - float(prev.atm_put_oi)

    if record_tick:
        insert_tick(
            db,
            captured_at=now,
            market_id=market_id,
            symbol=opts.symbol,
            expiry=opts.expiry,
            spot=opts.spot,
            atm_call_oi=ce,
            atm_put_oi=pe,
        )
    return opts


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
        return _empty_snapshot(symbol)
    return options_from_nse_option_chain_payload(data, symbol=symbol, ref_date=ref)


def options_snapshot_to_api_dict(opts: OptionsSnapshot) -> dict[str, Any]:
    """Single place for the ``options`` object shape in snapshot JSON."""
    return {
        "metrics_schema_version": 2,
        "symbol": opts.symbol,
        "expiry": opts.expiry,
        "pcr_atm": opts.pcr_oi,
        "pcr_oi": opts.pcr_oi,
        "pcr_15m": opts.pcr_15m,
        "call_oi_total": opts.total_call_oi,
        "put_oi_total": opts.total_put_oi,
        "resistance_strike_call_oi": opts.max_call_oi_strike,
        "support_strike_put_oi": opts.max_put_oi_strike,
        "call_wall_oi": opts.max_call_oi,
        "put_wall_oi": opts.max_put_oi,
        "atm_strike": opts.atm_strike,
        "atm_band_strikes": opts.atm_band_strikes,
        "active_strike_count": opts.active_strike_count,
        "call_oi_change": opts.call_oi_change,
        "put_oi_change": opts.put_oi_change,
        "call_aggression": opts.call_aggression,
        "put_aggression": opts.put_aggression,
        "metrics_note": (
            "PCR is ATM±3 strikes on the nearest expiry; OI walls use active strikes only "
            "(ATM±500 points or top 20 by volume). Totals are ATM-band sums. "
            "PCR_15m uses ATM-band OI ticks over ~15 minutes."
        ),
        "note": options_note(
            opts.pcr_oi,
            opts.max_put_oi_strike,
            opts.max_call_oi_strike,
            opts.max_put_oi,
            opts.max_call_oi,
        ),
    }
