# Market Snapshot Dashboard

**How to run (Docker, ports, stop/start):** see **[Run.md](Run.md)**.

---

End-to-end **daily Market Snapshot** system for India cash + derivatives context: Nifty 50 breadth, technical pivots, India VIX, FII/DII, index options (PCR + OI walls), global cues, commodities, optional **X List** sentiment (FinBERT), and a **composite 0–100 sentiment** score. A **FastAPI** backend persists snapshots in **PostgreSQL**; a **React + Tailwind** single-page dashboard renders the card layout; **Docker Compose** runs API + DB + static UI (nginx reverse proxy to the API).

## Architecture

- **Developer handbook (backend + frontend architecture, flows, extension points):** **[docs/developer-handbook-confluence.md](docs/developer-handbook-confluence.md)** — formatted for Confluence / onboarding.
- **Backend**: `backend/app` — modular services (`index_service`, `options_service`, `fii_dii_service`, `global_markets_service`, `x_sentiment_service`, `composite_sentiment`, `market_snapshot`), APScheduler jobs, Alembic migrations.
- **Frontend**: `frontend/src` — responsive dashboard calling `/snapshot/today`.
- **Infra**: `docker-compose.yml` — `db` (Postgres 16), `api` (Uvicorn + migrations on boot), `web` (nginx → `/snapshot`, `/sentiment`, `/health`).

## Environment variables

Copy `.env.example` to `.env` at the repo root (Compose reads `${XBEARER_TOKEN}` style substitutions from your shell environment or an `.env` file in the same directory as `docker compose`).

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres DSN (set automatically in Compose for `api`) |
| `XBEARER_TOKEN` | X API v2 Bearer token for List tweets |
| `X_LIST_ID` | Numeric List ID of curated traders |
| `SNAPSHOT_CRON_HOUR`, `SNAPSHOT_CRON_MINUTE` | IST time for daily persisted snapshot (default 16:00) |
| `INTRADAY_REFRESH_MINUTES` | If > 0, persist snapshots on that interval |
| `DISABLE_FINBERT` | `1` skips `transformers` model load; uses lexical fallback |
| `API_CORS_ORIGINS` | Comma-separated origins for browser calls to API |
| `YFIN_*` | Optional overrides for yfinance symbols (see `app/config.py`) |

Pydantic also accepts lowercase aliases `x_bearer_token` / `x_list_id` if you prefer.

## Composite sentiment (documented in code)

Weights and mapping logic live in `backend/app/services/composite_sentiment.py` (table + `compute_composite`). Subscores are normalized to 0–100 before applying weights that sum to **1.0**.

## API

- `GET /snapshot/today` — Prefer **today (IST)** row from DB; if missing, computes live. Query `live=true` bypasses DB cache; `persist=true` saves after a fresh build.
- `GET /snapshot/history?days=N` — Recent persisted payloads + headline fields.
- `GET /sentiment/x` — Drill-down: per-ticker aggregates + sample scored tweets.
- `POST /snapshot/refresh` — Rebuild and persist (manual / hook).
- `GET /health` — Liveness.

## Python version

- **Docker**: Python 3.12 (see `backend/Dockerfile`).
- **Local**: Python **3.9+** works with the pinned dependency ranges; **3.10+** is recommended for fewer typing edge cases.

## Run locally (without Docker)

1. **Postgres** running and `DATABASE_URL` set.
2. Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://snapshot:snapshot@localhost:5432/market_snapshot
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` (Vite proxies `/snapshot` to port 8000).

## Run with Docker Compose

```bash
export XBEARER_TOKEN=...   # optional
export X_LIST_ID=...       # optional
docker compose up --build
```

- API: `http://localhost:8000` — root `http://localhost:8000/` lists JSON links; **Swagger UI:** `http://localhost:8000/docs`
- Dashboard (nginx → API): `http://localhost:8080`

First FinBERT download can take time and disk; set `DISABLE_FINBERT=1` for a lighter smoke test.

## Data sources (disclaimer)

- **NSE** public JSON endpoints (session cookie warm-up) for Nifty constituents, option chain, FII/DII.
- **yfinance** for prior-day pivot inputs, India VIX proxy, global indices, USD/INR, gold/crude (when Yahoo responds; many Docker/datacenter IPs get empty data).
- **niftyindices.com** (official NSE index site) as a **fallback** for Nifty pivots, India VIX, and the GIFT/Nifty proxy bar when Yahoo Finance fails inside the container.
- **X** v2 List tweets with FinBERT (`ProsusAI/finbert`) when enabled.

NSE and Yahoo/X availability can change; this stack is intended as a **professional-style template** you can harden (broker feeds, retries, auth secrets manager, etc.).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres DSN (set automatically in Compose for `api`) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from `@BotFather` — powers volume alert notifications |
| `TELEGRAM_CHAT_ID` | Telegram channel/chat ID to send alerts to (e.g. `-1003949912386`) |
| `XBEARER_TOKEN` | X API v2 Bearer token for List tweets |
| `X_LIST_ID` | Numeric List ID of curated traders |
| `SNAPSHOT_CRON_HOUR`, `SNAPSHOT_CRON_MINUTE` | IST time for daily persisted snapshot (default 16:00) |
| `INTRADAY_REFRESH_MINUTES` | If > 0, persist snapshots on that interval |
| `DISABLE_FINBERT` | `1` skips `transformers` model load; uses lexical fallback |
| `API_CORS_ORIGINS` | Comma-separated origins for browser calls to API |
| `YFIN_*` | Optional overrides for yfinance symbols (see `app/config.py`) |

---

## 🚀 Production — Hostinger VPS

**Live app:** https://tradersmind.bashasena.com
**Volume Scanner:** https://tradersmind.bashasena.com/volume-strategy
**Telegram alerts channel:** https://t.me/trader_mind_alert

### Server details

| Item | Value |
|------|-------|
| Provider | Hostinger VPS |
| OS | Ubuntu 24.04 LTS |
| IP | `2.24.65.223` |
| Domain | `tradersmind.bashasena.com` |
| Reverse proxy | Caddy (auto HTTPS via Let's Encrypt) |
| App path | `/root/marketminds` |

### SSH access

```bash
ssh root@2.24.65.223
```

### Deploy / update after a git push

```bash
ssh root@2.24.65.223
cd ~/marketminds
git pull
docker compose up -d --build
docker compose ps
```

### Verify everything is running

```bash
docker compose ps                        # all 3 containers Up
curl -sI http://127.0.0.1:8080           # 200 from nginx
curl -s http://127.0.0.1:8000/health     # {"status":"ok"}
curl -s http://127.0.0.1:8000/volume/alerts  # watchlist JSON
```

### Environment file on server

The `.env` file lives at `/root/marketminds/.env` (not committed to git). It must contain:

```env
TELEGRAM_BOT_TOKEN=<bot token>
TELEGRAM_CHAT_ID=-1003949912386
API_CORS_ORIGINS=https://tradersmind.bashasena.com,http://localhost:5173,http://localhost:8080
```

After editing `.env`, restart only the API container (no rebuild needed):

```bash
docker compose up -d --force-recreate api
```

### Useful commands

```bash
# View live API logs
docker compose logs -f api

# View nginx logs
docker compose logs -f web

# Restart a single service
docker compose restart api

# Full rebuild (after Dockerfile or dependency changes)
docker compose up -d --build

# Stop everything
docker compose down

# Stop and wipe database (⚠️ destructive)
docker compose down -v
```

### Caddy config (HTTPS reverse proxy — on host OS, not Docker)

```
/etc/caddy/Caddyfile
```
```caddy
tradersmind.bashasena.com {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
systemctl status caddy          # check Caddy is running
systemctl restart caddy         # restart after config change
```

### Full deployment guide

For first-time VPS setup (DNS, firewall, Caddy install, CORS troubleshooting):
**[docs/deployment-full-guide.md](docs/deployment-full-guide.md)**

---

## Deployment notes

- Run **migrations** before or on boot (`backend/Dockerfile` runs `alembic upgrade head` automatically).
- Put secrets in `.env` on the server — never commit them to git.
- For production CORS, `API_CORS_ORIGINS` must include your public domain.
- Consider moving X + FinBERT job to a **worker** if API latency becomes an issue.
- **Telegram AlertManager** runs as a background thread inside the API container — polling every 5 min; restarts automatically with the container.

## License

Use and modify freely for internal / research workflows; verify exchange and vendor terms of use for your data paths.
