# Full production deployment guide (Hostinger VPS → HTTPS)

This is the **end-to-end** record: from choosing a **subdomain** through **Docker**, **DNS**, **firewall**, **HTTPS (Caddy)**, **`API_CORS_ORIGINS`**, **updates after Git**, and **every failure mode we hit** with the fix.

**Example hostname used below:** `tradersmind.bashasena.com` on VPS IP `2.24.65.223`. Substitute your subdomain and IP everywhere.

---

## What you end up with

| Layer | Result |
|--------|--------|
| **DNS** | Subdomain points at your VPS. |
| **Firewall** | SSH (22), HTTP (80), HTTPS (443) allowed from the internet. |
| **Docker** | Postgres + FastAPI + nginx/React UI; UI reachable at `http://127.0.0.1:8080` on the server. |
| **Caddy (host)** | `https://tradersmind.bashasena.com` with a real certificate; traffic forwarded to port **8080**. |
| **CORS** | API trusts `https://tradersmind.bashasena.com` via `.env`. |

---

## Part 1 — VPS and Docker

### 1.1 Create the VPS (Hostinger)

- Choose **Ubuntu 24.04 LTS** (or similar) and a template that includes **Docker**, or install Docker after SSH access.
- Note **public IPv4** (used for DNS and SSH).

### 1.2 SSH

```bash
ssh root@<YOUR_VPS_IP>
```

**Issue — `Permission denied`:** Wrong root password. Use the password from Hostinger email/hPanel, or **reset root password** in hPanel. The web **Terminal** in hPanel also works if SSH from your PC fails.

Verify Docker:

```bash
docker --version
docker compose version
```

### 1.3 Put the project on the server

```bash
cd /root   # or /var/www
git clone <your-repo-url> marketminds
cd marketminds
```

Confirm the **project root** (the folder that contains **`docker-compose.yml`**, **`backend/`**, **`frontend/`**).

### 1.4 Environment file

```bash
cp .env.example .env
nano .env
```

Fill in tokens, scheduler, and (after you know the public HTTPS URL) **`API_CORS_ORIGINS`** — see **Part 4**.

### 1.5 Start the stack

```bash
docker compose up -d --build
docker compose ps
curl -sI http://127.0.0.1:8080 | head -5
```

Expect **`HTTP/1.1 200 OK`** from nginx in the **`web`** container.

**Ports (default compose):**

| Host port | Service |
|-----------|---------|
| **8080** | Dashboard (nginx → API on `/snapshot`, etc.) |
| **8000** | FastAPI (optional exposure; lock down in production) |
| **5432** | Postgres (should not be public in production) |

---

## Part 2 — Subdomain and DNS

### 2.1 Why a subdomain

The app is built for **`/`** on one hostname (React assets at **`/assets/...`**, API paths **`/snapshot`**, **`/health`**, …). Serving under **`https://example.com/some-path`** needs extra app/nginx changes. A **subdomain** (e.g. **`tradersmind.bashasena.com`**) avoids that.

### 2.2 Add the DNS record

In **Hostinger → Domains → bashasena.com → DNS / DNS Zone**:

| Type | Name (host) | Points to | TTL |
|------|----------------|-----------|-----|
| **A** | `tradersmind` | **VPS IPv4** | Default |

Do **not** put `https://` or paths here — only the subdomain label and IP.

### 2.3 Check propagation

```bash
dig +short tradersmind.bashasena.com A
```

Should print your VPS IP.

---

## Part 3 — Firewall (required for browser access)

Hostinger’s VPS firewall **drops all inbound traffic** until you add rules.

In **hPanel → VPS → Security → Firewall**, create rules **in this order** (typical pattern):

1. **Accept** — TCP **22** — Source **Any** (SSH)  
2. **Accept** — TCP **80** — Source **Any** (HTTP; Let’s Encrypt)  
3. **Accept** — TCP **443** — Source **Any** (HTTPS)  
4. **Drop** — catch-all (often pre-filled)

**Issue — “This site can’t be reached” / connection time out to the domain:**  
- **`dig`** already returns the correct IP, but **curl** to **:80** and **:443** from outside **times out** → **firewall** was closed **or** nothing was listening on 80/443 yet.  
- **Fix:** Add the **Accept** rules above. **UFW** on Ubuntu was **inactive** in our case; the Hostinger panel firewall was the blocker.

---

## Part 4 — `API_CORS_ORIGINS` and the compose override bug

The API reads allowed browser origins from **`API_CORS_ORIGINS`** (comma-separated list).

### 4.1 What we wanted

In **`.env`** (repo root, next to `docker-compose.yml`):

```env
API_CORS_ORIGINS=https://tradersmind.bashasena.com,http://localhost:5173,http://localhost:8080
```

Then recreate the API container:

```bash
docker compose up -d --force-recreate api
```

### 4.2 Issue — `docker compose exec api printenv API_CORS_ORIGINS` still showed only localhost

**Cause:** In **`docker-compose.yml`**, the **`api`** service had a **fixed** line:

```yaml
API_CORS_ORIGINS: http://localhost:5173,http://localhost:8080
```

Docker Compose applies **`environment:`** **after** **`env_file:`**. A fixed value **overrides** `.env` for that key, so edits to **`.env`** had **no effect**.

**Fix (in the repo):** use substitution so `.env` wins:

```yaml
API_CORS_ORIGINS: ${API_CORS_ORIGINS:-http://localhost:5173,http://localhost:8080}
```

After **git pull** on the VPS, set **`.env`** and run **`docker compose up -d --force-recreate api`** again.

---

## Part 5 — HTTPS on the host with Caddy

Docker only exposes **8080** (and 8000/5432). Browsers expect **443** for **`https://`**. A **reverse proxy on the VPS OS** terminates TLS and forwards to Docker.

### 5.1 Issue — nothing on port 80 or 443

```bash
sudo ss -tlnp | egrep ':80|:443'
sudo systemctl status caddy
# Unit caddy.service could not be found
```

**Cause:** Caddy was **not installed**. Opening the firewall alone is not enough; **something must listen** on **80** and **443**.

### 5.2 Install and configure Caddy

```bash
apt update && apt install -y caddy
nano /etc/caddy/Caddyfile
```

Use the **exact** hostname that DNS points here — **subdomain only**, **no** `https://` prefix:

```caddy
tradersmind.bashasena.com {
    reverse_proxy 127.0.0.1:8080
}
```

Remove any leftover default **`:80`-only** blocks if warnings confuse you; keep one clear site block.

```bash
caddy validate --config /etc/caddy/Caddyfile
caddy fmt --overwrite /etc/caddy/Caddyfile   # optional
systemctl enable caddy
systemctl restart caddy
systemctl status caddy
```

Caddy obtains **Let’s Encrypt** certificates (needs **port 80** reachable from the internet for HTTP validation).

**Note:** `tradersmind.bashasena.com { ... }` **is** a real hostname (a **subdomain** is a normal “domain” for TLS). “Real domain” does not mean “only apex `bashasena.com`.”

---

## Part 6 — HTTP 502 from Caddy

### 6.1 Symptom

```bash
curl -sI https://tradersmind.bashasena.com | head -3
# HTTP/2 502
# server: Caddy
```

TLS and DNS work; **Caddy** is running. **502** means the **upstream** **`http://127.0.0.1:8080`** failed.

### 6.2 Diagnosis

```bash
curl -sI http://127.0.0.1:8080 | head -5
docker compose ps
docker compose logs web --tail=30
```

**What we saw:** **`docker compose ps`** showed **no running services**; **`web`** logs showed nginx **exiting** (SIGQUIT). So **nothing** listened on **8080**.

### 6.3 Fix

```bash
cd ~/marketminds
docker compose up -d
docker compose ps
curl -sI http://127.0.0.1:8080 | head -5
curl -sI https://tradersmind.bashasena.com | head -5
```

**Success:**

```text
HTTP/2 200
content-type: text/html
```

---

## Part 7 — Git and the VPS (no automatic deploy)

**Merging to `main` on GitHub does not update the server by itself.**

After each merge you care about:

```bash
ssh root@<VPS_IP>
cd ~/marketminds
git pull origin main
docker compose up -d --build    # if code or Dockerfile changed
```

---

## Part 8 — Final verification checklist

| Step | Command / check |
|------|------------------|
| DNS | `dig +short tradersmind.bashasena.com A` → VPS IP |
| Firewall | hPanel: **22, 80, 443** Accept |
| Docker | `docker compose ps` → `db` healthy, `api` / `web` **Up** |
| Upstream | `curl -sI http://127.0.0.1:8080` → **200** |
| Caddy | `systemctl status caddy` → **active** |
| HTTPS | `curl -sI https://tradersmind.bashasena.com` → **200** |
| CORS | `docker compose exec api printenv API_CORS_ORIGINS` includes **`https://tradersmind.bashasena.com`** |

---

## Part 9 — Errors fixed (quick index)

| Symptom | Cause | Fix |
|---------|--------|-----|
| SSH **Permission denied** | Wrong root password | Reset in hPanel / copy from email |
| **`API_CORS_ORIGINS`** unchanged | Hardcoded in **`docker-compose.yml`** | Use **`${API_CORS_ORIGINS:-...}`**; recreate **`api`** |
| Browser **can’t reach** site; **timeout** on **80/443** | Firewall blocked | Add **Accept** rules for **80**, **443**, **22** |
| **`caddy.service` not found** | Caddy not installed | **`apt install caddy`** + **`Caddyfile`** + **`systemctl restart caddy`** |
| **`HTTP/2 502`** from Caddy | **`web`** container down / nothing on **8080** | **`docker compose up -d`** |

---

## Part 10 — Optional hardening

- Bind **`web`** to localhost only: **`127.0.0.1:8080:80`** in `docker-compose.yml` so **8080** is not exposed on the public interface (Caddy on the same machine still works).
- Do **not** expose Postgres **5432** (or API **8000**) to **`0.0.0.0`** on the internet unless required.
- Add **SSH keys** in hPanel and disable password login when comfortable.
- Add **`restart: unless-stopped`** to Compose services if you want them back after reboot.

---

## Related files in this repo

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Services, **`API_CORS_ORIGINS`** substitution |
| `.env.example` | Template including **`API_CORS_ORIGINS`** |
| `.env` | **On server only** — secrets and production CORS (gitignored) |

For a shorter reference without the narrative, see **[deployment-hostinger-vps.md](deployment-hostinger-vps.md)** (checklist style).
