"""Telegram notification helper for volume alerts."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_SIGNAL_EMOJI = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}


def send_volume_alert(sym: str, name: str, band: int, ratio: float, signal: str, cur_vol: float, avg30: float) -> bool:
    """Send a Telegram message when a volume threshold band is crossed.

    Returns True on success, False on failure (non-raising).
    """
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.warning("Telegram not configured — TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing")
        return False

    emoji = _SIGNAL_EMOJI.get(signal, "🟡")
    vol_fmt = _fmt(cur_vol)
    avg_fmt = _fmt(avg30)

    text = (
        f"🔔 <b>Volume Alert: {sym}</b>\n"
        f"{name}\n\n"
        f"📈 Volume crossed <b>{band}×</b> average!\n"
        f"Current: <b>{vol_fmt}</b>  |  30D avg: {avg_fmt}\n"
        f"Ratio: <b>{ratio:.2f}×</b>\n"
        f"{emoji} Signal: <b>{signal.capitalize()}</b>"
    )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Telegram alert sent: %s crossed %d×", sym, band)
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


def _fmt(n: float) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}K"
    return str(int(n))
