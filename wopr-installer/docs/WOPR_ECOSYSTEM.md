# WOPR Sovereign Systems — Ecosystem Overview

## What Is WOPR?

WOPR (World Operations Platform & Registry) is a **self-hosted software-as-a-service platform** that provisions fully managed, privacy-first application stacks on dedicated VPS instances called **Beacons**. Each Beacon runs a curated bundle of open-source applications — all pre-configured with single sign-on, automatic HTTPS, backups, and monitoring — giving users a complete replacement for Big Tech services (Google Workspace, Slack, Dropbox, etc.) that they fully own and control.

The entire system is designed around a **one-click purchase-to-provision flow**: a customer picks a bundle on the website, pays via Stripe, and the WOPR Orchestrator automatically spins up a VPS, installs everything, configures DNS, and sends them a welcome email with credentials.

---

## Architecture

```
                        ┌──────────────────────────────┐
                        │     wopr.systems (website)     │
                        │    Stripe Checkout / Landing   │
                        └──────────────┬───────────────┘
                                       │ Stripe webhook
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │         WOPR ORCHESTRATOR                │
                  │         (orc.wopr.systems)               │
                  │                                         │
                  │  FastAPI control plane on 157.180.78.176│
                  │                                         │
                  │  • Stripe billing & dunning              │
                  │  • VPS provisioning (5 providers)        │
                  │  • Cloudflare DNS automation             │
                  │  • Beacon health monitoring              │
                  │  • Email (Mailgun) & PDF generation      │
                  │  • User dashboard API                    │
                  │  • PostgreSQL state persistence          │
                  └────┬────────┬────────┬────────┬────────┘
                       │        │        │        │
              Hetzner  DigitalOcean  Linode  OVHcloud  UpCloud
                  │        │         │       │         │
                  ▼        ▼         ▼       ▼         ▼
              ┌──────────────────────────────────────────┐
              │            BEACONS (customer VPS)         │
              │                                          │
              │  beacon1.wopr.systems  (Hetzner CX22)    │
              │  beacon2.wopr.systems  (DO Droplet)      │
              │  beacon3.wopr.systems  (Linode)          │
              │  ...                                     │
              │                                          │
              │  Each runs:                              │
              │  • Authentik (SSO)                       │
              │  • Caddy (reverse proxy + HTTPS)         │
              │  • PostgreSQL + Redis                    │
              │  • Bundle-specific apps                  │
              │  • WOPR Dashboard                        │
              └──────────────────────────────────────────┘
```

**Key distinction:** The Orchestrator is the **mothership** — it manages billing, provisioning, and monitoring from a single server. Beacons are the **children** — dedicated VPS instances running the actual apps for each customer.

---

## Provisioning Flow (9-State Machine)

```
PENDING → PAYMENT_RECEIVED → PROVISIONING_VPS → WAITING_FOR_VPS
    → CONFIGURING_DNS → DEPLOYING_WOPR → GENERATING_DOCS
    → SENDING_WELCOME → COMPLETED
                                          (or FAILED at any step)
```

1. Customer completes Stripe checkout
2. Stripe fires `checkout.session.completed` webhook to Orchestrator
3. Orchestrator creates provisioning job in PostgreSQL
4. Provider auto-selected via weighted round-robin (40% Hetzner, 20% DO, 20% Linode, 10% OVH, 10% UpCloud)
5. VPS created via provider API
6. Cloud-init bootstraps the beacon with WOPR installer
7. DNS records created in Cloudflare (`beacon.wopr.systems` + wildcard)
8. Health polling waits for beacon to come online
9. PDF documentation generated with credentials
10. Welcome email sent via Mailgun with PDF attached

---

## The Product Line

### 7 Sovereign Suites

Full-stack bundles designed for specific use cases. Each includes core infrastructure (Authentik SSO, Caddy, PostgreSQL, Redis) plus curated apps.

| Suite | Tagline | Module Count | T1 Price | T2 Price | T3 Price |
|-------|---------|:------------:|:--------:|:--------:|:--------:|
| **Starter** | Drive, calendar, notes, tasks, passwords — the essentials to ditch Big Tech | 6 | $29.99 | $45.99 | $65.99 |
| **Creator** | Blog, portfolio, online store, newsletter — monetize your work | 9 | $55.99 | $79.99 | $119.99 |
| **Developer** | Git hosting, CI/CD, code editor, Reactor AI coding assistant | 12 | $55.99 | $79.99 | $119.99 |
| **Professional** | Creator + Developer combined + DEFCON ONE security gateway | 22 | $99.99 | $149.99 | $199.99 |
| **Family** | 6 user accounts, shared photos, shared passwords, family calendar | 8 | $55.99 | $79.99 | $119.99 |
| **Small Business** | CRM, team chat, office suite, DEFCON ONE + Reactor AI | 21 | $129.99 | $179.99 | $249.99 |
| **Enterprise** | Unlimited users, custom integrations, dedicated support, full AI suite | 44 | $249.99 | $349.99 | Custom |

> **Ollama AI addon**: Local LLM runtime available as an opt-in addon at **$14.99/mo** for T2+ tiers (requires 8GB+ RAM). Not included in default bundles.

### 17 Micro-Bundles

Focused, affordable bundles targeting specific professions or needs.

| Micro-Bundle | Tagline | Modules | VPS Tier | T1 Price | T2 Price | T3 Price |
|-------------|---------|:-------:|:--------:|:--------:|:--------:|:--------:|
| **Personal Productivity** | De-Google your life | 5 | MEDIUM (4GB) | $29.99 | $45.99 | $65.99 |
| **Meeting Room** | Replace Zoom | 4 | MEDIUM (4GB) | $29.99 | $45.99 | $65.99 |
| **Privacy Pack** | Total privacy | 4 | MEDIUM (4GB) | $29.99 | $45.99 | $65.99 |
| **Writer's Studio** | Replace Substack | 5 | MEDIUM (4GB) | $29.99 | $45.99 | $65.99 |
| **Podcaster Pack** | Own your feed | 5 | MEDIUM (4GB) | $35.99 | $55.99 | $79.99 |
| **Freelancer Essentials** | Run your business | 5 | MEDIUM (4GB) | $35.99 | $55.99 | $79.99 |
| **Contractor Pro** | Digital contracts + project management | 5 | MEDIUM (4GB) | $35.99 | $55.99 | $79.99 |
| **Musician Bundle** | Own your music | 5 | MEDIUM (4GB) | $35.99 | $55.99 | $79.99 |
| **Bookkeeper Bundle** | Document scanner + client portal | 5 | MEDIUM (4GB) | $35.99 | $55.99 | $79.99 |
| **Artist Storefront** | Replace Etsy | 4 | HIGH (8GB) | $45.99 | $65.99 | $95.99 |
| **Family Hub** | Shared family cloud | 4 | HIGH (8GB) | $45.99 | $65.99 | $95.99 |
| **Video Creator** | Replace YouTube | 5 | HIGH (8GB) | $45.99 | $65.99 | $95.99 |
| **Real Estate Agent** | Lead CRM + listings | 5 | HIGH (8GB) | $45.99 | $65.99 | $95.99 |
| **Educator Suite** | Virtual classroom | 5 | HIGH (8GB) | $45.99 | $65.99 | $95.99 |
| **Photographer Pro** | Client galleries + portfolio | 5 | HIGH (8GB) | $55.99 | $79.99 | $119.99 |
| **Therapist/Coach** | HIPAA-ready sessions | 5 | HIGH (8GB) | $55.99 | $79.99 | $119.99 |
| **Legal Lite** | Document management + e-signatures | 6 | HIGH (8GB) | $55.99 | $79.99 | $119.99 |

---

## Storage Tiers

| Tier | Storage | RAM | Max Users | Backup Retention |
|:----:|:-------:|:---:|:---------:|:----------------:|
| T1 | 50 GB | 4 GB | 5 | 7 days |
| T2 | 200 GB | 8 GB | 25 | 30 days |
| T3 | 500 GB+ | 16 GB | 100 | 90 days |

---

## Module Catalog (76+ Modules, 9 Categories)

### Core (4) — Always installed on every Beacon
| Module | Purpose | RAM | Replaces |
|--------|---------|:---:|---------|
| authentik | SSO & identity management | 1 GB | Okta, Auth0 |
| caddy | Automatic HTTPS reverse proxy | 128 MB | Nginx, Apache |
| postgresql | Primary database | 512 MB | AWS RDS |
| redis | Cache & message broker | 256 MB | ElastiCache |

### Productivity (13)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| nextcloud | Files, calendar, contacts | included | Google Drive, Dropbox |
| collabora | Online office suite | $5.99/mo | Google Docs, Office 365 |
| outline | Team wiki | $4.99/mo | Notion, Confluence |
| paperless-ngx | Document management + OCR | $4.99/mo | Evernote, Adobe Scan |
| bookstack | Wiki & documentation | $2.99/mo | GitBook |
| affine | Knowledge base | $4.99/mo | Notion, Coda |
| linkwarden | Bookmark manager | included | Pocket, Raindrop |
| standardnotes | Encrypted notes | included | Apple Notes |
| calcom | Appointment scheduling | $4.99/mo | Calendly |
| hedgedoc | Collaborative markdown | included | HackMD |
| stirling-pdf | PDF tools suite | included | Adobe Acrobat |
| docuseal | Document signing | $4.99/mo | DocuSign |
| freshrss | RSS feed reader | included | Feedly |

### Security (6)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| vaultwarden | Password manager (Bitwarden-compatible) | included | 1Password, LastPass |
| netbird | WireGuard mesh VPN | $4.99/mo | Tailscale |
| crowdsec | Collaborative IDS | included | Fail2ban |
| wg-easy | Simple WireGuard VPN | included | NordVPN |
| adguard | Ad & tracker blocking | included | Pi-hole |
| passbolt | Team password manager | $4.99/mo | 1Password Teams |

### Communication (8)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| matrix-synapse | Decentralized chat server | $4.99/mo | Slack, Teams |
| element | Matrix chat client | included | Slack app |
| jitsi | Video conferencing | $9.99/mo | Zoom, Google Meet |
| mattermost | Team chat | $4.99/mo | Slack |
| mailcow | Complete email server | $9.99/mo | Gmail, Outlook |
| listmonk | Newsletter manager | $2.99/mo | Mailchimp |
| ntfy | Push notifications | included | Pushover |
| mumble | Voice chat | included | Discord |

### Developer (14)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| forgejo | Git repository hosting | $4.99/mo | GitHub, GitLab |
| woodpecker | CI/CD pipelines | $4.99/mo | GitHub Actions |
| ollama | Local LLM runtime | **$14.99/mo addon** | OpenAI API |
| reactor | AI code assistant + DEFCON ONE | $9.99/mo | GitHub Copilot, Cursor |
| defcon-one | Protected actions gateway | $4.99/mo | Custom approval flows |
| code-server | Browser-based VS Code | $4.99/mo | Codespaces |
| portainer | Docker management UI | included | Docker Desktop |
| registry | Private container registry | included | Docker Hub |
| langfuse | LLM observability | $4.99/mo | LangSmith |
| openwebui | ChatGPT-style LLM UI | included | ChatGPT |
| n8n | Workflow automation | $4.99/mo | Zapier, Make |
| nocodb | Airtable alternative | $4.99/mo | Airtable |
| plane | Project management | $4.99/mo | Jira, Linear |
| gitea-runner | CI/CD runner | included | GH Actions runners |

### Creator (10)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| ghost | Professional blog | $4.99/mo | Medium, Substack |
| saleor | E-commerce platform | $9.99/mo | Shopify |
| peertube | Video hosting | $9.99/mo | YouTube |
| pixelfed | Photo sharing | $4.99/mo | Instagram |
| writefreely | Minimalist blogging | included | Medium |
| funkwhale | Music streaming | $4.99/mo | SoundCloud |
| castopod | Podcast hosting | $4.99/mo | Anchor |
| mastodon | Decentralized social | $4.99/mo | Twitter/X |
| gotosocial | Lightweight ActivityPub | included | Twitter/X |
| lemmy | Reddit alternative | $4.99/mo | Reddit |

### Business (10)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| espocrm | CRM system | $4.99/mo | Salesforce |
| kimai | Time tracking | $2.99/mo | Toggl, Harvest |
| invoiceninja | Invoicing | $4.99/mo | FreshBooks |
| erpnext | Full ERP suite | $19.99/mo | SAP, NetSuite |
| dolibarr | ERP/CRM for SMBs | $4.99/mo | QuickBooks |
| odoo | Business suite | $14.99/mo | Zoho One |
| twenty | Modern CRM | $4.99/mo | HubSpot |
| akaunting | Accounting | $2.99/mo | QuickBooks, Xero |
| documenso | Document signing | $4.99/mo | DocuSign |
| chatwoot | Customer support | $4.99/mo | Intercom, Zendesk |

### Media (8)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| immich | Photo/video backup | $4.99/mo | Google Photos |
| jellyfin | Media server | $4.99/mo | Plex, Netflix |
| audiobookshelf | Audiobook server | $2.99/mo | Audible |
| navidrome | Music streaming | included | Spotify |
| stash | Media organizer | $2.99/mo | — |
| photoprism | AI photo management | $4.99/mo | Google Photos AI |
| kavita | Ebook/comic library | included | Kindle |
| calibre-web | Ebook library | included | Kindle, Kobo |

### Analytics & Monitoring (8)
| Module | Purpose | Addon Price | Replaces |
|--------|---------|:-----------:|---------|
| plausible | Privacy-first analytics | $4.99/mo | Google Analytics |
| uptime-kuma | Uptime monitoring | included | Pingdom |
| grafana | Metrics dashboards | included | Datadog |
| prometheus | Metrics collection | included | Datadog |
| netdata | Real-time monitoring | included | New Relic |
| umami | Simple analytics | included | Google Analytics |
| healthchecks | Cron job monitoring | included | Cronitor |
| gatus | Service health dashboard | included | StatusPage |

---

## Current Production Infrastructure

### WOPR Main Server (157.180.78.176)
- **38 Docker containers** running
- **Key services**: Authentik SSO, GoToSocial, SonicForge, Mastodon, Matrix, Nextcloud, ELK stack, Lemmy, Saleor, PeerTube, DEFCON ONE, Prometheus, Loki, Grafana
- **WOPR systemd services**: wopr-orchestrator, wopr-main, wopr-web, wopr-deploy-webhook, nedry-honeypot
- **Domains**: auth.wopr.systems, orc.wopr.systems, wopr.systems, nodemin.wopr.systems, powerforthepeople.party, wopr.foundation

### nodez3r0 Server (159.203.138.7)
- **16 Docker containers** running
- **Key services**: BrainJoos, n8n, Matrix, Grafana, Authentik, Reactor, Forgejo
- **Domains**: auth.nodez3r0.com, nodez3r0.com

### Orchestrator Control Plane
- **URL**: orc.wopr.systems (port 8001)
- **Database**: PostgreSQL with 9 tables (users, beacons, provisioning_jobs, subscriptions, trials, payment_failures, schema_migrations, user_themes, beacon_signups)
- **Integrations**: Stripe (billing), Cloudflare (DNS), Mailgun (email), all VPS providers
- **Background services**: Beacon health monitor (5-min polling), structured JSON logging

---

## Module Readiness Gap

### What's Ready (9 modules with deployment scripts)
authentik, caddy, postgresql, redis, nextcloud, vaultwarden, freshrss, reactor_ai, dashboard

### What's Catalog-Only (67 modules)
These are defined in the module registry with metadata (name, description, resource requirements, pricing) but **lack actual deployment automation** (no shell scripts, no verified docker-compose repos). The `ModuleDeployer` service exists and expects a GitHub repo per module at `vault.wopr.systems/wopr/{module-name}` with a `docker-compose.yml`, but the repos haven't been verified/populated for most modules.

### What's Needed
1. **Docker Compose files** for all 67 remaining modules
2. **Authentik SSO integration configs** per module (OIDC/SAML/proxy auth)
3. **Caddy reverse proxy snippets** per module
4. **Deploy/destroy scripts** per module
5. **Verification** that `create_module_repos.py` actually populated Forgejo repos

---

## VPS Provider Status

| Provider | SDK | Weight | Status | Token Configured |
|----------|-----|:------:|--------|:----------------:|
| Hetzner | hcloud (native) | 40% | Verified | Yes |
| DigitalOcean | Apache Libcloud | 20% | Verified | Yes |
| Linode (Akamai) | Apache Libcloud | 20% | Code complete, untested | **No — needs API token** |
| OVHcloud | Apache Libcloud (OpenStack) | 10% | Code complete, untested | **No — needs API keys** |
| UpCloud | REST API (httpx) | 10% | Code complete, untested | **No — needs credentials** |

**Provider selection**: Weighted round-robin distributes new beacons across providers automatically. Hetzner gets 40% of traffic due to best price/performance ratio. Weights are defined in `plan_registry.py:PROVIDER_WEIGHTS` and the counter is persisted in the `wopr_state` DB table.

**Why not Vultr?** Vultr's TOS grants them a "perpetual, irrevocable, royalty-free" license to all content hosted on their infrastructure. Dropped in favor of providers with clean data ownership terms.

---

## Why WOPR Exists

The average person uses 15-20 cloud services (Gmail, Google Drive, Dropbox, Slack, Zoom, 1Password, Notion, etc.), paying $50-200/month in subscriptions while surrendering their data to corporations that monetize it through advertising and surveillance.

WOPR replaces all of these with **self-hosted, privacy-first alternatives** running on a dedicated server the customer controls. The Orchestrator makes this accessible to non-technical users through one-click provisioning — no command line, no Docker knowledge, no server administration required.

**For customers**: One subscription, one server, all their apps, their data stays theirs.
**For WOPR**: Recurring SaaS revenue with low marginal cost per customer (VPS hosting is the primary COGS).

---

## VPS Provider API Token Setup

### Hetzner (already configured)

1. Log in at **console.hetzner.cloud**
2. Select your project (or create one)
3. Go to **Security** → **API Tokens** in the left sidebar
4. Click **Generate API Token**, give it a name, select **Read & Write**
5. Copy the token (shown only once)
6. Add to orchestrator config:
   ```
   HETZNER_API_TOKEN=<your-token>
   ```

### DigitalOcean (already configured)

1. Log in at **cloud.digitalocean.com**
2. Go to **API** in the left sidebar (or visit cloud.digitalocean.com/account/api)
3. Under **Personal Access Tokens**, click **Generate New Token**
4. Give it a name, select **Full Access** (read+write) scope
5. Copy the token (shown only once)
6. Add to orchestrator config:
   ```
   DIGITALOCEAN_API_TOKEN=<your-token>
   ```

### Linode (Akamai)

1. Log in at **cloud.linode.com**
2. Click your profile icon (top-right) → **API Tokens**
3. Click **Create a Personal Access Token**
4. Give it a label, set expiry (or no expiry), grant **Read/Write** on: Linodes, Firewalls, StackScripts, IPs
5. Copy the token (shown only once)
6. Add to orchestrator config:
   ```
   LINODE_API_TOKEN=<your-token>
   ```

### OVHcloud

1. Log in at **us.ovhcloud.com** (use the US portal, not EU)
2. Go to your name (top-right) → **My Account** → **My API keys** (or visit `api.us.ovhcloud.com/createToken`)
3. Create an application to get your **Application Key** and **Application Secret**
4. Generate a **Consumer Key** by authorizing the application with these access rules:
   - `GET /cloud/project/*`
   - `POST /cloud/project/*`
   - `DELETE /cloud/project/*`
5. Note your **Project ID** from the Public Cloud dashboard (left sidebar → **Public Cloud** → select project → the ID is in the URL)
6. Add to orchestrator config:
   ```
   OVH_APPLICATION_KEY=<your-app-key>
   OVH_APPLICATION_SECRET=<your-app-secret>
   OVH_CONSUMER_KEY=<your-consumer-key>
   OVH_PROJECT_ID=<your-project-id>
   ```

### UpCloud

1. Create an account at **upcloud.com**
2. Go to **People** in the left sidebar → **Account**
3. Note your **username** (the login username)
4. Your API password is your account password (or create a sub-account with API access for better security)
5. The credential format is `username:password`
6. Add to orchestrator config:
   ```
   UPCLOUD_CREDENTIALS=<username>:<password>
   ```

> **Tip**: For production, create a dedicated sub-account in UpCloud with only server management permissions rather than using your main account credentials.

### Where to put the tokens

SSH into the WOPR server and edit the config:
```bash
ssh root@157.180.78.176
nano /opt/wopr/orchestrator/config.env
```

The full set of provider env vars:

```bash
HETZNER_API_TOKEN=<already set>
DIGITALOCEAN_API_TOKEN=<already set>
LINODE_API_TOKEN=<your-token>
OVH_APPLICATION_KEY=<your-app-key>
OVH_APPLICATION_SECRET=<your-app-secret>
OVH_CONSUMER_KEY=<your-consumer-key>
OVH_PROJECT_ID=<your-project-id>
UPCLOUD_CREDENTIALS=<username>:<password>
```

After adding tokens, run the migration and restart:
```bash
python /opt/wopr/orchestrator/scripts/migrate.py
systemctl restart wopr-orchestrator
```

---

## Key Contacts & Credentials Reference

| Service | Endpoint |
|---------|----------|
| Orchestrator API | orc.wopr.systems |
| WOPR Authentik | auth.wopr.systems |
| nodez3r0 Authentik | auth.nodez3r0.com |
| Forgejo (code) | vault.wopr.systems |
| Stripe Dashboard | dashboard.stripe.com |
| Cloudflare DNS | dash.cloudflare.com |
| Mailgun | app.mailgun.com |
| Orchestrator Config | `/opt/wopr/orchestrator/config.env` on 157.180.78.176 |
