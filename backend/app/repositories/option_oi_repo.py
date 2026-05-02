"""Persist ATM-band OI ticks for rolling PCR (15‑minute window)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.snapshot import OptionOiTick


def insert_tick(
    db: Session,
    *,
    captured_at: datetime,
    market_id: str,
    symbol: str,
    expiry: str | None,
    spot: float | None,
    atm_call_oi: float,
    atm_put_oi: float,
) -> OptionOiTick:
    row = OptionOiTick(
        captured_at=captured_at,
        market_id=market_id,
        symbol=symbol.upper(),
        expiry=expiry,
        spot=spot,
        atm_call_oi=float(atm_call_oi),
        atm_put_oi=float(atm_put_oi),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_oldest_tick_since(
    db: Session,
    market_id: str,
    symbol: str,
    expiry: str | None,
    window_start: datetime,
    window_end: datetime,
) -> OptionOiTick | None:
    """Earliest tick in ``[window_start, window_end]`` for rolling ΔOI."""
    sym = symbol.upper()
    flt = [
        OptionOiTick.market_id == market_id,
        OptionOiTick.symbol == sym,
        OptionOiTick.captured_at >= window_start,
        OptionOiTick.captured_at <= window_end,
    ]
    if expiry is None:
        flt.append(OptionOiTick.expiry.is_(None))
    else:
        flt.append(OptionOiTick.expiry == expiry)
    q = (
        select(OptionOiTick)
        .where(*flt)
        .order_by(OptionOiTick.captured_at.asc())
        .limit(1)
    )
    return db.execute(q).scalar_one_or_none()


def get_latest_tick_before(
    db: Session,
    market_id: str,
    symbol: str,
    expiry: str | None,
    before: datetime,
) -> OptionOiTick | None:
    sym = symbol.upper()
    flt = [
        OptionOiTick.market_id == market_id,
        OptionOiTick.symbol == sym,
        OptionOiTick.captured_at < before,
    ]
    if expiry is None:
        flt.append(OptionOiTick.expiry.is_(None))
    else:
        flt.append(OptionOiTick.expiry == expiry)
    q = (
        select(OptionOiTick)
        .where(*flt)
        .order_by(OptionOiTick.captured_at.desc())
        .limit(1)
    )
    return db.execute(q).scalar_one_or_none()
