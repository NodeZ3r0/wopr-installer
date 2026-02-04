#!/bin/bash
#=================================================
# WOPR MODULE: FreshRSS
# Version: 1.0
# Purpose: Deploy FreshRSS feed reader
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

FRESHRSS_IMAGE="docker.io/freshrss/freshrss:latest"
FRESHRSS_PORT=8082
FRESHRSS_DATA_DIR="${WOPR_DATA_DIR}/freshrss"
FRESHRSS_SERVICE="wopr-freshrss"

wopr_deploy_freshrss() {
    wopr_log "INFO" "Deploying FreshRSS..."

    # Check if already installed
    if systemctl is-active --quiet "$FRESHRSS_SERVICE" 2>/dev/null; then
        wopr_log "INFO" "FreshRSS is already running"
        return 0
    fi

    # Create directories
    mkdir -p "${FRESHRSS_DATA_DIR}/data"
    mkdir -p "${FRESHRSS_DATA_DIR}/extensions"

    # Get configuration
    local domain=$(wopr_setting_get "domain")

    # Generate admin password if not set
    local admin_password=$(wopr_setting_get "freshrss_admin_password")
    if [ -z "$admin_password" ]; then
        admin_password=$(wopr_random_string 24)
        wopr_setting_set "freshrss_admin_password" "$admin_password"
    fi

    # Pull the image
    wopr_log "INFO" "Pulling FreshRSS image..."
    wopr_container_pull "$FRESHRSS_IMAGE"

    # Create systemd service
    cat > "/etc/systemd/system/${FRESHRSS_SERVICE}.service" <<EOF
[Unit]
Description=WOPR FreshRSS Feed Reader
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${FRESHRSS_SERVICE}
ExecStartPre=-/usr/bin/podman rm ${FRESHRSS_SERVICE}

ExecStart=/usr/bin/podman run --rm \\
    --name ${FRESHRSS_SERVICE} \\
    --network ${WOPR_NETWORK} \\
    -v ${FRESHRSS_DATA_DIR}/data:/var/www/FreshRSS/data:Z \\
    -v ${FRESHRSS_DATA_DIR}/extensions:/var/www/FreshRSS/extensions:Z \\
    -e TZ=America/New_York \\
    -e CRON_MIN=1,31 \\
    -e FRESHRSS_ENV=production \\
    -e FRESHRSS_INSTALL=1 \\
    -e FRESHRSS_USER=admin \\
    -e FRESHRSS_PASSWORD=${admin_password} \\
    -e FRESHRSS_BASE_URL=https://rss.${domain}/ \\
    -p 127.0.0.1:${FRESHRSS_PORT}:80 \\
    ${FRESHRSS_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${FRESHRSS_SERVICE}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start
    systemctl daemon-reload
    systemctl enable "$FRESHRSS_SERVICE"
    systemctl start "$FRESHRSS_SERVICE"

    # Wait for FreshRSS to be ready
    wopr_log "INFO" "Waiting for FreshRSS to be ready..."
    wopr_wait_for_port "127.0.0.1" "$FRESHRSS_PORT" 60

    # Add Caddy route with Authentik forward auth
    wopr_caddy_add_route_with_auth "rss" "$FRESHRSS_PORT"

    # Register with Authentik for SSO
    if systemctl is-active --quiet "wopr-authentik-server" 2>/dev/null; then
        wopr_log "INFO" "Registering FreshRSS with Authentik SSO..."
        wopr_authentik_register_app "FreshRSS" "freshrss" "rss"
    fi

    # Record installation
    wopr_setting_set "module_freshrss_installed" "true"
    wopr_setting_set "freshrss_port" "$FRESHRSS_PORT"
    wopr_setting_set "freshrss_url" "https://rss.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "freshrss"

    wopr_log "OK" "FreshRSS deployed successfully"
    wopr_log "INFO" "Admin login: admin / ${admin_password}"
    wopr_log "INFO" "Access at: https://rss.${domain}"
}

wopr_deploy_freshrss_trial() {
    # FreshRSS is included in all bundles, no trial needed
    wopr_deploy_freshrss
}

wopr_remove_freshrss() {
    wopr_log "INFO" "Removing FreshRSS..."

    systemctl stop "$FRESHRSS_SERVICE" 2>/dev/null || true
    systemctl disable "$FRESHRSS_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${FRESHRSS_SERVICE}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "rss"

    # Note: Data is preserved in ${FRESHRSS_DATA_DIR}
    wopr_log "INFO" "FreshRSS removed (data preserved)"
}

wopr_status_freshrss() {
    if systemctl is-active --quiet "$FRESHRSS_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}
