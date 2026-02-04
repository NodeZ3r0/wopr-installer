#!/bin/bash
#=================================================
# WOPR MODULE: Authentik
# Version: 1.0
# Purpose: Deploy Authentik SSO for WOPR services
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

AUTHENTIK_IMAGE="ghcr.io/goauthentik/server:latest"
AUTHENTIK_PORT=9000
AUTHENTIK_DATA_DIR="${WOPR_DATA_DIR}/authentik"
AUTHENTIK_SERVICE_SERVER="wopr-authentik-server"
AUTHENTIK_SERVICE_WORKER="wopr-authentik-worker"

wopr_deploy_authentik() {
    wopr_log "INFO" "Deploying Authentik SSO..."

    # Check if already installed
    if systemctl is-active --quiet "$AUTHENTIK_SERVICE_SERVER" 2>/dev/null; then
        wopr_log "INFO" "Authentik is already running"
        return 0
    fi

    # Ensure dependencies are running
    if ! systemctl is-active --quiet "wopr-postgresql" 2>/dev/null; then
        wopr_log "ERROR" "PostgreSQL must be running before Authentik"
        return 1
    fi

    if ! systemctl is-active --quiet "wopr-redis" 2>/dev/null; then
        wopr_log "ERROR" "Redis must be running before Authentik"
        return 1
    fi

    # Create directories
    mkdir -p "${AUTHENTIK_DATA_DIR}/media"
    mkdir -p "${AUTHENTIK_DATA_DIR}/templates"
    mkdir -p "${AUTHENTIK_DATA_DIR}/certs"

    # Get database credentials
    local db_password=$(wopr_setting_get "authentik_db_password")
    if [ -z "$db_password" ]; then
        wopr_log "ERROR" "Authentik database password not configured"
        return 1
    fi

    # Generate secrets if not exist
    local secret_key=$(wopr_setting_get "authentik_secret_key")
    if [ -z "$secret_key" ]; then
        secret_key=$(wopr_random_string 64)
        wopr_setting_set "authentik_secret_key" "$secret_key"
    fi

    # Generate bootstrap password for initial admin
    local bootstrap_password=$(wopr_setting_get "authentik_bootstrap_password")
    if [ -z "$bootstrap_password" ]; then
        bootstrap_password=$(wopr_random_string 24)
        wopr_setting_set "authentik_bootstrap_password" "$bootstrap_password"
    fi

    # Generate bootstrap token for API access
    local bootstrap_token=$(wopr_setting_get "authentik_bootstrap_token")
    if [ -z "$bootstrap_token" ]; then
        bootstrap_token=$(wopr_random_string 64)
        wopr_setting_set "authentik_bootstrap_token" "$bootstrap_token"
    fi

    local domain=$(wopr_setting_get "domain")
    local redis_url=$(wopr_redis_url)

    # Pull the image
    wopr_log "INFO" "Pulling Authentik image..."
    wopr_container_pull "$AUTHENTIK_IMAGE"

    # Create environment file
    cat > "${AUTHENTIK_DATA_DIR}/authentik.env" <<EOF
# Authentik Configuration
AUTHENTIK_SECRET_KEY=${secret_key}
AUTHENTIK_REDIS__HOST=wopr-redis
AUTHENTIK_REDIS__PORT=6379
AUTHENTIK_POSTGRESQL__HOST=wopr-postgresql
AUTHENTIK_POSTGRESQL__PORT=5432
AUTHENTIK_POSTGRESQL__NAME=authentik
AUTHENTIK_POSTGRESQL__USER=authentik
AUTHENTIK_POSTGRESQL__PASSWORD=${db_password}
AUTHENTIK_ERROR_REPORTING__ENABLED=false
AUTHENTIK_BOOTSTRAP_PASSWORD=${bootstrap_password}
AUTHENTIK_BOOTSTRAP_TOKEN=${bootstrap_token}
AUTHENTIK_BOOTSTRAP_EMAIL=admin@${domain}
EOF

    chmod 600 "${AUTHENTIK_DATA_DIR}/authentik.env"

    # Create systemd service for Authentik server
    cat > "/etc/systemd/system/${AUTHENTIK_SERVICE_SERVER}.service" <<EOF
[Unit]
Description=WOPR Authentik Server
After=network.target wopr-postgresql.service wopr-redis.service
Requires=wopr-postgresql.service wopr-redis.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${AUTHENTIK_SERVICE_SERVER}
ExecStartPre=-/usr/bin/podman rm ${AUTHENTIK_SERVICE_SERVER}

ExecStart=/usr/bin/podman run --rm \\
    --name ${AUTHENTIK_SERVICE_SERVER} \\
    --network ${WOPR_NETWORK} \\
    --env-file ${AUTHENTIK_DATA_DIR}/authentik.env \\
    -v ${AUTHENTIK_DATA_DIR}/media:/media:Z \\
    -v ${AUTHENTIK_DATA_DIR}/templates:/templates:Z \\
    -v ${AUTHENTIK_DATA_DIR}/certs:/certs:Z \\
    -p 127.0.0.1:${AUTHENTIK_PORT}:9000 \\
    -p 127.0.0.1:9443:9443 \\
    ${AUTHENTIK_IMAGE} \\
    server

ExecStop=/usr/bin/podman stop -t 10 ${AUTHENTIK_SERVICE_SERVER}

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd service for Authentik worker
    cat > "/etc/systemd/system/${AUTHENTIK_SERVICE_WORKER}.service" <<EOF
[Unit]
Description=WOPR Authentik Worker
After=network.target ${AUTHENTIK_SERVICE_SERVER}.service
Requires=${AUTHENTIK_SERVICE_SERVER}.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${AUTHENTIK_SERVICE_WORKER}
ExecStartPre=-/usr/bin/podman rm ${AUTHENTIK_SERVICE_WORKER}

ExecStart=/usr/bin/podman run --rm \\
    --name ${AUTHENTIK_SERVICE_WORKER} \\
    --network ${WOPR_NETWORK} \\
    --env-file ${AUTHENTIK_DATA_DIR}/authentik.env \\
    -v ${AUTHENTIK_DATA_DIR}/media:/media:Z \\
    -v ${AUTHENTIK_DATA_DIR}/templates:/templates:Z \\
    -v ${AUTHENTIK_DATA_DIR}/certs:/certs:Z \\
    ${AUTHENTIK_IMAGE} \\
    worker

ExecStop=/usr/bin/podman stop -t 10 ${AUTHENTIK_SERVICE_WORKER}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start services
    systemctl daemon-reload
    systemctl enable "$AUTHENTIK_SERVICE_SERVER"
    systemctl enable "$AUTHENTIK_SERVICE_WORKER"
    systemctl start "$AUTHENTIK_SERVICE_SERVER"

    # Wait for server to be ready before starting worker
    wopr_log "INFO" "Waiting for Authentik server to be ready..."
    wopr_authentik_wait_ready 120

    # Start the worker
    systemctl start "$AUTHENTIK_SERVICE_WORKER"

    # Set the API token for further configuration
    wopr_authentik_set_token "$bootstrap_token"

    # Add Caddy route for Authentik
    wopr_caddy_add_route "auth" "$AUTHENTIK_PORT"

    # Setup WOPR groups
    wopr_log "INFO" "Setting up WOPR groups in Authentik..."
    sleep 5  # Give Authentik a moment to fully initialize
    wopr_authentik_setup_wopr_groups

    # Record installation
    wopr_setting_set "module_authentik_installed" "true"
    wopr_setting_set "authentik_port" "$AUTHENTIK_PORT"
    wopr_setting_set "authentik_url" "https://auth.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "authentik"

    wopr_log "OK" "Authentik deployed successfully"
    wopr_log "INFO" "Admin login: admin@${domain} / ${bootstrap_password}"
    wopr_log "INFO" "Access at: https://auth.${domain}"
}

wopr_remove_authentik() {
    wopr_log "INFO" "Removing Authentik..."

    systemctl stop "$AUTHENTIK_SERVICE_WORKER" 2>/dev/null || true
    systemctl stop "$AUTHENTIK_SERVICE_SERVER" 2>/dev/null || true
    systemctl disable "$AUTHENTIK_SERVICE_WORKER" 2>/dev/null || true
    systemctl disable "$AUTHENTIK_SERVICE_SERVER" 2>/dev/null || true
    rm -f "/etc/systemd/system/${AUTHENTIK_SERVICE_SERVER}.service"
    rm -f "/etc/systemd/system/${AUTHENTIK_SERVICE_WORKER}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "auth"

    # Note: Data is preserved in ${AUTHENTIK_DATA_DIR}
    wopr_log "INFO" "Authentik removed (data preserved)"
}

wopr_status_authentik() {
    local server_status="stopped"
    local worker_status="stopped"

    if systemctl is-active --quiet "$AUTHENTIK_SERVICE_SERVER" 2>/dev/null; then
        server_status="running"
    fi

    if systemctl is-active --quiet "$AUTHENTIK_SERVICE_WORKER" 2>/dev/null; then
        worker_status="running"
    fi

    if [ "$server_status" = "running" ] && [ "$worker_status" = "running" ]; then
        echo "running"
    elif [ "$server_status" = "running" ] || [ "$worker_status" = "running" ]; then
        echo "partial"
    else
        echo "stopped"
    fi
}

# Create an outpost for forward auth
wopr_authentik_create_outpost() {
    local outpost_name="${1:-wopr-outpost}"

    wopr_log "INFO" "Creating Authentik outpost for forward auth..."

    local outpost_data=$(cat <<EOF
{
    "name": "${outpost_name}",
    "type": "proxy",
    "providers": [],
    "config": {
        "authentik_host": "http://127.0.0.1:${AUTHENTIK_PORT}/",
        "docker_network": null,
        "container_image": null,
        "docker_map_ports": true,
        "kubernetes_replicas": 1,
        "kubernetes_namespace": "default"
    }
}
EOF
)

    local response=$(wopr_authentik_api POST "/outposts/instances/" "$outpost_data")
    local outpost_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$outpost_pk" ]; then
        wopr_log "OK" "Authentik outpost created: ${outpost_name}"
        wopr_setting_set "authentik_outpost_pk" "$outpost_pk"
    else
        wopr_log "WARN" "Failed to create outpost (may already exist)"
    fi
}

# =========================================
# AUTHENTIK BRANDING / THEMING
# =========================================
# Applies customer branding to their Authentik instance:
#   - Logo, favicon
#   - Primary color
#   - Custom CSS
#   - Login page title
#
# Reads from /etc/wopr/bootstrap.json:
#   branding.logo_url     - URL to customer logo (or local path)
#   branding.favicon_url  - URL to favicon
#   branding.primary_color - Hex color (e.g. "#6559C5")
#   branding.title        - Login page title (e.g. "Acme Corp Cloud")
#   branding.custom_css   - Additional CSS for login page
# =========================================

wopr_authentik_apply_branding() {
    wopr_log "INFO" "Applying Authentik branding..."

    local domain=$(wopr_setting_get "domain")
    local bootstrap="/etc/wopr/bootstrap.json"

    # Read branding from bootstrap.json (set by orchestrator)
    local logo_url=$(jq -r '.branding.logo_url // empty' "$bootstrap" 2>/dev/null)
    local favicon_url=$(jq -r '.branding.favicon_url // empty' "$bootstrap" 2>/dev/null)
    local primary_color=$(jq -r '.branding.primary_color // empty' "$bootstrap" 2>/dev/null)
    local title=$(jq -r '.branding.title // empty' "$bootstrap" 2>/dev/null)
    local custom_css=$(jq -r '.branding.custom_css // empty' "$bootstrap" 2>/dev/null)

    # Defaults
    if [ -z "$title" ]; then
        title="Welcome to ${domain}"
    fi
    if [ -z "$primary_color" ]; then
        primary_color="#6559C5"
    fi

    # Build the branding payload for Authentik's tenant/brand API
    # Authentik v2024+ uses /api/v3/brands/ (formerly tenants)
    local brand_css=""
    if [ -n "$custom_css" ]; then
        brand_css="$custom_css"
    fi

    # Always inject WOPR default theme + customer primary color
    brand_css=":root { --ak-accent: ${primary_color}; } .pf-c-login__main { border-top: 4px solid ${primary_color}; } ${brand_css}"

    # Get the default brand/tenant
    local brands=$(wopr_authentik_api GET "/brands/" 2>/dev/null)
    local brand_pk=$(echo "$brands" | jq -r '.results[0].brand_uuid // .results[0].pk // empty' 2>/dev/null)

    if [ -z "$brand_pk" ]; then
        # Fallback: try tenants endpoint (older Authentik versions)
        brands=$(wopr_authentik_api GET "/core/tenants/" 2>/dev/null)
        brand_pk=$(echo "$brands" | jq -r '.results[0].tenant_uuid // empty' 2>/dev/null)
    fi

    if [ -z "$brand_pk" ]; then
        wopr_log "WARN" "Could not find Authentik brand/tenant to update"
        return 1
    fi

    # Build update payload
    local brand_update=$(jq -n \
        --arg title "$title" \
        --arg css "$brand_css" \
        --arg logo "$logo_url" \
        --arg favicon "$favicon_url" \
        --arg domain "$domain" \
        '{
            "branding_title": $title,
            "flow_authentication": null,
            "flow_invalidation": null,
            "branding_css": $css,
            "web_certificate": null,
            "default": true
        }
        | if ($logo | length) > 0 then . + {"branding_logo": $logo} else . end
        | if ($favicon | length) > 0 then . + {"branding_favicon": $favicon} else . end
    ')

    # Try brands endpoint first, fall back to tenants
    local response
    response=$(wopr_authentik_api PATCH "/brands/${brand_pk}/" "$brand_update" 2>/dev/null)
    if [ -z "$response" ] || echo "$response" | jq -r '.detail // empty' 2>/dev/null | grep -qi "not found"; then
        response=$(wopr_authentik_api PATCH "/core/tenants/${brand_pk}/" "$brand_update" 2>/dev/null)
    fi

    local result_title=$(echo "$response" | jq -r '.branding_title // empty' 2>/dev/null)
    if [ -n "$result_title" ]; then
        wopr_log "OK" "Authentik branding applied: title='${title}', color=${primary_color}"
    else
        wopr_log "WARN" "Branding update may not have applied correctly"
    fi

    # If logo_url is a remote URL, download and upload to Authentik media
    if [ -n "$logo_url" ] && [[ "$logo_url" == http* ]]; then
        wopr_log "INFO" "Downloading custom logo..."
        local logo_file="${AUTHENTIK_DATA_DIR}/media/custom_logo.png"
        curl -fsSL "$logo_url" -o "$logo_file" 2>/dev/null && \
            wopr_log "OK" "Custom logo saved" || \
            wopr_log "WARN" "Failed to download logo from $logo_url"
    fi

    if [ -n "$favicon_url" ] && [[ "$favicon_url" == http* ]]; then
        wopr_log "INFO" "Downloading custom favicon..."
        local favicon_file="${AUTHENTIK_DATA_DIR}/media/custom_favicon.ico"
        curl -fsSL "$favicon_url" -o "$favicon_file" 2>/dev/null && \
            wopr_log "OK" "Custom favicon saved" || \
            wopr_log "WARN" "Failed to download favicon from $favicon_url"
    fi

    wopr_setting_set "authentik_branding_applied" "true"
    wopr_setting_set "authentik_branding_title" "$title"
    wopr_setting_set "authentik_branding_color" "$primary_color"
}
