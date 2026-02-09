#!/bin/bash
#=================================================
# WOPR MODULE REGISTRY
# Version: 2.1
# Purpose: Container image, port, subdomain, OIDC config,
#          and env config for every module in the WOPR ecosystem.
#
# This file is sourced by wopr_install.sh.
# It provides:
#   registry_get_image <module_id>     -> container image
#   registry_get_port <module_id>      -> host port
#   registry_get_subdomain <module_id> -> subdomain prefix
#   registry_get_name <module_id>      -> display name
#   registry_get_deps <module_id>      -> space-separated dependencies
#   registry_get_auth_mode <id>        -> oauth2|proxy|header|none
#   registry_get_oidc_env <id>         -> OIDC env vars for container
#   wopr_deploy_from_registry <id>     -> generic deploy function
#
# License: AGPL-3.0
#=================================================

# -----------------------------------------------
# Registry data format:
#   IMAGE|PORT|SUBDOMAIN|DISPLAY_NAME|DEPS
# -----------------------------------------------

declare -A _WOPR_REGISTRY=(
    # === PRODUCTIVITY ===
    ["nextcloud"]="docker.io/library/nextcloud:stable|8080|files|Nextcloud|postgresql redis"
    ["collabora"]="docker.io/collabora/code:latest|9980|office|Collabora Online|"
    ["outline"]="docker.io/outlinewiki/outline:latest|3000|wiki|Outline Wiki|postgresql redis"
    ["vikunja"]="docker.io/vikunja/vikunja:latest|3456|tasks|Vikunja Tasks|"
    ["bookstack"]="docker.io/linuxserver/bookstack:latest|6875|books|BookStack|postgresql"
    ["hedgedoc"]="quay.io/hedgedoc/hedgedoc:latest|3000|pad|HedgeDoc|postgresql"
    ["affine"]="ghcr.io/toeverything/affine-graphql:stable|3010|affine|AFFiNE|postgresql redis"
    ["nocodb"]="docker.io/nocodb/nocodb:latest|8080|db|NocoDB|postgresql"
    ["stirling-pdf"]="docker.io/frooodle/s-pdf:latest|8080|pdf|Stirling PDF|"
    ["paperless-ngx"]="ghcr.io/paperless-ngx/paperless-ngx:latest|8000|docs|Paperless-ngx|postgresql redis"
    ["wallabag"]="docker.io/wallabag/wallabag:latest|8080|read|Wallabag|postgresql redis"
    ["freshrss"]="docker.io/freshrss/freshrss:latest|8082|rss|FreshRSS|"
    ["linkwarden"]="ghcr.io/linkwarden/linkwarden:latest|3000|links|Linkwarden|postgresql"

    # === SECURITY / PASSWORDS ===
    ["vaultwarden"]="docker.io/vaultwarden/server:latest|8081|vault|Vaultwarden|"
    ["passbolt"]="docker.io/passbolt/passbolt:latest|443|pass|Passbolt|postgresql"

    # === COMMUNICATION ===
    ["mattermost"]="docker.io/mattermost/mattermost-team-edition:latest|8065|chat|Mattermost|postgresql"
    ["matrix-synapse"]="docker.io/matrixdotorg/synapse:latest|8008|matrix|Matrix Synapse|postgresql"
    ["element"]="docker.io/vectorim/element-web:latest|8088|msg|Element Web|"
    ["jitsi"]="docker.io/jitsi/web:stable|8443|meet|Jitsi Meet|"
    ["ntfy"]="docker.io/binwiederhier/ntfy:latest|8092|notify|ntfy|"
    ["mailcow"]="ghcr.io/mailcow/mailcow-dockerized:latest|8443|mail|Mailcow|"
    ["listmonk"]="docker.io/listmonk/listmonk:latest|9000|newsletter|Listmonk|postgresql"
    ["chatwoot"]="docker.io/chatwoot/chatwoot:latest|3000|support|Chatwoot|postgresql redis"

    # === DEVELOPER ===
    ["forgejo"]="codeberg.org/forgejo/forgejo:latest|3000|git|Forgejo Git|postgresql"
    ["woodpecker"]="docker.io/woodpeckerci/woodpecker-server:latest|8000|ci|Woodpecker CI|postgresql"
    ["code-server"]="docker.io/linuxserver/code-server:latest|8443|code|VS Code|"
    ["reactor"]="localhost/wopr-ai-engine:latest|8000|reactor|Reactor AI|ollama"
    ["portainer"]="docker.io/portainer/portainer-ce:latest|9444|containers|Portainer|"
    ["n8n"]="docker.io/n8nio/n8n:latest|5678|auto|n8n Automation|postgresql"
    ["plane"]="docker.io/makeplane/plane-app:latest|3000|projects|Plane PM|postgresql redis"
    ["docker-registry"]="docker.io/library/registry:2|5000|registry|Docker Registry|"

    # === AI ===
    ["openwebui"]="ghcr.io/open-webui/open-webui:main|8080|ai|Open WebUI|"
    ["langfuse"]="docker.io/langfuse/langfuse:latest|3000|langfuse|Langfuse|postgresql"

    # === CREATOR / CMS ===
    ["ghost"]="docker.io/library/ghost:5-alpine|2368|blog|Ghost Blog|"
    ["saleor"]="ghcr.io/saleor/saleor:latest|8000|shop|Saleor Store|postgresql redis"
    ["castopod"]="docker.io/castopod/castopod:latest|8000|podcast|Castopod|"
    ["funkwhale"]="docker.io/funkwhale/all-in-one:latest|5000|music|Funkwhale|postgresql"
    ["peertube"]="docker.io/chocobozzz/peertube:production-bookworm|9000|video|PeerTube|postgresql redis"

    # === BUSINESS ===
    ["espocrm"]="docker.io/espocrm/espocrm:latest|8080|crm|EspoCRM|"
    ["invoiceninja"]="docker.io/invoiceninja/invoiceninja:latest|8080|invoice|Invoice Ninja|"
    ["kimai"]="docker.io/kimai/kimai2:latest|8001|time|Kimai|"
    ["calcom"]="docker.io/calcom/cal.com:latest|3000|schedule|Cal.com|postgresql"
    ["docuseal"]="docker.io/docuseal/docuseal:latest|3000|sign|DocuSeal|postgresql"

    # === MEDIA ===
    ["immich"]="ghcr.io/immich-app/immich-server:release|2283|photos|Immich Photos|postgresql redis"
    ["jellyfin"]="docker.io/jellyfin/jellyfin:latest|8096|media|Jellyfin|"
    ["photoprism"]="docker.io/photoprism/photoprism:latest|2342|gallery|PhotoPrism|"

    # === MONITORING / ANALYTICS ===
    ["plausible"]="ghcr.io/plausible/community-edition:latest|8000|analytics|Plausible|postgresql"
    ["grafana"]="docker.io/grafana/grafana-oss:latest|3000|grafana|Grafana|"
    ["prometheus"]="docker.io/prom/prometheus:latest|9090|prometheus|Prometheus|"
    ["alertmanager"]="docker.io/prom/alertmanager:latest|9093|_internal|Alertmanager|prometheus"
    ["uptime-kuma"]="docker.io/louislam/uptime-kuma:latest|3001|status|Uptime Kuma|"

    # === SECURITY / NETWORK ===
    ["crowdsec"]="docker.io/crowdsecurity/crowdsec:latest|8180|crowdsec|CrowdSec|"
    ["netbird"]="docker.io/netbirdio/management:latest|33073|vpn|NetBird VPN|"
    ["adguard"]="docker.io/adguard/adguardhome:latest|3000|dns|AdGuard Home|"

    # === OPS / CONTROL PLANE ===
    # These are built from source, not pulled from registry
    ["ollama"]="docker.io/ollama/ollama:latest|11434|_internal|Ollama LLM|"
    ["ai-engine"]="localhost/wopr-ai-engine:latest|8000|reactor|Reactor AI Engine|ollama"
    ["defcon-one"]="localhost/wopr-defcon-one:latest|8080|defcon|DEFCON ONE|"
    ["support-client"]="localhost/wopr-support-client:latest|8444|support|Support Client|"
    # NOTE: wopr-admin (staff escalations dashboard) is lighthouse-only, not deployed via installer
    ["deployment-queue"]="localhost/wopr-deployment-queue:latest|0|_internal|Deployment Queue|"

    # === NOTES (encrypted) ===
    ["standardnotes"]="docker.io/standardnotes/server:latest|3000|notes|Standard Notes|postgresql"
)

# -----------------------------------------------
# MASTER PORT ALLOCATION MAP
# -----------------------------------------------
# This is the SINGLE SOURCE OF TRUTH for all port assignments.
# EVERY service MUST be listed here. NO exceptions.
# Before adding a new service, check this list for conflicts!
#
# Port ranges:
#   2000-2999: Media (immich, photoprism, ghost, etc)
#   3000-3999: Web apps (grafana, outline, calcom, etc)
#   5000-5999: Developer tools (registry, n8n)
#   6000-6999: Books/docs (bookstack)
#   8000-8099: Core apps (nextcloud, mattermost, matrix)
#   8080-8099: HTTP apps
#   8100-8199: Automation/security (crowdsec)
#   8200-8299: CI/CD (woodpecker)
#   8300-8399: AI (openwebui)
#   8400-8499: Creator/CMS (saleor, castopod)
#   8500-8599: Business apps (espocrm, invoice, kimai)
#   8600-8699: OPS PLANE (ai-engine, defcon-one)
#   8700-8799: Reserved
#   9000-9099: Identity/monitoring (authentik, prometheus, listmonk)
#   9400-9499: Admin tools (portainer)
#   9900-9999: Office (collabora)
#   11000+: LLM/specialty (ollama)
#   33000+: VPN (netbird)
# -----------------------------------------------

declare -A _WOPR_PORTS=(
    # === CORE INFRASTRUCTURE ===
    ["postgresql"]="5432"
    ["redis"]="6379"
    ["caddy"]="443"
    ["dashboard-api"]="8090"     # WOPR Dashboard backend API

    # === IDENTITY & AUTH (9000-9099) ===
    ["authentik"]="9000"
    ["listmonk"]="9001"
    ["peertube"]="9002"

    # === OPS/CONTROL PLANE (8600-8699) ===
    ["ollama"]="11434"
    ["ai-engine"]="8600"
    ["reactor"]="8600"           # alias for ai-engine
    ["defcon-one"]="8601"
    ["defcon_one"]="8601"        # alias (underscore)
    ["support-client"]="8444"
    ["deployment-queue"]="0"     # no HTTP port (internal daemon)

    # === ADMIN TOOLS (9400-9499) ===
    ["portainer"]="9444"
    ["code-server"]="8444"
    ["code_server"]="8444"       # alias (underscore)

    # === MONITORING (3900-3999, 9090) ===
    ["grafana"]="3900"
    ["prometheus"]="9090"
    ["alertmanager"]="9093"
    ["uptime-kuma"]="3001"
    ["uptime_kuma"]="3001"       # alias (underscore)
    ["crowdsec"]="8180"
    ["plausible"]="8610"         # moved from 8600 to avoid ai-engine conflict

    # === PRODUCTIVITY (8080-8089, 3100-3499) ===
    ["nextcloud"]="8080"
    ["outline"]="3100"
    ["vikunja"]="3456"
    ["bookstack"]="6875"
    ["hedgedoc"]="3200"
    ["affine"]="3010"
    ["nocodb"]="8085"
    ["stirling-pdf"]="8086"
    ["paperless-ngx"]="8087"
    ["wallabag"]="8088"
    ["freshrss"]="8082"
    ["linkwarden"]="3300"

    # === SECURITY / PASSWORDS ===
    ["vaultwarden"]="8081"
    ["passbolt"]="8089"

    # === COMMUNICATION (8065, 8008, 8090-8099, 8443) ===
    ["mattermost"]="8065"
    ["matrix-synapse"]="8008"
    ["matrix"]="8008"            # alias for matrix-synapse
    ["element"]="8090"
    ["jitsi"]="8443"
    ["ntfy"]="8092"
    ["mailcow"]="8093"
    ["chatwoot"]="3400"

    # === DEVELOPER (3500-3699, 5000-5999, 8200-8299) ===
    ["forgejo"]="3500"
    ["woodpecker"]="8200"
    ["n8n"]="5678"
    ["plane"]="3600"
    ["docker-registry"]="5000"

    # === AI (8300-8399, 3700) ===
    ["openwebui"]="8300"
    ["langfuse"]="3700"

    # === CREATOR / CMS (2368, 8400-8499) ===
    ["ghost"]="2368"
    # NO WORDPRESS - security liability, hacker magnet
    ["saleor"]="8400"
    ["castopod"]="8401"
    ["funkwhale"]="8402"

    # === BUSINESS (8500-8599, 3800-3899) ===
    ["espocrm"]="8500"
    ["invoiceninja"]="8501"
    ["kimai"]="8502"
    ["calcom"]="3800"
    ["docuseal"]="3801"

    # === MEDIA (2283, 2342, 8096) ===
    ["immich"]="2283"
    ["jellyfin"]="8096"
    ["photoprism"]="2342"

    # === OFFICE (9980) ===
    ["collabora"]="9980"

    # === NETWORK / VPN (33000+) ===
    ["netbird"]="33073"
    ["adguard"]="3002"

    # === NOTES ===
    ["standardnotes"]="3003"
)

# -----------------------------------------------
# Auth mode per app: oauth2|proxy|header|none
# Determines how Authentik protects each app
# -----------------------------------------------

declare -A _WOPR_AUTH_MODE=(
    # OAuth2/OIDC (app handles auth natively)
    ["nextcloud"]="oauth2"
    ["outline"]="oauth2"
    ["vikunja"]="oauth2"
    ["linkwarden"]="oauth2"
    ["bookstack"]="oauth2"
    ["hedgedoc"]="oauth2"
    ["affine"]="oauth2"
    ["nocodb"]="oauth2"
    ["paperless-ngx"]="oauth2"
    ["forgejo"]="oauth2"
    ["woodpecker"]="oauth2"
    ["reactor"]="oauth2"
    ["ghost"]="oauth2"
    ["saleor"]="oauth2"
    ["immich"]="oauth2"
    ["jellyfin"]="oauth2"
    ["peertube"]="oauth2"
    ["grafana"]="oauth2"
    ["mattermost"]="oauth2"
    ["matrix-synapse"]="oauth2"
    ["plausible"]="oauth2"
    ["calcom"]="oauth2"
    ["docuseal"]="oauth2"
    ["invoiceninja"]="oauth2"
    ["langfuse"]="oauth2"
    ["chatwoot"]="oauth2"
    ["plane"]="oauth2"
    ["n8n"]="oauth2"
    ["defcon-one"]="oauth2"
    ["standardnotes"]="oauth2"
    ["funkwhale"]="oauth2"
    ["castopod"]="oauth2"
    ["photoprism"]="oauth2"
    ["wallabag"]="oauth2"
    ["passbolt"]="oauth2"

    # Proxy (Authentik forward auth via Caddy)
    ["vaultwarden"]="proxy"
    ["freshrss"]="proxy"
    ["code-server"]="proxy"
    ["jitsi"]="proxy"
    ["listmonk"]="proxy"
    ["portainer"]="proxy"
    ["uptime-kuma"]="proxy"
    ["kimai"]="proxy"
    ["espocrm"]="proxy"
    ["openwebui"]="proxy"
    ["adguard"]="proxy"

    # Header (X-Authentik-* headers passed through)
    ["ntfy"]="header"

    # None (no SSO needed)
    ["collabora"]="none"
    ["element"]="none"
    ["stirling-pdf"]="none"
    ["prometheus"]="none"
    ["crowdsec"]="none"
    ["netbird"]="none"
    ["docker-registry"]="none"
    ["mailcow"]="none"
)

# -----------------------------------------------
# Per-app command overrides
# Some containers need a specific command/entrypoint
# -----------------------------------------------

declare -A _WOPR_APP_COMMAND=(
    ["ntfy"]="serve --listen-http :8092"
    ["crowdsec"]=""
)

# -----------------------------------------------
# Per-app volume overrides
# Default is -v $data_dir:/data:Z
# Override with custom mount paths
# -----------------------------------------------

declare -A _WOPR_APP_VOLUMES=(
    ["crowdsec"]="-v {data_dir}/data:/var/lib/crowdsec/data:Z -v {data_dir}/config:/etc/crowdsec:Z"
    ["portainer"]="-v {data_dir}:/data:Z -v /run/podman/podman.sock:/var/run/docker.sock:ro"
)

# -----------------------------------------------
# Per-app DB env var overrides
# Some apps need specific env var names for DB connection
# Placeholders: {db_name} {db_pass} {db_host}
# -----------------------------------------------

declare -A _WOPR_DB_ENV=(
    ["mattermost"]="MM_SQLSETTINGS_DRIVERNAME=postgres MM_SQLSETTINGS_DATASOURCE=postgres://{db_name}:{db_pass}@{db_host}:5432/{db_name}?sslmode=disable&connect_timeout=10"
    ["outline"]="DATABASE_URL=postgres://{db_name}:{db_pass}@{db_host}:5432/{db_name}?sslmode=disable SECRET_KEY={admin_secret} UTILS_SECRET={admin_secret}"
)

# -----------------------------------------------
# Per-app OIDC environment variable mappings
#
# Each app has its own env var names for OIDC.
# This map tells the deployer what env vars to set.
# Format: space-separated KEY=VALUE_TEMPLATE pairs
# Placeholders: {client_id} {client_secret} {issuer} {auth_url} {token_url} {userinfo_url} {redirect_uri} {domain}
# -----------------------------------------------

declare -A _WOPR_OIDC_ENV=(
    ["outline"]="OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret} OIDC_AUTH_URI={auth_url} OIDC_TOKEN_URI={token_url} OIDC_USERINFO_URI={userinfo_url} OIDC_DISPLAY_NAME=WOPR OIDC_SCOPES=openid,profile,email"
    ["vikunja"]="VIKUNJA_AUTH_OPENID_ENABLED=true VIKUNJA_AUTH_OPENID_REDIRECTURL=https://tasks.{domain}/auth/openid/authentik VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHENTIK_NAME=WOPR VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHENTIK_AUTHURL={auth_url} VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHENTIK_CLIENTID={client_id} VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHENTIK_CLIENTSECRET={client_secret}"
    ["linkwarden"]="NEXT_PUBLIC_AUTHENTIK_ENABLED=true AUTHENTIK_ISSUER={issuer} AUTHENTIK_CLIENT_ID={client_id} AUTHENTIK_CLIENT_SECRET={client_secret}"
    ["bookstack"]="AUTH_METHOD=oidc OIDC_NAME=WOPR OIDC_DISPLAY_NAME_CLAIMS=name OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret} OIDC_ISSUER={issuer} OIDC_ISSUER_DISCOVER=true"
    ["hedgedoc"]="CMD_OAUTH2_PROVIDERNAME=WOPR CMD_OAUTH2_CLIENT_ID={client_id} CMD_OAUTH2_CLIENT_SECRET={client_secret} CMD_OAUTH2_AUTHORIZATION_URL={auth_url} CMD_OAUTH2_TOKEN_URL={token_url} CMD_OAUTH2_USER_PROFILE_URL={userinfo_url} CMD_OAUTH2_SCOPE=openid,profile,email CMD_OAUTH2_USER_PROFILE_USERNAME_ATTR=preferred_username CMD_OAUTH2_USER_PROFILE_DISPLAY_NAME_ATTR=name CMD_OAUTH2_USER_PROFILE_EMAIL_ATTR=email"
    ["affine"]="OAUTH_PROVIDER_NAME=WOPR OAUTH_CLIENT_ID={client_id} OAUTH_CLIENT_SECRET={client_secret} OAUTH_AUTHORIZATION_URL={auth_url} OAUTH_TOKEN_URL={token_url} OAUTH_USERINFO_URL={userinfo_url}"
    ["nocodb"]="NC_OIDC_ISSUER={issuer} NC_OIDC_CLIENT_ID={client_id} NC_OIDC_CLIENT_SECRET={client_secret} NC_OIDC_AUTHORIZATION_URL={auth_url} NC_OIDC_TOKEN_URL={token_url} NC_OIDC_USERINFO_URL={userinfo_url}"
    ["paperless-ngx"]="PAPERLESS_SOCIALACCOUNT_PROVIDERS={\"openid_connect\":{\"APPS\":[{\"provider_id\":\"authentik\",\"name\":\"WOPR\",\"client_id\":\"{client_id}\",\"secret\":\"{client_secret}\",\"settings\":{\"server_url\":\"{issuer}\"}}]}}"
    ["forgejo"]="FORGEJO__oauth2__ENABLED=true FORGEJO__oauth2_client__OPENID_CONNECT_SCOPES=openid,profile,email"
    ["woodpecker"]="WOODPECKER_AUTHENTIK=true WOODPECKER_AUTHENTIK_URL=https://auth.{domain} WOODPECKER_AUTHENTIK_CLIENT={client_id} WOODPECKER_AUTHENTIK_SECRET={client_secret}"
    ["reactor"]="AUTHENTIK_ENABLED=true AUTHENTIK_ISSUER={issuer} AUTHENTIK_CLIENT_ID={client_id} AUTHENTIK_CLIENT_SECRET={client_secret}"
    ["ghost"]="oauth__name=WOPR oauth__clientId={client_id} oauth__clientSecret={client_secret} oauth__authorizeUrl={auth_url} oauth__tokenUrl={token_url} oauth__userinfoUrl={userinfo_url}"
    ["saleor"]="OIDC_ENABLE=True OIDC_URL={issuer} OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret}"
    ["immich"]="OAUTH_ENABLED=true OAUTH_ISSUER_URL={issuer} OAUTH_CLIENT_ID={client_id} OAUTH_CLIENT_SECRET={client_secret} OAUTH_SCOPE=openid,profile,email OAUTH_AUTO_REGISTER=true OAUTH_BUTTON_TEXT=Login_with_WOPR"
    ["jellyfin"]="JELLYFIN_OIDC_ENABLED=true JELLYFIN_OIDC_PROVIDER_NAME=WOPR JELLYFIN_OIDC_CLIENT_ID={client_id} JELLYFIN_OIDC_CLIENT_SECRET={client_secret} JELLYFIN_OIDC_AUTHORITY={issuer}"
    ["peertube"]="PEERTUBE_AUTH_OIDC_ENABLED=true PEERTUBE_AUTH_OIDC_DISPLAY_NAME=WOPR PEERTUBE_AUTH_OIDC_DISCOVERY_URL={issuer}/.well-known/openid-configuration PEERTUBE_AUTH_OIDC_CLIENT_ID={client_id} PEERTUBE_AUTH_OIDC_CLIENT_SECRET={client_secret} PEERTUBE_AUTH_OIDC_SCOPE=openid,profile,email"
    ["grafana"]="GF_AUTH_GENERIC_OAUTH_ENABLED=true GF_AUTH_GENERIC_OAUTH_NAME=WOPR GF_AUTH_GENERIC_OAUTH_CLIENT_ID={client_id} GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET={client_secret} GF_AUTH_GENERIC_OAUTH_SCOPES=openid,profile,email GF_AUTH_GENERIC_OAUTH_AUTH_URL={auth_url} GF_AUTH_GENERIC_OAUTH_TOKEN_URL={token_url} GF_AUTH_GENERIC_OAUTH_API_URL={userinfo_url} GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH=groups GF_AUTH_SIGNOUT_REDIRECT_URL=https://auth.{domain}/application/o/grafana/end-session/"
    ["mattermost"]="MM_GITLABSETTINGS_ENABLE=false MM_OPENIDSETTINGS_ENABLE=true MM_OPENIDSETTINGS_DISCOVERYENDPOINT={issuer}/.well-known/openid-configuration MM_OPENIDSETTINGS_ID={client_id} MM_OPENIDSETTINGS_SECRET={client_secret} MM_OPENIDSETTINGS_BUTTONTEXT=Login_with_WOPR MM_OPENIDSETTINGS_BUTTONCOLOR=#6559C5"
    ["matrix-synapse"]="SYNAPSE_OIDC_ENABLED=true SYNAPSE_OIDC_IDP_NAME=WOPR SYNAPSE_OIDC_ISSUER={issuer} SYNAPSE_OIDC_CLIENT_ID={client_id} SYNAPSE_OIDC_CLIENT_SECRET={client_secret} SYNAPSE_OIDC_SCOPES=openid,profile,email"
    ["plausible"]="GOOGLE_CLIENT_ID= OAUTH_PROVIDER=custom OAUTH_CLIENT_ID={client_id} OAUTH_CLIENT_SECRET={client_secret} OAUTH_AUTHORIZE_URL={auth_url} OAUTH_TOKEN_URL={token_url} OAUTH_USERINFO_URL={userinfo_url}"
    ["calcom"]="OIDC_ISSUER={issuer} OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret}"
    ["docuseal"]="OIDC_ISSUER={issuer} OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret}"
    ["invoiceninja"]="OAUTH_PROVIDER=generic OAUTH_CLIENT_ID={client_id} OAUTH_CLIENT_SECRET={client_secret} OAUTH_AUTHORIZATION_URL={auth_url} OAUTH_TOKEN_URL={token_url} OAUTH_USER_URL={userinfo_url}"
    ["langfuse"]="AUTH_CUSTOM_CLIENT_ID={client_id} AUTH_CUSTOM_CLIENT_SECRET={client_secret} AUTH_CUSTOM_ISSUER={issuer} AUTH_CUSTOM_NAME=WOPR"
    ["chatwoot"]="OPENID_CONNECT_ENABLED=true OPENID_CONNECT_PROVIDER_NAME=WOPR OPENID_CONNECT_CLIENT_ID={client_id} OPENID_CONNECT_CLIENT_SECRET={client_secret} OPENID_CONNECT_DISCOVERY_URL={issuer}/.well-known/openid-configuration"
    ["plane"]="OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret} OIDC_ISSUER={issuer}"
    ["n8n"]="N8N_AUTH_OIDC_ENABLED=true N8N_AUTH_OIDC_CLIENT_ID={client_id} N8N_AUTH_OIDC_CLIENT_SECRET={client_secret} N8N_AUTH_OIDC_ISSUER={issuer} N8N_AUTH_OIDC_DISPLAY_NAME=WOPR"
    ["defcon-one"]="AUTHENTIK_ENABLED=true AUTHENTIK_ISSUER={issuer} AUTHENTIK_CLIENT_ID={client_id} AUTHENTIK_CLIENT_SECRET={client_secret}"
    ["standardnotes"]="AUTH_JWT_SECRET={client_secret} OIDC_ENABLED=true OIDC_ISSUER={issuer} OIDC_CLIENT_ID={client_id} OIDC_CLIENT_SECRET={client_secret}"
    ["funkwhale"]="FUNKWHALE_OIDC_ENABLED=true FUNKWHALE_OIDC_PROVIDER_NAME=WOPR FUNKWHALE_OIDC_CLIENT_ID={client_id} FUNKWHALE_OIDC_CLIENT_SECRET={client_secret} FUNKWHALE_OIDC_SERVER_URL={issuer}"
    ["castopod"]="AUTH_OIDC_ACTIVE=1 AUTH_OIDC_CLIENT_ID={client_id} AUTH_OIDC_CLIENT_SECRET={client_secret} AUTH_OIDC_DISCOVERY_URL={issuer}/.well-known/openid-configuration"
    ["photoprism"]="PHOTOPRISM_OIDC_ENABLED=true PHOTOPRISM_OIDC_ISSUER={issuer} PHOTOPRISM_OIDC_CLIENT={client_id} PHOTOPRISM_OIDC_SECRET={client_secret}"
    ["wallabag"]="SYMFONY__ENV__OAUTH_ENABLED=true SYMFONY__ENV__OAUTH_CLIENT_ID={client_id} SYMFONY__ENV__OAUTH_CLIENT_SECRET={client_secret} SYMFONY__ENV__OAUTH_AUTHORIZE_URL={auth_url} SYMFONY__ENV__OAUTH_ACCESS_TOKEN_URL={token_url} SYMFONY__ENV__OAUTH_RESOURCE_OWNER_URL={userinfo_url}"
    ["passbolt"]="PASSBOLT_PLUGINS_SSO_ENABLED=true PASSBOLT_SECURITY_SSO_OPENID_CLIENT_ID={client_id} PASSBOLT_SECURITY_SSO_OPENID_CLIENT_SECRET={client_secret} PASSBOLT_SECURITY_SSO_OPENID_PROVIDER_URL={issuer}"
)

# -----------------------------------------------
# Accessor functions
# -----------------------------------------------

_registry_field() {
    local module_id="$1"
    local field_idx="$2"
    local entry="${_WOPR_REGISTRY[$module_id]:-}"
    if [ -z "$entry" ]; then
        echo ""
        return 1
    fi
    echo "$entry" | cut -d'|' -f"$field_idx"
}

registry_get_image()     { _registry_field "$1" 1; }
registry_get_port()      { echo "${_WOPR_PORTS[$1]:-$(_registry_field "$1" 2)}"; }
registry_get_subdomain() { _registry_field "$1" 3; }
registry_get_name()      { _registry_field "$1" 4; }
registry_get_deps()      { _registry_field "$1" 5; }
registry_get_auth_mode() { echo "${_WOPR_AUTH_MODE[$1]:-none}"; }
registry_has_module()    { [ -n "${_WOPR_REGISTRY[$1]:-}" ]; }

# -----------------------------------------------
# OIDC CREDENTIAL MANAGEMENT
#
# Creates OAuth2 provider in Authentik for a module
# and returns the client_id + client_secret.
# -----------------------------------------------

_oidc_create_for_module() {
    local module_id="$1"
    local domain=$(wopr_setting_get "domain")
    local subdomain=$(registry_get_subdomain "$module_id")
    local display_name=$(registry_get_name "$module_id")

    local client_id="wopr-${module_id}"
    local client_secret=$(wopr_random_string 64)

    # Store credentials
    wopr_setting_set "oidc_${module_id//-/_}_client_id" "$client_id"
    wopr_setting_set "oidc_${module_id//-/_}_client_secret" "$client_secret"

    # Register with Authentik (creates provider + application)
    if systemctl is-active --quiet "wopr-authentik-server" 2>/dev/null; then
        wopr_authentik_register_app "$display_name" "${module_id//-/_}" "$subdomain" || \
            wopr_log "WARN" "Authentik registration deferred for $module_id"
    fi

    echo "$client_id $client_secret"
}

# Build OIDC env flags for podman
_build_oidc_env_flags() {
    local module_id="$1"
    local auth_mode=$(registry_get_auth_mode "$module_id")

    # Only OAuth2 apps get OIDC env vars
    if [ "$auth_mode" != "oauth2" ]; then
        echo ""
        return
    fi

    local oidc_template="${_WOPR_OIDC_ENV[$module_id]:-}"
    if [ -z "$oidc_template" ]; then
        echo ""
        return
    fi

    local domain=$(wopr_setting_get "domain")
    local client_id=$(wopr_setting_get "oidc_${module_id//-/_}_client_id")
    local client_secret=$(wopr_setting_get "oidc_${module_id//-/_}_client_secret")

    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        # Create credentials if not yet generated
        local creds
        creds=$(_oidc_create_for_module "$module_id")
        client_id=$(echo "$creds" | cut -d' ' -f1)
        client_secret=$(echo "$creds" | cut -d' ' -f2)
    fi

    local issuer="https://auth.${domain}/application/o/${module_id//-/_}"
    local auth_url="https://auth.${domain}/application/o/authorize/"
    local token_url="https://auth.${domain}/application/o/token/"
    local userinfo_url="https://auth.${domain}/application/o/userinfo/"
    local subdomain=$(registry_get_subdomain "$module_id")
    local redirect_uri="https://${subdomain}.${domain}/auth/callback"

    # Replace placeholders in template
    local env_flags=""
    for pair in $oidc_template; do
        local key="${pair%%=*}"
        local val="${pair#*=}"

        val="${val//\{client_id\}/$client_id}"
        val="${val//\{client_secret\}/$client_secret}"
        val="${val//\{issuer\}/$issuer}"
        val="${val//\{auth_url\}/$auth_url}"
        val="${val//\{token_url\}/$token_url}"
        val="${val//\{userinfo_url\}/$userinfo_url}"
        val="${val//\{redirect_uri\}/$redirect_uri}"
        val="${val//\{domain\}/$domain}"

        env_flags="$env_flags -e ${key}=${val}"
    done

    echo "$env_flags"
}

# -----------------------------------------------
# GENERIC DEPLOY FUNCTION
#
# Deploys any module from registry data alone:
# 1. Pull container image
# 2. Create data directories
# 3. Create PostgreSQL DB if needed
# 4. Generate OIDC credentials + env vars
# 5. Create systemd service
# 6. Start and wait for port
# 7. Record installation
# -----------------------------------------------

wopr_deploy_from_registry() {
    local module_id="$1"

    if ! registry_has_module "$module_id"; then
        wopr_log "ERROR" "Module not in registry: $module_id"
        return 1
    fi

    local image=$(registry_get_image "$module_id")
    local port=$(registry_get_port "$module_id")
    local subdomain=$(registry_get_subdomain "$module_id")
    local display_name=$(registry_get_name "$module_id")
    local deps=$(registry_get_deps "$module_id")
    local auth_mode=$(registry_get_auth_mode "$module_id")

    local service_name="wopr-${module_id}"
    local data_dir="${WOPR_DATA_DIR}/${module_id}"
    local domain=$(wopr_setting_get "domain")
    local container_port

    container_port=$(_registry_field "$module_id" 2)

    wopr_log "INFO" "Generic deploy: $display_name ($module_id)"
    wopr_log "INFO" "  Image: $image | Auth: $auth_mode"
    wopr_log "INFO" "  Port:  127.0.0.1:$port -> container:$container_port"
    wopr_log "INFO" "  URL:   https://${subdomain}.${domain}"

    # Check if already running
    if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        wopr_log "INFO" "$display_name is already running"
        wopr_setting_set "module_${module_id//-/_}_installed" "true"
        return 0
    fi

    mkdir -p "$data_dir"

    # Pull image
    wopr_log "INFO" "Pulling $display_name image..."
    if ! wopr_container_pull "$image"; then
        wopr_log "ERROR" "Failed to pull image: $image"
        return 1
    fi

    # Build environment variables
    local env_flags=""

    # Generate admin secret early (needed for DB env var substitutions)
    local admin_secret=$(wopr_random_string 32)
    wopr_setting_set "${module_id//-/_}_admin_secret" "$admin_secret"

    # PostgreSQL
    if echo "$deps" | grep -q "postgresql"; then
        local db_name="${module_id//-/_}"
        local db_pass=$(wopr_random_string 32)
        wopr_setting_set "${module_id//-/_}_db_password" "$db_pass"

        podman exec wopr-postgresql psql -U wopr -c \
            "CREATE DATABASE ${db_name};" 2>/dev/null || true
        podman exec wopr-postgresql psql -U wopr -c \
            "CREATE USER ${db_name} WITH PASSWORD '${db_pass}';" 2>/dev/null || true
        podman exec wopr-postgresql psql -U wopr -c \
            "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_name};" 2>/dev/null || true
        # PG 15+ requires schema grants
        podman exec wopr-postgresql psql -U wopr -d "${db_name}" -c \
            "GRANT ALL ON SCHEMA public TO ${db_name};" 2>/dev/null || true

        # Check for per-app DB env var overrides
        if [ -n "${_WOPR_DB_ENV[$module_id]+x}" ]; then
            local db_env="${_WOPR_DB_ENV[$module_id]}"
            db_env="${db_env//\{db_name\}/${db_name}}"
            db_env="${db_env//\{db_pass\}/${db_pass}}"
            db_env="${db_env//\{db_host\}/wopr-postgresql}"
            db_env="${db_env//\{admin_secret\}/${admin_secret}}"
            for kv in $db_env; do
                env_flags="$env_flags -e $kv"
            done
        fi
        # Always set standard DB env vars as well
        env_flags="$env_flags -e DATABASE_URL=postgresql://${db_name}:${db_pass}@wopr-postgresql:5432/${db_name}"
        env_flags="$env_flags -e POSTGRES_HOST=wopr-postgresql"
        env_flags="$env_flags -e POSTGRES_DB=${db_name}"
        env_flags="$env_flags -e POSTGRES_USER=${db_name}"
        env_flags="$env_flags -e POSTGRES_PASSWORD=${db_pass}"
    fi

    # Redis
    if echo "$deps" | grep -q "redis"; then
        env_flags="$env_flags -e REDIS_URL=redis://wopr-redis:6379"
        env_flags="$env_flags -e REDIS_HOST=wopr-redis"
    fi

    # Common
    env_flags="$env_flags -e BASE_URL=https://${subdomain}.${domain}"
    env_flags="$env_flags -e APP_URL=https://${subdomain}.${domain}"
    env_flags="$env_flags -e SECRET_KEY=${admin_secret}"

    # OIDC env vars (for oauth2 apps)
    local oidc_flags=$(_build_oidc_env_flags "$module_id")
    if [ -n "$oidc_flags" ]; then
        env_flags="$env_flags $oidc_flags"
        wopr_log "INFO" "  OIDC: injected env vars for $auth_mode auth"
    fi

    # Resolve per-app volume overrides
    local volume_flags="-v ${data_dir}:/data:Z"
    if [ -n "${_WOPR_APP_VOLUMES[$module_id]+x}" ]; then
        volume_flags="${_WOPR_APP_VOLUMES[$module_id]}"
        volume_flags="${volume_flags//\{data_dir\}/${data_dir}}"
        # Create any custom directories
        for dir_path in $(echo "$volume_flags" | grep -oP '(?<=-v )[^:]+' ); do
            mkdir -p "$dir_path"
        done
    fi

    # Resolve per-app command overrides
    local app_command=""
    if [ -n "${_WOPR_APP_COMMAND[$module_id]+x}" ]; then
        app_command="${_WOPR_APP_COMMAND[$module_id]}"
    fi

    # Create systemd service
    cat > "/etc/systemd/system/${service_name}.service" <<SVCEOF
[Unit]
Description=WOPR ${display_name}
After=network.target wopr-postgresql.service wopr-redis.service
Wants=wopr-postgresql.service wopr-redis.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${service_name}
ExecStartPre=-/usr/bin/podman rm ${service_name}

ExecStart=/usr/bin/podman run --rm \\
    --name ${service_name} \\
    --network ${WOPR_NETWORK} \\
    ${volume_flags} \\
    ${env_flags} \\
    -p 127.0.0.1:${port}:${container_port} \\
    ${image} ${app_command}

ExecStop=/usr/bin/podman stop -t 10 ${service_name}

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    systemctl enable "$service_name"
    systemctl start "$service_name"

    # Wait for port
    wopr_log "INFO" "Waiting for $display_name on port $port..."
    if wopr_wait_for_port "127.0.0.1" "$port" 120; then
        wopr_log "OK" "$display_name is running on port $port"
    else
        wopr_log "WARN" "$display_name may still be starting (port $port not ready in 120s)"
    fi

    # For proxy-auth apps, add Caddy route with Authentik forward auth
    if [ "$auth_mode" = "proxy" ] || [ "$auth_mode" = "header" ]; then
        wopr_caddy_add_route_with_auth "$subdomain" "$port"
    else
        wopr_caddy_add_route "$subdomain" "$port"
    fi

    # Record installation
    wopr_setting_set "module_${module_id//-/_}_installed" "true"
    wopr_setting_set "${module_id//-/_}_port" "$port"
    wopr_setting_set "${module_id//-/_}_url" "https://${subdomain}.${domain}"

    wopr_log "OK" "$display_name deployed: https://${subdomain}.${domain} (auth=$auth_mode)"
    return 0
}

# -----------------------------------------------
# ALERTING CONFIGURATION
# Sets up Prometheus + Alertmanager + ntfy integration
# Called after monitoring modules are deployed
# -----------------------------------------------

wopr_configure_alerting() {
    wopr_log "INFO" "Configuring alerting stack (Prometheus + Alertmanager + ntfy)..."

    local domain=$(wopr_setting_get "domain")
    local prometheus_dir="${WOPR_DATA_DIR}/prometheus"

    mkdir -p "$prometheus_dir/data"
    chmod 777 "$prometheus_dir/data"

    # Create Alertmanager config with ntfy webhook
    cat > "$prometheus_dir/alertmanager.yml" << 'EOF'
global:
  resolve_timeout: 5m

route:
  receiver: ntfy
  group_wait: 10s
  group_interval: 1m
  repeat_interval: 4h

receivers:
  - name: ntfy
    webhook_configs:
      - url: "http://wopr-ntfy:8092/wopr-alerts"
        send_resolved: true
        http_config:
          follow_redirects: true
EOF

    # Create Prometheus alert rules
    cat > "$prometheus_dir/alert_rules.yml" << 'EOF'
groups:
  - name: wopr_alerts
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is DOWN"
          description: "{{ $labels.instance }} has been down for 30 seconds"

      - alert: HighMemory
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.9
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage (>90%)"

      - alert: HighDisk
        expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Disk usage above 85%"

      - alert: ContainerDown
        expr: absent(container_last_seen{name=~"wopr-.*"}) or (time() - container_last_seen{name=~"wopr-.*"}) > 60
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.name }} is down"
EOF

    # Create Prometheus config
    cat > "$prometheus_dir/prometheus.yml" << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alert_rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["wopr-alertmanager:9093"]

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: caddy
    static_configs:
      - targets: ["wopr-caddy:2019"]
EOF

    # Deploy Alertmanager service
    cat > /etc/systemd/system/wopr-alertmanager.service << 'EOF'
[Unit]
Description=WOPR Alertmanager
After=network.target wopr-prometheus.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-alertmanager
ExecStartPre=-/usr/bin/podman rm wopr-alertmanager

ExecStart=/usr/bin/podman run --rm \
    --name wopr-alertmanager \
    --network wopr-network \
    -v /var/lib/wopr/prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro \
    -p 127.0.0.1:9093:9093 \
    docker.io/prom/alertmanager:latest

ExecStop=/usr/bin/podman stop -t 10 wopr-alertmanager

[Install]
WantedBy=multi-user.target
EOF

    # Update Prometheus service to include alert rules
    cat > /etc/systemd/system/wopr-prometheus.service << 'EOF'
[Unit]
Description=WOPR Prometheus
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-prometheus
ExecStartPre=-/usr/bin/podman rm wopr-prometheus

ExecStart=/usr/bin/podman run --rm \
    --name wopr-prometheus \
    --network wopr-network \
    -v /var/lib/wopr/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
    -v /var/lib/wopr/prometheus/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro \
    -v /var/lib/wopr/prometheus/data:/prometheus:Z \
    -p 127.0.0.1:9090:9090 \
    docker.io/prom/prometheus:latest \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/prometheus

ExecStop=/usr/bin/podman stop -t 10 wopr-prometheus

[Install]
WantedBy=multi-user.target
EOF

    # Pull and start services
    wopr_container_pull "docker.io/prom/alertmanager:latest"

    systemctl daemon-reload
    systemctl enable wopr-alertmanager
    systemctl restart wopr-prometheus
    systemctl start wopr-alertmanager

    # Wait for services
    sleep 5
    if wopr_wait_for_port "127.0.0.1" "9093" 60; then
        wopr_log "OK" "Alertmanager running on port 9093"
    else
        wopr_log "WARN" "Alertmanager may still be starting"
    fi

    # Send test notification to ntfy
    curl -s -X POST "http://127.0.0.1:8092/wopr-alerts" \
        -H "Title: WOPR Alerting Configured" \
        -H "Priority: high" \
        -d "Prometheus + Alertmanager → ntfy pipeline active. You will receive service alerts here." \
        > /dev/null 2>&1 || true

    wopr_setting_set "alerting_configured" "true"
    wopr_log "OK" "Alerting stack configured: Prometheus → Alertmanager → ntfy"
}
