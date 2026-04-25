# How to run Market Snapshot

Step-by-step instructions to run the **database**, **backend (FastAPI)**, and **frontend (React, served by nginx)** with Docker Compose.

All commands are run from the project root (the folder that contains `docker-compose.yml`).

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose on Linux
- Docker **daemon running** (Docker Desktop app started)

Verify:

```bash
docker --version
docker compose version
```

---

## 1. Open a terminal in the project root

```bash
cd /path/to/HeatMapDashboard
```

Example (adjust to your machine):

```bash
cd ~/Desktop/GIT-TradeAutomater/HeatMapDashboard
```

---

## 2. (Optional) Environment variables

```bash
cp .env.example .env
```

Edit `.env` if you need:

- **`XBEARER_TOKEN`**, **`X_LIST_ID`** — X (Twitter) List sentiment (optional)
- **`DISABLE_FINBERT=1`** — faster first start; skips downloading FinBERT (uses a simple text fallback for X sentiment)

Compose automatically loads `.env` next to `docker-compose.yml`.

---

## 3. Build and start all services

This starts **three** containers:

| Service | Name in Compose | What it is |
|--------|------------------|------------|
| Database | `db` | PostgreSQL 16 (data persisted in volume `pgdata`) |
| Backend | `api` | FastAPI + Uvicorn; runs Alembic migrations on boot |
| Frontend | `web` | Production build of the React app + nginx, proxies API routes |

**Foreground** (see logs in the terminal; stop with `Ctrl+C`):

```bash
docker compose up --build
```

**Background** (detached):

```bash
docker compose up --build -d
```

The first build can take **several minutes** (Python + ML stack, then frontend `npm run build`).

The API container waits until Postgres is **healthy** before starting.

---

## 4. Check that the API is running

If you used `-d`, follow logs until you see the server listening on port 8000:

```bash
docker compose logs -f api
```

Press `Ctrl+C` to stop following logs (containers keep running).

---

## 5. Open the app

| What | URL |
|------|-----|
| **Dashboard (main UI)** | <http://localhost:8080> |
| **API Swagger (try endpoints)** | <http://localhost:8000/docs> |
| **API index (JSON links)** | <http://localhost:8000/> |
| **Health** | <http://localhost:8000/health> |
| **Today’s snapshot (JSON)** | <http://localhost:8000/snapshot/today> |

**Postgres** (for SQL clients, not a browser): host `localhost`, port **5432**, user **`snapshot`**, password **`snapshot`**, database **`market_snapshot`**.

---

## 6. Run only part of the stack (optional)

Same database + API only (no static UI):

```bash
docker compose up --build -d db api
```

You would need to run the frontend separately (`cd frontend && npm install && npm run dev` → <http://localhost:5173>) and point it at the API, or use only the API on port 8000.

---

## 7. Stop the stack

- If `docker compose up` is in the **foreground**: press **`Ctrl+C`**.

- If services run in the **background**:

```bash
docker compose down
```

Database files stay in the volume until you run:

```bash
docker compose down -v
```

(`-v` removes the Postgres volume; you lose stored snapshots.)

---

## 8. After you change code

Rebuild images so containers include your changes:

```bash
docker compose up --build -d
```

If the API still shows old code:

```bash
docker compose build --no-cache api
docker compose up -d api
```

---

## 9. Local development without Docker (optional)

- Install **Postgres** on your machine and set **`DATABASE_URL`**.
- **Backend:** see `README.md` → “Run locally (without Docker)”.
- **Frontend:** `cd frontend && npm install && npm run dev` → <http://localhost:5173> (Vite proxies API paths to `localhost:8000` when the API is running locally on port 8000).

---

## One-line summary

From the project root: **`docker compose up --build`**, then open **<http://localhost:8080>** for the dashboard and **<http://localhost:8000/docs>** for the API.

For architecture, environment variables, and API details, see the main [README](README.md).
