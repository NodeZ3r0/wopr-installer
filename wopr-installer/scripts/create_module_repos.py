#!/usr/bin/env python3
"""
Create GitHub repos for all 81 WOPR modules with SSO configurations.
"""

import subprocess
import os
import json
import time

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_USER = "NodeZ3r0"
BASE_DIR = "/opt/wopr-modules"

MODULES = [
    {"id": "authentik", "name": "Authentik", "desc": "SSO and identity management", "image": "ghcr.io/goauthentik/server:2025.8", "port": 9000, "sso": "none", "subdomain": "auth", "ram": 1024, "replaces": "Okta, Auth0"},
    {"id": "caddy", "name": "Caddy", "desc": "Automatic HTTPS reverse proxy", "image": "caddy:2-alpine", "port": 443, "sso": "none", "subdomain": "", "ram": 128, "replaces": "Nginx, Apache"},
    {"id": "postgresql", "name": "PostgreSQL", "desc": "Primary database", "image": "postgres:16-alpine", "port": 5432, "sso": "none", "subdomain": "", "ram": 512, "replaces": "AWS RDS"},
    {"id": "redis", "name": "Redis", "desc": "Cache and message broker", "image": "redis:7-alpine", "port": 6379, "sso": "none", "subdomain": "", "ram": 256, "replaces": "AWS ElastiCache"},
    {"id": "nextcloud", "name": "Nextcloud", "desc": "Files, calendar, contacts", "image": "nextcloud:29-apache", "port": 80, "sso": "oidc", "subdomain": "files", "ram": 1024, "replaces": "Google Drive, Dropbox"},
    {"id": "collabora", "name": "Collabora Online", "desc": "Online office suite", "image": "collabora/code:24.04", "port": 9980, "sso": "oidc", "subdomain": "office", "ram": 2048, "replaces": "Google Docs, Microsoft 365"},
    {"id": "outline", "name": "Outline", "desc": "Team wiki and knowledge base", "image": "outlinewiki/outline:latest", "port": 3000, "sso": "oidc", "subdomain": "wiki", "ram": 512, "replaces": "Notion, Confluence"},
    {"id": "paperless-ngx", "name": "Paperless-ngx", "desc": "Document management with OCR", "image": "ghcr.io/paperless-ngx/paperless-ngx:latest", "port": 8000, "sso": "oidc", "subdomain": "docs", "ram": 1024, "replaces": "Evernote, Adobe Scan"},
    {"id": "bookstack", "name": "BookStack", "desc": "Wiki and documentation", "image": "lscr.io/linuxserver/bookstack:latest", "port": 6875, "sso": "oidc", "subdomain": "books", "ram": 512, "replaces": "GitBook"},
    {"id": "affine", "name": "AFFiNE", "desc": "Notion alternative knowledge base", "image": "ghcr.io/toeverything/affine-graphql:stable", "port": 3010, "sso": "oidc", "subdomain": "notes", "ram": 1024, "replaces": "Notion, Coda"},
    {"id": "linkwarden", "name": "Linkwarden", "desc": "Bookmark manager with archival", "image": "ghcr.io/linkwarden/linkwarden:latest", "port": 3000, "sso": "proxy", "subdomain": "links", "ram": 512, "replaces": "Pocket, Raindrop"},
    {"id": "standardnotes", "name": "Standard Notes", "desc": "Encrypted notes", "image": "standardnotes/server:latest", "port": 3000, "sso": "proxy", "subdomain": "notes", "ram": 512, "replaces": "Apple Notes, Evernote"},
    {"id": "calcom", "name": "Cal.com", "desc": "Appointment scheduling", "image": "calcom/cal.com:v6.1.11", "port": 3000, "sso": "oidc", "subdomain": "cal", "ram": 1024, "replaces": "Calendly"},
    {"id": "hedgedoc", "name": "HedgeDoc", "desc": "Collaborative markdown", "image": "quay.io/hedgedoc/hedgedoc:latest", "port": 3000, "sso": "oidc", "subdomain": "pad", "ram": 512, "replaces": "HackMD"},
    {"id": "stirling-pdf", "name": "Stirling PDF", "desc": "PDF tools suite", "image": "frooodle/s-pdf:latest", "port": 8080, "sso": "proxy", "subdomain": "pdf", "ram": 512, "replaces": "Adobe Acrobat"},
    {"id": "docuseal", "name": "DocuSeal", "desc": "Document signing", "image": "docuseal/docuseal:latest", "port": 3000, "sso": "oidc", "subdomain": "sign", "ram": 512, "replaces": "DocuSign"},
    {"id": "freshrss", "name": "FreshRSS", "desc": "RSS feed reader", "image": "freshrss/freshrss:latest", "port": 80, "sso": "proxy", "subdomain": "rss", "ram": 256, "replaces": "Feedly"},
    {"id": "vaultwarden", "name": "Vaultwarden", "desc": "Password manager (Bitwarden)", "image": "vaultwarden/server:latest", "port": 80, "sso": "oidc", "subdomain": "vault", "ram": 256, "replaces": "Bitwarden, 1Password, LastPass"},
    {"id": "netbird", "name": "NetBird", "desc": "WireGuard mesh VPN", "image": "netbirdio/netbird:latest", "port": 443, "sso": "oidc", "subdomain": "vpn", "ram": 512, "replaces": "Tailscale, NordVPN"},
    {"id": "crowdsec", "name": "CrowdSec", "desc": "Collaborative IDS", "image": "crowdsecurity/crowdsec:latest", "port": 8080, "sso": "proxy", "subdomain": "security", "ram": 512, "replaces": "Fail2ban"},
    {"id": "wg-easy", "name": "WireGuard Easy", "desc": "Simple WireGuard VPN", "image": "ghcr.io/wg-easy/wg-easy:latest", "port": 51821, "sso": "proxy", "subdomain": "wg", "ram": 128, "replaces": "NordVPN, ExpressVPN"},
    {"id": "adguard", "name": "AdGuard Home", "desc": "Ad and tracker blocking", "image": "adguard/adguardhome:latest", "port": 3000, "sso": "proxy", "subdomain": "dns", "ram": 256, "replaces": "Pi-hole, NextDNS"},
    {"id": "passbolt", "name": "Passbolt", "desc": "Team password manager", "image": "passbolt/passbolt:latest", "port": 443, "sso": "oidc", "subdomain": "passwords", "ram": 512, "replaces": "1Password Teams"},
    {"id": "matrix-synapse", "name": "Matrix Synapse", "desc": "Decentralized chat server", "image": "matrixdotorg/synapse:latest", "port": 8008, "sso": "oidc", "subdomain": "matrix", "ram": 1024, "replaces": "Slack, Teams"},
    {"id": "element", "name": "Element", "desc": "Matrix chat client", "image": "vectorim/element-web:latest", "port": 80, "sso": "oidc", "subdomain": "chat", "ram": 128, "replaces": "Slack app"},
    {"id": "jitsi", "name": "Jitsi Meet", "desc": "Video conferencing", "image": "jitsi/web:stable", "port": 443, "sso": "oidc", "subdomain": "meet", "ram": 2048, "replaces": "Zoom, Google Meet"},
    {"id": "mattermost", "name": "Mattermost", "desc": "Slack alternative", "image": "mattermost/mattermost-team-edition:latest", "port": 8065, "sso": "oidc", "subdomain": "team", "ram": 1024, "replaces": "Slack, Teams"},
    {"id": "mailcow", "name": "Mailcow", "desc": "Complete email server", "image": "mailcow/mailcow-dockerized:latest", "port": 443, "sso": "oidc", "subdomain": "mail", "ram": 4096, "replaces": "Gmail, Outlook"},
    {"id": "listmonk", "name": "Listmonk", "desc": "Newsletter manager", "image": "listmonk/listmonk:latest", "port": 9000, "sso": "proxy", "subdomain": "newsletter", "ram": 256, "replaces": "Mailchimp"},
    {"id": "ntfy", "name": "ntfy", "desc": "Push notifications", "image": "binwiederhier/ntfy:latest", "port": 80, "sso": "proxy", "subdomain": "notify", "ram": 128, "replaces": "Pushover"},
    {"id": "mumble", "name": "Mumble", "desc": "Voice chat", "image": "mumblevoip/mumble-server:latest", "port": 64738, "sso": "proxy", "subdomain": "voice", "ram": 256, "replaces": "Discord voice"},
    {"id": "forgejo", "name": "Forgejo", "desc": "Git repository hosting", "image": "codeberg.org/forgejo/forgejo:8", "port": 3000, "sso": "oidc", "subdomain": "git", "ram": 512, "replaces": "GitHub, GitLab"},
    {"id": "woodpecker", "name": "Woodpecker CI", "desc": "CI/CD pipelines", "image": "woodpeckerci/woodpecker-server:latest", "port": 8000, "sso": "oidc", "subdomain": "ci", "ram": 512, "replaces": "GitHub Actions, CircleCI"},
    {"id": "ollama", "name": "Ollama", "desc": "Local LLM runtime", "image": "ollama/ollama:latest", "port": 11434, "sso": "proxy", "subdomain": "llm", "ram": 8192, "replaces": "OpenAI API, Claude API"},
    {"id": "reactor", "name": "Reactor AI", "desc": "AI code assistant with DEFCON ONE", "image": "wopr/reactor:latest", "port": 8080, "sso": "oidc", "subdomain": "reactor", "ram": 2048, "replaces": "GitHub Copilot, Cursor"},
    {"id": "defcon-one", "name": "DEFCON ONE", "desc": "Protected actions gateway", "image": "wopr/defcon-one:latest", "port": 8081, "sso": "oidc", "subdomain": "defcon", "ram": 512, "replaces": "Custom approval workflows"},
    {"id": "code-server", "name": "VS Code Server", "desc": "Browser-based VS Code", "image": "codercom/code-server:latest", "port": 8080, "sso": "oidc", "subdomain": "code", "ram": 1024, "replaces": "VS Code, Codespaces"},
    {"id": "portainer", "name": "Portainer", "desc": "Docker management UI", "image": "portainer/portainer-ce:latest", "port": 9000, "sso": "oidc", "subdomain": "docker", "ram": 256, "replaces": "Docker Desktop"},
    {"id": "docker-registry", "name": "Docker Registry", "desc": "Private container registry", "image": "registry:2", "port": 5000, "sso": "proxy", "subdomain": "registry", "ram": 256, "replaces": "Docker Hub, GHCR"},
    {"id": "langfuse", "name": "Langfuse", "desc": "LLM observability", "image": "langfuse/langfuse:latest", "port": 3000, "sso": "oidc", "subdomain": "llm-ops", "ram": 512, "replaces": "LangSmith"},
    {"id": "openwebui", "name": "Open WebUI", "desc": "ChatGPT-style LLM UI", "image": "ghcr.io/open-webui/open-webui:main", "port": 8080, "sso": "oidc", "subdomain": "ai", "ram": 512, "replaces": "ChatGPT, Claude.ai"},
    {"id": "n8n", "name": "n8n", "desc": "Workflow automation", "image": "n8nio/n8n:latest", "port": 5678, "sso": "oidc", "subdomain": "automation", "ram": 512, "replaces": "Zapier, Make"},
    {"id": "nocodb", "name": "NocoDB", "desc": "Airtable alternative", "image": "nocodb/nocodb:latest", "port": 8080, "sso": "oidc", "subdomain": "tables", "ram": 512, "replaces": "Airtable"},
    {"id": "plane", "name": "Plane", "desc": "Project management", "image": "makeplane/plane-frontend:latest", "port": 3000, "sso": "oidc", "subdomain": "projects", "ram": 512, "replaces": "Jira, Linear"},
    {"id": "gitea-runner", "name": "Gitea Act Runner", "desc": "CI/CD runner", "image": "gitea/act_runner:latest", "port": 0, "sso": "none", "subdomain": "", "ram": 1024, "replaces": "GitHub Actions runners"},
    {"id": "ghost", "name": "Ghost", "desc": "Professional blog platform", "image": "ghost:5-alpine", "port": 2368, "sso": "oidc", "subdomain": "blog", "ram": 512, "replaces": "Medium, Substack"},
    {"id": "saleor", "name": "Saleor", "desc": "E-commerce platform", "image": "ghcr.io/saleor/saleor:latest", "port": 8000, "sso": "proxy", "subdomain": "store", "ram": 1024, "replaces": "Shopify"},
    {"id": "peertube", "name": "PeerTube", "desc": "Video hosting platform", "image": "chocobozzz/peertube:production-bookworm", "port": 9000, "sso": "oidc", "subdomain": "video", "ram": 2048, "replaces": "YouTube, Vimeo"},
    {"id": "pixelfed", "name": "Pixelfed", "desc": "Photo sharing (Instagram)", "image": "pixelfed/pixelfed:latest", "port": 80, "sso": "oidc", "subdomain": "photos", "ram": 1024, "replaces": "Instagram"},
    {"id": "writefreely", "name": "WriteFreely", "desc": "Minimalist blogging", "image": "writeas/writefreely:latest", "port": 8080, "sso": "oidc", "subdomain": "write", "ram": 256, "replaces": "Medium"},
    {"id": "funkwhale", "name": "Funkwhale", "desc": "Music streaming/hosting", "image": "funkwhale/all-in-one:latest", "port": 80, "sso": "oidc", "subdomain": "music", "ram": 1024, "replaces": "Bandcamp, SoundCloud"},
    {"id": "castopod", "name": "Castopod", "desc": "Podcast hosting", "image": "castopod/castopod:latest", "port": 8000, "sso": "oidc", "subdomain": "podcast", "ram": 512, "replaces": "Anchor, Spotify"},
    {"id": "mastodon", "name": "Mastodon", "desc": "Decentralized social", "image": "tootsuite/mastodon:latest", "port": 3000, "sso": "oidc", "subdomain": "social", "ram": 1024, "replaces": "Twitter/X"},
    {"id": "gotosocial", "name": "GoToSocial", "desc": "Lightweight ActivityPub", "image": "superseriousbusiness/gotosocial:latest", "port": 8080, "sso": "oidc", "subdomain": "fedi", "ram": 256, "replaces": "Twitter/X"},
    {"id": "lemmy", "name": "Lemmy", "desc": "Reddit alternative", "image": "dessalines/lemmy:latest", "port": 8536, "sso": "oidc", "subdomain": "community", "ram": 512, "replaces": "Reddit"},
    {"id": "espocrm", "name": "EspoCRM", "desc": "CRM system", "image": "espocrm/espocrm:latest", "port": 80, "sso": "oidc", "subdomain": "crm", "ram": 512, "replaces": "Salesforce"},
    {"id": "kimai", "name": "Kimai", "desc": "Time tracking", "image": "kimai/kimai2:latest", "port": 8001, "sso": "oidc", "subdomain": "time", "ram": 256, "replaces": "Toggl, Harvest"},
    {"id": "invoiceninja", "name": "Invoice Ninja", "desc": "Invoicing", "image": "invoiceninja/invoiceninja:latest", "port": 80, "sso": "oidc", "subdomain": "invoices", "ram": 512, "replaces": "FreshBooks"},
    {"id": "erpnext", "name": "ERPNext", "desc": "Full ERP suite", "image": "frappe/erpnext:latest", "port": 8000, "sso": "oidc", "subdomain": "erp", "ram": 4096, "replaces": "SAP, NetSuite"},
    {"id": "dolibarr", "name": "Dolibarr", "desc": "ERP/CRM for SMBs", "image": "dolibarr/dolibarr:latest", "port": 80, "sso": "oidc", "subdomain": "business", "ram": 512, "replaces": "QuickBooks"},
    {"id": "odoo", "name": "Odoo Community", "desc": "Business suite", "image": "odoo:17", "port": 8069, "sso": "oidc", "subdomain": "odoo", "ram": 2048, "replaces": "Zoho One"},
    {"id": "twenty", "name": "Twenty", "desc": "Modern CRM", "image": "twentycrm/twenty:latest", "port": 3000, "sso": "oidc", "subdomain": "sales", "ram": 512, "replaces": "HubSpot"},
    {"id": "akaunting", "name": "Akaunting", "desc": "Accounting", "image": "akaunting/akaunting:latest", "port": 80, "sso": "oidc", "subdomain": "accounting", "ram": 512, "replaces": "QuickBooks, Xero"},
    {"id": "documenso", "name": "Documenso", "desc": "Document signing", "image": "documenso/documenso:latest", "port": 3000, "sso": "oidc", "subdomain": "esign", "ram": 512, "replaces": "DocuSign"},
    {"id": "chatwoot", "name": "Chatwoot", "desc": "Customer support", "image": "chatwoot/chatwoot:latest", "port": 3000, "sso": "oidc", "subdomain": "support", "ram": 1024, "replaces": "Intercom, Zendesk"},
    {"id": "immich", "name": "Immich", "desc": "Photo/video backup", "image": "ghcr.io/immich-app/immich-server:latest", "port": 3001, "sso": "oidc", "subdomain": "photos", "ram": 2048, "replaces": "Google Photos"},
    {"id": "jellyfin", "name": "Jellyfin", "desc": "Media server", "image": "jellyfin/jellyfin:latest", "port": 8096, "sso": "oidc", "subdomain": "media", "ram": 2048, "replaces": "Plex, Netflix"},
    {"id": "audiobookshelf", "name": "Audiobookshelf", "desc": "Audiobook server", "image": "ghcr.io/advplyr/audiobookshelf:latest", "port": 80, "sso": "oidc", "subdomain": "audiobooks", "ram": 512, "replaces": "Audible"},
    {"id": "navidrome", "name": "Navidrome", "desc": "Music streaming", "image": "deluan/navidrome:latest", "port": 4533, "sso": "proxy", "subdomain": "stream", "ram": 256, "replaces": "Spotify"},
    {"id": "stash", "name": "Stash", "desc": "Media organizer", "image": "stashapp/stash:latest", "port": 9999, "sso": "proxy", "subdomain": "stash", "ram": 1024, "replaces": "Custom media org"},
    {"id": "photoprism", "name": "PhotoPrism", "desc": "AI photo management", "image": "photoprism/photoprism:latest", "port": 2342, "sso": "oidc", "subdomain": "gallery", "ram": 4096, "replaces": "Google Photos AI"},
    {"id": "kavita", "name": "Kavita", "desc": "Ebook/comic library", "image": "kizaing/kavita:latest", "port": 5000, "sso": "proxy", "subdomain": "library", "ram": 512, "replaces": "Kindle"},
    {"id": "calibre-web", "name": "Calibre-Web", "desc": "Ebook library", "image": "lscr.io/linuxserver/calibre-web:latest", "port": 8083, "sso": "oidc", "subdomain": "ebooks", "ram": 512, "replaces": "Kindle, Kobo"},
    {"id": "plausible", "name": "Plausible", "desc": "Privacy analytics", "image": "plausible/analytics:latest", "port": 8000, "sso": "oidc", "subdomain": "analytics", "ram": 512, "replaces": "Google Analytics"},
    {"id": "uptime-kuma", "name": "Uptime Kuma", "desc": "Uptime monitoring", "image": "louislam/uptime-kuma:latest", "port": 3001, "sso": "proxy", "subdomain": "status", "ram": 256, "replaces": "Pingdom, UptimeRobot"},
    {"id": "grafana", "name": "Grafana", "desc": "Metrics dashboards", "image": "grafana/grafana:latest", "port": 3000, "sso": "oidc", "subdomain": "grafana", "ram": 512, "replaces": "Datadog"},
    {"id": "prometheus", "name": "Prometheus", "desc": "Metrics collection", "image": "prom/prometheus:latest", "port": 9090, "sso": "proxy", "subdomain": "metrics", "ram": 512, "replaces": "Datadog"},
    {"id": "netdata", "name": "Netdata", "desc": "Real-time monitoring", "image": "netdata/netdata:latest", "port": 19999, "sso": "proxy", "subdomain": "monitor", "ram": 512, "replaces": "New Relic"},
    {"id": "umami", "name": "Umami", "desc": "Simple analytics", "image": "ghcr.io/umami-software/umami:postgresql-latest", "port": 3000, "sso": "oidc", "subdomain": "stats", "ram": 256, "replaces": "Google Analytics"},
    {"id": "healthchecks", "name": "Healthchecks", "desc": "Cron job monitoring", "image": "healthchecks/healthchecks:latest", "port": 8000, "sso": "oidc", "subdomain": "health", "ram": 256, "replaces": "Cronitor"},
    {"id": "gatus", "name": "Gatus", "desc": "Service health dashboard", "image": "twinproduction/gatus:latest", "port": 8080, "sso": "proxy", "subdomain": "health-status", "ram": 128, "replaces": "StatusPage"},
]


def gen_docker_compose(m):
    return f'''version: "3.8"
# WOPR Module: {m["name"]}
# Replaces: {m["replaces"]}
# SSO Type: {m["sso"]}

services:
  {m["id"]}:
    image: {m["image"]}
    container_name: wopr-{m["id"]}
    restart: unless-stopped
    ports:
      - "{m["port"]}:{m["port"]}"
    environment:
      - TZ=${{TZ:-UTC}}
    volumes:
      - {m["id"]}_data:/data
    labels:
      - "wopr.module={m["id"]}"
      - "wopr.sso={m["sso"]}"
    networks:
      - wopr
    deploy:
      resources:
        limits:
          memory: {m["ram"]}M
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:{m["port"]}/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

volumes:
  {m["id"]}_data:

networks:
  wopr:
    external: true
'''


def gen_caddy_config(m):
    if not m["subdomain"]:
        return "# No subdomain configured for this module\n"

    if m["sso"] == "proxy":
        return f'''# Caddy config for {m["name"]} with Authentik forward auth
{m["subdomain"]}.{{$DOMAIN}} {{
    forward_auth {{$AUTHENTIK_HOST}} {{
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid
        trusted_proxies private_ranges
    }}
    reverse_proxy {m["id"]}:{m["port"]}
}}
'''
    else:
        return f'''# Caddy config for {m["name"]}
{m["subdomain"]}.{{$DOMAIN}} {{
    reverse_proxy {m["id"]}:{m["port"]}
}}
'''


def gen_authentik_config(m):
    if m["sso"] == "none":
        return "# No SSO configured for this core module\n"

    if m["sso"] == "oidc":
        return f'''# Authentik OIDC Provider for {m["name"]}
# Create via Authentik Admin UI or API

provider:
  name: {m["name"]}
  type: oauth2
  authorization_flow: default-provider-authorization-implicit-consent
  client_type: confidential
  client_id: wopr-{m["id"]}
  # client_secret: <generate-secure-secret>
  redirect_uris:
    - https://{m["subdomain"]}.${{DOMAIN}}/oauth2/callback
    - https://{m["subdomain"]}.${{DOMAIN}}/auth/callback
  signing_key: authentik Self-signed Certificate

application:
  name: {m["name"]}
  slug: {m["id"]}
  provider: {m["name"]}
  meta_launch_url: https://{m["subdomain"]}.${{DOMAIN}}
  policy_engine_mode: any

group:
  name: {m["id"]}-users
  parent: wopr-users
'''
    elif m["sso"] == "proxy":
        return f'''# Authentik Proxy Provider for {m["name"]}
# Forward auth via Caddy

provider:
  name: {m["name"]} Proxy
  type: proxy
  authorization_flow: default-provider-authorization-implicit-consent
  mode: forward_single
  external_host: https://{m["subdomain"]}.${{DOMAIN}}

application:
  name: {m["name"]}
  slug: {m["id"]}
  provider: {m["name"]} Proxy
  meta_launch_url: https://{m["subdomain"]}.${{DOMAIN}}
  policy_engine_mode: any

outpost:
  name: wopr-outpost
  type: proxy
  # Add this application to the existing outpost
'''
    return ""


def gen_readme(m):
    return f'''# {m["name"]}

> {m["desc"]}

**Replaces:** {m["replaces"]}

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit configuration
nano .env

# 3. Start the service
docker compose up -d
```

## SSO Configuration

**Type:** {m["sso"].upper()}

{"This module uses Authentik OIDC for single sign-on. See `authentik/config.yaml` for provider setup." if m["sso"] == "oidc" else ""}
{"This module uses Authentik forward auth proxy. Caddy handles authentication before requests reach the app." if m["sso"] == "proxy" else ""}
{"This is a core infrastructure module and does not require SSO." if m["sso"] == "none" else ""}

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOMAIN` | Your domain | required |
| `TZ` | Timezone | UTC |

## Resources

- **RAM:** {m["ram"]}MB recommended
- **Port:** {m["port"]}

## Files

- `docker-compose.yml` - Container configuration
- `caddy/Caddyfile` - Reverse proxy config
- `authentik/config.yaml` - SSO provider config
- `.env.example` - Environment template

## Part of WOPR Sovereign Suite

https://github.com/NodeZ3r0/wopr-installer
'''


def gen_env_example(m):
    return f'''# {m["name"]} Configuration
DOMAIN=example.com
TZ=UTC
AUTHENTIK_HOST=https://auth.${{DOMAIN}}
'''


def create_github_repo(name, desc):
    """Create repo on GitHub"""
    import urllib.request
    import json

    data = json.dumps({
        "name": name,
        "description": f"WOPR Module: {desc}",
        "private": False,
        "auto_init": False
    }).encode()

    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=data,
        headers={
            "Authorization": f"token {GH_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 422:  # Already exists
            return {"exists": True}
        raise


def create_module_repo(m):
    """Create a complete module repo"""
    repo_name = f"wopr-{m['id']}"
    repo_dir = f"{BASE_DIR}/{repo_name}"

    # Create directory structure
    os.makedirs(f"{repo_dir}/caddy", exist_ok=True)
    os.makedirs(f"{repo_dir}/authentik", exist_ok=True)

    # Generate files
    with open(f"{repo_dir}/docker-compose.yml", "w") as f:
        f.write(gen_docker_compose(m))

    with open(f"{repo_dir}/caddy/Caddyfile", "w") as f:
        f.write(gen_caddy_config(m))

    with open(f"{repo_dir}/authentik/config.yaml", "w") as f:
        f.write(gen_authentik_config(m))

    with open(f"{repo_dir}/README.md", "w") as f:
        f.write(gen_readme(m))

    with open(f"{repo_dir}/.env.example", "w") as f:
        f.write(gen_env_example(m))

    # Create GitHub repo
    print(f"  Creating GitHub repo...")
    create_github_repo(repo_name, m["desc"])
    time.sleep(0.5)  # Rate limit

    # Git init and push
    os.chdir(repo_dir)
    subprocess.run(["git", "init"], capture_output=True)
    subprocess.run(["git", "add", "."], capture_output=True)
    subprocess.run(["git", "commit", "-m", f"Initial commit: {m['name']} module with SSO"], capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], capture_output=True)
    subprocess.run(["git", "remote", "add", "origin",
                    f"https://{GH_USER}:{GH_TOKEN}@github.com/{GH_USER}/{repo_name}.git"], capture_output=True)
    result = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True)

    return result.returncode == 0


def main():
    os.makedirs(BASE_DIR, exist_ok=True)

    success = 0
    failed = 0

    for i, m in enumerate(MODULES):
        print(f"[{i+1}/{len(MODULES)}] Creating wopr-{m['id']}...")
        try:
            if create_module_repo(m):
                success += 1
                print(f"  ✓ Done")
            else:
                failed += 1
                print(f"  ✗ Push failed")
        except Exception as e:
            failed += 1
            print(f"  ✗ Error: {e}")

        time.sleep(0.3)  # Rate limit

    print(f"\nComplete: {success} succeeded, {failed} failed")


if __name__ == "__main__":
    main()
