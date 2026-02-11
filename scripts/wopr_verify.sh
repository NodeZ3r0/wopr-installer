#!/bin/bash
#=================================================
# WOPR VERIFICATION SCRIPT
# Version: 1.0
# Purpose: Verify WOPR installation is working correctly
# License: AGPL-3.0
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/wopr_common.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

check_pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    PASS=$((PASS + 1))
}

check_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    FAIL=$((FAIL + 1))
}

check_warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    WARN=$((WARN + 1))
}

#=================================================
# CHECKS
#=================================================

check_settings() {
    echo ""
    echo "Checking WOPR settings..."

    local domain=$(wopr_setting_get "domain")
    if [ -n "$domain" ]; then
        check_pass "Domain configured: $domain"
    else
        check_fail "Domain not configured"
    fi

    local bundle=$(wopr_setting_get "bundle")
    if [ -n "$bundle" ]; then
        check_pass "Bundle configured: $bundle"
    else
        check_fail "Bundle not configured"
    fi

    local install_complete=$(wopr_setting_get "install_complete")
    if [ "$install_complete" = "true" ]; then
        check_pass "Installation marked complete"
    else
        check_fail "Installation not marked complete"
    fi
}

check_services() {
    echo ""
    echo "Checking system services..."

    # Caddy
    if systemctl is-active --quiet caddy; then
        check_pass "Caddy is running"
    else
        check_fail "Caddy is not running"
    fi

    # Dashboard API
    if systemctl is-active --quiet wopr-dashboard-api 2>/dev/null; then
        check_pass "Dashboard API is running"
    else
        check_warn "Dashboard API is not running (may not be installed)"
    fi
}

check_containers() {
    echo ""
    echo "Checking containers..."

    local containers=(
        "wopr-postgresql"
        "wopr-redis"
        "wopr-authentik-server"
        "wopr-authentik-worker"
        "wopr-nextcloud"
        "wopr-vaultwarden"
        "wopr-freshrss"
    )

    for container in "${containers[@]}"; do
        local status=$(podman inspect --format '{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
        if [ "$status" = "running" ]; then
            check_pass "$container is running"
        elif [ "$status" = "not found" ]; then
            check_warn "$container not found (may not be installed)"
        else
            check_fail "$container status: $status"
        fi
    done
}

check_ports() {
    echo ""
    echo "Checking port availability..."

    local ports=(
        "80:Caddy HTTP"
        "443:Caddy HTTPS"
        "2019:Caddy Admin API"
        "5432:PostgreSQL"
        "6379:Redis"
        "9000:Authentik"
        "8080:Nextcloud"
        "8081:Vaultwarden"
        "8082:FreshRSS"
        "8090:Dashboard API"
    )

    for port_info in "${ports[@]}"; do
        local port="${port_info%%:*}"
        local name="${port_info#*:}"

        if nc -z 127.0.0.1 "$port" 2>/dev/null; then
            check_pass "Port $port ($name) is listening"
        else
            check_warn "Port $port ($name) is not listening"
        fi
    done
}

check_web_endpoints() {
    echo ""
    echo "Checking web endpoints..."

    local domain=$(wopr_setting_get "domain")
    if [ -z "$domain" ]; then
        check_fail "Cannot check endpoints: domain not configured"
        return
    fi

    # Check if we can resolve the domain locally
    # In development, we might need to use localhost
    local test_host="127.0.0.1"

    # Caddy Admin API
    local caddy_status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:2019/config/" 2>/dev/null || echo "000")
    if [ "$caddy_status" = "200" ]; then
        check_pass "Caddy Admin API responding (HTTP $caddy_status)"
    else
        check_fail "Caddy Admin API not responding (HTTP $caddy_status)"
    fi

    # Dashboard API
    local dashboard_status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8090/api/status" 2>/dev/null || echo "000")
    if [ "$dashboard_status" = "200" ]; then
        check_pass "Dashboard API responding (HTTP $dashboard_status)"
    else
        check_warn "Dashboard API not responding (HTTP $dashboard_status)"
    fi

    # Authentik
    local authentik_status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:9000/-/health/live/" 2>/dev/null || echo "000")
    if [ "$authentik_status" = "200" ] || [ "$authentik_status" = "204" ]; then
        check_pass "Authentik responding (HTTP $authentik_status)"
    else
        check_warn "Authentik not responding (HTTP $authentik_status)"
    fi
}

check_data_directories() {
    echo ""
    echo "Checking data directories..."

    local dirs=(
        "/var/lib/wopr"
        "/var/lib/wopr/postgresql/data"
        "/var/lib/wopr/redis/data"
        "/var/lib/wopr/authentik"
        "/var/lib/wopr/nextcloud"
        "/var/lib/wopr/vaultwarden"
        "/var/lib/wopr/freshrss"
        "/var/www/wopr-dashboard"
    )

    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            check_pass "Directory exists: $dir"
        else
            check_warn "Directory missing: $dir"
        fi
    done
}

check_ssl() {
    echo ""
    echo "Checking SSL configuration..."

    local domain=$(wopr_setting_get "domain")
    if [ -z "$domain" ]; then
        check_warn "Cannot check SSL: domain not configured"
        return
    fi

    # Check if certificates exist in Caddy data
    local caddy_cert_dir="/var/lib/caddy/.local/share/caddy/certificates"
    if [ -d "$caddy_cert_dir" ]; then
        local cert_count=$(find "$caddy_cert_dir" -name "*.crt" 2>/dev/null | wc -l)
        if [ "$cert_count" -gt 0 ]; then
            check_pass "Found $cert_count SSL certificate(s)"
        else
            check_warn "No SSL certificates found yet (will be generated on first access)"
        fi
    else
        check_warn "Caddy certificate directory not found"
    fi
}

check_logs() {
    echo ""
    echo "Checking logs for errors..."

    local log_file="/var/log/wopr/installer.log"
    if [ -f "$log_file" ]; then
        local error_count=$(grep -c "\[ERROR\]" "$log_file" 2>/dev/null || echo "0")
        if [ "$error_count" -eq 0 ]; then
            check_pass "No errors in installer log"
        else
            check_warn "Found $error_count error(s) in installer log"
        fi
    else
        check_warn "Installer log not found"
    fi

    # Check container logs for recent errors
    for container in wopr-postgresql wopr-authentik-server; do
        local container_errors=$(podman logs --tail 100 "$container" 2>&1 | grep -ci "error" || echo "0")
        if [ "$container_errors" -lt 5 ]; then
            check_pass "$container logs look healthy"
        else
            check_warn "$container has $container_errors error mentions in recent logs"
        fi
    done
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
    echo "  Installation Verification"
    echo ""

    check_settings
    check_services
    check_containers
    check_ports
    check_web_endpoints
    check_data_directories
    check_ssl
    check_logs

    echo ""
    echo "============================================"
    echo "  VERIFICATION SUMMARY"
    echo "============================================"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}  $PASS"
    echo -e "  ${RED}Failed:${NC}  $FAIL"
    echo -e "  ${YELLOW}Warnings:${NC} $WARN"
    echo ""

    if [ "$FAIL" -eq 0 ]; then
        echo -e "  ${GREEN}Installation appears healthy!${NC}"
        exit 0
    else
        echo -e "  ${RED}Some checks failed. Review the output above.${NC}"
        exit 1
    fi
}

main "$@"
