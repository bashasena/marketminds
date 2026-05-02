"""
Composite market sentiment (0 = max bearish, 100 = max bullish).

Subscores are each mapped to [0, 100] then combined with fixed weights.
Weights are chosen for an India cash + derivatives desk-style read:

| Component        | Weight | Rationale                                      |
|-----------------|--------|------------------------------------------------|
| Index % change  | 0.22   | Trend and risk appetite in the headline index |
| India VIX       | 0.15   | Fear gauge; rising VIX subtracts from score   |
| Options PCR(OI) ATM ±3 | 0.15   | Positioning skew near the money |
| FII net flow    | 0.18   | Foreign positioning in cash market            |
| X / FinBERT     | 0.30   | Narrative + positioning chatter from List     |

TOTAL_WEIGHT must remain 1.0 when adjusting these constants.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

W_INDEX = 0.22
W_VIX = 0.15
W_PCR = 0.15
W_FII = 0.18
W_X = 0.30

TOTAL_WEIGHT = W_INDEX + W_VIX + W_PCR + W_FII + W_X


@dataclass
class CompositeResult:
    score_0_100: float
    label: str
    components: dict[str, float]
    weights: dict[str, float]
    explanation: str


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def subscore_index(pct_change: float | None) -> float:
    """Map daily % change roughly: -3% -> ~25, 0% -> 50, +3% -> 75."""
    if pct_change is None:
        return 50.0
    x = 50.0 + pct_change * 8.0
    return _clamp(x)


def subscore_vix(level: float | None, pct_change: float | None) -> float:
    """Higher VIX and sharp VIX spikes are treated as bearish."""
    if level is None:
        return 50.0
    # Level effect: VIX ~12 low fear, ~20 elevated, ~30 panic
    level_score = 70.0 - max(0.0, level - 12.0) * 2.2
    ch = pct_change or 0.0
    spike_penalty = min(25.0, max(0.0, ch) * 3.0)
    return _clamp(level_score - spike_penalty)


def subscore_pcr(pcr: float | None) -> float:
    """
    OI PCR: very low (<0.7) call-heavy / complacent; very high (>1.3) put-heavy.
    We treat moderate-high PCR as supportive for a contrarian-bullish Indian context.
    """
    if pcr is None:
        return 50.0
    if pcr < 0.5:
        return 35.0
    if pcr < 0.8:
        return 42.0 + (pcr - 0.5) * 26.0
    if pcr <= 1.4:
        return 50.0 + (pcr - 0.8) * 25.0
    return _clamp(65.0 + (pcr - 1.4) * 10.0)


def subscore_fii(net_crores: float | None) -> float:
    """Scale FII net (INR crores) into a sentiment subscore."""
    if net_crores is None:
        return 50.0
    x = 50.0 + net_crores / 800.0 * 10.0
    return _clamp(x)


def subscore_x(x_score: float | None) -> float:
    if x_score is None:
        return 50.0
    return _clamp(float(x_score))


def compute_composite(
    nifty_pct: float | None,
    vix_level: float | None,
    vix_pct_change: float | None,
    pcr_oi: float | None,
    fii_net_crores: float | None,
    x_sentiment_0_100: float | None,
) -> CompositeResult:
    assert math.isclose(TOTAL_WEIGHT, 1.0), "Composite weights must sum to 1.0"

    s_idx = subscore_index(nifty_pct)
    s_vix = subscore_vix(vix_level, vix_pct_change)
    s_pcr = subscore_pcr(pcr_oi)
    s_fii = subscore_fii(fii_net_crores)
    s_x = subscore_x(x_sentiment_0_100)

    score = (
        W_INDEX * s_idx
        + W_VIX * s_vix
        + W_PCR * s_pcr
        + W_FII * s_fii
        + W_X * s_x
    )
    score = round(_clamp(score), 2)

    if score >= 62:
        label = "Bullish"
    elif score <= 42:
        label = "Bearish"
    else:
        label = "Neutral"

    parts = []
    if nifty_pct is not None and abs(nifty_pct) > 0.05:
        parts.append("index move")
    if vix_level is not None and vix_level > 16:
        parts.append("elevated VIX")
    if pcr_oi is not None and pcr_oi > 1.05:
        parts.append("supportive PCR skew")
    if fii_net_crores is not None and fii_net_crores > 0:
        parts.append("FII net buying")
    elif fii_net_crores is not None and fii_net_crores < 0:
        parts.append("FII net selling")
    if s_x >= 58:
        parts.append("constructive List sentiment")
    elif s_x <= 42:
        parts.append("cautious List sentiment")

    if not parts:
        explanation = "Balanced inputs with no strong single driver."
    else:
        explanation = "Key drivers: " + ", ".join(parts) + "."

    return CompositeResult(
        score_0_100=score,
        label=label,
        components={
            "index": round(s_idx, 2),
            "vix": round(s_vix, 2),
            "pcr": round(s_pcr, 2),
            "fii": round(s_fii, 2),
            "x": round(s_x, 2),
        },
        weights={
            "index": W_INDEX,
            "vix": W_VIX,
            "pcr": W_PCR,
            "fii": W_FII,
            "x": W_X,
        },
        explanation=explanation,
    )
