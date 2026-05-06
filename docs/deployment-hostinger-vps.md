# Hostinger VPS — quick reference

**For the full walkthrough** (subdomain → DNS → firewall → CORS/compose fix → Caddy → 502 troubleshooting → errors we fixed), use:

**[deployment-full-guide.md](deployment-full-guide.md)**

The sections below are a short checklist; the full guide is authoritative.

---

## Architecture

| Piece | Role |
|--------|------|
| **DNS** | Subdomain **A** record → VPS public IPv4 |
| **Hostinger firewall** | Inbound **TCP 22, 80, 443** Accept |
| **Docker Compose** | `db`, `api`, `web` — UI on host **8080** |
| **Caddy (host)** | `reverse_proxy` **127.0.0.1:8080**; automatic HTTPS |

## One-line Caddyfile

```caddy
your-subdomain.yourdomain.com {
    reverse_proxy 127.0.0.1:8080
}
```

## `.env` (repo root)

```env
API_CORS_ORIGINS=https://your-subdomain.yourdomain.com,http://localhost:5173,http://localhost:8080
```

Then: `docker compose up -d --force-recreate api`

## Verify

```bash
curl -sI http://127.0.0.1:8080 | head -3
curl -sI https://your-subdomain.yourdomain.com | head -3
```
