# WOPR Control Plane Containers

Containerized deployment for the WOPR orchestration layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WOPR Control Plane Host                       │
│                     (orc.wopr.systems)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              wopr-orc (Podman Container)                  │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │  FastAPI    │  │   Stripe    │  │    Provider     │   │   │
│  │  │ Orchestrator│  │   Webhook   │  │   Adapters      │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │   Email     │  │     DNS     │  │   PDF Generator │   │   │
│  │  │   Service   │  │  (Cloudflare)│  │   (WeasyPrint) │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │                                                           │   │
│  │  Port 8001 ◄─────── Caddy Reverse Proxy ◄─── HTTPS      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────┐   ┌──────────────────────────────┐  │
│  │  wopr-provider-health  │   │  PostgreSQL (External)       │  │
│  │  (Scheduled - Timer)   │   │  on nodez3r0                 │  │
│  └────────────────────────┘   └──────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Development (podman-compose)

```bash
# Start the stack
cd /path/to/wopr-installer
cp .env.example .env
# Edit .env with your secrets
podman-compose up -d

# Check logs
podman-compose logs -f orc

# Stop
podman-compose down
```

### Production (systemd quadlets)

```bash
# Deploy to a Linux host
./containers/deploy.sh

# Or manually:
sudo cp containers/systemd/*.container /etc/containers/systemd/
sudo cp containers/systemd/*.timer /etc/containers/systemd/
sudo cp .env /etc/wopr/orchestrator.env
sudo chmod 600 /etc/wopr/orchestrator.env
sudo systemctl daemon-reload
sudo systemctl enable --now wopr-orc
sudo systemctl enable --now wopr-provider-health.timer
```

## Container Images

### Building Locally

```bash
# Build the control-plane image
podman build -t wopr-control-plane -f containers/control-plane/Containerfile .

# Run it
podman run -d --name wopr-orc \
  -p 8001:8001 \
  --env-file .env \
  wopr-control-plane
```

### Pushing to Registry

```bash
# Tag and push to GHCR
podman tag wopr-control-plane ghcr.io/woprsystems/control-plane:latest
podman push ghcr.io/woprsystems/control-plane:latest
```

## Directory Structure

```
containers/
├── control-plane/
│   ├── Containerfile      # Container build definition
│   └── entrypoint.sh      # Container startup script
├── systemd/
│   ├── wopr-orc.container             # Main orchestrator quadlet
│   ├── wopr-provider-health.container # Health monitor quadlet
│   └── wopr-provider-health.timer     # Scheduled health checks
├── deploy.sh              # Deployment automation script
└── README.md              # This file
```

## Volumes

| Volume | Purpose | Mount Point |
|--------|---------|-------------|
| `wopr-jobs` | Provisioning job state | `/var/lib/wopr/jobs` |
| `wopr-docs` | Generated PDFs | `/var/lib/wopr/documents` |
| `wopr-logs` | Application logs | `/var/log/wopr` |
| `wopr-health-state` | Provider health state | `/var/lib/wopr/provider-health` |

## Environment Variables

See [.env.example](../.env.example) for all configuration options.

Required:
- `STRIPE_TEST_SECRET_KEY` / `STRIPE_LIVE_SECRET_KEY`
- `HETZNER_API_TOKEN` (or other provider token)
- `DATABASE_URL`
- `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ZONE_ID`
- `SMTP_*` credentials
- `AUTHENTIK_URL` + `AUTHENTIK_API_TOKEN`

## Health Checks

The orchestrator exposes a health endpoint:

```bash
curl http://localhost:8001/api/health
```

Returns:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T...",
  "providers": ["hetzner"],
  "stripe_configured": true,
  "database_connected": true,
  "email_configured": true,
  "dns_configured": true
}
```

## Logs

```bash
# Container logs
podman logs -f wopr-orc

# Systemd journal (if using quadlets)
journalctl -u wopr-orc -f

# Provider health check logs
journalctl -u wopr-provider-health
```

## Scaling

For high availability:
1. Run multiple `wopr-orc` instances behind a load balancer
2. Enable Redis for shared job queue
3. Use PostgreSQL for all state (no local JSON files)

```yaml
# Example: podman-compose with multiple replicas
services:
  orc:
    deploy:
      replicas: 3
```

## Troubleshooting

### Container won't start

```bash
# Check for missing env vars
podman run --rm --env-file .env wopr-control-plane /entrypoint.sh echo "OK"

# Check database connectivity
podman run --rm --env-file .env wopr-control-plane nc -zv <db-host> 5432
```

### Webhook not receiving events

1. Check Caddy is proxying to port 8001
2. Verify Stripe webhook URL: `https://orc.wopr.systems/api/webhook/stripe`
3. Check webhook secret matches

### VPS provisioning fails

```bash
# Test Hetzner API manually
curl -H "Authorization: Bearer $HETZNER_API_TOKEN" \
  https://api.hetzner.cloud/v1/servers
```
