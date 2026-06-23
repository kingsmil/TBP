# Run HDB Match locally, shared over HTTPS

Runs the whole app on your machine and exposes it as a public, trusted
`https://….trycloudflare.com` URL via a Cloudflare quick tunnel. No domain, no
account, nothing for visitors to install. The app and all data stay on your PC.

```
Internet ──https──► Cloudflare Tunnel ──► Caddy :8080 ──┬─ /      → frontend dist
                                                        └─ /api/* → backend :8010
                         Docker: Postgres + Redis   ·   uvicorn backend
```

## One-time install (Windows)

```powershell
winget install Cloudflare.cloudflared
winget install CaddyServer.Caddy
# (or: choco install cloudflared caddy   /   scoop install cloudflared caddy)
```

## Start it (4 terminals, from the repo root)

**1. Database** — start Docker Desktop, then:
```powershell
docker compose up -d db redis
```

**2. Backend** (serves the API on :8010; reads .env for DB + OneMap):
```powershell
cd backend; .\.venv\Scripts\python.exe -m app.run_server
```

**3. Build the frontend, then serve everything through Caddy on :8080:**
```powershell
cd frontend; npm run build; cd ..
caddy run --config deploy/Caddyfile
```
> `npm run build` uses the default API base `/api`, which Caddy proxies to the
> backend — so the same build works on any tunnel URL. Rebuild only when the
> frontend changes.

**4. Open the public HTTPS tunnel:**
```powershell
cloudflared tunnel --url http://localhost:8080
```
cloudflared prints a line like:
```
https://random-words-1234.trycloudflare.com
```
That URL is your live, HTTPS app. Share it. It's valid until you stop
cloudflared (each run gets a fresh URL).

## Verify
- `https://localhost:8080`-equivalent locally: open `http://localhost:8080` →
  the app loads and the map shows live data (`/api/health` returns
  `"mode":"postgis"`).
- Then open the `trycloudflare.com` URL from your phone / another network.

## Notes
- **Stable URL / custom domain:** swap the quick tunnel for a *named* Cloudflare
  Tunnel (`cloudflared tunnel create`, route a domain, `ingress` → `localhost:8080`)
  to keep the same URL across restarts.
- **ngrok alternative:** `ngrok http 8080` (needs a free account/authtoken).
- **Auth/AI:** the shared build is the Explore product (map, scoring, info).
  AI mode and login are disabled, so there's nothing to secure for a demo.
- **Keep Docker running** — stopping it drops the app back to mock data.
