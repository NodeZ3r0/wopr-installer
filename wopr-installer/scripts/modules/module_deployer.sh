#!/bin/bash
#=================================================
# WOPR MODULE DEPLOYER
# Version: 1.5
# Purpose: Central module deployment orchestrator
#
# Usage:
#   ./module_deployer.sh deploy <module_id> [--trial]
#   ./module_deployer.sh list [--bundle <bundle>]
#   ./module_deployer.sh status <module_id>
#   ./module_deployer.sh remove <module_id>
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../wopr_common.sh"

#=================================================
# MODULE CATALOG
#=================================================

# Format: module_id|name|category|tier|bundles|trial_days
declare -A MODULE_CATALOG=(
    # Core (always installed)
    ["authentik"]="Authentik|core|minimal|personal,creator,developer,professional|0"
    ["caddy"]="Caddy|core|minimal|personal,creator,developer,professional|0"
    ["postgresql"]="PostgreSQL|core|minimal|personal,creator,developer,professional|0"
    ["redis"]="Redis|core|minimal|personal,creator,developer,professional|0"

    # Productivity
    ["nextcloud"]="Nextcloud|productivity|low|personal,creator,developer,professional|0"
    ["freshrss"]="FreshRSS|productivity|minimal|personal,creator,developer,professional|0"
    ["collabora"]="Collabora Online|productivity|medium|professional|30"
    ["outline"]="Outline Wiki|productivity|medium|professional|30"

    # Security
    ["vaultwarden"]="Vaultwarden|security|minimal|personal,creator,developer,professional|0"

    # Communication
    ["matrix"]="Matrix/Synapse|communication|medium|professional|14"
    ["element"]="Element Chat|communication|minimal|professional|14"
    ["jitsi"]="Jitsi Meet|communication|high|professional|14"

    # Developer
    ["forgejo"]="Forgejo Git|developer|low|developer,professional|30"
    ["woodpecker"]="Woodpecker CI|developer|medium|developer,professional|30"
    ["ollama"]="Ollama LLM|developer|medium|developer,professional|90"
    ["reactor"]="Reactor AI|developer|medium|developer,professional|90"
    ["defcon_one"]="DEFCON ONE|developer|low|developer,professional|90"
    ["code_server"]="VS Code Server|developer|medium|developer,professional|30"
    ["uptime_kuma"]="Uptime Kuma|developer|minimal|developer,professional|30"

    # Creator
    ["ghost"]="Ghost Blog|creator|low|creator,professional|30"
    ["saleor"]="Saleor Store|creator|medium|creator,professional|30"
    ["wordpress"]="WordPress|creator|low||30"

    # Business
    ["espocrm"]="EspoCRM|business|low||30"
    ["kimai"]="Kimai Time|business|low||30"
    ["invoiceninja"]="Invoice Ninja|business|low||30"

    # Media
    ["immich"]="Immich Photos|media|medium||30"
    ["jellyfin"]="Jellyfin Media|media|medium||30"

    # Analytics
    ["plausible"]="Plausible Analytics|analytics|low||30"
)

#=================================================
# HELPER FUNCTIONS
#=================================================

get_module_info() {
    local module_id="$1"
    echo "${MODULE_CATALOG[$module_id]:-}"
}

get_module_field() {
    local module_id="$1"
    local field="$2"
    local info=$(get_module_info "$module_id")

    if [ -z "$info" ]; then
        return 1
    fi

    case $field in
        name)     echo "$info" | cut -d'|' -f1 ;;
        category) echo "$info" | cut -d'|' -f2 ;;
        tier)     echo "$info" | cut -d'|' -f3 ;;
        bundles)  echo "$info" | cut -d'|' -f4 ;;
        trial)    echo "$info" | cut -d'|' -f5 ;;
        *)        return 1 ;;
    esac
}

is_module_in_bundle() {
    local module_id="$1"
    local bundle="$2"
    local bundles=$(get_module_field "$module_id" "bundles")

    [[ ",$bundles," == *",$bundle,"* ]]
}

can_trial_module() {
    local module_id="$1"
    local current_bundle="$2"

    # Check if module is already in bundle
    if is_module_in_bundle "$module_id" "$current_bundle"; then
        return 1  # Already has access
    fi

    # Check if trial is available
    local trial_days=$(get_module_field "$module_id" "trial")
    [ "$trial_days" -gt 0 ]
}

#=================================================
# LIST MODULES
#=================================================

cmd_list() {
    local filter_bundle="${1:-}"

    echo ""
    echo "WOPR Module Catalog"
    echo "==================="
    echo ""

    local current_bundle=$(wopr_setting_get "bundle" 2>/dev/null || echo "none")

    for module_id in "${!MODULE_CATALOG[@]}"; do
        local name=$(get_module_field "$module_id" "name")
        local category=$(get_module_field "$module_id" "category")
        local tier=$(get_module_field "$module_id" "tier")
        local bundles=$(get_module_field "$module_id" "bundles")
        local trial=$(get_module_field "$module_id" "trial")

        # Filter by bundle if specified
        if [ -n "$filter_bundle" ]; then
            if ! is_module_in_bundle "$module_id" "$filter_bundle"; then
                continue
            fi
        fi

        # Determine status
        local status="available"
        local installed=$(wopr_setting_get "${module_id}_installed" 2>/dev/null || echo "")

        if [ -n "$installed" ]; then
            status="installed"
        elif is_module_in_bundle "$module_id" "$current_bundle"; then
            status="included"
        elif [ "$trial" -gt 0 ]; then
            status="trial:${trial}d"
        fi

        printf "  %-15s %-20s %-12s %-8s %s\n" \
            "$module_id" "$name" "$category" "$tier" "[$status]"
    done

    echo ""
}

#=================================================
# MODULE STATUS
#=================================================

cmd_status() {
    local module_id="$1"

    if [ -z "$(get_module_info "$module_id")" ]; then
        wopr_die "Unknown module: $module_id"
    fi

    local name=$(get_module_field "$module_id" "name")
    local installed=$(wopr_setting_get "${module_id}_installed" 2>/dev/null || echo "false")
    local url=$(wopr_setting_get "${module_id}_url" 2>/dev/null || echo "")

    echo ""
    echo "Module: $name ($module_id)"
    echo "========================="
    echo "  Installed: $installed"
    echo "  URL: ${url:-N/A}"

    # Check trial status
    local trial_started=$(wopr_setting_get "${module_id}_trial_started" 2>/dev/null || echo "")
    if [ -n "$trial_started" ]; then
        local trial_expires=$(wopr_setting_get "${module_id}_trial_expires" 2>/dev/null || echo "")
        echo "  Trial started: $trial_started"
        echo "  Trial expires: $trial_expires"
    fi

    # Check service status if installed
    if [ "$installed" = "true" ]; then
        local service="wopr-${module_id//_/-}"
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            echo "  Service: running"
        else
            echo "  Service: stopped"
        fi
    fi

    echo ""
}

#=================================================
# DEPLOY MODULE
#=================================================

cmd_deploy() {
    local module_id="$1"
    local trial_mode="${2:-false}"

    if [ -z "$(get_module_info "$module_id")" ]; then
        wopr_die "Unknown module: $module_id"
    fi

    local name=$(get_module_field "$module_id" "name")
    local tier=$(get_module_field "$module_id" "tier")
    local current_bundle=$(wopr_setting_get "bundle" 2>/dev/null || echo "personal")

    wopr_log "INFO" "Deploying module: $name"

    # Check if already installed
    local installed=$(wopr_setting_get "${module_id}_installed" 2>/dev/null || echo "")
    if [ -n "$installed" ]; then
        wopr_log "WARN" "Module already installed: $module_id"
        return 0
    fi

    # Check if trial mode is valid
    if [ "$trial_mode" = "true" ]; then
        if ! can_trial_module "$module_id" "$current_bundle"; then
            wopr_die "Trial not available for $module_id with $current_bundle bundle"
        fi
        wopr_log "INFO" "Deploying in TRIAL mode"
    fi

    # Check resource tier
    if ! wopr_validate_resources "$tier"; then
        wopr_log "WARN" "System may not meet resource requirements for $tier tier"
        if [ "$trial_mode" != "true" ]; then
            read -p "Continue anyway? [y/N]: " continue_anyway
            if [ "$continue_anyway" != "y" ]; then
                wopr_die "Deployment cancelled"
            fi
        fi
    fi

    # Find and run module deploy script
    local module_script="${SCRIPT_DIR}/${module_id}.sh"
    local module_script_alt="${SCRIPT_DIR}/${module_id//_/-}.sh"

    if [ -f "$module_script" ]; then
        if [ "$trial_mode" = "true" ]; then
            source "$module_script"
            "wopr_deploy_${module_id}_trial" 2>/dev/null || "wopr_deploy_${module_id}"
        else
            source "$module_script"
            "wopr_deploy_${module_id}"
        fi
    elif [ -f "$module_script_alt" ]; then
        source "$module_script_alt"
        local func_name="wopr_deploy_${module_id//-/_}"
        if [ "$trial_mode" = "true" ]; then
            "${func_name}_trial" 2>/dev/null || "$func_name"
        else
            "$func_name"
        fi
    else
        # Use generic deployment
        wopr_deploy_generic "$module_id" "$trial_mode"
    fi

    # Record trial if applicable
    if [ "$trial_mode" = "true" ]; then
        local trial_days=$(get_module_field "$module_id" "trial")
        wopr_setting_set "${module_id}_trial_started" "$(date -Iseconds)"
        wopr_setting_set "${module_id}_trial_expires" "$(date -d "+${trial_days} days" -Iseconds)"
        wopr_defcon_log "MODULE_TRIAL_STARTED" "module=$module_id,days=$trial_days"
    fi

    wopr_defcon_log "MODULE_DEPLOYED" "module=$module_id,trial=$trial_mode"
    wopr_log "OK" "Module deployed: $name"
}

#=================================================
# GENERIC DEPLOYMENT (for modules without custom scripts)
#=================================================

wopr_deploy_generic() {
    local module_id="$1"
    local trial_mode="$2"

    local name=$(get_module_field "$module_id" "name")
    local domain=$(wopr_setting_get "domain")

    wopr_log "INFO" "Using generic deployment for: $name"

    # This is a placeholder for modules that need manual setup
    # or will have their scripts added later

    wopr_setting_set "${module_id}_installed" "pending"
    wopr_log "WARN" "Module $module_id requires manual setup or script not yet available"
}

#=================================================
# REMOVE MODULE
#=================================================

cmd_remove() {
    local module_id="$1"

    if [ -z "$(get_module_info "$module_id")" ]; then
        wopr_die "Unknown module: $module_id"
    fi

    local name=$(get_module_field "$module_id" "name")
    local category=$(get_module_field "$module_id" "category")

    # Don't allow removal of core modules
    if [ "$category" = "core" ]; then
        wopr_die "Cannot remove core module: $module_id"
    fi

    wopr_log "INFO" "Removing module: $name"
    wopr_require_confirmation "MODULE_REMOVE" "Remove $name? This will stop the service but preserve data."

    # Stop service
    local service="wopr-${module_id//_/-}"
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        systemctl stop "$service"
        systemctl disable "$service"
    fi

    # Clear settings
    wopr_setting_set "${module_id}_installed" ""

    # Remove Caddy route
    # wopr_caddy_remove_route "${module_id}.${domain}"

    wopr_defcon_log "MODULE_REMOVED" "module=$module_id"
    wopr_log "OK" "Module removed: $name (data preserved in ${WOPR_DATA_DIR}/${module_id})"
}

#=================================================
# TRIAL EXPIRY CHECK
#=================================================

cmd_check_trials() {
    wopr_log "INFO" "Checking trial expirations..."

    local now=$(date +%s)
    local warnings=()
    local expired=()

    for module_id in "${!MODULE_CATALOG[@]}"; do
        local trial_expires=$(wopr_setting_get "${module_id}_trial_expires" 2>/dev/null || echo "")

        if [ -n "$trial_expires" ]; then
            local expires_ts=$(date -d "$trial_expires" +%s 2>/dev/null || echo "0")
            local days_left=$(( (expires_ts - now) / 86400 ))

            if [ "$days_left" -lt 0 ]; then
                expired+=("$module_id")
            elif [ "$days_left" -lt 15 ]; then
                warnings+=("$module_id:${days_left}d")
            fi
        fi
    done

    if [ ${#expired[@]} -gt 0 ]; then
        wopr_log "WARN" "Expired trials: ${expired[*]}"
        for module_id in "${expired[@]}"; do
            wopr_log "INFO" "Disabling expired trial: $module_id"
            # Don't remove, just disable
            local service="wopr-${module_id//_/-}"
            systemctl stop "$service" 2>/dev/null || true
        done
    fi

    if [ ${#warnings[@]} -gt 0 ]; then
        wopr_log "WARN" "Trials expiring soon: ${warnings[*]}"
    fi

    wopr_log "OK" "Trial check complete"
}

#=================================================
# MAIN
#=================================================

usage() {
    cat << EOF
WOPR Module Deployer v1.5

Usage:
    $0 deploy <module_id> [--trial]   Deploy a module
    $0 list [--bundle <bundle>]        List available modules
    $0 status <module_id>              Check module status
    $0 remove <module_id>              Remove a module
    $0 check-trials                    Check trial expirations

Examples:
    $0 deploy reactor_ai --trial       Start Reactor AI trial
    $0 list --bundle developer         Show Developer bundle modules
    $0 status forgejo                  Check Forgejo status

EOF
    exit 0
}

main() {
    local command="${1:-}"
    shift || true

    case "$command" in
        deploy)
            local module_id="${1:-}"
            local trial_flag="${2:-}"
            [ -z "$module_id" ] && usage
            if [ "$trial_flag" = "--trial" ]; then
                cmd_deploy "$module_id" "true"
            else
                cmd_deploy "$module_id" "false"
            fi
            ;;
        list)
            local bundle=""
            if [ "${1:-}" = "--bundle" ]; then
                bundle="${2:-}"
            fi
            cmd_list "$bundle"
            ;;
        status)
            [ -z "${1:-}" ] && usage
            cmd_status "$1"
            ;;
        remove)
            [ -z "${1:-}" ] && usage
            cmd_remove "$1"
            ;;
        check-trials)
            cmd_check_trials
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"
