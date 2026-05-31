"""Server-side volume alert manager.

Maintains a watchlist of symbols and polls them every 5 minutes.
Fires Telegram notifications when a new integer band is crossed.
State is in-memory (reset on restart) — the frontend localStorage acts as
the persistent source of truth and re-registers on page load.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict

from app.services.telegram_service import send_volume_alert
from app.services.volume_scan_service import run_watch_scan

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 5 * 60  # 5 minutes


@dataclass
class WatchEntry:
    sym: str
    name: str
    last_crossed: int = 0  # highest integer band already notified


class AlertManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watchlist: Dict[str, WatchEntry] = {}
        self._timer: threading.Timer | None = None
        self._started = False

    # ── Public API ──────────────────────────────────────────────────────────

    def add(self, sym: str, name: str, current_ratio: float) -> None:
        """Add a symbol to the watchlist. Sets last_crossed to the current
        integer band so we don't immediately re-fire an existing level."""
        with self._lock:
            if sym not in self._watchlist:
                self._watchlist[sym] = WatchEntry(
                    sym=sym,
                    name=name,
                    last_crossed=int(current_ratio),  # don't re-alert for current level
                )
                logger.info("Alert added: %s (current ratio %.2f, last_crossed=%d)", sym, current_ratio, int(current_ratio))

    def remove(self, sym: str) -> bool:
        with self._lock:
            existed = sym in self._watchlist
            self._watchlist.pop(sym, None)
            if existed:
                logger.info("Alert removed: %s", sym)
            return existed

    def list_symbols(self) -> list[dict]:
        with self._lock:
            return [
                {"sym": e.sym, "name": e.name, "last_crossed": e.last_crossed}
                for e in self._watchlist.values()
            ]

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._schedule_next()
            logger.info("AlertManager polling started (every %ds)", POLL_INTERVAL_SEC)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._started = False

    # ── Internal polling ────────────────────────────────────────────────────

    def _schedule_next(self) -> None:
        self._timer = threading.Timer(POLL_INTERVAL_SEC, self._poll)
        self._timer.daemon = True
        self._timer.start()

    def _poll(self) -> None:
        try:
            self._check_thresholds()
        except Exception as exc:
            logger.error("AlertManager poll error: %s", exc)
        finally:
            if self._started:
                self._schedule_next()

    def _check_thresholds(self) -> None:
        with self._lock:
            syms = [e.sym for e in self._watchlist.values()]
        if not syms:
            return

        logger.info("AlertManager polling %d symbols: %s", len(syms), syms)
        results = run_watch_scan(syms)

        for item in results:
            if item.get("error"):
                continue
            sym = item["sym"]
            ratio = float(item.get("volRatio", 0))
            new_band = int(ratio)

            with self._lock:
                entry = self._watchlist.get(sym)
                if entry is None:
                    continue
                if new_band > entry.last_crossed:
                    # Fire Telegram
                    send_volume_alert(
                        sym=sym,
                        name=item.get("name", sym),
                        band=new_band,
                        ratio=ratio,
                        signal=item.get("signal", "neutral"),
                        cur_vol=float(item.get("curVol", 0)),
                        avg30=float(item.get("avg30", 0)),
                    )
                    entry.last_crossed = new_band
                    logger.info("Threshold crossed: %s → %d×", sym, new_band)


# Singleton — imported by main.py and routers
alert_manager = AlertManager()
