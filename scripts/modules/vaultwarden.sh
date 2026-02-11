#!/bin/bash
#=================================================
# WOPR MODULE: Vaultwarden
# Version: 1.0
# Purpose: Deploy Vaultwarden password manager
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

VAULTWARDEN_IMAGE="docker.io/vaultwarden/server:latest"
VAULTWARDEN_PORT=8081
VAULTWARDEN_DATA_DIR="${WOPR_DATA_DIR}/vaultwarden"
VAULTWARDEN_SERVICE="wopr-vaultwarden"

wopr_deploy_vaultwarden() {
    wopr_log "INFO" "Deploying Vaultwarden..."

    # Check if already installed
    if systemctl is-active --quiet "$VAULTWARDEN_SERVICE" 2>/dev/null; then
        wopr_log "INFO" "Vaultwarden is already running"
        return 0
    fi

    # Create directories
    mkdir -p "${VAULTWARDEN_DATA_DIR}/data"

    # Get configuration
    local domain=$(wopr_setting_get "domain")

    # Generate admin token if not set
    local admin_token=$(wopr_setting_get "vaultwarden_admin_token")
    if [ -z "$admin_token" ]; then
        admin_token=$(wopr_random_string 48)
        wopr_setting_set "vaultwarden_admin_token" "$admin_token"
    fi

    # Pull the image
    wopr_log "INFO" "Pulling Vaultwarden image..."
    wopr_container_pull "$VAULTWARDEN_IMAGE"

    # Create systemd service
    cat > "/etc/systemd/system/${VAULTWARDEN_SERVICE}.service" <<EOF
[Unit]
Description=WOPR Vaultwarden Password Manager
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${VAULTWARDEN_SERVICE}
ExecStartPre=-/usr/bin/podman rm ${VAULTWARDEN_SERVICE}

ExecStart=/usr/bin/podman run --rm \\
    --name ${VAULTWARDEN_SERVICE} \\
    --network ${WOPR_NETWORK} \\
    -v ${VAULTWARDEN_DATA_DIR}/data:/data:Z \\
    -e DOMAIN=https://vault.${domain} \\
    -e ADMIN_TOKEN=${admin_token} \\
    -e SIGNUPS_ALLOWED=true \\
    -e INVITATIONS_ALLOWED=true \\
    -e WEBSOCKET_ENABLED=true \\
    -e LOG_FILE=/data/vaultwarden.log \\
    -p 127.0.0.1:${VAULTWARDEN_PORT}:80 \\
    -p 127.0.0.1:3012:3012 \\
    ${VAULTWARDEN_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${VAULTWARDEN_SERVICE}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start
    systemctl daemon-reload
    systemctl enable "$VAULTWARDEN_SERVICE"
    systemctl start "$VAULTWARDEN_SERVICE"

    # Wait for Vaultwarden to be ready
    wopr_log "INFO" "Waiting for Vaultwarden to be ready..."
    wopr_wait_for_port "127.0.0.1" "$VAULTWARDEN_PORT" 60

    # Add Caddy route with Authentik forward auth
    wopr_caddy_add_route_with_auth "vault" "$VAULTWARDEN_PORT"

    # Register with Authentik for SSO
    if systemctl is-active --quiet "wopr-authentik-server" 2>/dev/null; then
        wopr_log "INFO" "Registering Vaultwarden with Authentik SSO..."
        wopr_authentik_register_app "Vaultwarden" "vaultwarden" "vault"
    fi

    # Record installation
    wopr_setting_set "module_vaultwarden_installed" "true"
    wopr_setting_set "vaultwarden_port" "$VAULTWARDEN_PORT"
    wopr_setting_set "vaultwarden_url" "https://vault.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "vaultwarden"

    wopr_log "OK" "Vaultwarden deployed successfully"
    wopr_log "INFO" "Admin panel: https://vault.${domain}/admin"
    wopr_log "INFO" "Admin token saved in settings"
    wopr_log "INFO" "Access at: https://vault.${domain}"
}

wopr_deploy_vaultwarden_trial() {
    # Vaultwarden is included in all bundles, no trial needed
    wopr_deploy_vaultwarden
}

wopr_remove_vaultwarden() {
    wopr_log "INFO" "Removing Vaultwarden..."

    systemctl stop "$VAULTWARDEN_SERVICE" 2>/dev/null || true
    systemctl disable "$VAULTWARDEN_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${VAULTWARDEN_SERVICE}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "vault"

    # Note: Data is preserved in ${VAULTWARDEN_DATA_DIR}
    wopr_log "INFO" "Vaultwarden removed (data preserved)"
}

wopr_status_vaultwarden() {
    if systemctl is-active --quiet "$VAULTWARDEN_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Configure Vaultwarden for SSO with Authentik
wopr_vaultwarden_configure_sso() {
    local domain=$(wopr_setting_get "domain")
    local client_id=$(wopr_setting_get "authentik_app_vaultwarden_client_id")
    local client_secret=$(wopr_setting_get "authentik_wopr-vaultwarden_secret")

    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        wopr_log "WARN" "Authentik SSO credentials not available for Vaultwarden"
        return 1
    fi

    wopr_log "INFO" "Configuring Vaultwarden SSO with Authentik..."

    # Vaultwarden SSO requires additional environment variables
    # This would require restarting the container with new env vars
    # For now, log that SSO is available but requires manual config
    wopr_log "INFO" "Vaultwarden SSO is available. Configure in admin panel."

    wopr_log "OK" "Vaultwarden SSO info logged"
}
