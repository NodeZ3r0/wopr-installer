# WOPR Full Monitoring Stack

DEFCON ONE multi-server monitoring with Grafana, Prometheus, Loki, and ntfy alerting.

```
┌─────────────────────────────────────────────────────────────┐
│                    HETZNER FINLAND (Primary)                 │
│                                                             │
│  Grafana ─── Prometheus ─── Alertmanager ─── ntfy           │
│      │                                                      │
│      ├── Loki ◄── Promtail                                  │
│      ├── Umami (web analytics)                              │
│      ├── Uptime Kuma (uptime monitoring)                    │
│      └── ntopng (network analysis)                          │
│                                                             │
│  Subdomains:                                                │
│    grafana.wopr.systems      defcon.wopr.systems            │
│    loki.wopr.systems         ntfy.wopr.systems              │
│    umami.wopr.systems        uptime.wopr.systems            │
└──────────────────────┬──────────────────────────────────────┘
                       │ Nebula Mesh (10.42.0.0/16)
┌──────────────────────┴──────────────────────────────────────┐
│               NODEZ3R0 DO VPS (Secondary)                   │
│                                                             │
│  Grafana ─── Prometheus ─── Loki ◄── Promtail               │
│  Node Exporter                                              │
│                                                             │
│  Cross-scrapes Hetzner + Home Rig over Nebula               │
│  grafana-secondary.wopr.systems                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ Nebula Mesh
┌──────────────────────┴──────────────────────────────────────┐
│                    HOME RIG (Agents Only)                    │
│                                                             │
│  Node Exporter + Promtail                                   │
│  Feeds both Prometheus/Loki instances                       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose on all nodes
- Nebula VPN mesh already configured between nodes
- Domain `wopr.systems` with DNS configured

### 1. Get Your Nebula IPs

On each node, run:
```bash
nebula-cert print -path /etc/nebula/host.crt | grep "ip:"
```

### 2. Deploy Hetzner Primary

```bash
cd hetzner-primary

# Copy and configure environment
cp .env.example .env
nano .env  # Fill in all values

# Generate secrets
echo "UMAMI_DB_PASSWORD=$(openssl rand -hex 32)" >> .env
echo "UMAMI_APP_SECRET=$(openssl rand -hex 32)" >> .env
echo "GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 32)" >> .env

# Replace Nebula IPs in Prometheus config
sed -i 's/\${NODEZ3R0_NEBULA_IP}/10.42.0.2/g' prometheus/prometheus.yml
sed -i 's/\${HOMERIG_NEBULA_IP}/10.42.0.3/g' prometheus/prometheus.yml

# Start services
docker compose up -d

# Verify
docker compose ps
docker compose logs -f grafana
```

### 3. Deploy NodeZ3r0 Secondary

```bash
cd nodez3r0-secondary

cp .env.example .env
nano .env

# Replace Nebula IPs
sed -i 's/\${HETZNER_NEBULA_IP}/10.42.0.1/g' prometheus/prometheus.yml
sed -i 's/\${HOMERIG_NEBULA_IP}/10.42.0.3/g' prometheus/prometheus.yml
sed -i 's/\${HETZNER_NEBULA_IP}/10.42.0.1/g' promtail/config.yml

docker compose up -d
```

### 4. Deploy Home Rig Agents

```bash
cd homerig-agents

cp .env.example .env
nano .env

# Replace Nebula IPs in Promtail config
sed -i 's/\${HETZNER_NEBULA_IP}/10.42.0.1/g' promtail/config.yml
sed -i 's/\${NODEZ3R0_NEBULA_IP}/10.42.0.2/g' promtail/config.yml

docker compose up -d
```

### 5. Configure Caddy (on Hetzner)

Add the routes from `hetzner-primary/caddy/Caddyfile` to your existing Caddy configuration:

```bash
sudo nano /etc/caddy/Caddyfile
# Add the monitoring routes
sudo systemctl reload caddy
```

### 6. Access Dashboards

- **Grafana**: https://grafana.wopr.systems (admin / your password)
- **DEFCON Dashboard**: https://defcon.wopr.systems
- **Uptime Kuma**: https://uptime.wopr.systems
- **Umami**: https://umami.wopr.systems
- **ntfy**: https://ntfy.wopr.systems

### 7. Subscribe to ntfy Alerts

On your phone:
1. Install ntfy app (iOS/Android)
2. Subscribe to topics:
   - `wopr-critical` - DEFCON 1 alerts (urgent)
   - `wopr-alerts` - DEFCON 2-4 alerts (normal)
   - `wopr-info` - Informational alerts (low priority)

Or use the web UI at https://ntfy.wopr.systems

## Directory Structure

```
wopr-monitoring-stack/
├── hetzner-primary/           # Main monitoring stack
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── prometheus/
│   │   ├── prometheus.yml     # Scrape configs
│   │   └── alerts.yml         # DEFCON alert rules
│   ├── alertmanager/
│   │   └── alertmanager.yml   # ntfy + email routing
│   ├── loki/
│   │   └── config.yml
│   ├── promtail/
│   │   └── config.yml
│   ├── ntfy/
│   │   └── server.yml
│   ├── caddy/
│   │   └── Caddyfile
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   └── dashboards/
│       └── dashboards/
│           └── defcon-overview.json
│
├── nodez3r0-secondary/        # Redundant monitoring
│   ├── docker-compose.yml
│   ├── prometheus/
│   ├── loki/
│   └── promtail/
│
├── homerig-agents/            # Agent-only deployment
│   ├── docker-compose.yml
│   └── promtail/
│
└── defcon-dashboard/          # Custom CRT-style dashboard
    ├── Dockerfile
    ├── main.py
    ├── requirements.txt
    ├── templates/
    │   └── dashboard.html
    └── static/
        ├── css/
        │   └── crt.css
        └── js/
            └── dashboard.js
```

## Alert Levels

| DEFCON | Severity | Description | Notification |
|--------|----------|-------------|--------------|
| 1 | Critical | Instance down, disk full, OOM | ntfy urgent + email |
| 2 | High | High CPU/memory, disk warning | ntfy high + email |
| 3 | Warning | Network issues, service degraded | ntfy normal |
| 4 | Low | Target missing, minor issues | ntfy normal |
| 5 | Info | Reboots, clock skew | ntfy low |

## Grafana Dashboards

After deployment, import these community dashboards:

| Dashboard | Grafana ID | Purpose |
|-----------|-----------|---------|
| Node Exporter Full | 1860 | System metrics per host |
| Docker Container | 893 | Container resource usage |
| Loki & Promtail | 13639 | Log volume and errors |
| Caddy Monitoring | 14280 | HTTP metrics |

Import via: Grafana > Dashboards > Import > Enter ID > Load

## Troubleshooting

### Check Prometheus Targets
```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

### Check Loki Ingestion
```bash
curl http://localhost:3100/ready
curl http://localhost:3100/metrics | grep loki_distributor_lines_received_total
```

### Check Alertmanager
```bash
curl http://localhost:9093/api/v2/status
curl http://localhost:9093/api/v2/alerts
```

### Test ntfy Notification
```bash
curl -d "Test alert from WOPR monitoring" https://ntfy.wopr.systems/wopr-alerts
```

### View Container Logs
```bash
docker compose logs -f prometheus
docker compose logs -f loki
docker compose logs -f alertmanager
```

## Maintenance

### Backup Grafana
```bash
docker exec grafana grafana-cli admin export > grafana-backup.json
```

### Update Stack
```bash
docker compose pull
docker compose up -d
```

### Compact Prometheus Data
```bash
docker exec prometheus promtool tsdb compact /prometheus
```

## Security Notes

- All services are behind Caddy with automatic HTTPS
- Internal APIs (Prometheus, Loki) restricted to Nebula IPs
- ntfy topics are public by default - configure auth in `ntfy/server.yml` if needed
- Grafana has anonymous access disabled
- Change default passwords immediately after deployment

## Related

- [WOPR Support Plane](../wopr-support-plane/) - Diagnostics and remediation
- [WOPR Installer](../wopr-installer/) - Full beacon deployment
- [Nebula](https://github.com/slackhq/nebula) - Mesh VPN