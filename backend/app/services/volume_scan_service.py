"""Volume surge scanner — fetches real volume via Yahoo Finance chart API (query2).

Supports full NASDAQ 100 (101 stocks) and full S&P 500 (503 stocks). No API key required.
"""

from __future__ import annotations

import logging
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Literal

import requests
import yfinance as yf

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    return s

# Shared session for the full bulk scanner (604 stocks, high concurrency)
_YF_SESSION = _make_session()

# Dedicated session for the watchlist refresh — kept separate so the bulk
# scanner's connection-pool exhaustion / rate-limit doesn't zero out watchlist data
_WATCH_SESSION = _make_session()

logger = logging.getLogger(__name__)

Signal = Literal["bullish", "bearish", "neutral"]

NASDAQ_STOCKS = [
    ("ADBE", "Adobe Inc."),
    ("AMD", "Advanced Micro Devices"),
    ("ABNB", "Airbnb"),
    ("ALNY", "Alnylam Pharmaceuticals"),
    ("GOOGL", "Alphabet Inc. (Class A)"),
    ("GOOG", "Alphabet Inc. (Class C)"),
    ("AMZN", "Amazon"),
    ("AEP", "American Electric Power"),
    ("AMGN", "Amgen"),
    ("ADI", "Analog Devices"),
    ("AAPL", "Apple Inc."),
    ("AMAT", "Applied Materials"),
    ("APP", "AppLovin"),
    ("ARM", "Arm Holdings"),
    ("ASML", "ASML Holding"),
    ("ADSK", "Autodesk"),
    ("ADP", "Automatic Data Processing"),
    ("AXON", "Axon Enterprise"),
    ("BKR", "Baker Hughes"),
    ("BKNG", "Booking Holdings"),
    ("AVGO", "Broadcom"),
    ("CDNS", "Cadence Design Systems"),
    ("CHTR", "Charter Communications"),
    ("CTAS", "Cintas"),
    ("CSCO", "Cisco"),
    ("CCEP", "Coca-Cola Europacific Partners"),
    ("CTSH", "Cognizant"),
    ("CMCSA", "Comcast"),
    ("CEG", "Constellation Energy"),
    ("CPRT", "Copart"),
    ("COST", "Costco"),
    ("CRWD", "CrowdStrike"),
    ("CSX", "CSX Corporation"),
    ("DDOG", "Datadog"),
    ("DXCM", "DexCom"),
    ("FANG", "Diamondback Energy"),
    ("DASH", "DoorDash"),
    ("EA", "Electronic Arts"),
    ("EXC", "Exelon"),
    ("FAST", "Fastenal"),
    ("FER", "Ferrovial"),
    ("FTNT", "Fortinet"),
    ("GEHC", "GE HealthCare"),
    ("GILD", "Gilead Sciences"),
    ("HON", "Honeywell"),
    ("IDXX", "Idexx Laboratories"),
    ("INSM", "Insmed Incorporated"),
    ("INTC", "Intel"),
    ("INTU", "Intuit"),
    ("ISRG", "Intuitive Surgical"),
    ("KDP", "Keurig Dr Pepper"),
    ("KLAC", "KLA Corporation"),
    ("KHC", "Kraft Heinz"),
    ("LRCX", "Lam Research"),
    ("LIN", "Linde plc"),
    ("LITE", "Lumentum"),
    ("MAR", "Marriott International"),
    ("MRVL", "Marvell Technology"),
    ("MELI", "Mercado Libre"),
    ("META", "Meta Platforms"),
    ("MCHP", "Microchip Technology"),
    ("MU", "Micron Technology"),
    ("MSFT", "Microsoft"),
    ("MSTR", "MicroStrategy"),
    ("MDLZ", "Mondelez International"),
    ("MPWR", "Monolithic Power Systems"),
    ("MNST", "Monster Beverage"),
    ("NFLX", "Netflix, Inc."),
    ("NVDA", "Nvidia"),
    ("NXPI", "NXP Semiconductors"),
    ("ORLY", "OReilly Automotive"),
    ("ODFL", "Old Dominion Freight Line"),
    ("PCAR", "Paccar"),
    ("PLTR", "Palantir Technologies"),
    ("PANW", "Palo Alto Networks"),
    ("PAYX", "Paychex"),
    ("PYPL", "PayPal"),
    ("PDD", "PDD Holdings"),
    ("PEP", "PepsiCo"),
    ("QCOM", "Qualcomm"),
    ("REGN", "Regeneron Pharmaceuticals"),
    ("ROP", "Roper Technologies"),
    ("ROST", "Ross Stores"),
    ("SNDK", "Sandisk"),
    ("STX", "Seagate Technology"),
    ("SHOP", "Shopify"),
    ("SBUX", "Starbucks"),
    ("SNPS", "Synopsys"),
    ("TMUS", "T-Mobile US"),
    ("TTWO", "Take-Two Interactive"),
    ("TSLA", "Tesla, Inc."),
    ("TXN", "Texas Instruments"),
    ("TRI", "Thomson Reuters"),
    ("VRSK", "Verisk Analytics"),
    ("VRTX", "Vertex Pharmaceuticals"),
    ("WMT", "Walmart"),
    ("WBD", "Warner Bros. Discovery"),
    ("WDC", "Western Digital"),
    ("WDAY", "Workday, Inc."),
    ("XEL", "Xcel Energy"),
    ("ZS", "Zscaler"),
]

SP500_STOCKS = [
    ("MMM", "3M"),
    ("AOS", "A. O. Smith"),
    ("ABT", "Abbott Laboratories"),
    ("ABBV", "AbbVie"),
    ("ACN", "Accenture"),
    ("ADBE", "Adobe Inc."),
    ("AMD", "Advanced Micro Devices"),
    ("AES", "AES Corporation"),
    ("AFL", "Aflac"),
    ("A", "Agilent Technologies"),
    ("APD", "Air Products"),
    ("ABNB", "Airbnb"),
    ("AKAM", "Akamai Technologies"),
    ("ALB", "Albemarle Corporation"),
    ("ARE", "Alexandria Real Estate Equities"),
    ("ALGN", "Align Technology"),
    ("ALLE", "Allegion"),
    ("LNT", "Alliant Energy"),
    ("ALL", "Allstate"),
    ("GOOGL", "Alphabet Inc. (Class A)"),
    ("GOOG", "Alphabet Inc. (Class C)"),
    ("MO", "Altria"),
    ("AMZN", "Amazon"),
    ("AMCR", "Amcor"),
    ("AEE", "Ameren"),
    ("AEP", "American Electric Power"),
    ("AXP", "American Express"),
    ("AIG", "American International Group"),
    ("AMT", "American Tower"),
    ("AWK", "American Water Works"),
    ("AMP", "Ameriprise Financial"),
    ("AME", "Ametek"),
    ("AMGN", "Amgen"),
    ("APH", "Amphenol"),
    ("ADI", "Analog Devices"),
    ("AON", "Aon plc"),
    ("APA", "APA Corporation"),
    ("APO", "Apollo Global Management"),
    ("AAPL", "Apple Inc."),
    ("AMAT", "Applied Materials"),
    ("APP", "AppLovin"),
    ("APTV", "Aptiv"),
    ("ACGL", "Arch Capital Group"),
    ("ADM", "Archer Daniels Midland"),
    ("ARES", "Ares Management"),
    ("ANET", "Arista Networks"),
    ("AJG", "Arthur J. Gallagher & Co."),
    ("AIZ", "Assurant"),
    ("T", "AT&T"),
    ("ATO", "Atmos Energy"),
    ("ADSK", "Autodesk"),
    ("ADP", "Automatic Data Processing"),
    ("AZO", "AutoZone"),
    ("AVB", "AvalonBay Communities"),
    ("AVY", "Avery Dennison"),
    ("AXON", "Axon Enterprise"),
    ("BKR", "Baker Hughes"),
    ("BALL", "Ball Corporation"),
    ("BAC", "Bank of America"),
    ("BAX", "Baxter International"),
    ("BDX", "Becton Dickinson"),
    ("BRK-B", "Berkshire Hathaway"),
    ("BBY", "Best Buy"),
    ("TECH", "Bio-Techne"),
    ("BIIB", "Biogen"),
    ("BLK", "BlackRock"),
    ("BX", "Blackstone Inc."),
    ("XYZ", "Block, Inc."),
    ("BNY", "BNY Mellon"),
    ("BA", "Boeing"),
    ("BKNG", "Booking Holdings"),
    ("BSX", "Boston Scientific"),
    ("BMY", "Bristol Myers Squibb"),
    ("AVGO", "Broadcom"),
    ("BR", "Broadridge Financial Solutions"),
    ("BRO", "Brown & Brown"),
    ("BF-B", "Brown–Forman"),
    ("BLDR", "Builders FirstSource"),
    ("BG", "Bunge Global"),
    ("BXP", "BXP, Inc."),
    ("CHRW", "C.H. Robinson"),
    ("CDNS", "Cadence Design Systems"),
    ("CPT", "Camden Property Trust"),
    ("CPB", "Campbells Company (The)"),
    ("COF", "Capital One"),
    ("CAH", "Cardinal Health"),
    ("CCL", "Carnival Corporation"),
    ("CARR", "Carrier Global"),
    ("CVNA", "Carvana"),
    ("CASY", "Caseys"),
    ("CAT", "Caterpillar Inc."),
    ("CBOE", "Cboe Global Markets"),
    ("CBRE", "CBRE Group"),
    ("CDW", "CDW Corporation"),
    ("COR", "Cencora"),
    ("CNC", "Centene Corporation"),
    ("CNP", "CenterPoint Energy"),
    ("CF", "CF Industries"),
    ("CRL", "Charles River Laboratories"),
    ("SCHW", "Charles Schwab Corporation"),
    ("CHTR", "Charter Communications"),
    ("CVX", "Chevron Corporation"),
    ("CMG", "Chipotle Mexican Grill"),
    ("CB", "Chubb Limited"),
    ("CHD", "Church & Dwight"),
    ("CIEN", "Ciena"),
    ("CI", "Cigna"),
    ("CINF", "Cincinnati Financial"),
    ("CTAS", "Cintas"),
    ("CSCO", "Cisco"),
    ("C", "Citigroup"),
    ("CFG", "Citizens Financial Group"),
    ("CLX", "Clorox"),
    ("CME", "CME Group"),
    ("CMS", "CMS Energy"),
    ("KO", "Coca-Cola Company (The)"),
    ("CTSH", "Cognizant"),
    ("COHR", "Coherent Corp."),
    ("COIN", "Coinbase"),
    ("CL", "Colgate-Palmolive"),
    ("CMCSA", "Comcast"),
    ("FIX", "Comfort Systems USA"),
    ("CAG", "Conagra Brands"),
    ("COP", "ConocoPhillips"),
    ("ED", "Consolidated Edison"),
    ("STZ", "Constellation Brands"),
    ("CEG", "Constellation Energy"),
    ("COO", "Cooper Companies (The)"),
    ("CPRT", "Copart"),
    ("GLW", "Corning Inc."),
    ("CPAY", "Corpay"),
    ("CTVA", "Corteva"),
    ("CSGP", "CoStar Group"),
    ("COST", "Costco"),
    ("CRH", "CRH plc"),
    ("CRWD", "CrowdStrike"),
    ("CCI", "Crown Castle"),
    ("CSX", "CSX Corporation"),
    ("CMI", "Cummins"),
    ("CVS", "CVS Health"),
    ("DHR", "Danaher Corporation"),
    ("DRI", "Darden Restaurants"),
    ("DDOG", "Datadog"),
    ("DVA", "DaVita"),
    ("DECK", "Deckers Brands"),
    ("DE", "Deere & Company"),
    ("DELL", "Dell Technologies"),
    ("DAL", "Delta Air Lines"),
    ("DVN", "Devon Energy"),
    ("DXCM", "Dexcom"),
    ("FANG", "Diamondback Energy"),
    ("DLR", "Digital Realty"),
    ("DG", "Dollar General"),
    ("DLTR", "Dollar Tree"),
    ("D", "Dominion Energy"),
    ("DPZ", "Dominos"),
    ("DASH", "DoorDash"),
    ("DOV", "Dover Corporation"),
    ("DOW", "Dow Inc."),
    ("DHI", "D. R. Horton"),
    ("DTE", "DTE Energy"),
    ("DUK", "Duke Energy"),
    ("DD", "DuPont"),
    ("ETN", "Eaton Corporation"),
    ("EBAY", "eBay Inc."),
    ("SATS", "EchoStar"),
    ("ECL", "Ecolab"),
    ("EIX", "Edison International"),
    ("EW", "Edwards Lifesciences"),
    ("EA", "Electronic Arts"),
    ("ELV", "Elevance Health"),
    ("EME", "Emcor"),
    ("EMR", "Emerson Electric"),
    ("ETR", "Entergy"),
    ("EOG", "EOG Resources"),
    ("EPAM", "EPAM Systems"),
    ("EQT", "EQT Corporation"),
    ("EFX", "Equifax"),
    ("EQIX", "Equinix"),
    ("EQR", "Equity Residential"),
    ("ERIE", "Erie Indemnity"),
    ("ESS", "Essex Property Trust"),
    ("EL", "Estée Lauder Companies (The)"),
    ("EG", "Everest Group"),
    ("EVRG", "Evergy"),
    ("ES", "Eversource Energy"),
    ("EXC", "Exelon"),
    ("EXE", "Expand Energy"),
    ("EXPE", "Expedia Group"),
    ("EXPD", "Expeditors International"),
    ("EXR", "Extra Space Storage"),
    ("XOM", "ExxonMobil"),
    ("FFIV", "F5, Inc."),
    ("FDS", "FactSet"),
    ("FICO", "Fair Isaac"),
    ("FAST", "Fastenal"),
    ("FRT", "Federal Realty Investment Trust"),
    ("FDX", "FedEx"),
    ("FIS", "Fidelity National Information Services"),
    ("FITB", "Fifth Third Bancorp"),
    ("FSLR", "First Solar"),
    ("FE", "FirstEnergy"),
    ("FISV", "Fiserv"),
    ("F", "Ford Motor Company"),
    ("FTNT", "Fortinet"),
    ("FTV", "Fortive"),
    ("FOXA", "Fox Corporation (Class A)"),
    ("FOX", "Fox Corporation (Class B)"),
    ("BEN", "Franklin Resources"),
    ("FCX", "Freeport-McMoRan"),
    ("GRMN", "Garmin"),
    ("IT", "Gartner"),
    ("GE", "GE Aerospace"),
    ("GEHC", "GE HealthCare"),
    ("GEV", "GE Vernova"),
    ("GEN", "Gen Digital"),
    ("GNRC", "Generac"),
    ("GD", "General Dynamics"),
    ("GIS", "General Mills"),
    ("GM", "General Motors"),
    ("GPC", "Genuine Parts Company"),
    ("GILD", "Gilead Sciences"),
    ("GPN", "Global Payments"),
    ("GL", "Globe Life"),
    ("GDDY", "GoDaddy"),
    ("GS", "Goldman Sachs"),
    ("HAL", "Halliburton"),
    ("HIG", "Hartford (The)"),
    ("HAS", "Hasbro"),
    ("HCA", "HCA Healthcare"),
    ("DOC", "Healthpeak Properties"),
    ("HSIC", "Henry Schein"),
    ("HSY", "Hershey Company (The)"),
    ("HPE", "Hewlett Packard Enterprise"),
    ("HLT", "Hilton Worldwide"),
    ("HD", "Home Depot (The)"),
    ("HON", "Honeywell"),
    ("HRL", "Hormel Foods"),
    ("HST", "Host Hotels & Resorts"),
    ("HWM", "Howmet Aerospace"),
    ("HPQ", "HP Inc."),
    ("HUBB", "Hubbell Incorporated"),
    ("HUM", "Humana"),
    ("HBAN", "Huntington Bancshares"),
    ("HII", "Huntington Ingalls Industries"),
    ("IBM", "IBM"),
    ("IEX", "IDEX Corporation"),
    ("IDXX", "Idexx Laboratories"),
    ("ITW", "Illinois Tool Works"),
    ("INCY", "Incyte"),
    ("IR", "Ingersoll Rand"),
    ("PODD", "Insulet Corporation"),
    ("INTC", "Intel"),
    ("IBKR", "Interactive Brokers"),
    ("ICE", "Intercontinental Exchange"),
    ("IFF", "International Flavors & Fragrances"),
    ("IP", "International Paper"),
    ("INTU", "Intuit"),
    ("ISRG", "Intuitive Surgical"),
    ("IVZ", "Invesco"),
    ("INVH", "Invitation Homes"),
    ("IQV", "IQVIA"),
    ("IRM", "Iron Mountain"),
    ("JBHT", "J.B. Hunt"),
    ("JBL", "Jabil"),
    ("JKHY", "Jack Henry & Associates"),
    ("J", "Jacobs Solutions"),
    ("JNJ", "Johnson & Johnson"),
    ("JCI", "Johnson Controls"),
    ("JPM", "JPMorgan Chase"),
    ("KVUE", "Kenvue"),
    ("KDP", "Keurig Dr Pepper"),
    ("KEY", "KeyCorp"),
    ("KEYS", "Keysight Technologies"),
    ("KMB", "Kimberly-Clark"),
    ("KIM", "Kimco Realty"),
    ("KMI", "Kinder Morgan"),
    ("KKR", "KKR & Co."),
    ("KLAC", "KLA Corporation"),
    ("KHC", "Kraft Heinz"),
    ("KR", "Kroger"),
    ("LHX", "L3Harris"),
    ("LH", "Labcorp"),
    ("LRCX", "Lam Research"),
    ("LVS", "Las Vegas Sands"),
    ("LDOS", "Leidos"),
    ("LEN", "Lennar"),
    ("LII", "Lennox International"),
    ("LLY", "Lilly (Eli)"),
    ("LIN", "Linde plc"),
    ("LYV", "Live Nation Entertainment"),
    ("LMT", "Lockheed Martin"),
    ("L", "Loews Corporation"),
    ("LOW", "Lowes"),
    ("LULU", "Lululemon Athletica"),
    ("LITE", "Lumentum"),
    ("LYB", "LyondellBasell"),
    ("MTB", "M&T Bank"),
    ("MPC", "Marathon Petroleum"),
    ("MAR", "Marriott International"),
    ("MRSH", "Marsh McLennan"),
    ("MLM", "Martin Marietta Materials"),
    ("MAS", "Masco"),
    ("MA", "Mastercard"),
    ("MKC", "McCormick & Company"),
    ("MCD", "McDonalds"),
    ("MCK", "McKesson Corporation"),
    ("MDT", "Medtronic"),
    ("MRK", "Merck & Co."),
    ("META", "Meta Platforms"),
    ("MET", "MetLife"),
    ("MTD", "Mettler Toledo"),
    ("MGM", "MGM Resorts"),
    ("MCHP", "Microchip Technology"),
    ("MU", "Micron Technology"),
    ("MSFT", "Microsoft"),
    ("MAA", "Mid-America Apartment Communities"),
    ("MRNA", "Moderna"),
    ("TAP", "Molson Coors Beverage Company"),
    ("MDLZ", "Mondelez International"),
    ("MPWR", "Monolithic Power Systems"),
    ("MNST", "Monster Beverage"),
    ("MCO", "Moodys Corporation"),
    ("MS", "Morgan Stanley"),
    ("MOS", "Mosaic Company (The)"),
    ("MSI", "Motorola Solutions"),
    ("MSCI", "MSCI Inc."),
    ("NDAQ", "Nasdaq, Inc."),
    ("NTAP", "NetApp"),
    ("NFLX", "Netflix"),
    ("NEM", "Newmont"),
    ("NWSA", "News Corp (Class A)"),
    ("NWS", "News Corp (Class B)"),
    ("NEE", "NextEra Energy"),
    ("NKE", "Nike, Inc."),
    ("NI", "NiSource"),
    ("NDSN", "Nordson Corporation"),
    ("NSC", "Norfolk Southern"),
    ("NTRS", "Northern Trust"),
    ("NOC", "Northrop Grumman"),
    ("NCLH", "Norwegian Cruise Line Holdings"),
    ("NRG", "NRG Energy"),
    ("NUE", "Nucor"),
    ("NVDA", "Nvidia"),
    ("NVR", "NVR, Inc."),
    ("NXPI", "NXP Semiconductors"),
    ("ORLY", "O’Reilly Automotive"),
    ("OXY", "Occidental Petroleum"),
    ("ODFL", "Old Dominion"),
    ("OMC", "Omnicom Group"),
    ("ON", "ON Semiconductor"),
    ("OKE", "Oneok"),
    ("ORCL", "Oracle Corporation"),
    ("OTIS", "Otis Worldwide"),
    ("PCAR", "Paccar"),
    ("PKG", "Packaging Corporation of America"),
    ("PLTR", "Palantir Technologies"),
    ("PANW", "Palo Alto Networks"),
    ("PSKY", "Paramount Skydance Corporation"),
    ("PH", "Parker Hannifin"),
    ("PAYX", "Paychex"),
    ("PYPL", "PayPal"),
    ("PNR", "Pentair"),
    ("PEP", "PepsiCo"),
    ("PFE", "Pfizer"),
    ("PCG", "PG&E Corporation"),
    ("PM", "Philip Morris International"),
    ("PSX", "Phillips 66"),
    ("PNW", "Pinnacle West Capital"),
    ("PNC", "PNC Financial Services"),
    ("POOL", "Pool Corporation"),
    ("PPG", "PPG Industries"),
    ("PPL", "PPL Corporation"),
    ("PFG", "Principal Financial Group"),
    ("PG", "Procter & Gamble"),
    ("PGR", "Progressive Corporation"),
    ("PLD", "Prologis"),
    ("PRU", "Prudential Financial"),
    ("PEG", "Public Service Enterprise Group"),
    ("PTC", "PTC Inc."),
    ("PSA", "Public Storage"),
    ("PHM", "PulteGroup"),
    ("PWR", "Quanta Services"),
    ("QCOM", "Qualcomm"),
    ("DGX", "Quest Diagnostics"),
    ("Q", "Qnity Electronics"),
    ("RL", "Ralph Lauren Corporation"),
    ("RJF", "Raymond James Financial"),
    ("RTX", "RTX Corporation"),
    ("O", "Realty Income"),
    ("REG", "Regency Centers"),
    ("REGN", "Regeneron Pharmaceuticals"),
    ("RF", "Regions Financial Corporation"),
    ("RSG", "Republic Services"),
    ("RMD", "ResMed"),
    ("RVTY", "Revvity"),
    ("HOOD", "Robinhood Markets"),
    ("ROK", "Rockwell Automation"),
    ("ROL", "Rollins, Inc."),
    ("ROP", "Roper Technologies"),
    ("ROST", "Ross Stores"),
    ("RCL", "Royal Caribbean Group"),
    ("SPGI", "S&P Global"),
    ("CRM", "Salesforce"),
    ("SNDK", "Sandisk"),
    ("SBAC", "SBA Communications"),
    ("SLB", "Schlumberger"),
    ("STX", "Seagate Technology"),
    ("SRE", "Sempra"),
    ("NOW", "ServiceNow"),
    ("SHW", "Sherwin-Williams"),
    ("SPG", "Simon Property Group"),
    ("SWKS", "Skyworks Solutions"),
    ("SJM", "J.M. Smucker Company (The)"),
    ("SW", "Smurfit Westrock"),
    ("SNA", "Snap-on"),
    ("SOLV", "Solventum"),
    ("SO", "Southern Company"),
    ("LUV", "Southwest Airlines"),
    ("SWK", "Stanley Black & Decker"),
    ("SBUX", "Starbucks"),
    ("STT", "State Street Corporation"),
    ("STLD", "Steel Dynamics"),
    ("STE", "Steris"),
    ("SYK", "Stryker Corporation"),
    ("SMCI", "Supermicro"),
    ("SYF", "Synchrony Financial"),
    ("SNPS", "Synopsys"),
    ("SYY", "Sysco"),
    ("TMUS", "T-Mobile US"),
    ("TROW", "T. Rowe Price"),
    ("TTWO", "Take-Two Interactive"),
    ("TPR", "Tapestry, Inc."),
    ("TRGP", "Targa Resources"),
    ("TGT", "Target Corporation"),
    ("TEL", "TE Connectivity"),
    ("TDY", "Teledyne Technologies"),
    ("TER", "Teradyne"),
    ("TSLA", "Tesla, Inc."),
    ("TXN", "Texas Instruments"),
    ("TPL", "Texas Pacific Land Corporation"),
    ("TXT", "Textron"),
    ("TMO", "Thermo Fisher Scientific"),
    ("TJX", "TJX Companies"),
    ("TKO", "TKO Group Holdings"),
    ("TTD", "Trade Desk (The)"),
    ("TSCO", "Tractor Supply"),
    ("TT", "Trane Technologies"),
    ("TDG", "TransDigm Group"),
    ("TRV", "Travelers Companies (The)"),
    ("TRMB", "Trimble Inc."),
    ("TFC", "Truist Financial"),
    ("TYL", "Tyler Technologies"),
    ("TSN", "Tyson Foods"),
    ("USB", "U.S. Bancorp"),
    ("UBER", "Uber"),
    ("UDR", "UDR, Inc."),
    ("ULTA", "Ulta Beauty"),
    ("UNP", "Union Pacific Corporation"),
    ("UAL", "United Airlines Holdings"),
    ("UPS", "United Parcel Service"),
    ("URI", "United Rentals"),
    ("UNH", "UnitedHealth Group"),
    ("UHS", "Universal Health Services"),
    ("VLO", "Valero Energy"),
    ("VEEV", "Veeva Systems"),
    ("VTR", "Ventas"),
    ("VLTO", "Veralto"),
    ("VRSN", "Verisign"),
    ("VRSK", "Verisk Analytics"),
    ("VZ", "Verizon"),
    ("VRTX", "Vertex Pharmaceuticals"),
    ("VRT", "Vertiv"),
    ("VTRS", "Viatris"),
    ("VICI", "Vici Properties"),
    ("V", "Visa Inc."),
    ("VST", "Vistra Corp."),
    ("VMC", "Vulcan Materials Company"),
    ("WRB", "W. R. Berkley Corporation"),
    ("GWW", "W. W. Grainger"),
    ("WAB", "Wabtec"),
    ("WMT", "Walmart"),
    ("DIS", "Walt Disney Company (The)"),
    ("WBD", "Warner Bros. Discovery"),
    ("WM", "Waste Management"),
    ("WAT", "Waters Corporation"),
    ("WEC", "WEC Energy Group"),
    ("WFC", "Wells Fargo"),
    ("WELL", "Welltower"),
    ("WST", "West Pharmaceutical Services"),
    ("WDC", "Western Digital"),
    ("WY", "Weyerhaeuser"),
    ("WSM", "Williams-Sonoma, Inc."),
    ("WMB", "Williams Companies"),
    ("WTW", "Willis Towers Watson"),
    ("WDAY", "Workday, Inc."),
    ("WYNN", "Wynn Resorts"),
    ("XEL", "Xcel Energy"),
    ("XYL", "Xylem Inc."),
    ("YUM", "Yum! Brands"),
    ("ZBRA", "Zebra Technologies"),
    ("ZBH", "Zimmer Biomet"),
    ("ZTS", "Zoetis"),
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
    # threshold=0 and pcr_min=0 means no filtering — return all stocks
    no_filter = vol_threshold == 0 and pcr_min == 0
    filtered = all_stocks if no_filter else [
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
    Uses _WATCH_SESSION — a dedicated session kept separate from the bulk scanner's
    session so connection-pool exhaustion from full scans doesn't affect watchlist data.
    Returns current vol data for each — no threshold filtering, caller decides what to alert.
    """
    pool = [(sym, _ALL_SYM_TO_NAME.get(sym, sym), "nasdaq") for sym in symbols]

    def _fetch_watch_stock(sym: str, name: str, market: str) -> VolumeScanResult:
        """Fetch stock data using the dedicated watch session."""
        yfin_sym = _yfin_sym(sym, market)
        try:
            # Use _WATCH_SESSION for volume chart fetch
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yfin_sym}?range=35d&interval=1d"
            r = _WATCH_SESSION.get(url, timeout=10)
            r.raise_for_status()
            result = r.json()["chart"]["result"][0]
            volumes = result["indicators"]["quote"][0].get("volume") or []
            volumes = [v for v in volumes if v is not None and v > 0]
            if not volumes:
                cur_vol, avg30 = 0, 0
            else:
                cur_vol = int(volumes[-1])
                avg30 = int(statistics.mean(volumes))
            if avg30 == 0:
                avg30 = cur_vol or 1
            vol_ratio = round(cur_vol / avg30, 2) if avg30 > 0 else 1.0
            pcr, oi_trend = _fetch_pcr(yfin_sym)
            signal = _classify_signal(pcr, vol_ratio)
            return VolumeScanResult(sym=sym, name=name, avg30=avg30, cur_vol=cur_vol,
                                    vol_ratio=vol_ratio, pcr=pcr, oi_trend=oi_trend, signal=signal)
        except Exception as e:
            logger.warning("Watch scan fetch failed for %s: %s", sym, e)
            return VolumeScanResult(sym=sym, name=name, avg30=0, cur_vol=0,
                                    vol_ratio=0.0, pcr=1.0, oi_trend="Flat", signal="neutral",
                                    error=str(e))

    results: list[VolumeScanResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_fetch_watch_stock, sym, name, mkt): sym for sym, name, mkt in pool}
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

