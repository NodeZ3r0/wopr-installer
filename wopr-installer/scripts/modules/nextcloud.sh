#!/bin/bash
#=================================================
# WOPR MODULE: Nextcloud
# Version: 1.0
# Purpose: Deploy Nextcloud file storage and collaboration
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

NEXTCLOUD_IMAGE="docker.io/library/nextcloud:stable"
NEXTCLOUD_PORT=8080
NEXTCLOUD_DATA_DIR="${WOPR_DATA_DIR}/nextcloud"
NEXTCLOUD_SERVICE="wopr-nextcloud"

wopr_deploy_nextcloud() {
    wopr_log "INFO" "Deploying Nextcloud..."

    # Check if already installed
    if systemctl is-active --quiet "$NEXTCLOUD_SERVICE" 2>/dev/null; then
        wopr_log "INFO" "Nextcloud is already running"
        return 0
    fi

    # Ensure dependencies are running
    if ! systemctl is-active --quiet "wopr-postgresql" 2>/dev/null; then
        wopr_log "ERROR" "PostgreSQL must be running before Nextcloud"
        return 1
    fi

    if ! systemctl is-active --quiet "wopr-redis" 2>/dev/null; then
        wopr_log "ERROR" "Redis must be running before Nextcloud"
        return 1
    fi

    # Create directories
    mkdir -p "${NEXTCLOUD_DATA_DIR}/html"
    mkdir -p "${NEXTCLOUD_DATA_DIR}/data"
    mkdir -p "${NEXTCLOUD_DATA_DIR}/config"
    mkdir -p "${NEXTCLOUD_DATA_DIR}/apps"

    # Get configuration
    local domain=$(wopr_setting_get "domain")
    local db_password=$(wopr_setting_get "nextcloud_db_password")
    local redis_port=$(wopr_setting_get "redis_port" || echo "6379")

    if [ -z "$db_password" ]; then
        wopr_log "ERROR" "Nextcloud database password not configured"
        return 1
    fi

    # Generate admin password if not set
    local admin_password=$(wopr_setting_get "nextcloud_admin_password")
    if [ -z "$admin_password" ]; then
        admin_password=$(wopr_random_string 24)
        wopr_setting_set "nextcloud_admin_password" "$admin_password"
    fi

    # Pull the image
    wopr_log "INFO" "Pulling Nextcloud image..."
    wopr_container_pull "$NEXTCLOUD_IMAGE"

    # Create systemd service
    cat > "/etc/systemd/system/${NEXTCLOUD_SERVICE}.service" <<EOF
[Unit]
Description=WOPR Nextcloud
After=network.target wopr-postgresql.service wopr-redis.service
Requires=wopr-postgresql.service wopr-redis.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${NEXTCLOUD_SERVICE}
ExecStartPre=-/usr/bin/podman rm ${NEXTCLOUD_SERVICE}

ExecStart=/usr/bin/podman run --rm \\
    --name ${NEXTCLOUD_SERVICE} \\
    --network \${WOPR_NETWORK} \\
    -v ${NEXTCLOUD_DATA_DIR}/html:/var/www/html:Z \\
    -v ${NEXTCLOUD_DATA_DIR}/data:/var/www/html/data:Z \\
    -v ${NEXTCLOUD_DATA_DIR}/config:/var/www/html/config:Z \\
    -v ${NEXTCLOUD_DATA_DIR}/apps:/var/www/html/custom_apps:Z \\
    -e POSTGRES_HOST=wopr-postgresql \\
    -e POSTGRES_DB=nextcloud \\
    -e POSTGRES_USER=nextcloud \\
    -e POSTGRES_PASSWORD=${db_password} \\
    -e REDIS_HOST=wopr-redis \\
    -e REDIS_HOST_PORT=${redis_port} \\
    -e NEXTCLOUD_ADMIN_USER=admin \\
    -e NEXTCLOUD_ADMIN_PASSWORD=${admin_password} \\
    -e NEXTCLOUD_TRUSTED_DOMAINS=files.${domain} \\
    -e OVERWRITEPROTOCOL=https \\
    -e OVERWRITEHOST=files.${domain} \\
    -p 127.0.0.1:${NEXTCLOUD_PORT}:80 \\
    ${NEXTCLOUD_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${NEXTCLOUD_SERVICE}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start
    systemctl daemon-reload
    systemctl enable "$NEXTCLOUD_SERVICE"
    systemctl start "$NEXTCLOUD_SERVICE"

    # Wait for Nextcloud to be ready
    wopr_log "INFO" "Waiting for Nextcloud to be ready..."
    wopr_wait_for_port "127.0.0.1" "$NEXTCLOUD_PORT" 120

    # Add Caddy route with Authentik forward auth
    wopr_caddy_add_route_with_auth "files" "$NEXTCLOUD_PORT"

    # Register with Authentik for SSO
    if systemctl is-active --quiet "wopr-authentik-server" 2>/dev/null; then
        wopr_log "INFO" "Registering Nextcloud with Authentik SSO..."
        wopr_authentik_register_app "Nextcloud" "nextcloud" "files"
    fi

    # Record installation
    wopr_setting_set "module_nextcloud_installed" "true"
    wopr_setting_set "nextcloud_port" "$NEXTCLOUD_PORT"
    wopr_setting_set "nextcloud_url" "https://files.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "nextcloud"

    wopr_log "OK" "Nextcloud deployed successfully"
    wopr_log "INFO" "Admin login: admin / ${admin_password}"
    wopr_log "INFO" "Access at: https://files.${domain}"
}

wopr_deploy_nextcloud_trial() {
    # Nextcloud is included in all bundles, no trial needed
    wopr_deploy_nextcloud
}

wopr_remove_nextcloud() {
    wopr_log "INFO" "Removing Nextcloud..."

    systemctl stop "$NEXTCLOUD_SERVICE" 2>/dev/null || true
    systemctl disable "$NEXTCLOUD_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${NEXTCLOUD_SERVICE}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "files"

    # Note: Data is preserved in ${NEXTCLOUD_DATA_DIR}
    wopr_log "INFO" "Nextcloud removed (data preserved)"
}

wopr_status_nextcloud() {
    if systemctl is-active --quiet "$NEXTCLOUD_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Configure Nextcloud for OIDC with Authentik
wopr_nextcloud_configure_sso() {
    local domain=$(wopr_setting_get "domain")
    local client_id=$(wopr_setting_get "authentik_app_nextcloud_client_id")
    local client_secret=$(wopr_setting_get "authentik_wopr-nextcloud_secret")

    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        wopr_log "WARN" "Authentik SSO credentials not available for Nextcloud"
        return 1
    fi

    wopr_log "INFO" "Configuring Nextcloud SSO with Authentik..."

    # Install and configure the OIDC app via occ command
    podman exec "$NEXTCLOUD_SERVICE" php occ app:install user_oidc 2>/dev/null || true
    podman exec "$NEXTCLOUD_SERVICE" php occ app:enable user_oidc

    # Configure the OIDC provider
    podman exec "$NEXTCLOUD_SERVICE" php occ user_oidc:provider authentik \
        --clientid="$client_id" \
        --clientsecret="$client_secret" \
        --discoveryuri="https://auth.${domain}/application/o/nextcloud/.well-known/openid-configuration" \
        --unique-uid=1 \
        --mapping-uid="preferred_username"

    wopr_log "OK" "Nextcloud SSO configured"
}
