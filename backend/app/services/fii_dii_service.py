"""FII/DII net cash-market flows from NSE."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.services.nse_client import get_nse_client

logger = logging.getLogger(__name__)


@dataclass
class FiiDiiSnapshot:
    as_of_date: date | None
    fii_net_crores: float | None
    dii_net_crores: float | None
    raw: list[dict[str, Any]]


def _parse_fii_dii_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_net_value(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_fii_dii() -> FiiDiiSnapshot:
    try:
        nse = get_nse_client()
        data = nse.get_json("/api/fiidii")
    except Exception as e:
        logger.warning("FII/DII NSE endpoint unavailable: %s", e)
        return FiiDiiSnapshot(as_of_date=None, fii_net_crores=None, dii_net_crores=None, raw=[])
    rows = data if isinstance(data, list) else data.get("data", []) or []
    grouped: dict[date, dict[str, float | None]] = defaultdict(lambda: {"fii": None, "dii": None})
    for row in rows:
        d_raw = row.get("date") or row.get("tradeDate")
        row_date = _parse_fii_dii_date(str(d_raw)) if d_raw else None
        if row_date is None:
            continue
        cat = str(row.get("category") or "").upper()
        nv = _parse_net_value(row.get("netValue") or row.get("net_value"))
        if "FII" in cat or "FPI" in cat:
            grouped[row_date]["fii"] = nv
        elif "DII" in cat:
            grouped[row_date]["dii"] = nv
    as_of = max(grouped.keys()) if grouped else None
    fii_net = grouped[as_of]["fii"] if as_of else None
    dii_net = grouped[as_of]["dii"] if as_of else None
    return FiiDiiSnapshot(as_of_date=as_of, fii_net_crores=fii_net, dii_net_crores=dii_net, raw=rows[:10])
