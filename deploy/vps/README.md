# Deploy on a VPS (attendance.cookblog.net)

Runs the whole stack (Postgres, backend, frontend, Prometheus, Grafana) with Docker Compose. A Cloudflare Tunnel (`cloudflared` service) publishes it, so no ports are opened and the host's nginx is not involved. Cloudflare handles HTTPS.

- App: `https://attendance.cookblog.net`
- Grafana: `https://attendance.cookblog.net/grafana/`

## Files

| File | Purpose |
|---|---|
| `compose.yml` | Production stack. Only the frontend (`127.0.0.1:8095`) and Grafana (`127.0.0.1:3005`) listen, and only on localhost. |
| `prometheus.yml` | Scrapes the backend's `/metrics` inside the Docker network (not exposed publicly). |
| `../../frontend/Dockerfile.prebuilt` | Serves a `dist/` built on another machine, for small servers that can't run the Node build. |
| `frontend-nginx.conf` | Frontend container config: the SPA, `/api/` to the backend, `/grafana/` to Grafana. |
| `nginx-host.conf`, `setup-host.sh` | Alternative to the tunnel: host nginx site and Let's Encrypt certificate (needs sudo). |

## First deploy

1. Build the frontend locally: `cd frontend && npm ci && npm run build`.
2. Copy `backend/`, `infra/`, `frontend/{dist,nginx.conf,Dockerfile.prebuilt}` and the files in this folder to `~/attendance` on the server.
3. In Cloudflare Zero Trust, create a tunnel and copy its token. Add a DNS `CNAME` record `attendance` pointing to `<tunnel-id>.cfargotunnel.com` (proxied).
4. Create `~/attendance/.env` with `POSTGRES_PASSWORD`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` and `TUNNEL_TOKEN`.
5. `docker compose up -d --build`

## Updating

Repeat steps 1, 2 and 5. The database, uploaded photos and Grafana state are kept in Docker volumes.
