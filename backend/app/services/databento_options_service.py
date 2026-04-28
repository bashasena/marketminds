"""US ETF options (SPY / QQQ) from Databento OPRA — parent symbology, T+1-style (prior weekday)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from databento_dbn import (
    InstrumentClass,
    SecurityUpdateAction,
    StatType,
    StatUpdateAction,
    UNDEF_PRICE,
)

from app.config import Settings
from app.services.options_service import OptionsSnapshot

logger = logging.getLogger(__name__)

_STAT_TYPES_WIDE = (
    StatType.OPEN_INTEREST,
    StatType.CLEARED_VOLUME,
    StatType.VOLATILITY,
    StatType.DELTA,
    StatType.CLOSE_PRICE,
    StatType.SETTLEMENT_PRICE,
)


def _empty(symbol: str) -> OptionsSnapshot:
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


def _prior_weekday(ref: date) -> date:
    """One pandas business day back (Mon–Fri only; no exchange holiday calendar)."""
    return (pd.Timestamp(ref) - pd.tseries.offsets.BDay(1)).date()


def _expiry_date(val: Any) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


def _is_option_leg(ic: Any) -> bool:
    return ic in (InstrumentClass.CALL, InstrumentClass.PUT) or ic in ("C", "P", "c", "p")


def _is_call(ic: Any) -> bool:
    return ic in (InstrumentClass.CALL, "C", "c")


def _is_put(ic: Any) -> bool:
    return ic in (InstrumentClass.PUT, "P", "p")


def _is_def_delete(val: Any) -> bool:
    if val == SecurityUpdateAction.DELETE:
        return True
    return str(val) == str(SecurityUpdateAction.DELETE)


def _price_usable(v: Any) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return False
    return fv != float(UNDEF_PRICE)


def _quantity_usable_positive(v: Any) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def _stat_numeric(row: pd.Series, st: Any) -> float | None:
    if st == StatType.OPEN_INTEREST:
        if not _quantity_usable_positive(row.get("quantity")):
            return None
        return float(row["quantity"])
    if st == StatType.CLEARED_VOLUME:
        q = row.get("quantity")
        if q is None or (isinstance(q, float) and pd.isna(q)):
            return None
        try:
            return float(q)
        except (TypeError, ValueError):
            return None
    px = row.get("price")
    if not _price_usable(px):
        return None
    return float(px)


def _first_float(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.iloc[0])


def _instrument_stat_wide(stats: pd.DataFrame) -> pd.DataFrame:
    """One row per instrument with OI, cleared vol, IV, delta, official prices (latest per stat type)."""
    s = stats[stats["stat_type"].isin(_STAT_TYPES_WIDE)].copy()
    if s.empty:
        return pd.DataFrame()
    if "update_action" in s.columns:
        s = s[s["update_action"] != StatUpdateAction.DELETE]
    s = s.sort_values("ts_event").groupby(["instrument_id", "stat_type"], as_index=False).last()

    buckets: dict[int, dict[str, Any]] = {}
    for _, r in s.iterrows():
        iid = int(r["instrument_id"])
        st = r["stat_type"]
        val = _stat_numeric(r, st)
        if val is None:
            continue
        row = buckets.setdefault(iid, {"instrument_id": iid})
        if st == StatType.OPEN_INTEREST:
            row["oi"] = val
        elif st == StatType.CLEARED_VOLUME:
            row["cleared_volume"] = val
        elif st == StatType.VOLATILITY:
            row["iv"] = val
        elif st == StatType.DELTA:
            row["delta"] = val
        elif st == StatType.CLOSE_PRICE:
            row["close_px"] = val
        elif st == StatType.SETTLEMENT_PRICE:
            row["settlement_px"] = val
    if not buckets:
        return pd.DataFrame()
    return pd.DataFrame(list(buckets.values()))


def _oi_weighted_mean(df: pd.DataFrame, col: str) -> float | None:
    if col not in df.columns or "oi" not in df.columns:
        return None
    sub = df[df[col].notna() & (df["oi"] > 0)]
    if sub.empty:
        return None
    w = sub["oi"].astype(float)
    x = sub[col].astype(float)
    return float((x * w).sum() / w.sum())


def _atm_strike_for_spot(merged: pd.DataFrame, spot: float) -> float | None:
    ks = merged["strike_price"].dropna().unique()
    if len(ks) == 0:
        return None
    return float(min((float(k) for k in ks), key=lambda k: abs(k - spot)))


def _databento_options_bundle(
    underlying: str,
    settings: Settings,
    ref_date: date,
    spot: float | None,
) -> tuple[OptionsSnapshot, dict[str, Any]]:
    import databento as db

    sym = underlying.strip().upper()
    parent = f"{sym}.OPT"
    session = _prior_weekday(ref_date)
    day_end = session + timedelta(days=1)
    dataset = settings.databento_dataset
    api_key = (settings.databento_api_key or "").strip()

    base_detail: dict[str, Any] = {
        "source": "databento",
        "dataset": dataset,
        "parent_symbol": parent,
        "oi_session_date": session.isoformat(),
        "nearest_expiry": None,
        "spot_for_atm": spot,
        "cleared_volume": None,
        "oi_weighted_iv": None,
        "atm": None,
        "official_prices": None,
        "has_quotes": False,
        "note": (
            "OPRA statistics via parent symbology; session is the prior weekday (no holiday calendar). "
            "IV, delta, and volume depend on what the venue published for that day."
        ),
    }

    client = db.Historical(key=api_key)
    def_store = client.timeseries.get_range(
        dataset,
        start=session,
        end=day_end,
        symbols=parent,
        schema="definition",
        stype_in="parent",
    )
    stat_store = client.timeseries.get_range(
        dataset,
        start=session,
        end=day_end,
        symbols=parent,
        schema="statistics",
        stype_in="parent",
    )

    defs = def_store.to_df()
    stats = stat_store.to_df()

    if defs.empty or stats.empty:
        logger.warning("Databento %s: empty definition or statistics for %s on %s", dataset, parent, session)
        return _empty(sym), {**base_detail, "note": base_detail["note"] + " No rows returned for this range."}

    if "instrument_id" not in defs.columns or "instrument_id" not in stats.columns:
        logger.warning("Databento %s: unexpected dataframe columns", dataset)
        return _empty(sym), {**base_detail, "note": "Unexpected Databento frame shape (missing instrument_id)."}

    defs = defs.sort_values("ts_event").groupby("instrument_id", as_index=False).last()
    if "security_update_action" in defs.columns:
        defs = defs[~defs["security_update_action"].map(_is_def_delete)]

    wide = _instrument_stat_wide(stats)
    if wide.empty or "oi" not in wide.columns:
        return _empty(sym), {**base_detail, "note": base_detail["note"] + " No open-interest statistics to join."}

    def_need = ("instrument_id", "instrument_class", "strike_price", "expiration")
    if any(c not in defs.columns for c in def_need):
        logger.warning("Databento definition frame missing columns (have %s)", list(defs.columns))
        return _empty(sym), {**base_detail, "note": "Definition schema missing expected columns."}

    def_sub = defs[list(def_need)].copy()
    oi_sub = wide[wide["oi"].notna() & (wide["oi"] > 0)][["instrument_id", "oi"]].copy()
    extra_cols = [c for c in ("cleared_volume", "iv", "delta", "close_px", "settlement_px") if c in wide.columns]
    if extra_cols:
        oi_sub = oi_sub.merge(wide[["instrument_id"] + extra_cols], on="instrument_id", how="left")
    merged = oi_sub.merge(def_sub, on="instrument_id", how="inner")
    merged = merged[merged["instrument_class"].apply(_is_option_leg)]
    if merged.empty:
        return _empty(sym), {**base_detail, "note": base_detail["note"] + " OI did not join to option definitions."}

    expiries: list[date] = []
    for raw in merged["expiration"]:
        d = _expiry_date(raw)
        if d:
            expiries.append(d)
    if not expiries:
        return _empty(sym), {**base_detail, "note": "Could not parse expiries on option definitions."}

    unique_exp = sorted(set(expiries))
    nearest = min(unique_exp, key=lambda d: abs((d - ref_date).days))
    merged["_exp_d"] = merged["expiration"].map(_expiry_date)
    merged = merged[merged["_exp_d"] == nearest]
    if merged.empty:
        return _empty(sym), {**base_detail, "note": "No chain rows for the nearest expiry slice."}

    strike_col = "strike_price"
    total_call = 0.0
    total_put = 0.0
    max_ce_strike: float | None = None
    max_ce_val = 0.0
    max_pe_strike: float | None = None
    max_pe_val = 0.0

    for _, row in merged.iterrows():
        ic = row["instrument_class"]
        try:
            k = float(row[strike_col])
        except (TypeError, ValueError):
            continue
        try:
            oi = float(row["oi"])
        except (TypeError, ValueError):
            continue
        if oi <= 0:
            continue
        if _is_call(ic):
            total_call += oi
            if oi > max_ce_val:
                max_ce_val = oi
                max_ce_strike = k
        elif _is_put(ic):
            total_put += oi
            if oi > max_pe_val:
                max_pe_val = oi
                max_pe_strike = k

    if max_ce_val <= 0:
        max_ce_strike = None
    if max_pe_val <= 0:
        max_pe_strike = None

    pcr = (total_put / total_call) if total_call > 0 else None
    raw_exp = [d.isoformat() for d in unique_exp[:8]]

    snap = OptionsSnapshot(
        symbol=sym,
        expiry=nearest.isoformat(),
        pcr_oi=pcr,
        total_call_oi=total_call,
        total_put_oi=total_put,
        max_call_oi_strike=max_ce_strike,
        max_put_oi_strike=max_pe_strike,
        max_call_oi=float(max_ce_val),
        max_put_oi=float(max_pe_val),
        spot=spot,
        raw_expiry_dates=raw_exp,
    )

    call_m = merged[merged["instrument_class"].apply(_is_call)]
    put_m = merged[merged["instrument_class"].apply(_is_put)]

    cv_call = float(call_m["cleared_volume"].fillna(0).sum()) if "cleared_volume" in call_m.columns else 0.0
    cv_put = float(put_m["cleared_volume"].fillna(0).sum()) if "cleared_volume" in put_m.columns else 0.0
    cleared_block: dict[str, Any] | None = None
    if cv_call > 0 or cv_put > 0:
        cleared_block = {
            "call": cv_call,
            "put": cv_put,
            "pcr": (cv_put / cv_call) if cv_call > 0 else None,
        }

    iv_block: dict[str, Any] | None = None
    wc_iv = _oi_weighted_mean(call_m, "iv")
    wp_iv = _oi_weighted_mean(put_m, "iv")
    if wc_iv is not None or wp_iv is not None:
        iv_block = {"calls": wc_iv, "puts": wp_iv}

    official: dict[str, Any] | None = None
    wc_c = _oi_weighted_mean(call_m, "close_px")
    wp_c = _oi_weighted_mean(put_m, "close_px")
    wc_s = _oi_weighted_mean(call_m, "settlement_px")
    wp_s = _oi_weighted_mean(put_m, "settlement_px")
    if any(v is not None for v in (wc_c, wp_c, wc_s, wp_s)):
        official = {
            "oi_weighted_close_call": wc_c,
            "oi_weighted_close_put": wp_c,
            "oi_weighted_settlement_call": wc_s,
            "oi_weighted_settlement_put": wp_s,
        }

    atm_block: dict[str, Any] | None = None
    if spot is not None and spot > 0:
        k_atm = _atm_strike_for_spot(merged, float(spot))
        if k_atm is not None:
            slice_k = merged[np.isclose(merged["strike_price"].astype(float), k_atm, rtol=0, atol=1e-4)]
            c_row = slice_k[slice_k["instrument_class"].apply(_is_call)]
            p_row = slice_k[slice_k["instrument_class"].apply(_is_put)]
            atm_block = {
                "strike": k_atm,
                "call_iv": _first_float(c_row["iv"]) if not c_row.empty and "iv" in c_row.columns else None,
                "put_iv": _first_float(p_row["iv"]) if not p_row.empty and "iv" in p_row.columns else None,
                "call_delta": _first_float(c_row["delta"]) if not c_row.empty and "delta" in c_row.columns else None,
                "put_delta": _first_float(p_row["delta"]) if not p_row.empty and "delta" in p_row.columns else None,
            }

    has_quotes = bool(
        cleared_block
        or iv_block
        or official
        or (atm_block and any(atm_block.get(k) is not None for k in atm_block if k != "strike"))
    )

    detail: dict[str, Any] = {
        **base_detail,
        "nearest_expiry": nearest.isoformat(),
        "cleared_volume": cleared_block,
        "oi_weighted_iv": iv_block,
        "atm": atm_block,
        "official_prices": official,
        "has_quotes": has_quotes,
    }
    return snap, detail


def fetch_us_options_snapshot(
    underlying: str,
    *,
    settings: Settings,
    ref_date: date,
    spot: float | None = None,
) -> tuple[OptionsSnapshot, dict[str, Any] | None, str | None]:
    """
    SPY / QQQ options from Databento (parent ``.OPT`` symbol). Returns PCR/OI snapshot plus an optional
    ``databento_options`` detail block for the dashboard. Without ``DATABENTO_API_KEY``, detail is ``None``.
    """
    key = (settings.databento_api_key or "").strip()
    if not key:
        return (
            _empty(underlying.strip().upper()),
            None,
            "us_options: set DATABENTO_API_KEY for SPY/QQQ PCR (Databento OPRA, prior weekday OI)",
        )
    try:
        snap, detail = _databento_options_bundle(underlying, settings, ref_date, spot)
        return snap, detail, None
    except Exception as e:
        logger.warning("Databento options failed for %s: %s", underlying, e, exc_info=True)
        return _empty(underlying.strip().upper()), None, f"us_options_databento: {e}"
