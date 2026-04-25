# Market Snapshot Dashboard

**How to run (Docker, ports, stop/start):** see **[Run.md](Run.md)**.

---

End-to-end **daily Market Snapshot** system for India cash + derivatives context: Nifty 50 breadth, technical pivots, India VIX, FII/DII, index options (PCR + OI walls), global cues, commodities, optional **X List** sentiment (FinBERT), and a **composite 0–100 sentiment** score. A **FastAPI** backend persists snapshots in **PostgreSQL**; a **React + Tailwind** single-page dashboard renders the card layout; **Docker Compose** runs API + DB + static UI (nginx reverse proxy to the API).

## Architecture

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

## Deployment notes

- Run **migrations** before or on boot (`backend/Dockerfile` runs `alembic upgrade head`).
- Put secrets in the orchestrator (K8s Secrets, ECS parameters), not in the image.
- For production CORS, set `API_CORS_ORIGINS` to your real UI origin(s).
- Consider moving the X + FinBERT job to a **worker** if API latency becomes an issue.

## License

Use and modify freely for internal / research workflows; verify exchange and vendor terms of use for your data paths.
