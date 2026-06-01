# All Services & APIs — MarketMinds

Complete reference for every API endpoint, backend service, and infrastructure component in the project.

---

## API Endpoints

### System

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/health` | Server health check — returns `{status: ok, ist: <time>}` |
| `GET` | `/` | API index — lists all routes |
| `GET` | `/docs` | Swagger UI (interactive API explorer) |

### Snapshot (Dashboard data)

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/snapshot/today` | Today's market snapshot (NASDAQ / S&P / Nifty) from DB or live |
| `GET` | `/snapshot/history` | Historical snapshots (`?days=30`) |
| `POST` | `/snapshot/refresh` | Trigger a live data refresh and save to DB |
| `POST` | `/snapshot/ingest` | Manually paste a full snapshot JSON (offline import) |
| `POST` | `/snapshot/options/from-nse-json` | Upload NSE option-chain JSON to patch PCR into snapshot |

### Volume Scanner

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/volume/scan` | Full market scan — NASDAQ / S&P / both, with threshold + PCR filters |
| `GET` | `/volume/watch` | Live data for specific symbols (comma-separated) |
| `GET` | `/volume/pcr/{sym}` | Live PCR for a single symbol via Yahoo Finance options chain |

### Alert Watchlist

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/volume/alerts` | List all watched symbols with latest volume + PCR data |
| `POST` | `/volume/alerts` | Add a symbol to the server-side watchlist |
| `DELETE` | `/volume/alerts/{sym}` | Remove a symbol from the watchlist |

### Sentiment & News

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/sentiment/x` | Latest X (Twitter) sentiment scores from DB |
| `POST` | `/x/sync` | Fetch X List tweets + run FinBERT sentiment, optionally save |
| `GET` | `/news` | Market news feed (`?market=in_nifty` or `nasdaq`) |

### Admin

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/admin/settings` | Get current watchlist refresh & alert interval |
| `POST` | `/admin/settings` | Update watchlist refresh interval (5 / 10 / 30 / 60 min) |

---

## Backend Services

| Service | Purpose | External API used |
|---------|---------|-------------------|
| `volume_scan_service` | Scans 604 stocks (NASDAQ 101 + S&P 503) for volume surges | **Yahoo Finance** chart API (free) |
| `alert_manager` | Unified refresh + alert loop; fetches live data, checks thresholds, fires Telegram; daily reset at 9:30 AM ET | Calls `volume_scan_service` + Telegram Bot API |
| `telegram_service` | Sends formatted alert messages to Telegram channel `@trader_mind_alert` | **Telegram Bot API** (free) |
| `market_snapshot` | India / Nifty market snapshot builder | **NSE** + yfinance |
| `us_market_snapshot` | US market dashboard snapshot | **yfinance** (free) |
| `us_nasdaq_market_snapshot` | NASDAQ-specific snapshot | **yfinance** (free) |
| `x_sentiment_service` | Fetches tweets from a Twitter List and scores them with FinBERT | **X API v2** (paid Bearer token) + **FinBERT** (local ML model) |
| `news_feed_service` | Market news articles | Public RSS / news APIs |
| `databento_options_service` | SPY / QQQ full options OI from OPRA exchange feed | **Databento** (paid — key not set in `.env`) |
| `options_service` | Options snapshot data model (used by snapshot pipeline) | Internal |
| `nse_client` | NSE India data fetching (indices, option chain) | **NSE website** |
| `composite_sentiment` | Combines X sentiment + PCR + VIX into a single composite score | Internal |
| `global_markets_service` | Global index prices (Dow, NASDAQ, gold, crude, USD) | yfinance |
| `index_service` | Index price data | yfinance |
| `vix_service` | VIX (volatility index) data | yfinance |
| `technical_levels` | Support / resistance level calculations | Internal |
| `narrative_service` | Market narrative text generation for dashboard | Internal |
| `fii_dii_service` | FII / DII institutional flow data (India) | NSE |
| `yahoo_chart_bars` | Raw OHLCV bar data for charting | Yahoo Finance |

---

## Background Jobs

| Job | Schedule | What it does |
|-----|----------|--------------|
| **Watchlist refresh + alert** | Every 5 min (configurable: 5 / 10 / 30 / 60 min) | Fetches live volume + PCR for all watched symbols, updates DB, fires Telegram if a new integer band is crossed |
| **Daily last_crossed reset** | 13:30 UTC (≈ 9:30 AM ET) daily | Resets `last_crossed = 0` for all watchlist symbols so Telegram alerts re-arm for the new trading day |
| **Daily snapshot** | 16:00 IST (configurable via `SNAPSHOT_CRON_HOUR/MINUTE`) | Runs the full market snapshot pipeline and saves to DB |
| **Intraday snapshot** | Optional interval via `INTRADAY_REFRESH_MINUTES` (default off) | Same as daily snapshot but runs on a repeating interval |

---

## Infrastructure

| Component | Technology | Port |
|-----------|-----------|------|
| **API server** | FastAPI + Python 3.12 + Uvicorn | `8000` |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS (served via nginx) | `8080` |
| **Database** | PostgreSQL 16 | `5432` |
| **Scheduler** | APScheduler (daily / intraday snapshot jobs) | — |
| **Alert loop** | Python `threading.Timer` (two timers: check loop + daily reset) | — |
| **Container** | Docker Compose (`api`, `web`, `db` services) | — |

---

## External Dependencies & API Keys

| Service | Key env var | Required for | Cost |
|---------|-------------|--------------|------|
| Telegram Bot API | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Volume surge alerts to `@trader_mind_alert` | Free |
| Yahoo Finance | *(no key)* | Volume scanner, PCR, all US market data | Free |
| X (Twitter) API v2 | `XBEARER_TOKEN`, `X_LIST_ID` | X sentiment scoring | Paid |
| Databento OPRA | `DATABENTO_API_KEY` | SPY / QQQ full options chain OI | Paid (not currently set) |
| NSE India | *(no key — scraping)* | India / Nifty snapshot | Free |

---

## Quick curl reference

```bash
# Health check
curl http://localhost:8000/health

# Full S&P 500 scan (no filter)
curl "http://localhost:8000/volume/scan?market=sp500&threshold=0&pcr_min=0"

# Live PCR for a single stock
curl http://localhost:8000/volume/pcr/AAPL

# List watchlist
curl http://localhost:8000/volume/alerts

# Add to watchlist
curl -X POST http://localhost:8000/volume/alerts \
  -H "Content-Type: application/json" \
  -d '{"sym":"NVDA","name":"NVIDIA","current_ratio":2.5}'

# Remove from watchlist
curl -X DELETE http://localhost:8000/volume/alerts/NVDA

# Get admin settings
curl http://localhost:8000/admin/settings

# Update refresh interval to 5 min
curl -X POST http://localhost:8000/admin/settings \
  -H "Content-Type: application/json" \
  -d '{"pcr_refresh_interval_minutes":5}'

# Test Telegram alert
curl "https://api.telegram.org/bot8860793765:AAHdTDrvyz2SOMpIheWXtiD1cRYOt37nf-Y/sendMessage" \
  -d "chat_id=-1003949912386" \
  -d "parse_mode=HTML" \
  -d "text=🔔 <b>Test Alert — AAPL</b>"
```

---

## Production

- **Server**: Hostinger VPS — `ssh root@2.24.65.223`
- **App directory**: `~/marketminds`
- **Live URL**: `https://tradersmind.bashasena.com`
- **Volume Scanner**: `https://tradersmind.bashasena.com/volume-strategy`
- **Telegram channel**: `https://t.me/trader_mind_alert`

**Deploy**:
```bash
ssh root@2.24.65.223
cd ~/marketminds && git pull
docker compose up -d --build
```
