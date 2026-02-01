#!/bin/bash
#=================================================
# WOPR MODULE REGISTRY
# Version: 2.0
# Purpose: Container image, port, subdomain, and env config
#          for every module in the WOPR ecosystem.
#
# This file is sourced by wopr_install.sh.
# It provides:
#   registry_get_image <module_id>     -> container image
#   registry_get_port <module_id>      -> host port
#   registry_get_subdomain <module_id> -> subdomain prefix
#   registry_get_name <module_id>      -> display name
#   registry_get_env <module_id>       -> env var flags for podman
#   registry_get_volumes <module_id>   -> volume mount flags
#   registry_get_deps <module_id>      -> space-separated dependencies
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
    ["reactor"]="docker.io/wopr/reactor:latest|8100|reactor|Reactor AI|postgresql redis"
    ["portainer"]="docker.io/portainer/portainer-ce:latest|9443|containers|Portainer|"
    ["n8n"]="docker.io/n8nio/n8n:latest|5678|auto|n8n Automation|postgresql"
    ["plane"]="makeplane/plane-app:latest|3000|projects|Plane PM|postgresql redis"
    ["docker-registry"]="docker.io/library/registry:2|5000|registry|Docker Registry|"

    # === AI ===
    ["openwebui"]="ghcr.io/open-webui/open-webui:main|8080|ai|Open WebUI|"
    ["langfuse"]="docker.io/langfuse/langfuse:latest|3000|langfuse|Langfuse|postgresql"

    # === CREATOR / CMS ===
    ["ghost"]="docker.io/library/ghost:5-alpine|2368|blog|Ghost Blog|"
    ["saleor"]="ghcr.io/saleor/saleor:latest|8000|shop|Saleor Store|postgresql redis"
    ["castopod"]="docker.io/castopod/castopod:latest|8000|podcast|Castopod|"
    ["funkwhale"]="funkwhale/all-in-one:latest|5000|music|Funkwhale|postgresql"
    ["peertube"]="chocobozzz/peertube:production-bookworm|9000|video|PeerTube|postgresql redis"

    # === BUSINESS ===
    ["espocrm"]="docker.io/espocrm/espocrm:latest|8080|crm|EspoCRM|"
    ["invoiceninja"]="docker.io/invoiceninja/invoiceninja:latest|8080|invoice|Invoice Ninja|"
    ["kimai"]="kimai/kimai2:latest|8001|time|Kimai|"
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
    ["uptime-kuma"]="docker.io/louislam/uptime-kuma:latest|3001|status|Uptime Kuma|"

    # === SECURITY / NETWORK ===
    ["defcon-one"]="docker.io/wopr/defcon-one:latest|8110|defcon|DEFCON ONE|postgresql redis"
    ["crowdsec"]="docker.io/crowdsecurity/crowdsec:latest|8180|crowdsec|CrowdSec|"
    ["netbird"]="netbirdio/management:latest|33073|vpn|NetBird VPN|"
    ["adguard"]="docker.io/adguard/adguardhome:latest|3000|dns|AdGuard Home|"

    # === NOTES (encrypted) ===
    ["standardnotes"]="standardnotes/server:latest|3000|notes|Standard Notes|postgresql"
)

# -----------------------------------------------
# Port allocation map (avoids collisions)
# Each module gets a unique host port.
# -----------------------------------------------

declare -A _WOPR_PORTS=(
    # Infrastructure (fixed)
    ["postgresql"]="5432"
    ["redis"]="6379"
    ["authentik"]="9000"
    ["caddy"]="443"

    # Productivity
    ["nextcloud"]="8080"
    ["collabora"]="9980"
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

    # Security
    ["vaultwarden"]="8081"
    ["passbolt"]="8089"

    # Communication
    ["mattermost"]="8065"
    ["matrix-synapse"]="8008"
    ["element"]="8090"
    ["jitsi"]="8443"
    ["ntfy"]="8092"
    ["mailcow"]="8093"
    ["listmonk"]="9001"
    ["chatwoot"]="3400"

    # Developer
    ["forgejo"]="3500"
    ["woodpecker"]="8200"
    ["code-server"]="8443"
    ["reactor"]="8100"
    ["portainer"]="9443"
    ["n8n"]="5678"
    ["plane"]="3600"
    ["docker-registry"]="5000"

    # AI
    ["openwebui"]="8300"
    ["langfuse"]="3700"

    # Creator
    ["ghost"]="2368"
    ["saleor"]="8400"
    ["castopod"]="8401"
    ["funkwhale"]="8402"
    ["peertube"]="9002"

    # Business
    ["espocrm"]="8500"
    ["invoiceninja"]="8501"
    ["kimai"]="8502"
    ["calcom"]="3800"
    ["docuseal"]="3801"

    # Media
    ["immich"]="2283"
    ["jellyfin"]="8096"
    ["photoprism"]="2342"

    # Monitoring
    ["plausible"]="8600"
    ["grafana"]="3900"
    ["prometheus"]="9090"
    ["uptime-kuma"]="3001"

    # Security/Network
    ["defcon-one"]="8110"
    ["crowdsec"]="8180"
    ["netbird"]="33073"
    ["adguard"]="3002"

    # Notes
    ["standardnotes"]="3003"
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

registry_get_image() {
    _registry_field "$1" 1
}

registry_get_port() {
    # Use the port allocation map (avoids collisions)
    echo "${_WOPR_PORTS[$1]:-$(_registry_field "$1" 2)}"
}

registry_get_subdomain() {
    _registry_field "$1" 3
}

registry_get_name() {
    _registry_field "$1" 4
}

registry_get_deps() {
    _registry_field "$1" 5
}

registry_has_module() {
    [ -n "${_WOPR_REGISTRY[$1]:-}" ]
}

# -----------------------------------------------
# GENERIC DEPLOY FUNCTION
#
# Deploys any module from registry data alone:
# 1. Pull container image
# 2. Create data directories
# 3. Create systemd service
# 4. Start and wait for port
# 5. Record installation
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

    local service_name="wopr-${module_id}"
    local data_dir="${WOPR_DATA_DIR}/${module_id}"
    local domain=$(wopr_setting_get "domain")
    local container_port  # The port inside the container

    # Determine internal container port from the registry image default
    container_port=$(_registry_field "$module_id" 2)

    wopr_log "INFO" "Generic deploy: $display_name ($module_id)"
    wopr_log "INFO" "  Image: $image"
    wopr_log "INFO" "  Port:  127.0.0.1:$port -> container:$container_port"
    wopr_log "INFO" "  URL:   https://${subdomain}.${domain}"

    # Check if already running
    if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        wopr_log "INFO" "$display_name is already running"
        wopr_setting_set "module_${module_id//-/_}_installed" "true"
        return 0
    fi

    # Create data directory
    mkdir -p "$data_dir"

    # Pull image
    wopr_log "INFO" "Pulling $display_name image..."
    if ! wopr_container_pull "$image"; then
        wopr_log "ERROR" "Failed to pull image: $image"
        return 1
    fi

    # Build environment variables
    local env_flags=""

    # If module needs PostgreSQL, create a database and pass credentials
    if echo "$deps" | grep -q "postgresql"; then
        local db_name="${module_id//-/_}"
        local db_pass=$(wopr_random_string 32)
        wopr_setting_set "${module_id//-/_}_db_password" "$db_pass"

        # Create the database (assumes PostgreSQL is running)
        podman exec wopr-postgresql psql -U postgres -c \
            "CREATE DATABASE ${db_name};" 2>/dev/null || true
        podman exec wopr-postgresql psql -U postgres -c \
            "CREATE USER ${db_name} WITH PASSWORD '${db_pass}';" 2>/dev/null || true
        podman exec wopr-postgresql psql -U postgres -c \
            "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_name};" 2>/dev/null || true

        env_flags="$env_flags -e DATABASE_URL=postgresql://${db_name}:${db_pass}@host.containers.internal:5432/${db_name}"
        env_flags="$env_flags -e POSTGRES_HOST=host.containers.internal"
        env_flags="$env_flags -e POSTGRES_DB=${db_name}"
        env_flags="$env_flags -e POSTGRES_USER=${db_name}"
        env_flags="$env_flags -e POSTGRES_PASSWORD=${db_pass}"
    fi

    # If module needs Redis
    if echo "$deps" | grep -q "redis"; then
        env_flags="$env_flags -e REDIS_URL=redis://host.containers.internal:6379"
        env_flags="$env_flags -e REDIS_HOST=host.containers.internal"
    fi

    # Common env vars
    env_flags="$env_flags -e BASE_URL=https://${subdomain}.${domain}"
    env_flags="$env_flags -e APP_URL=https://${subdomain}.${domain}"

    # Generate admin secret for the module
    local admin_secret=$(wopr_random_string 32)
    wopr_setting_set "${module_id//-/_}_admin_secret" "$admin_secret"
    env_flags="$env_flags -e SECRET_KEY=${admin_secret}"

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
    --add-host=host.containers.internal:host-gateway \\
    -v ${data_dir}:/data:Z \\
    ${env_flags} \\
    -p 127.0.0.1:${port}:${container_port} \\
    ${image}

ExecStop=/usr/bin/podman stop -t 10 ${service_name}

[Install]
WantedBy=multi-user.target
SVCEOF

    # Enable and start
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

    # Record installation
    wopr_setting_set "module_${module_id//-/_}_installed" "true"
    wopr_setting_set "${module_id//-/_}_port" "$port"
    wopr_setting_set "${module_id//-/_}_url" "https://${subdomain}.${domain}"

    wopr_log "OK" "$display_name deployed: https://${subdomain}.${domain}"
    return 0
}
