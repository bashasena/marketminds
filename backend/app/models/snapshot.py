"""ORM models for persisted daily market snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class OptionOiTick(Base):
    """Time-series of ATM-band call/put OI for rolling PCR (e.g. 15‑minute window)."""

    __tablename__ = "option_oi_ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    market_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expiry: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    spot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atm_call_oi: Mapped[float] = mapped_column(Float, nullable=False)
    atm_put_oi: Mapped[float] = mapped_column(Float, nullable=False)


class DailySnapshot(Base):
    """One row per calendar day: full JSON payload + headline fields for queries."""

    __tablename__ = "daily_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "market_id", name="uq_daily_snapshots_date_market"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market_id: Mapped[str] = mapped_column(String(32), nullable=False, default="in_nifty", index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    composite_sentiment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nifty_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nifty_pct_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FiiDiiFlow(Base):
    """Normalized time-series for FII/DII cash-market net flows."""

    __tablename__ = "fii_dii_flows"
    __table_args__ = (UniqueConstraint("flow_date", name="uq_fii_dii_flow_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fii_net_crores: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dii_net_crores: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
