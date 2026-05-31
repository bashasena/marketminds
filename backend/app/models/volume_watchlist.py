"""ORM models for server-side volume alert watchlist and app settings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base


class VolumeWatchlist(Base):
    """One row per watched symbol — shared across all users."""

    __tablename__ = "volume_watchlist"

    sym: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    last_crossed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_avg30: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_cur_vol: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_pcr: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_oi_trend: Mapped[str] = mapped_column(String(20), nullable=False, default="Flat")
    last_signal: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AppSetting(Base):
    """Generic key-value store for persistent app configuration."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
