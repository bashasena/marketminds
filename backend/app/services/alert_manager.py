"""Server-side volume alert manager — DB-backed watchlist with unified refresh + alert loop.

Single loop (configurable interval, default 5 min):
  1. Fetch fresh volume + PCR for every watched symbol via Yahoo Finance.
  2. Persist updated data to DB (last_ratio, last_pcr, last_checked, etc.)
  3. Check thresholds — fire Telegram when a new integer band is crossed.

Separate daily reset at 13:30 UTC (≈ 9:30 AM ET):
  - Resets last_crossed = 0 for all symbols so alerts re-arm each morning.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.volume_watchlist import AppSetting, VolumeWatchlist
from app.services.telegram_service import send_volume_alert
from app.services.volume_scan_service import run_watch_scan

logger = logging.getLogger(__name__)

# Default check interval — fetch fresh data + fire Telegram alerts
DEFAULT_CHECK_INTERVAL_MINUTES = 5
VALID_CHECK_INTERVALS = {5, 10, 30, 60}

# Daily reset fires at 13:30 UTC ≈ 9:30 AM ET
DAILY_RESET_HOUR_UTC = 13
DAILY_RESET_MINUTE_UTC = 30


# ── helpers ──────────────────────────────────────────────────────────────────

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
        self._check_timer: Optional[threading.Timer] = None
        self._reset_timer: Optional[threading.Timer] = None
        self._started = False
        self._check_interval_sec: int = DEFAULT_CHECK_INTERVAL_MINUTES * 60

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            with SessionLocal() as db:
                mins = int(_get_setting(db, "pcr_refresh_interval_minutes", str(DEFAULT_CHECK_INTERVAL_MINUTES)))
                if mins in VALID_CHECK_INTERVALS:
                    self._check_interval_sec = mins * 60
        except Exception:
            pass
        self._schedule_check()
        self._schedule_daily_reset()
        logger.info(
            "AlertManager started — refresh+alert every %dm, daily reset at %02d:%02dUTC",
            self._check_interval_sec // 60,
            DAILY_RESET_HOUR_UTC,
            DAILY_RESET_MINUTE_UTC,
        )

    def stop(self) -> None:
        self._started = False
        for t in (self._check_timer, self._reset_timer):
            if t:
                t.cancel()
        self._check_timer = self._reset_timer = None

    # ── public API ───────────────────────────────────────────────────────────

    def add(self, sym: str, name: str, current_ratio: float) -> dict:
        """Add a symbol to the watchlist. Sets last_crossed to current band so we don't
        immediately re-alert for the level it's already at — only new crossings fire."""
        with SessionLocal() as db:
            row = db.query(VolumeWatchlist).filter(VolumeWatchlist.sym == sym).first()
            if row is None:
                row = VolumeWatchlist(
                    sym=sym,
                    name=name,
                    last_crossed=int(current_ratio),  # arm for next crossing
                    last_ratio=current_ratio,
                )
                db.add(row)
                db.commit()
                logger.info("Watchlist add: %s (ratio=%.2f, armed at band %d)", sym, current_ratio, int(current_ratio))
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
        return self._check_interval_sec // 60

    def set_pcr_interval_minutes(self, minutes: int) -> None:
        """Change the refresh+alert interval and persist to DB. Takes effect immediately."""
        minutes = max(5, min(60, minutes))
        self._check_interval_sec = minutes * 60
        try:
            with SessionLocal() as db:
                _set_setting(db, "pcr_refresh_interval_minutes", str(minutes))
        except Exception as exc:
            logger.error("Failed to persist check interval: %s", exc)
        if self._check_timer:
            self._check_timer.cancel()
        if self._started:
            self._schedule_check()
        logger.info("Refresh+alert interval updated to %d min", minutes)

    # ── Unified refresh + alert loop ─────────────────────────────────────────

    def _schedule_check(self) -> None:
        self._check_timer = threading.Timer(self._check_interval_sec, self._run_check)
        self._check_timer.daemon = True
        self._check_timer.start()
        logger.debug("Next refresh+alert check in %d s", self._check_interval_sec)

    def _run_check(self) -> None:
        try:
            self._refresh_and_alert()
        except Exception as exc:
            logger.error("Refresh+alert error: %s", exc)
        finally:
            if self._started:
                self._schedule_check()

    def _refresh_and_alert(self) -> None:
        """Core loop:
        1. Fetch fresh volume + PCR for all watched symbols (live, not from DB).
        2. Persist updated data to DB.
        3. Fire Telegram for every new integer band crossed since last check.
        """
        # Step 1 — read symbol list from DB
        with SessionLocal() as db:
            rows = db.query(VolumeWatchlist).all()
            syms = [r.sym for r in rows]
        if not syms:
            return

        logger.info("Watchlist refresh+alert: fetching %d symbols", len(syms))
        results = run_watch_scan(syms)  # live Yahoo Finance call
        now = datetime.now(timezone.utc)
        alerts_fired = 0

        # Step 2+3 — update DB and check thresholds in one transaction
        with SessionLocal() as db:
            for item in results:
                if item.get("error"):
                    logger.warning("Watch scan error for %s: %s", item.get("sym"), item.get("error"))
                    continue

                sym = item["sym"]
                row = db.query(VolumeWatchlist).filter(VolumeWatchlist.sym == sym).first()
                if row is None:
                    continue

                new_ratio = float(item.get("volRatio", row.last_ratio))
                new_band = int(new_ratio)

                # Update all fields with fresh data
                row.last_ratio   = new_ratio
                row.last_avg30   = float(item.get("avg30",   row.last_avg30))
                row.last_cur_vol = float(item.get("curVol",  row.last_cur_vol))
                row.last_pcr     = float(item.get("pcr",     row.last_pcr))
                row.last_oi_trend = str(item.get("oiTrend",  row.last_oi_trend))
                row.last_signal  = str(item.get("signal",    row.last_signal))
                row.last_checked = now

                # Fire Telegram if a new integer band is crossed
                if new_band > row.last_crossed and new_ratio > 0:
                    ok = send_volume_alert(
                        sym=row.sym,
                        name=row.name,
                        band=new_band,
                        ratio=new_ratio,
                        signal=row.last_signal,
                        cur_vol=row.last_cur_vol,
                        avg30=row.last_avg30,
                    )
                    if ok:
                        row.last_crossed = new_band
                        alerts_fired += 1
                        logger.info(
                            "ALERT fired: %s crossed %dx (ratio=%.2f, prev_crossed=%d)",
                            sym, new_band, new_ratio, row.last_crossed,
                        )
                    else:
                        logger.warning("Telegram send failed for %s — last_crossed NOT updated", sym)

            db.commit()

        logger.info(
            "Watchlist refresh+alert complete: %d symbols, %d alert(s) fired",
            len(syms), alerts_fired,
        )

    # ── Daily reset (market open) ─────────────────────────────────────────────

    def _seconds_until_next_reset(self) -> float:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=DAILY_RESET_HOUR_UTC, minute=DAILY_RESET_MINUTE_UTC, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def _schedule_daily_reset(self) -> None:
        delay = self._seconds_until_next_reset()
        self._reset_timer = threading.Timer(delay, self._run_daily_reset)
        self._reset_timer.daemon = True
        self._reset_timer.start()
        logger.info(
            "Daily reset scheduled in %.0f s (%.1f h) at %02d:%02d UTC",
            delay, delay / 3600, DAILY_RESET_HOUR_UTC, DAILY_RESET_MINUTE_UTC,
        )

    def _run_daily_reset(self) -> None:
        try:
            self._reset_last_crossed()
        except Exception as exc:
            logger.error("Daily reset error: %s", exc)
        finally:
            if self._started:
                self._schedule_daily_reset()

    def _reset_last_crossed(self) -> None:
        """Zero last_crossed at market open so every integer band re-arms for the new day."""
        with SessionLocal() as db:
            rows = db.query(VolumeWatchlist).all()
            for row in rows:
                row.last_crossed = 0
            db.commit()
            logger.info("Daily reset: last_crossed cleared for %d symbols", len(rows))

    # ── serialisation ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: VolumeWatchlist) -> dict:
        return {
            "sym":         row.sym,
            "name":        row.name,
            "lastCrossed": row.last_crossed,
            "lastRatio":   row.last_ratio,
            "avg30":       row.last_avg30,
            "curVol":      row.last_cur_vol,
            "pcr":         row.last_pcr,
            "oiTrend":     row.last_oi_trend,
            "signal":      row.last_signal,
            "lastChecked": row.last_checked.strftime("%H:%M") if row.last_checked else "—",
        }


# Singleton
alert_manager = AlertManager()
