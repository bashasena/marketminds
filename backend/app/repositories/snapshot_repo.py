"""Persistence helpers for daily snapshots and FII/DII rows."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.snapshot import DailySnapshot, FiiDiiFlow

DEFAULT_MARKET = "in_nifty"


def get_snapshot_for_date(db: Session, d: date, market_id: str = DEFAULT_MARKET) -> DailySnapshot | None:
    return (
        db.execute(
            select(DailySnapshot).where(
                DailySnapshot.snapshot_date == d,
                DailySnapshot.market_id == market_id,
            )
        )
        .scalars()
        .first()
    )


def get_latest_snapshot(db: Session, market_id: str = DEFAULT_MARKET) -> DailySnapshot | None:
    q = (
        select(DailySnapshot)
        .where(DailySnapshot.market_id == market_id)
        .order_by(DailySnapshot.snapshot_date.desc())
        .limit(1)
    )
    return db.execute(q).scalars().first()


def list_recent_snapshots(db: Session, days: int) -> list[DailySnapshot]:
    q = select(DailySnapshot).order_by(DailySnapshot.snapshot_date.desc()).limit(max(1, days))
    return list(db.execute(q).scalars().all())


def upsert_daily_snapshot(
    db: Session,
    snapshot_date: date,
    payload: dict[str, Any],
    composite: float | None,
    nifty_close: float | None,
    nifty_pct: float | None,
    market_id: str = DEFAULT_MARKET,
) -> DailySnapshot:
    row = get_snapshot_for_date(db, snapshot_date, market_id)
    if row is None:
        row = DailySnapshot(
            snapshot_date=snapshot_date,
            market_id=market_id,
            payload=payload,
            composite_sentiment=composite,
            nifty_close=nifty_close,
            nifty_pct_change=nifty_pct,
        )
        db.add(row)
    else:
        row.payload = payload
        row.composite_sentiment = composite
        row.nifty_close = nifty_close
        row.nifty_pct_change = nifty_pct
    db.commit()
    db.refresh(row)
    return row


def upsert_fii_dii_flow(
    db: Session,
    flow_date: date,
    fii_net: float | None,
    dii_net: float | None,
    raw_note: str | None = None,
) -> FiiDiiFlow:
    row = db.execute(select(FiiDiiFlow).where(FiiDiiFlow.flow_date == flow_date)).scalar_one_or_none()
    if row is None:
        row = FiiDiiFlow(flow_date=flow_date, fii_net_crores=fii_net, dii_net_crores=dii_net, raw_note=raw_note)
        db.add(row)
    else:
        row.fii_net_crores = fii_net
        row.dii_net_crores = dii_net
        row.raw_note = raw_note
    db.commit()
    db.refresh(row)
    return row
