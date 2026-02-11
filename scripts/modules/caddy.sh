#!/bin/bash
#=================================================
# WOPR MODULE: Caddy
# Version: 1.0
# Purpose: Configure Caddy reverse proxy for WOPR services
# License: AGPL-3.0
#=================================================

# Caddy is installed via apt in step 2 (core stack).
# This module script handles initial configuration only.

CADDY_SERVICE="caddy"

wopr_deploy_caddy() {
    wopr_log "INFO" "Configuring Caddy..."

    # Caddy should already be installed via apt
    if ! command -v caddy >/dev/null 2>&1; then
        wopr_die "Caddy binary not found. Was step 2 (core stack install) completed?"
    fi

    local domain=$(wopr_setting_get domain)
    if [ -z "$domain" ]; then
        wopr_die "Domain not set in settings"
    fi

    # Write initial Caddyfile
    mkdir -p /etc/caddy
    cat > /etc/caddy/Caddyfile <<EOF
{
    admin 127.0.0.1:2019
    email admin@${domain}
}

# Default site
${domain} {
    respond "WOPR Sovereign Suite - Initializing..." 200
}

# Authentik (will be updated after authentik deploys)
auth.${domain} {
    reverse_proxy 127.0.0.1:9000
}
EOF

    # Ensure Caddy service is enabled and running
    systemctl enable caddy
    systemctl restart caddy

    # Wait for Caddy admin API
    local count=0
    while [ "$count" -lt 15 ]; do
        if curl -s http://127.0.0.1:2019/config/ >/dev/null 2>&1; then
            wopr_log "OK" "Caddy admin API is ready"
            break
        fi
        sleep 1
        count=$((count + 1))
    done

    if [ "$count" -ge 15 ]; then
        wopr_log "WARN" "Caddy admin API not responding, but service may still be working"
    fi

    wopr_setting_set "module_caddy_installed" "true"
    wopr_defcon_log "MODULE_DEPLOYED" "caddy"

    wopr_log "OK" "Caddy configured successfully"
}

wopr_remove_caddy() {
    wopr_log "INFO" "Removing Caddy configuration..."
    rm -f /etc/caddy/Caddyfile
    systemctl stop caddy 2>/dev/null || true
    wopr_log "INFO" "Caddy stopped (package not removed)"
}

wopr_status_caddy() {
    if systemctl is-active --quiet "$CADDY_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}
