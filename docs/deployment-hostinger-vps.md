# Hostinger VPS deployment (Docker + Caddy + HTTPS)

This document describes the **production-style setup** used for a public dashboard: **Hostinger KVM VPS (Ubuntu)**, **Docker Compose** (Postgres + API + nginx web), **Caddy** on the host for TLS, and **DNS** for a subdomain.

Merging to `main` on GitHub **does not** deploy by itself unless you add CI; after a push, **pull on the server** and restart containers as needed.

---

## Architecture

| Piece | Role |
|--------|------|
| **DNS** | Subdomain (e.g. `tradersmind.example.com`) **A record** → VPS public IPv4 |
| **Hostinger firewall** | Allow inbound **TCP 22**, **80**, **443** (SSH, HTTP for ACME, HTTPS) |
| **Docker Compose** | `db` (Postgres), `api` (FastAPI), `web` (nginx + static React; proxies `/snapshot`, `/sentiment`, etc. to `api`) |
| **Host port 8080** | Published as `8080:80` on `web` → `http://127.0.0.1:8080` on the VPS |
| **Caddy** (on host, not in Compose) | Listens on **80/443**, obtains Let’s Encrypt certs, **reverse_proxy** to `http://127.0.0.1:8080` |

---

## 1. VPS and Docker

- **OS:** Ubuntu 24.04 LTS (example).
- **Docker** and **Docker Compose** installed; project cloned to e.g. `~/marketminds`.
- From the directory that contains **`docker-compose.yml`**:

```bash
cp .env.example .env
nano .env   # secrets, scheduler, optional keys — see .env.example
docker compose up -d --build
```

- **Dashboard (direct to Docker, no TLS):** `http://<VPS_IP>:8080`
- **API (if exposed):** `http://<VPS_IP>:8000` — restrict in production (firewall / bind to localhost).

---

## 2. Environment: `API_CORS_ORIGINS`

The API allows browser origins listed in **`API_CORS_ORIGINS`** (comma-separated, no spaces required between entries).

For HTTPS on your subdomain, set in the **repo root** `.env` (same folder as `docker-compose.yml`), for example:

```env
API_CORS_ORIGINS=https://tradersmind.example.com,http://localhost:5173,http://localhost:8080
```

Compose passes this via **`${API_CORS_ORIGINS:-...}`** (see `docker-compose.yml`). After changing `.env`:

```bash
docker compose up -d --force-recreate api
docker compose exec api printenv API_CORS_ORIGINS
```

---

## 3. DNS

In Hostinger **DNS zone** for your apex domain (e.g. `example.com`):

| Type | Name / Host | Value |
|------|-------------|--------|
| **A** | `tradersmind` (subdomain only) | **VPS public IPv4** |

TTL: default is fine.

Verify from your PC:

```bash
dig +short tradersmind.example.com A
```

---

## 4. Hostinger VPS firewall (hPanel)

Create a firewall profile with **inbound Accept** rules:

| Protocol | Port | Source |
|----------|------|--------|
| TCP | **22** | Any (SSH) |
| TCP | **80** | Any (HTTP — Let’s Encrypt HTTP-01) |
| TCP | **443** | Any (HTTPS) |

Keep the implicit **drop** rule for everything else (as provided by the panel).

Without **80** and **443**, browsers will **time out** (not a certificate warning).

---

## 5. Caddy on the host (HTTPS → Docker)

Install Caddy on the **VPS OS** (not inside a container):

```bash
apt update && apt install -y caddy
```

Edit `/etc/caddy/Caddyfile`. Use the **exact** hostname you use in the browser and in DNS (subdomain is fine):

```caddy
tradersmind.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Do **not** prefix the hostname with `https://` in the Caddyfile.

Validate and run:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy
systemctl restart caddy
systemctl status caddy
```

Optional: remove default/example blocks in the same file so only this site remains; run `caddy fmt --overwrite /etc/caddy/Caddyfile` for formatting.

---

## 6. Verification

On the VPS:

```bash
curl -sI http://127.0.0.1:8080 | head -5     # expect 200 from nginx (web)
curl -sI https://tradersmind.example.com | head -5   # expect 200 via Caddy
```

If **`https://...` returns 502**:

- Caddy is up but the **upstream** is bad → usually **`web` container stopped**. Run `docker compose ps`, then `docker compose up -d`.

---

## 7. Ubuntu UFW (optional)

If you enable **UFW**, allow the same ports:

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

While testing, an **inactive** UFW does not block traffic.

---

## 8. Operational notes

- **After `git pull` on the server**, rebuild/restart if code or `docker-compose.yml` changed:  
  `docker compose up -d --build`
- **Secrets** stay in **`.env`** on the server (never commit `.env`).
- **Postgres** is exposed on **5432** in the default Compose file; for production, consider **not** publishing `5432` to `0.0.0.0` or restrict via firewall.
- **Reboot:** Compose services do not restart automatically unless you add **`restart: unless-stopped`** to services or use a systemd unit.

---

## 9. Checklist summary

1. [ ] DNS **A** record: subdomain → VPS IP  
2. [ ] Firewall: **22**, **80**, **443**  
3. [ ] `docker compose up -d` — **`web`** listening on **8080**  
4. [ ] Caddy **Caddyfile** hostname matches DNS; **`reverse_proxy 127.0.0.1:8080`**  
5. [ ] `.env`: **`API_CORS_ORIGINS`** includes **`https://<your-subdomain>`**  
6. [ ] **`curl -sI https://<your-subdomain>`** → **200**
