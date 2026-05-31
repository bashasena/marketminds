"""Server-side volume alert manager — DB-backed watchlist, configurable PCR batch job.

Two independent loops:
  1. PCR/volume refresh  — interval configurable (5/10/30/60 min), set via admin API.
     Fetches fresh volume + PCR for every watched symbol and persists to DB.
  2. Telegram threshold check — always every 5 min.
     Reads latest data already in DB; fires Telegram when a new integer band is crossed.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.volume_watchlist import AppSetting, VolumeWatchlist
from app.services.telegram_service import send_volume_alert
from app.services.volume_scan_service import run_watch_scan

logger = logging.getLogger(__name__)

DEFAULT_PCR_INTERVAL = 30   # minutes
TELEGRAM_INTERVAL_SEC = 5 * 60  # always 5 min


# ── helpers ─────────────────────────────────────────────────────────────────

def _get_setting(db: Session, key: str, default: str) -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else default


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


# ── AlertManager ─────────────────────────────────────────────────────────────

class AlertManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pcr_timer: Optional[threading.Timer] = None
        self._tg_timer: Optional[threading.Timer] = None
        self._started = False
        self._pcr_interval_sec: int = DEFAULT_PCR_INTERVAL * 60

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        # Load persisted interval from DB
        try:
            with SessionLocal() as db:
                mins = int(_get_setting(db, "pcr_refresh_interval_minutes", str(DEFAULT_PCR_INTERVAL)))
                self._pcr_interval_sec = mins * 60
        except Exception:
            pass
        self._schedule_pcr()
        self._schedule_telegram()
        logger.info(
            "AlertManager started — PCR refresh every %dm, Telegram check every 5m",
            self._pcr_interval_sec // 60,
        )

    def stop(self) -> None:
        self._started = False
        for t in (self._pcr_timer, self._tg_timer):
            if t:
                t.cancel()
        self._pcr_timer = self._tg_timer = None

    # ── public API ───────────────────────────────────────────────────────────

    def add(self, sym: str, name: str, current_ratio: float) -> dict:
        """Add or update a symbol in the DB watchlist."""
        with SessionLocal() as db:
            row = db.query(VolumeWatchlist).filter(VolumeWatchlist.sym == sym).first()
            if row is None:
                row = VolumeWatchlist(
                    sym=sym,
                    name=name,
                    last_crossed=int(current_ratio),
                    last_ratio=current_ratio,
                )
                db.add(row)
                db.commit()
                logger.info("Watchlist add: %s (ratio=%.2f)", sym, current_ratio)
            return self._row_to_dict(row)

    def remove(self, sym: str) -> bool:
        with SessionLocal() as db:
            row = db.query(VolumeWatchlist).filter(VolumeWatchlist.sym == sym).first()
            if row is None:
                return False
            db.delete(row)
            db.commit()
            logger.info("Watchlist remove: %s", sym)
            return True

    def list_all(self) -> list[dict]:
        with SessionLocal() as db:
            rows = db.query(VolumeWatchlist).order_by(VolumeWatchlist.added_at).all()
            return [self._row_to_dict(r) for r in rows]

    def get_pcr_interval_minutes(self) -> int:
        return self._pcr_interval_sec // 60

    def set_pcr_interval_minutes(self, minutes: int) -> None:
        """Change PCR refresh interval and persist to DB. Reschedules the timer."""
        minutes = max(5, min(60, minutes))
        self._pcr_interval_sec = minutes * 60
        try:
            with SessionLocal() as db:
                _set_setting(db, "pcr_refresh_interval_minutes", str(minutes))
        except Exception as exc:
            logger.error("Failed to persist PCR interval: %s", exc)
        # Cancel current timer and reschedule with new interval
        if self._pcr_timer:
            self._pcr_timer.cancel()
        if self._started:
            self._schedule_pcr()
        logger.info("PCR refresh interval updated to %d min", minutes)

    # ── PCR / volume refresh loop ────────────────────────────────────────────

    def _schedule_pcr(self) -> None:
        self._pcr_timer = threading.Timer(self._pcr_interval_sec, self._run_pcr)
        self._pcr_timer.daemon = True
        self._pcr_timer.start()

    def _run_pcr(self) -> None:
        try:
            self._refresh_watchlist_data()
        except Exception as exc:
            logger.error("PCR refresh error: %s", exc)
        finally:
            if self._started:
                self._schedule_pcr()

    def _refresh_watchlist_data(self) -> None:
        """Fetch fresh volume + PCR for all watched symbols and update DB."""
        with SessionLocal() as db:
            rows = db.query(VolumeWatchlist).all()
            syms = [r.sym for r in rows]
        if not syms:
            return

        logger.info("PCR refresh: fetching %d symbols", len(syms))
        results = run_watch_scan(syms)
        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            for item in results:
                if item.get("error"):
                    continue
                sym = item["sym"]
                row = db.query(VolumeWatchlist).filter(VolumeWatchlist.sym == sym).first()
                if row is None:
                    continue
                row.last_ratio = float(item.get("volRatio", row.last_ratio))
                row.last_avg30 = float(item.get("avg30", row.last_avg30))
                row.last_cur_vol = float(item.get("curVol", row.last_cur_vol))
                row.last_pcr = float(item.get("pcr", row.last_pcr))
                row.last_oi_trend = str(item.get("oiTrend", row.last_oi_trend))
                row.last_signal = str(item.get("signal", row.last_signal))
                row.last_checked = now
            db.commit()
        logger.info("PCR refresh complete for %d symbols", len(syms))

    # ── Telegram threshold check loop ────────────────────────────────────────

    def _schedule_telegram(self) -> None:
        self._tg_timer = threading.Timer(TELEGRAM_INTERVAL_SEC, self._run_telegram)
        self._tg_timer.daemon = True
        self._tg_timer.start()

    def _run_telegram(self) -> None:
        try:
            self._check_thresholds()
        except Exception as exc:
            logger.error("Telegram check error: %s", exc)
        finally:
            if self._started:
                self._schedule_telegram()

    def _check_thresholds(self) -> None:
        """Read latest data from DB; fire Telegram if a new integer band is crossed."""
        with SessionLocal() as db:
            rows = db.query(VolumeWatchlist).all()
            for row in rows:
                new_band = int(row.last_ratio)
                if new_band > row.last_crossed and row.last_ratio > 0:
                    send_volume_alert(
                        sym=row.sym,
                        name=row.name,
                        band=new_band,
                        ratio=row.last_ratio,
                        signal=row.last_signal,
                        cur_vol=row.last_cur_vol,
                        avg30=row.last_avg30,
                    )
                    row.last_crossed = new_band
            db.commit()

    # ── serialisation ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: VolumeWatchlist) -> dict:
        return {
            "sym": row.sym,
            "name": row.name,
            "lastCrossed": row.last_crossed,
            "lastRatio": row.last_ratio,
            "avg30": row.last_avg30,
            "curVol": row.last_cur_vol,
            "pcr": row.last_pcr,
            "oiTrend": row.last_oi_trend,
            "signal": row.last_signal,
            "lastChecked": row.last_checked.strftime("%H:%M") if row.last_checked else "—",
        }


# Singleton
alert_manager = AlertManager()
