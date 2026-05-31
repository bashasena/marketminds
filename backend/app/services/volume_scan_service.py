"""Volume surge scanner — fetches real volume via Yahoo Finance chart API (query2).

Supports NASDAQ 100 and S&P 500 top constituents. No API key required.
"""

from __future__ import annotations

import logging
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Literal

import requests
import yfinance as yf

_YF_SESSION = requests.Session()
_YF_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

logger = logging.getLogger(__name__)

Signal = Literal["bullish", "bearish", "neutral"]

NASDAQ_STOCKS = [
    # Mega-cap tech & e-commerce
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("META", "Meta Platforms"),
    ("GOOGL", "Alphabet A"),
    ("GOOG", "Alphabet C"),
    ("TSLA", "Tesla"),
    ("AVGO", "Broadcom"),
    # Consumer / Retail / Media
    ("COST", "Costco"),
    ("NFLX", "Netflix"),
    ("SBUX", "Starbucks"),
    ("MNST", "Monster Beverage"),
    ("MDLZ", "Mondelez"),
    ("KDP", "Keurig Dr Pepper"),
    ("KHC", "Kraft Heinz"),
    ("DLTR", "Dollar Tree"),
    ("ROST", "Ross Stores"),
    ("LULU", "Lululemon"),
    ("CCEP", "Coca-Cola Europacific"),
    # Semiconductors
    ("AMD", "Advanced Micro Devices"),
    ("QCOM", "Qualcomm"),
    ("INTC", "Intel"),
    ("MU", "Micron Technology"),
    ("AMAT", "Applied Materials"),
    ("LRCX", "Lam Research"),
    ("KLAC", "KLA Corporation"),
    ("MRVL", "Marvell Technology"),
    ("ADI", "Analog Devices"),
    ("MCHP", "Microchip Technology"),
    ("NXPI", "NXP Semiconductors"),
    ("ON", "ON Semiconductor"),
    ("ARM", "ARM Holdings"),
    ("GFS", "GlobalFoundries"),
    # Software / Cloud / Cybersecurity
    ("ADBE", "Adobe"),
    ("CSCO", "Cisco"),
    ("ORCL", "Oracle"),
    ("PANW", "Palo Alto Networks"),
    ("CRWD", "CrowdStrike"),
    ("FTNT", "Fortinet"),
    ("ZS", "Zscaler"),
    ("DDOG", "Datadog"),
    ("WDAY", "Workday"),
    ("TEAM", "Atlassian"),
    ("TTD", "The Trade Desk"),
    ("PYPL", "PayPal"),
    ("SNPS", "Synopsys"),
    ("CDNS", "Cadence Design"),
    ("ROP", "Roper Technologies"),
    ("ANSS", "ANSYS"),
    ("CDW", "CDW"),
    ("CTSH", "Cognizant"),
    ("PLTR", "Palantir"),
    ("APP", "AppLovin"),
    ("COIN", "Coinbase"),
    ("MSTR", "MicroStrategy"),
    ("ADP", "Automatic Data Processing"),
    # Biotech / Healthcare
    ("AMGN", "Amgen"),
    ("GILD", "Gilead Sciences"),
    ("VRTX", "Vertex Pharmaceuticals"),
    ("REGN", "Regeneron"),
    ("ISRG", "Intuitive Surgical"),
    ("DXCM", "DexCom"),
    ("IDXX", "IDEXX Laboratories"),
    ("ILMN", "Illumina"),
    ("BIIB", "Biogen"),
    ("MRNA", "Moderna"),
    ("GEHC", "GE HealthCare"),
    # Travel / Entertainment / Platforms
    ("BKNG", "Booking Holdings"),
    ("ABNB", "Airbnb"),
    ("EXPE", "Expedia"),
    ("MAR", "Marriott"),
    ("EA", "Electronic Arts"),
    ("TTWO", "Take-Two Interactive"),
    ("WBD", "Warner Bros. Discovery"),
    ("DASH", "DoorDash"),
    # Industrials / Logistics
    ("HON", "Honeywell"),
    ("FAST", "Fastenal"),
    ("PCAR", "PACCAR"),
    ("ODFL", "Old Dominion Freight"),
    ("PAYX", "Paychex"),
    ("VRSK", "Verisk Analytics"),
    ("CSGP", "CoStar Group"),
    ("CPRT", "Copart"),
    ("CSX", "CSX Corporation"),
    # Energy / Utilities
    ("CEG", "Constellation Energy"),
    ("EXC", "Exelon"),
    ("XEL", "Xcel Energy"),
    ("FANG", "Diamondback Energy"),
    # International / ADR on NASDAQ
    ("ASML", "ASML Holding"),
    ("AZN", "AstraZeneca"),
    ("MELI", "MercadoLibre"),
    ("PDD", "PDD Holdings"),
    # Comms / Other
    ("SIRI", "SiriusXM"),
]

SP500_STOCKS = [
    # Financials
    ("BRK-B", "Berkshire Hathaway"),
    ("JPM", "JPMorgan Chase"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("BAC", "Bank of America"),
    ("WFC", "Wells Fargo"),
    ("GS", "Goldman Sachs"),
    ("MS", "Morgan Stanley"),
    ("C", "Citigroup"),
    ("AXP", "American Express"),
    ("BLK", "BlackRock"),
    ("SCHW", "Charles Schwab"),
    ("USB", "U.S. Bancorp"),
    ("PNC", "PNC Financial"),
    ("COF", "Capital One"),
    ("TFC", "Truist Financial"),
    ("CB", "Chubb"),
    ("PGR", "Progressive"),
    ("MET", "MetLife"),
    ("PRU", "Prudential"),
    ("AFL", "Aflac"),
    ("TRV", "Travelers"),
    ("ALL", "Allstate"),
    ("ICE", "Intercontinental Exchange"),
    ("CME", "CME Group"),
    ("SPGI", "S&P Global"),
    ("MCO", "Moody's"),
    ("FI", "Fiserv"),
    ("FIS", "Fidelity National"),
    # Healthcare (NYSE-listed)
    ("UNH", "UnitedHealth"),
    ("JNJ", "Johnson & Johnson"),
    ("LLY", "Eli Lilly"),
    ("ABBV", "AbbVie"),
    ("MRK", "Merck"),
    ("ABT", "Abbott Laboratories"),
    ("TMO", "Thermo Fisher"),
    ("DHR", "Danaher"),
    ("PFE", "Pfizer"),
    ("BMY", "Bristol-Myers Squibb"),
    ("CVS", "CVS Health"),
    ("CI", "Cigna"),
    ("HUM", "Humana"),
    ("SYK", "Stryker"),
    ("MDT", "Medtronic"),
    ("BSX", "Boston Scientific"),
    ("EW", "Edwards Lifesciences"),
    ("BDX", "Becton Dickinson"),
    ("IQV", "IQVIA"),
    ("HCA", "HCA Healthcare"),
    ("MCK", "McKesson"),
    ("CAH", "Cardinal Health"),
    # Consumer Staples
    ("PG", "Procter & Gamble"),
    ("KO", "Coca-Cola"),
    ("WMT", "Walmart"),
    ("PM", "Philip Morris"),
    ("MO", "Altria"),
    ("CL", "Colgate-Palmolive"),
    ("KMB", "Kimberly-Clark"),
    ("GIS", "General Mills"),
    ("K", "Kellanova"),
    ("HSY", "Hershey"),
    ("CAG", "Conagra Brands"),
    ("HRL", "Hormel Foods"),
    ("SJM", "J.M. Smucker"),
    ("CPB", "Campbell Soup"),
    ("CLX", "Clorox"),
    ("CHD", "Church & Dwight"),
    ("EL", "Estee Lauder"),
    ("STZ", "Constellation Brands"),
    # Consumer Discretionary (NYSE)
    ("HD", "Home Depot"),
    ("LOW", "Lowe's"),
    ("MCD", "McDonald's"),
    ("NKE", "Nike"),
    ("TGT", "Target"),
    ("TJX", "TJX Companies"),
    ("F", "Ford Motor"),
    ("GM", "General Motors"),
    ("RIVN", "Rivian"),
    ("HLT", "Hilton Worldwide"),
    ("YUM", "Yum! Brands"),
    ("DRI", "Darden Restaurants"),
    ("CMG", "Chipotle"),
    ("DHI", "D.R. Horton"),
    ("LEN", "Lennar"),
    ("PHM", "PulteGroup"),
    ("BBY", "Best Buy"),
    ("EBAY", "eBay"),
    # Industrials
    ("BA", "Boeing"),
    ("GE", "GE Aerospace"),
    ("CAT", "Caterpillar"),
    ("DE", "Deere & Company"),
    ("UPS", "United Parcel Service"),
    ("FDX", "FedEx"),
    ("RTX", "RTX Corporation"),
    ("LMT", "Lockheed Martin"),
    ("NOC", "Northrop Grumman"),
    ("GD", "General Dynamics"),
    ("MMM", "3M"),
    ("EMR", "Emerson Electric"),
    ("ETN", "Eaton"),
    ("PH", "Parker Hannifin"),
    ("ROK", "Rockwell Automation"),
    ("CMI", "Cummins"),
    ("DOV", "Dover"),
    ("ITW", "Illinois Tool Works"),
    ("SWK", "Stanley Black & Decker"),
    ("IR", "Ingersoll Rand"),
    ("CARR", "Carrier Global"),
    ("OTIS", "Otis Worldwide"),
    ("TDG", "TransDigm"),
    ("LHX", "L3Harris Technologies"),
    ("WAB", "Wabtec"),
    ("UBER", "Uber"),
    ("LYFT", "Lyft"),
    # Technology (NYSE-listed)
    ("IBM", "IBM"),
    ("ACN", "Accenture"),
    ("CRM", "Salesforce"),
    ("NOW", "ServiceNow"),
    ("INTU", "Intuit"),
    ("TXN", "Texas Instruments"),
    ("ANET", "Arista Networks"),
    ("HPQ", "HP Inc."),
    ("HPE", "Hewlett Packard Enterprise"),
    ("DELL", "Dell Technologies"),
    ("WDC", "Western Digital"),
    ("STX", "Seagate Technology"),
    ("TEL", "TE Connectivity"),
    ("APH", "Amphenol"),
    ("GLW", "Corning"),
    ("MSI", "Motorola Solutions"),
    ("KEYS", "Keysight Technologies"),
    # Energy
    ("XOM", "ExxonMobil"),
    ("CVX", "Chevron"),
    ("COP", "ConocoPhillips"),
    ("EOG", "EOG Resources"),
    ("SLB", "SLB"),
    ("OXY", "Occidental Petroleum"),
    ("HAL", "Halliburton"),
    ("BKR", "Baker Hughes"),
    ("VLO", "Valero Energy"),
    ("PSX", "Phillips 66"),
    ("MPC", "Marathon Petroleum"),
    ("DVN", "Devon Energy"),
    ("HES", "Hess"),
    ("APA", "APA Corporation"),
    ("MRO", "Marathon Oil"),
    # Materials
    ("LIN", "Linde"),
    ("APD", "Air Products"),
    ("SHW", "Sherwin-Williams"),
    ("ECL", "Ecolab"),
    ("DD", "DuPont"),
    ("PPG", "PPG Industries"),
    ("NEM", "Newmont"),
    ("FCX", "Freeport-McMoRan"),
    ("NUE", "Nucor"),
    ("STLD", "Steel Dynamics"),
    ("ALB", "Albemarle"),
    ("CF", "CF Industries"),
    ("MOS", "Mosaic"),
    # Utilities
    ("NEE", "NextEra Energy"),
    ("DUK", "Duke Energy"),
    ("SO", "Southern Company"),
    ("D", "Dominion Energy"),
    ("AEP", "American Electric Power"),
    ("SRE", "Sempra"),
    ("PEG", "PSEG"),
    ("ES", "Eversource Energy"),
    ("WEC", "WEC Energy"),
    ("ETR", "Entergy"),
    ("PPL", "PPL Corporation"),
    ("AES", "AES Corporation"),
    ("AWK", "American Water Works"),
    # Communication Services (NYSE)
    ("T", "AT&T"),
    ("VZ", "Verizon"),
    ("DIS", "Walt Disney"),
    ("CMCSA", "Comcast"),
    ("CHTR", "Charter Communications"),
    ("PARA", "Paramount Global"),
    ("OMC", "Omnicom"),
    ("IPG", "Interpublic Group"),
    ("NYT", "New York Times"),
    # Real Estate
    ("AMT", "American Tower"),
    ("PLD", "Prologis"),
    ("CCI", "Crown Castle"),
    ("SPG", "Simon Property"),
    ("O", "Realty Income"),
    ("DLR", "Digital Realty"),
    ("PSA", "Public Storage"),
    ("EQR", "Equity Residential"),
    ("AVB", "AvalonBay Communities"),
    ("WELL", "Welltower"),
    ("VTR", "Ventas"),
    ("ARE", "Alexandria Real Estate"),
]


@dataclass
class VolumeScanResult:
    sym: str
    name: str
    avg30: int
    cur_vol: int
    vol_ratio: float
    pcr: float
    oi_trend: str
    signal: Signal
    error: str | None = None


def _yfin_sym(sym: str, market: str) -> str:
    return f"{sym}.NS" if market == "nse" else sym


def _classify_signal(pcr: float, vol_ratio: float) -> Signal:
    if pcr < 0.8 and vol_ratio > 1.5:
        return "bullish"
    if pcr > 1.3 and vol_ratio > 1.5:
        return "bearish"
    return "neutral"


def _fetch_volume_chart(yfin_sym: str) -> tuple[int, int]:
    """
    Fetch (current_volume, avg30_volume) via Yahoo Finance chart API (query2).
    Uses a custom User-Agent to avoid rate-limiting that affects the yfinance wrapper.
    Returns (0, 0) on failure.
    """
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yfin_sym}?range=35d&interval=1d"
    try:
        r = _YF_SESSION.get(url, timeout=10)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        volumes = result["indicators"]["quote"][0].get("volume") or []
        volumes = [v for v in volumes if v is not None and v > 0]
        if not volumes:
            return 0, 0
        cur_vol = int(volumes[-1])
        avg30 = int(statistics.mean(volumes))
        return cur_vol, avg30
    except Exception as e:
        logger.debug("Chart API volume fetch failed for %s: %s", yfin_sym, e)
        return 0, 0


def _fetch_pcr(yfin_sym: str) -> tuple[float, str]:
    """Fetch Put-Call Ratio from nearest expiry options chain via yfinance. Returns (pcr, oi_trend)."""
    try:
        ticker = yf.Ticker(yfin_sym, session=_YF_SESSION)
        expirations = ticker.options
        if not expirations:
            return 1.0, "Flat"
        chain = ticker.option_chain(expirations[0])
        call_oi = chain.calls["openInterest"].sum() if "openInterest" in chain.calls.columns else 0
        put_oi = chain.puts["openInterest"].sum() if "openInterest" in chain.puts.columns else 0
        if call_oi == 0:
            return 1.0, "Flat"
        pcr = round(float(put_oi) / float(call_oi), 2)
        oi_trend = "Rising" if put_oi > call_oi * 1.2 else "Falling" if call_oi > put_oi * 1.2 else "Flat"
        return pcr, oi_trend
    except Exception as e:
        logger.debug("PCR fetch failed for %s: %s", yfin_sym, e)
        return 1.0, "Flat"


def _fetch_stock(sym: str, name: str, market: str) -> VolumeScanResult:
    yfin_sym = _yfin_sym(sym, market)
    try:
        cur_vol, avg30 = _fetch_volume_chart(yfin_sym)
        if avg30 == 0:
            avg30 = cur_vol or 1
        vol_ratio = round(cur_vol / avg30, 2) if avg30 > 0 else 1.0
        pcr, oi_trend = _fetch_pcr(yfin_sym)
        signal = _classify_signal(pcr, vol_ratio)
        return VolumeScanResult(sym=sym, name=name, avg30=avg30, cur_vol=cur_vol,
                                vol_ratio=vol_ratio, pcr=pcr, oi_trend=oi_trend, signal=signal)
    except Exception as e:
        logger.warning("Volume scan failed for %s: %s", sym, e)
        return VolumeScanResult(sym=sym, name=name, avg30=0, cur_vol=0,
                                vol_ratio=0.0, pcr=1.0, oi_trend="Flat", signal="neutral", error=str(e))


def run_volume_scan(
    market: str = "nasdaq",
    vol_threshold: float = 1.5,
    pcr_min: float = 0.7,
    max_workers: int = 10,
) -> dict:
    """
    Scan stocks for volume surges.
    market: "nasdaq" | "sp500" | "both"
    Returns dict with scanned list, filtered alerts, and summary metrics.
    """
    pool: list[tuple[str, str, str]] = []
    if market in ("nasdaq", "both"):
        pool += [(sym, name, "nasdaq") for sym, name in NASDAQ_STOCKS]
    if market in ("sp500", "both"):
        pool += [(sym, name, "sp500") for sym, name in SP500_STOCKS]

    results: list[VolumeScanResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_fetch_stock, sym, name, mkt): sym for sym, name, mkt in pool}
        for fut in as_completed(futures):
            results.append(fut.result())

    all_stocks = [r for r in results if r.error is None]
    filtered = [
        r for r in all_stocks
        if r.vol_ratio >= vol_threshold and r.pcr >= pcr_min
    ]
    filtered.sort(key=lambda r: r.vol_ratio, reverse=True)

    bull = sum(1 for r in filtered if r.signal == "bullish")
    bear = sum(1 for r in filtered if r.signal == "bearish")

    def to_dict(r: VolumeScanResult) -> dict:
        return {
            "sym": r.sym,
            "name": r.name,
            "avg30": r.avg30,
            "curVol": r.cur_vol,
            "volRatio": r.vol_ratio,
            "pcr": r.pcr,
            "oiTrend": r.oi_trend,
            "signal": r.signal,
        }

    errors = [{"sym": r.sym, "error": r.error} for r in results if r.error]

    return {
        "scanned": len(all_stocks),
        "alerts": [to_dict(r) for r in filtered],
        "metrics": {
            "scanned": len(all_stocks),
            "alertCount": len(filtered),
            "bullish": bull,
            "bearish": bear,
        },
        "errors": errors,
    }


# Build a combined symbol→name lookup from both lists
_ALL_SYM_TO_NAME: dict[str, str] = {
    sym: name for sym, name in NASDAQ_STOCKS + SP500_STOCKS
}


def run_watch_scan(symbols: list[str], max_workers: int = 10) -> list[dict]:
    """
    Scan a specific list of symbols (the user's watchlist).
    Returns current vol data for each — no threshold filtering, caller decides what to alert.
    """
    # Determine market suffix: symbols in NASDAQ list are plain, others also plain (both US markets)
    pool = [(sym, _ALL_SYM_TO_NAME.get(sym, sym), "nasdaq") for sym in symbols]

    results: list[VolumeScanResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_fetch_stock, sym, name, mkt): sym for sym, name, mkt in pool}
        for fut in as_completed(futures):
            results.append(fut.result())

    return [
        {
            "sym": r.sym,
            "name": r.name,
            "avg30": r.avg30,
            "curVol": r.cur_vol,
            "volRatio": r.vol_ratio,
            "pcr": r.pcr,
            "oiTrend": r.oi_trend,
            "signal": r.signal,
            "error": r.error,
        }
        for r in sorted(results, key=lambda r: r.sym)
    ]

