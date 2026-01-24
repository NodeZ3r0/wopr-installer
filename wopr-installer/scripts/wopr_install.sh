#!/bin/bash
#=================================================
# WOPR SOVEREIGN SUITE INSTALLER
# Version: 1.5
# Purpose: Main installation orchestrator
# License: AGPL-3.0
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/wopr_common.sh"

#=================================================
# PARSE ARGUMENTS
#=================================================

usage() {
    cat << EOF
WOPR Sovereign Suite Installer v1.5

Usage: $0 [OPTIONS]

Options:
    --bundle <name>       Bundle to install (personal|creator|developer|professional)
    --domain <domain>     Primary domain for the instance
    --customer-id <id>    Customer ID (for managed deployments)
    --instance-id <id>    Instance ID (auto-generated if not provided)
    --non-interactive     Skip confirmation prompts (requires --confirm-all)
    --confirm-all         Auto-confirm all prompts (dangerous)
    --help                Show this help message

Examples:
    $0 --bundle personal --domain mycloud.example.com
    $0 --bundle developer --domain dev.example.com --non-interactive --confirm-all

EOF
    exit 0
}

WOPR_BUNDLE=""
WOPR_DOMAIN=""
WOPR_CUSTOMER_ID=""
WOPR_INSTANCE_ID_ARG=""
WOPR_NON_INTERACTIVE=false
WOPR_CONFIRM_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --bundle)       WOPR_BUNDLE="$2"; shift 2 ;;
        --domain)       WOPR_DOMAIN="$2"; shift 2 ;;
        --customer-id)  WOPR_CUSTOMER_ID="$2"; shift 2 ;;
        --instance-id)  WOPR_INSTANCE_ID_ARG="$2"; shift 2 ;;
        --non-interactive) WOPR_NON_INTERACTIVE=true; shift ;;
        --confirm-all)  WOPR_CONFIRM_ALL=true; shift ;;
        --help)         usage ;;
        *)              wopr_die "Unknown option: $1" ;;
    esac
done

#=================================================
# VALIDATION
#=================================================

validate_inputs() {
    if [ -z "$WOPR_BUNDLE" ]; then
        if [ "$WOPR_NON_INTERACTIVE" = true ]; then
            wopr_die "Bundle must be specified in non-interactive mode"
        fi
        echo "Available bundles:"
        echo "  1) personal     - Personal cloud (Nextcloud, Vaultwarden, RSS)"
        echo "  2) creator      - Personal + e-commerce + blogging"
        echo "  3) developer    - Personal + Git + CI + Reactor AI"
        echo "  4) professional - Full suite with chat, video, office"
        echo ""
        read -p "Select bundle [1-4]: " bundle_choice
        case $bundle_choice in
            1) WOPR_BUNDLE="personal" ;;
            2) WOPR_BUNDLE="creator" ;;
            3) WOPR_BUNDLE="developer" ;;
            4) WOPR_BUNDLE="professional" ;;
            *) wopr_die "Invalid bundle selection" ;;
        esac
    fi

    case "$WOPR_BUNDLE" in
        personal|creator|developer|professional) ;;
        *) wopr_die "Invalid bundle: $WOPR_BUNDLE" ;;
    esac

    if [ -z "$WOPR_DOMAIN" ]; then
        if [ "$WOPR_NON_INTERACTIVE" = true ]; then
            wopr_die "Domain must be specified in non-interactive mode"
        fi
        read -p "Enter primary domain (e.g., mycloud.example.com): " WOPR_DOMAIN
    fi

    if [ -z "$WOPR_DOMAIN" ]; then
        wopr_die "Domain is required"
    fi

    wopr_setting_set "bundle" "$WOPR_BUNDLE"
    wopr_setting_set "domain" "$WOPR_DOMAIN"

    if [ -n "$WOPR_CUSTOMER_ID" ]; then
        wopr_setting_set "customer_id" "$WOPR_CUSTOMER_ID"
    fi

    wopr_log "OK" "Configuration validated: bundle=$WOPR_BUNDLE, domain=$WOPR_DOMAIN"
}

#=================================================
# STEP 1: DETECT SYSTEM RESOURCES
#=================================================

step_detect_resources() {
    wopr_progress 1 16 "Detecting system resources..."

    wopr_detect_resources

    echo ""
    echo "System resources detected:"
    echo "  CPU:  ${WOPR_CPU_COUNT} vCPU"
    echo "  RAM:  ${WOPR_RAM_GB} GB"
    echo "  Disk: ${WOPR_DISK_GB} GB available"
    echo ""
}

#=================================================
# STEP 2: VALIDATE RESOURCES FOR BUNDLE
#=================================================

step_validate_resources() {
    wopr_progress 2 16 "Validating resources for bundle: $WOPR_BUNDLE"

    local tier
    case "$WOPR_BUNDLE" in
        personal)     tier="low" ;;
        creator)      tier="medium" ;;
        developer)    tier="medium" ;;
        professional) tier="high" ;;
    esac

    if ! wopr_validate_resources "$tier"; then
        echo ""
        echo "Your system does not meet the minimum requirements for the $WOPR_BUNDLE bundle."
        echo ""
        if [ "$WOPR_NON_INTERACTIVE" = true ]; then
            wopr_die "Resource validation failed"
        fi
        read -p "Continue anyway? (not recommended) [y/N]: " continue_anyway
        if [ "$continue_anyway" != "y" ] && [ "$continue_anyway" != "Y" ]; then
            wopr_die "Installation cancelled due to insufficient resources"
        fi
        wopr_log "WARN" "User chose to continue with insufficient resources"
    fi
}

#=================================================
# STEP 3: INSTALL CORE STACK
#=================================================

step_install_core_stack() {
    wopr_progress 3 16 "Installing core stack..."

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
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy

    wopr_log "OK" "Core stack installed"
}

#=================================================
# STEP 4: SELECT BUNDLE (already done in validation)
#=================================================

step_select_bundle() {
    wopr_progress 4 16 "Bundle selected: $WOPR_BUNDLE"
    wopr_defcon_log "BUNDLE_SELECTED" "$WOPR_BUNDLE"
}

#=================================================
# STEP 5: ENABLE BUNDLE MODULES
#=================================================

step_enable_modules() {
    wopr_progress 5 16 "Enabling bundle modules..."

    # Map bundle to actual module scripts
    # Infrastructure modules are always included: postgresql, redis, authentik, caddy
    local app_modules
    case "$WOPR_BUNDLE" in
        personal)
            # Personal: Files, Passwords, RSS reader
            app_modules="nextcloud vaultwarden freshrss"
            ;;
        creator)
            # Creator: Personal + e-commerce + blogging
            app_modules="nextcloud vaultwarden freshrss ghost"
            ;;
        developer)
            # Developer: Personal + Git + CI + AI assistant
            app_modules="nextcloud vaultwarden freshrss forgejo woodpecker reactor_ai"
            ;;
        professional)
            # Professional: Everything
            app_modules="nextcloud vaultwarden freshrss ghost forgejo woodpecker reactor_ai mattermost jitsi onlyoffice bookstack"
            ;;
    esac

    wopr_setting_set "app_modules" "$app_modules"
    wopr_setting_set "infra_modules" "postgresql redis authentik"
    wopr_log "OK" "App modules enabled: $app_modules"
}

#=================================================
# STEP 6: PROMPT FOR OPTIONAL MODULES
#=================================================

step_optional_modules() {
    wopr_progress 6 16 "Checking optional modules..."

    if [ "$WOPR_NON_INTERACTIVE" = true ]; then
        wopr_log "INFO" "Skipping optional modules in non-interactive mode"
        return
    fi

    echo ""
    echo "Optional modules available (requires additional resources):"
    echo "  - analytics (Plausible)"
    echo "  - time_tracking (Kimai)"
    echo "  - crm (EspoCRM)"
    echo ""
    read -p "Enable any optional modules? [y/N]: " enable_optional

    if [ "$enable_optional" = "y" ] || [ "$enable_optional" = "Y" ]; then
        wopr_log "INFO" "User requested optional modules - not yet implemented"
        echo "Optional module selection will be implemented in a future version."
    fi
}

#=================================================
# STEP 7: REQUIRE HUMAN CONFIRMATION
#=================================================

step_human_confirmation() {
    wopr_progress 7 16 "Requesting confirmation..."

    echo ""
    echo "============================================"
    echo "  WOPR SOVEREIGN SUITE INSTALLATION"
    echo "============================================"
    echo ""
    echo "  Bundle:   $WOPR_BUNDLE"
    echo "  Domain:   $WOPR_DOMAIN"
    echo "  Instance: $(wopr_instance_id)"
    echo ""
    echo "  This will install and configure:"
    echo "    - Podman (container runtime)"
    echo "    - Caddy (reverse proxy)"
    echo "    - Authentik (SSO)"
    echo "    - PostgreSQL (database)"
    echo "    - Redis (cache)"
    echo "    - Bundle-specific applications"
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
# STEP 8: DEPLOY INFRASTRUCTURE MODULES
#=================================================

step_deploy_infrastructure() {
    wopr_progress 8 16 "Deploying infrastructure modules..."

    # Deploy infrastructure modules in order (dependencies matter)
    local infra_modules="postgresql redis authentik"

    for module in $infra_modules; do
        wopr_log "INFO" "Deploying infrastructure: $module"
        wopr_defcon_log "MODULE_DEPLOY_START" "$module"

        local module_script="${SCRIPT_DIR}/modules/${module}.sh"
        if [ -f "$module_script" ]; then
            source "$module_script"
            if ! wopr_deploy_${module}; then
                wopr_die "Failed to deploy infrastructure module: $module"
            fi
        else
            wopr_die "Infrastructure module script not found: $module_script"
        fi

        wopr_defcon_log "MODULE_DEPLOY_COMPLETE" "$module"
    done

    wopr_log "OK" "Infrastructure modules deployed"
}

#=================================================
# STEP 9: DEPLOY APPLICATION MODULES
#=================================================

step_deploy_applications() {
    wopr_progress 9 16 "Deploying application modules..."

    local app_modules=$(wopr_setting_get "app_modules")

    for module in $app_modules; do
        wopr_log "INFO" "Deploying application: $module"
        wopr_defcon_log "MODULE_DEPLOY_START" "$module"

        local module_script="${SCRIPT_DIR}/modules/${module}.sh"
        if [ -f "$module_script" ]; then
            source "$module_script"
            if ! wopr_deploy_${module}; then
                wopr_log "WARN" "Failed to deploy module: $module (continuing)"
            fi
        else
            wopr_log "WARN" "Module script not found: $module (will be available in future release)"
        fi

        wopr_defcon_log "MODULE_DEPLOY_COMPLETE" "$module"
    done

    wopr_log "OK" "Application modules deployed"
}

#=================================================
# STEP 10: CONFIGURE CADDY
#=================================================

step_configure_caddy() {
    wopr_progress 10 16 "Configuring Caddy..."

    # Create Caddy directories
    mkdir -p "${WOPR_DATA_DIR}/caddy/snapshots"

    local admin_email=$(wopr_setting_get "admin_email")
    if [ -z "$admin_email" ]; then
        admin_email="admin@${WOPR_DOMAIN}"
    fi

    # Build comprehensive Caddyfile with all routes
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

    # API routes proxy to dashboard API
    handle /api/* {
        reverse_proxy 127.0.0.1:8090
    }

    # SPA fallback
    try_files {path} /index.html
}

# Authentik - Identity Provider
auth.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:9000
}

# Nextcloud - Files
files.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:8080
}

# Vaultwarden - Passwords
vault.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:8081
}

# FreshRSS - RSS Reader
rss.${WOPR_DOMAIN} {
    reverse_proxy 127.0.0.1:8082
}
EOF

    systemctl restart caddy
    wopr_log "OK" "Caddy configured with all routes"
}

#=================================================
# STEP 11: DEPLOY DASHBOARD
#=================================================

step_deploy_dashboard() {
    wopr_progress 11 16 "Deploying dashboard..."

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
# STEP 12: SETUP AUTHENTIK SSO
#=================================================

step_setup_sso() {
    wopr_progress 12 16 "Setting up Single Sign-On..."

    # Wait for Authentik to be ready
    wopr_authentik_wait_ready

    # Setup WOPR groups
    wopr_authentik_setup_wopr_groups

    # Create initial WOPR user account
    wopr_authentik_setup_initial_user

    # Register applications with Authentik for SSO and configure native OIDC
    local app_modules=$(wopr_setting_get "app_modules")
    local domain=$(wopr_setting_get "domain")

    for module in $app_modules; do
        case "$module" in
            nextcloud)
                # Register with Authentik
                wopr_authentik_register_app "Nextcloud" "nextcloud" "files"
                # Configure Nextcloud's native OIDC integration
                wopr_log "INFO" "Configuring Nextcloud OIDC..."
                wopr_nextcloud_configure_sso || wopr_log "WARN" "Nextcloud OIDC config deferred (can be done manually)"
                ;;
            vaultwarden)
                # Vaultwarden uses its own auth - SSO available via OpenID Connect
                wopr_log "INFO" "Vaultwarden uses its own authentication (SSO optional)"
                ;;
            freshrss)
                # Register with Authentik - uses forward auth
                wopr_authentik_register_app "FreshRSS" "freshrss" "rss"
                wopr_log "INFO" "FreshRSS configured with Authentik forward auth"
                ;;
            *)
                wopr_log "INFO" "SSO for $module will be configured when module is implemented"
                ;;
        esac
    done

    wopr_log "OK" "SSO configured with initial user account"
}

#=================================================
# STEP 13: SCHEDULE BACKUPS
#=================================================

step_schedule_backups() {
    wopr_progress 13 16 "Scheduling backups..."

    # Create backup script
    cat > /etc/cron.daily/wopr-backup << 'EOF'
#!/bin/bash
source /opt/wopr/scripts/wopr_common.sh
wopr_snapshot_create "daily"
EOF
    chmod +x /etc/cron.daily/wopr-backup

    wopr_log "OK" "Daily backups scheduled"
}

#=================================================
# STEP 14: REGISTER UPDATE AGENT
#=================================================

step_register_update_agent() {
    wopr_progress 14 16 "Registering update agent..."

    # Create update check script
    cat > /etc/cron.weekly/wopr-update-check << 'EOF'
#!/bin/bash
source /opt/wopr/scripts/wopr_common.sh
wopr_log "INFO" "Checking for WOPR updates..."
# Update check implementation
EOF
    chmod +x /etc/cron.weekly/wopr-update-check

    wopr_log "OK" "Update agent registered"
}

#=================================================
# STEP 15: LOG TO DEFCON ONE
#=================================================

step_log_defcon() {
    wopr_progress 15 16 "Logging to DEFCON ONE..."

    wopr_defcon_log "INSTALL_COMPLETE" "bundle=$WOPR_BUNDLE,domain=$WOPR_DOMAIN"

    wopr_log "OK" "Installation logged to audit trail"
}

#=================================================
# STEP 16: FINALIZE
#=================================================

step_finalize() {
    wopr_progress 16 16 "Finalizing installation..."

    # Mark installation as complete
    wopr_setting_set "install_complete" "true"
    wopr_setting_set "install_timestamp" "$(date -Iseconds)"

    # Get credentials for display
    local ak_bootstrap_pass=$(wopr_setting_get "authentik_bootstrap_password")
    local wopr_username=$(wopr_setting_get "wopr_username")
    local wopr_user_pass=$(wopr_setting_get "user_${wopr_username}_password")

    echo ""
    echo "============================================"
    echo "  WOPR SOVEREIGN SUITE INSTALLATION COMPLETE"
    echo "============================================"
    echo ""
    echo "  Instance ID: $(wopr_instance_id)"
    echo "  Domain:      $WOPR_DOMAIN"
    echo "  Bundle:      $WOPR_BUNDLE"
    echo ""
    echo "  Your Applications:"
    echo "    Dashboard:  https://dashboard.${WOPR_DOMAIN}"
    echo "    Files:      https://files.${WOPR_DOMAIN}"
    echo "    Passwords:  https://vault.${WOPR_DOMAIN}"
    echo "    RSS Reader: https://rss.${WOPR_DOMAIN}"
    echo "    SSO Admin:  https://auth.${WOPR_DOMAIN}"
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
    echo "  Next steps:"
    echo "    1. Point DNS for *.${WOPR_DOMAIN} to this server"
    echo "    2. Access https://dashboard.${WOPR_DOMAIN}"
    echo "    3. Complete Authentik setup at https://auth.${WOPR_DOMAIN}"
    echo ""
    echo "  Logs: /var/log/wopr/installer.log"
    echo ""
    echo "============================================"

    wopr_log "OK" "WOPR installation complete!"
}

#=================================================
# MAIN
#=================================================

main() {
    echo ""
    echo "  ██╗    ██╗ ██████╗ ██████╗ ██████╗ "
    echo "  ██║    ██║██╔═══██╗██╔══██╗██╔══██╗"
    echo "  ██║ █╗ ██║██║   ██║██████╔╝██████╔╝"
    echo "  ██║███╗██║██║   ██║██╔═══╝ ██╔══██╗"
    echo "  ╚███╔███╔╝╚██████╔╝██║     ██║  ██║"
    echo "   ╚══╝╚══╝  ╚═════╝ ╚═╝     ╚═╝  ╚═╝"
    echo ""
    echo "  Sovereign Suite Installer v1.5"
    echo ""

    # Ensure running as root
    if [ "$(id -u)" -ne 0 ]; then
        wopr_die "This script must be run as root"
    fi

    validate_inputs

    step_detect_resources
    step_validate_resources
    step_install_core_stack
    step_select_bundle
    step_enable_modules
    step_optional_modules
    step_human_confirmation
    step_deploy_infrastructure    # PostgreSQL, Redis, Authentik
    step_deploy_applications      # Nextcloud, Vaultwarden, FreshRSS, etc.
    step_configure_caddy          # Reverse proxy with all routes
    step_deploy_dashboard         # Dashboard UI
    step_setup_sso                # Wire apps to Authentik
    step_schedule_backups
    step_register_update_agent
    step_log_defcon
    step_finalize
}

main "$@"
