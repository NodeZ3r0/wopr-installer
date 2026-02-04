#!/bin/bash
#=================================================
# WOPR INSTALLER
# Version: 2.0
# Purpose: Manifest-driven installation orchestrator
# License: AGPL-3.0
#
# This installer reads module lists from /etc/wopr/bootstrap.json
# (written by the orchestrator during cloud-init).
# It does NOT hardcode bundle-to-module mappings.
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/wopr_common.sh"
source "${SCRIPT_DIR}/modules/registry.sh"
source "${SCRIPT_DIR}/modules/mesh.sh"

BOOTSTRAP_FILE="/etc/wopr/bootstrap.json"

#=================================================
# PARSE ARGUMENTS
#=================================================

usage() {
    cat << EOF
WOPR Installer v2.0

Usage: $0 [OPTIONS]

Options:
    --domain <domain>     Primary domain (read from bootstrap.json if omitted)
    --non-interactive     Skip confirmation prompts (requires --confirm-all)
    --confirm-all         Auto-confirm all prompts (for cloud-init)
    --help                Show this help message

The installer reads core_modules and app_modules from /etc/wopr/bootstrap.json
which is written by the orchestrator during provisioning.

EOF
    exit 0
}

WOPR_DOMAIN=""
WOPR_NON_INTERACTIVE=false
WOPR_CONFIRM_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)       WOPR_DOMAIN="$2"; shift 2 ;;
        --non-interactive) WOPR_NON_INTERACTIVE=true; shift ;;
        --confirm-all)  WOPR_CONFIRM_ALL=true; shift ;;
        --help)         usage ;;
        *)              wopr_die "Unknown option: $1" ;;
    esac
done

#=================================================
# BOOTSTRAP.JSON READER
#=================================================

bootstrap_get() {
    local key="$1"
    jq -r "$key // empty" "$BOOTSTRAP_FILE"
}

bootstrap_get_array() {
    local key="$1"
    jq -r "$key[]? // empty" "$BOOTSTRAP_FILE"
}

validate_bootstrap() {
    if [ ! -f "$BOOTSTRAP_FILE" ]; then
        wopr_die "Bootstrap file not found: $BOOTSTRAP_FILE"
    fi

    # Validate required fields
    local bundle=$(bootstrap_get '.bundle')
    local domain=$(bootstrap_get '.domain')

    if [ -z "$bundle" ]; then
        wopr_die "bootstrap.json missing 'bundle' field"
    fi
    if [ -z "$domain" ]; then
        if [ -z "$WOPR_DOMAIN" ]; then
            wopr_die "No domain found in bootstrap.json or --domain flag"
        fi
    else
        WOPR_DOMAIN="$domain"
    fi

    # Read module arrays
    WOPR_CORE_MODULES=()
    while IFS= read -r mod; do
        [ -n "$mod" ] && WOPR_CORE_MODULES+=("$mod")
    done < <(bootstrap_get_array '.core_modules')

    WOPR_APP_MODULES=()
    while IFS= read -r mod; do
        [ -n "$mod" ] && WOPR_APP_MODULES+=("$mod")
    done < <(bootstrap_get_array '.app_modules')

    WOPR_BUNDLE=$(bootstrap_get '.bundle')
    WOPR_STORAGE_TIER=$(bootstrap_get '.storage_tier')
    WOPR_JOB_ID=$(bootstrap_get '.job_id')
    WOPR_CUSTOMER_ID=$(bootstrap_get '.customer_id')
    WOPR_ORCHESTRATOR_URL=$(bootstrap_get '.orchestrator_url')

    if [ ${#WOPR_CORE_MODULES[@]} -eq 0 ]; then
        wopr_log "WARN" "No core_modules in bootstrap.json, using defaults"
        WOPR_CORE_MODULES=("authentik" "caddy" "postgresql" "redis")
    fi

    if [ ${#WOPR_APP_MODULES[@]} -eq 0 ]; then
        wopr_die "No app_modules in bootstrap.json — cannot determine what to install"
    fi

    local total_modules=$(( ${#WOPR_CORE_MODULES[@]} + ${#WOPR_APP_MODULES[@]} ))

    wopr_setting_set "bundle" "$WOPR_BUNDLE"
    wopr_setting_set "domain" "$WOPR_DOMAIN"
    wopr_setting_set "storage_tier" "$WOPR_STORAGE_TIER"
    wopr_setting_set "job_id" "$WOPR_JOB_ID"
    wopr_setting_set "customer_id" "$WOPR_CUSTOMER_ID"
    wopr_setting_set "orchestrator_url" "$WOPR_ORCHESTRATOR_URL"

    wopr_log "OK" "Bootstrap validated: bundle=$WOPR_BUNDLE, domain=$WOPR_DOMAIN"
    wopr_log "INFO" "Core modules (${#WOPR_CORE_MODULES[@]}): ${WOPR_CORE_MODULES[*]}"
    wopr_log "INFO" "App modules (${#WOPR_APP_MODULES[@]}): ${WOPR_APP_MODULES[*]}"
}

#=================================================
# ORCHESTRATOR CALLBACK
#=================================================

report_status() {
    local status="$1"
    local message="${2:-}"

    if [ -n "$WOPR_ORCHESTRATOR_URL" ] && [ -n "$WOPR_JOB_ID" ]; then
        curl -sf -X POST "${WOPR_ORCHESTRATOR_URL}/api/v1/provision/${WOPR_JOB_ID}/status" \
            -H "Content-Type: application/json" \
            -d "{\"status\": \"$status\", \"message\": \"$message\"}" \
            2>/dev/null || true
    fi
}

#=================================================
# STEP 1: DETECT SYSTEM RESOURCES
#=================================================

step_detect_resources() {
    wopr_progress 1 "$TOTAL_STEPS" "Detecting system resources..."

    wopr_detect_resources

    echo ""
    echo "System resources detected:"
    echo "  CPU:  ${WOPR_CPU_COUNT} vCPU"
    echo "  RAM:  ${WOPR_RAM_GB} GB"
    echo "  Disk: ${WOPR_DISK_GB} GB available"
    echo ""
}

#=================================================
# STEP 2: INSTALL CORE STACK (apt packages)
#=================================================

step_install_core_stack() {
    wopr_progress 2 "$TOTAL_STEPS" "Installing core stack..."
    report_status "installing" "Installing system packages"

    # Update package manager
    wopr_log "INFO" "Updating package manager..."
    apt-get update -qq

    # Install essential packages
    wopr_log "INFO" "Installing essential packages..."
    apt-get install -y -qq \
        curl \
        wget \
        gnupg \
        lsb-release \
        ca-certificates \
        apt-transport-https \
        software-properties-common \
        jq \
        uuid-runtime \
        netcat-openbsd

    # Install Podman
    wopr_log "INFO" "Installing Podman..."
    apt-get install -y -qq podman

    # Install Caddy
    wopr_log "INFO" "Installing Caddy..."
    apt-get install -y -qq debian-keyring debian-archive-keyring
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy

    wopr_log "OK" "Core stack installed"
}

#=================================================
# STEP 3: HUMAN CONFIRMATION (skipped in cloud-init)
#=================================================

step_human_confirmation() {
    wopr_progress 3 "$TOTAL_STEPS" "Requesting confirmation..."

    local total_modules=$(( ${#WOPR_CORE_MODULES[@]} + ${#WOPR_APP_MODULES[@]} ))

    echo ""
    echo "============================================"
    echo "  WOPR INSTALLATION"
    echo "============================================"
    echo ""
    echo "  Bundle:      $WOPR_BUNDLE"
    echo "  Domain:      $WOPR_DOMAIN"
    echo "  Tier:        $WOPR_STORAGE_TIER"
    echo "  Instance:    $(wopr_instance_id)"
    echo "  Modules:     $total_modules total"
    echo ""
    echo "  Infrastructure: ${WOPR_CORE_MODULES[*]}"
    echo "  Applications:  ${WOPR_APP_MODULES[*]}"
    echo ""
    echo "============================================"

    if [ "$WOPR_CONFIRM_ALL" = true ]; then
        wopr_log "WARN" "Auto-confirming installation (--confirm-all)"
        wopr_defcon_log "INSTALL_AUTO_CONFIRMED" "$WOPR_BUNDLE"
    else
        wopr_require_confirmation "WOPR_INSTALL" "Proceed with installation?"
    fi
}

#=================================================
# STEP 4: DEPLOY INFRASTRUCTURE MODULES
#=================================================

step_deploy_infrastructure() {
    wopr_progress 4 "$TOTAL_STEPS" "Deploying infrastructure modules..."
    report_status "deploying_infra" "Deploying infrastructure"

    local infra_count=${#WOPR_CORE_MODULES[@]}
    local infra_idx=0

    for module in "${WOPR_CORE_MODULES[@]}"; do
        infra_idx=$((infra_idx + 1))
        wopr_log "INFO" "Deploying infrastructure ($infra_idx/$infra_count): $module"
        wopr_defcon_log "MODULE_DEPLOY_START" "$module"

        local module_script="${SCRIPT_DIR}/modules/${module}.sh"
        local module_script_alt="${SCRIPT_DIR}/modules/${module//-/_}.sh"

        if [ -f "$module_script" ]; then
            source "$module_script"
            local func_name="wopr_deploy_${module//-/_}"
            if ! "$func_name"; then
                wopr_die "Failed to deploy infrastructure module: $module"
            fi
        elif [ -f "$module_script_alt" ]; then
            source "$module_script_alt"
            local func_name="wopr_deploy_${module//-/_}"
            if ! "$func_name"; then
                wopr_die "Failed to deploy infrastructure module: $module"
            fi
        else
            wopr_die "Infrastructure module script not found: $module"
        fi

        wopr_defcon_log "MODULE_DEPLOY_COMPLETE" "$module"
    done

    wopr_log "OK" "Infrastructure modules deployed"
}

#=================================================
# STEP 5: DEPLOY APPLICATION MODULES
#=================================================

step_deploy_applications() {
    wopr_progress 5 "$TOTAL_STEPS" "Deploying application modules..."
    report_status "deploying_apps" "Deploying applications"

    local app_count=${#WOPR_APP_MODULES[@]}
    local app_idx=0
    local failed_modules=()

    for module in "${WOPR_APP_MODULES[@]}"; do
        app_idx=$((app_idx + 1))
        wopr_log "INFO" "Deploying application ($app_idx/$app_count): $module"
        wopr_defcon_log "MODULE_DEPLOY_START" "$module"
        report_status "deploying_apps" "Deploying $module ($app_idx/$app_count)"

        local module_script="${SCRIPT_DIR}/modules/${module}.sh"
        local module_script_alt="${SCRIPT_DIR}/modules/${module//-/_}.sh"

        if [ -f "$module_script" ]; then
            # Custom deploy script exists
            source "$module_script"
            local func_name="wopr_deploy_${module//-/_}"
            if ! "$func_name"; then
                wopr_log "WARN" "Failed to deploy module: $module (continuing)"
                failed_modules+=("$module")
            fi
        elif [ -f "$module_script_alt" ]; then
            source "$module_script_alt"
            local func_name="wopr_deploy_${module//-/_}"
            if ! "$func_name"; then
                wopr_log "WARN" "Failed to deploy module: $module (continuing)"
                failed_modules+=("$module")
            fi
        else
            # Use generic deployment from registry
            if wopr_deploy_from_registry "$module"; then
                wopr_log "OK" "Deployed $module via registry"
            else
                wopr_log "WARN" "Failed to deploy module: $module (no script, registry deploy failed)"
                failed_modules+=("$module")
            fi
        fi

        wopr_defcon_log "MODULE_DEPLOY_COMPLETE" "$module"
    done

    if [ ${#failed_modules[@]} -gt 0 ]; then
        wopr_log "WARN" "Some modules failed to deploy: ${failed_modules[*]}"
        wopr_setting_set "failed_modules" "${failed_modules[*]}"
    fi

    wopr_log "OK" "Application modules deployed ($((app_count - ${#failed_modules[@]}))/$app_count successful)"
}

#=================================================
# STEP 6: CONFIGURE CADDY
#=================================================

step_configure_caddy() {
    wopr_progress 6 "$TOTAL_STEPS" "Configuring Caddy..."
    report_status "configuring" "Configuring reverse proxy"

    mkdir -p "${WOPR_DATA_DIR}/caddy/snapshots"

    local admin_email=$(wopr_setting_get "admin_email")
    if [ -z "$admin_email" ]; then
        admin_email="admin@${WOPR_DOMAIN}"
    fi

    # Build Caddyfile header
    cat > /etc/caddy/Caddyfile << EOF
{
    admin 127.0.0.1:2019
    email ${admin_email}
}

# Main domain - redirect to dashboard
${WOPR_DOMAIN} {
    redir https://dashboard.${WOPR_DOMAIN}{uri} permanent
}

# Dashboard
dashboard.${WOPR_DOMAIN} {
    root * /var/www/wopr-dashboard
    file_server

    handle /api/* {
        reverse_proxy 127.0.0.1:8090
    }

    try_files {path} /index.html
}

# Authentik - Identity Provider
auth.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:9000
}
EOF

    # Add routes for each deployed app module from registry
    for module in "${WOPR_APP_MODULES[@]}"; do
        local subdomain=$(registry_get_subdomain "$module")
        local port=$(registry_get_port "$module")

        if [ -n "$subdomain" ] && [ -n "$port" ]; then
            local installed=$(wopr_setting_get "module_${module//-/_}_installed" 2>/dev/null || echo "")
            if [ "$installed" = "true" ]; then
                cat >> /etc/caddy/Caddyfile << EOF

# ${module}
${subdomain}.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:${port}
}
EOF
            fi
        fi
    done

    systemctl restart caddy
    wopr_log "OK" "Caddy configured with all routes"
}

#=================================================
# STEP 7: DEPLOY DASHBOARD
#=================================================

step_deploy_dashboard() {
    wopr_progress 7 "$TOTAL_STEPS" "Deploying dashboard..."

    local dashboard_script="${SCRIPT_DIR}/modules/dashboard.sh"
    if [ -f "$dashboard_script" ]; then
        source "$dashboard_script"
        wopr_deploy_dashboard
    else
        wopr_log "WARN" "Dashboard script not found, creating placeholder"
        mkdir -p /var/www/wopr-dashboard
        echo "<h1>WOPR Dashboard</h1><p>Coming soon</p>" > /var/www/wopr-dashboard/index.html
    fi

    wopr_log "OK" "Dashboard deployed"
}

#=================================================
# STEP 8: SETUP AUTHENTIK SSO
#=================================================

step_setup_sso() {
    wopr_progress 8 "$TOTAL_STEPS" "Setting up Single Sign-On..."
    report_status "configuring_sso" "Setting up SSO"

    # Wait for Authentik to be ready
    wopr_authentik_wait_ready

    # Setup WOPR groups
    wopr_authentik_setup_wopr_groups

    # Create initial WOPR user account
    wopr_authentik_setup_initial_user

    # Register apps with Authentik based on deployed modules
    local domain=$(wopr_setting_get "domain")

    for module in "${WOPR_APP_MODULES[@]}"; do
        local subdomain=$(registry_get_subdomain "$module")
        local display_name=$(registry_get_name "$module")

        if [ -n "$subdomain" ] && [ -n "$display_name" ]; then
            local installed=$(wopr_setting_get "module_${module//-/_}_installed" 2>/dev/null || echo "")
            if [ "$installed" = "true" ]; then
                local slug="${module//-/_}"
                wopr_authentik_register_app "$display_name" "$slug" "$subdomain" || \
                    wopr_log "WARN" "SSO registration deferred for $module"
            fi
        fi
    done

    # Apply customer branding (colors, logo, title)
    wopr_authentik_apply_branding || wopr_log "WARN" "Branding deferred"

    wopr_log "OK" "SSO configured"
}

#=================================================
# STEP 9: SCHEDULE BACKUPS
#=================================================

step_schedule_backups() {
    wopr_progress 9 "$TOTAL_STEPS" "Scheduling backups..."

    cat > /etc/cron.daily/wopr-backup << 'EOF'
#!/bin/bash
source /opt/wopr/scripts/wopr_common.sh
wopr_snapshot_create "daily"
EOF
    chmod +x /etc/cron.daily/wopr-backup

    wopr_log "OK" "Daily backups scheduled"
}

#=================================================
# STEP 10: DEPLOY MESH NETWORK
#=================================================

step_deploy_mesh() {
    wopr_progress 10 "$TOTAL_STEPS" "Deploying peer-to-peer mesh network..."
    report_status "deploying_mesh" "Setting up mesh network"

    # Deploy the mesh agent (identity + API + Caddy route)
    wopr_deploy_mesh

    # Install hourly health check cron
    wopr_mesh_install_cron

    # If bootstrap.json contains mesh_peers, auto-accept invites
    local mesh_peers=$(jq -r '.mesh_peers // empty' "$BOOTSTRAP_FILE" 2>/dev/null)
    if [ -n "$mesh_peers" ] && [ "$mesh_peers" != "null" ]; then
        local peer_count=$(echo "$mesh_peers" | jq 'length')
        wopr_log "INFO" "Found ${peer_count} mesh peer invite(s) in bootstrap.json"

        for i in $(seq 0 $((peer_count - 1))); do
            local invite_token=$(echo "$mesh_peers" | jq -r ".[$i]")
            if [ -n "$invite_token" ]; then
                wopr_log "INFO" "Accepting mesh invite ($((i + 1))/${peer_count})..."
                wopr_mesh_accept_invite "$invite_token" || \
                    wopr_log "WARN" "Failed to accept mesh invite $((i + 1)) (will retry later)"
            fi
        done
    fi

    wopr_log "OK" "Mesh network ready ($(wopr_mesh_peer_count) peers)"
}

#=================================================
# STEP 11: REGISTER UPDATE AGENT
#=================================================

step_register_update_agent() {
    wopr_progress 11 "$TOTAL_STEPS" "Registering update agent..."

    cat > /etc/cron.weekly/wopr-update-check << 'EOF'
#!/bin/bash
source /opt/wopr/scripts/wopr_common.sh
wopr_log "INFO" "Checking for WOPR updates..."
EOF
    chmod +x /etc/cron.weekly/wopr-update-check

    wopr_log "OK" "Update agent registered"
}

#=================================================
# STEP 12: FINALIZE
#=================================================

step_finalize() {
    wopr_progress 12 "$TOTAL_STEPS" "Finalizing installation..."
    report_status "complete" "Installation complete"

    wopr_setting_set "install_complete" "true"
    wopr_setting_set "install_timestamp" "$(date -Iseconds)"
    wopr_defcon_log "INSTALL_COMPLETE" "bundle=$WOPR_BUNDLE,domain=$WOPR_DOMAIN"

    local ak_bootstrap_pass=$(wopr_setting_get "authentik_bootstrap_password")
    local wopr_username=$(wopr_setting_get "wopr_username")
    local wopr_user_pass=$(wopr_setting_get "user_${wopr_username}_password")

    echo ""
    echo "============================================"
    echo "  WOPR INSTALLATION COMPLETE"
    echo "============================================"
    echo ""
    echo "  Instance ID: $(wopr_instance_id)"
    echo "  Domain:      $WOPR_DOMAIN"
    echo "  Bundle:      $WOPR_BUNDLE"
    echo ""
    echo "  Your Applications:"
    echo "    Dashboard:  https://dashboard.${WOPR_DOMAIN}"

    # List all deployed app URLs
    for module in "${WOPR_APP_MODULES[@]}"; do
        local subdomain=$(registry_get_subdomain "$module")
        local display_name=$(registry_get_name "$module")
        local installed=$(wopr_setting_get "module_${module//-/_}_installed" 2>/dev/null || echo "")
        if [ "$installed" = "true" ] && [ -n "$subdomain" ]; then
            printf "    %-12s https://%s.%s\n" "${display_name}:" "${subdomain}" "${WOPR_DOMAIN}"
        fi
    done

    echo ""
    echo "  Mesh Network:"
    echo "    Mesh API:    https://mesh.${WOPR_DOMAIN}"
    echo "    Fingerprint: $(wopr_mesh_get_fingerprint)"
    echo "    Peers:       $(wopr_mesh_peer_count)"
    echo ""
    echo "  ============================================"
    echo "  YOUR LOGIN CREDENTIALS (SAVE THESE!)"
    echo "  ============================================"
    echo ""
    if [ -n "$wopr_username" ] && [ -n "$wopr_user_pass" ]; then
        echo "  WOPR User Account (use for all apps):"
        echo "    Username: $wopr_username"
        echo "    Password: $wopr_user_pass"
        echo ""
    fi
    if [ -n "$ak_bootstrap_pass" ]; then
        echo "  Authentik Admin (for SSO configuration):"
        echo "    Username: akadmin"
        echo "    Password: $ak_bootstrap_pass"
        echo ""
    fi
    echo "  ============================================"
    echo ""
    echo "  Logs: /var/log/wopr/installer.log"
    echo ""
    echo "============================================"

    wopr_log "OK" "WOPR installation complete!"
}

#=================================================
# MAIN
#=================================================

TOTAL_STEPS=12

main() {
    echo ""
    echo "  ██╗    ██╗ ██████╗ ██████╗ ██████╗ "
    echo "  ██║    ██║██╔═══██╗██╔══██╗██╔══██╗"
    echo "  ██║ █╗ ██║██║   ██║██████╔╝██████╔╝"
    echo "  ██║███╗██║██║   ██║██╔═══╝ ██╔══██╗"
    echo "  ╚███╔███╔╝╚██████╔╝██║     ██║  ██║"
    echo "   ╚══╝╚══╝  ╚═════╝ ╚═╝     ╚═╝  ╚═╝"
    echo ""
    echo "  Installer v2.0 (manifest-driven)"
    echo ""

    # Ensure running as root
    if [ "$(id -u)" -ne 0 ]; then
        wopr_die "This script must be run as root"
    fi

    # Read and validate bootstrap.json
    validate_bootstrap

    step_detect_resources
    step_install_core_stack
    step_human_confirmation
    step_deploy_infrastructure    # Core modules from bootstrap.json
    step_deploy_applications      # App modules from bootstrap.json
    step_configure_caddy          # Reverse proxy with all routes
    step_deploy_dashboard         # Dashboard UI
    step_setup_sso                # Wire apps to Authentik
    step_schedule_backups
    step_deploy_mesh                # P2P mesh network agent
    step_register_update_agent
    step_finalize
}

main "$@"
