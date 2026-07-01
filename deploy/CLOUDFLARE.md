# Cloudflare + Caddy Deployment Guide

This setup keeps Caddy as the local reverse proxy and uses Cloudflare only for
DNS, HTTPS at the edge, DDoS protection, and the tunnel from Cloudflare to your
server.

## What Is Free

Use Cloudflare's Free application plan plus Cloudflare Tunnel/Zero Trust Free.
For this app, the free pieces are enough:

- DNS hosting for your domain
- proxied hostname/CDN edge
- Universal SSL at the Cloudflare edge
- basic DDoS protection
- Cloudflare Tunnel for exposing local Caddy without opening inbound ports

Avoid enabling these unless you intentionally want a paid feature:

- Load Balancing
- paid Health Checks or Synthetic Monitoring
- Argo Smart Routing
- APO
- Workers paid usage
- Pro, Business, or Enterprise plan upgrades

Official pages to verify before enabling anything:

- https://www.cloudflare.com/plans/application-services/
- https://www.cloudflare.com/products/tunnel/
- https://www.cloudflare.com/plans/zero-trust-services/

## Account Setup

1. Create an account at https://dash.cloudflare.com/sign-up.
2. Add your domain.
3. Select the Free plan.
4. Cloudflare will show two nameservers. Set those at your domain registrar.
5. Wait until the domain shows as active in Cloudflare.

## Stable Tunnel Setup

Install `cloudflared` on the server, then authenticate:

```powershell
cloudflared tunnel login
```

Create a named tunnel:

```powershell
cloudflared tunnel create hdbmatch
```

Route your hostname to it:

```powershell
cloudflared tunnel route dns hdbmatch app.example.com
```

Copy `deploy/cloudflared-config.yml.example` to:

```text
%USERPROFILE%\.cloudflared\config.yml
```

Then edit:

- `tunnel`
- `credentials-file`
- `hostname`

Point the hostname service to Caddy:

```yaml
service: http://localhost:8080
```

Run it:

```powershell
cloudflared tunnel run hdbmatch
```

When this works, install it as a service so it restarts after reboot:

```powershell
cloudflared service install
```

## Run The App

Start the app stack:

```powershell
.\deploy\serve.ps1 -TunnelName hdbmatch
```

Health URLs:

```text
https://app.example.com/health
https://app.example.com/api/health
```

Use `/health` to verify Caddy is reachable. Use `/api/health` to verify the
backend and data path.

## Uptime Notes

This repo now sets `restart: unless-stopped` for the Docker services and adds a
backend container health check. For a real production machine, also run Caddy as
a system service instead of a foreground terminal process.

On Windows, use Caddy's service mode if installed through a service-capable
package, or run Caddy from Task Scheduler at startup:

```powershell
caddy run --config deploy/Caddyfile
```

Recommended free external monitoring:

- UptimeRobot free monitor against `https://app.example.com/api/health`
- Better Stack free monitor, if you already use it

Do not enable Cloudflare Load Balancing or paid Health Checks just for this
single-server setup.
