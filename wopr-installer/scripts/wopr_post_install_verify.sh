#\!/bin/bash
#=================================================
# WOPR POST-INSTALL VERIFICATION SCRIPT
# Version: 2.0
# Purpose: Verify services and HTTPS endpoints before completion callback
# License: AGPL-3.0
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/wopr_common.sh"

BOOTSTRAP_FILE="/opt/wopr/bootstrap.json"

VERIFY_PASSED=0
VERIFY_FAILED=0
VERIFY_WARNINGS=0
FAILED_SERVICES=()
FAILED_ENDPOINTS=()
REMEDIATION_ATTEMPTED=false

get_orchestrator_url() {
    if [ -f "$BOOTSTRAP_FILE" ]; then
        jq -r ".orchestrator_url // empty" "$BOOTSTRAP_FILE" 2>/dev/null || echo ""
    fi
}

get_job_id() {
    if [ -f "$BOOTSTRAP_FILE" ]; then
        jq -r ".job_id // empty" "$BOOTSTRAP_FILE" 2>/dev/null || echo ""
    fi
}

report_verification_status() {
    local status="$1"
    local message="$2"
    local orc_url=$(get_orchestrator_url)
    local job_id=$(get_job_id)
    if [ -n "$orc_url" ] && [ -n "$job_id" ]; then
        curl -sf -X POST "${orc_url}/api/v1/provision/${job_id}/status"             -H "Content-Type: application/json"             -d "{\"status\": \"verifying\", \"phase\": \"$status\", \"message\": \"$message\"}"             2>/dev/null || true
    fi
    wopr_log "VERIFY" "$status: $message"
}

report_verification_failure() {
    local failures="$1"
    local orc_url=$(get_orchestrator_url)
    local job_id=$(get_job_id)
    if [ -n "$orc_url" ] && [ -n "$job_id" ]; then
        curl -sf -X POST "${orc_url}/api/v1/provision/${job_id}/verification-failed"             -H "Content-Type: application/json"             -d "{\"status\": \"verification_failed\", \"failed_checks\": $VERIFY_FAILED, \"failures\": \"$failures\", \"remediation_attempted\": $REMEDIATION_ATTEMPTED}"             2>/dev/null || true
    fi
}

trigger_support_plane_remediation() {
    local service="$1"
    local action="${2:-restart}"
    local orc_url=$(get_orchestrator_url)
    local job_id=$(get_job_id)
    wopr_log "REMEDIATE" "Requesting remediation for $service ($action)"
    REMEDIATION_ATTEMPTED=true
    if [ -n "$orc_url" ] && [ -n "$job_id" ]; then
        curl -sf -X POST "${orc_url}/api/v1/provision/${job_id}/remediate"             -H "Content-Type: application/json"             -d "{\"action\": \"remediate\", \"service\": \"$service\", \"operation\": \"$action\"}"             2>/dev/null || true
    fi
    case "$service" in
        caddy) systemctl restart caddy 2>/dev/null || true ;;
        wopr-*) systemctl restart "$service" 2>/dev/null || true ;;
        *) podman container exists "$service" 2>/dev/null && podman restart "$service" 2>/dev/null || true ;;
    esac
    sleep 5
}

verify_pass() { wopr_log "OK" "[PASS] $1"; VERIFY_PASSED=$((VERIFY_PASSED + 1)); }
verify_fail() { wopr_log "ERROR" "[FAIL] $1"; VERIFY_FAILED=$((VERIFY_FAILED + 1)); }
verify_warn() { wopr_log "WARN" "[WARN] $1"; VERIFY_WARNINGS=$((VERIFY_WARNINGS + 1)); }

verify_systemd_services() {
    report_verification_status "services" "Checking systemd services"
    local services=("caddy" "wopr-dashboard-api")
    for svc in "${services[@]}"; do
        if systemctl is-enabled "$svc" 2>/dev/null | grep -q "enabled\|static"; then
            if systemctl is-active --quiet "$svc" 2>/dev/null; then
                verify_pass "Service $svc is running"
            else
                verify_fail "Service $svc is not running"
                FAILED_SERVICES+=("$svc")
            fi
        fi
    done
}

verify_container_services() {
    report_verification_status "containers" "Checking container services"
    local installed_modules=()
    while IFS= read -r -d "" setting_file; do
        local setting_name="$(basename "$setting_file" .conf)"
        if [[ "$setting_name" =~ ^module_.*_installed$ ]]; then
            local value="$(cat "$setting_file" 2>/dev/null)"
            if [ "$value" = "true" ]; then
                local module_name="$(echo "$setting_name" | sed "s/^module_//; s/_installed$//" | tr "_" "-")"
                installed_modules+=("$module_name")
            fi
        fi
    done < <(find /opt/wopr/settings -name "*.conf" -print0 2>/dev/null)

    declare -A module_containers=(
        ["postgresql"]="wopr-postgresql"
        ["redis"]="wopr-redis"
        ["authentik"]="wopr-authentik-server wopr-authentik-worker"
        ["nextcloud"]="wopr-nextcloud"
        ["vaultwarden"]="wopr-vaultwarden"
        ["freshrss"]="wopr-freshrss"
        ["ntfy"]="wopr-ntfy"
        ["uptime-kuma"]="wopr-uptime-kuma"
        ["prometheus"]="wopr-prometheus"
        ["grafana"]="wopr-grafana"
        ["loki"]="wopr-loki"
        ["mealie"]="wopr-mealie"
        ["jellyfin"]="wopr-jellyfin"
        ["home-assistant"]="wopr-home-assistant"
        ["n8n"]="wopr-n8n"
        ["minio"]="wopr-minio"
        ["registry"]="wopr-registry"
    )

    for module in "${installed_modules[@]}"; do
        local containers="${module_containers[$module]:-wopr-$module}"
        for container in $containers; do
            local status="$(podman inspect --format "{{.State.Status}}" "$container" 2>/dev/null || echo "not found")"
            if [ "$status" = "running" ]; then
                verify_pass "Container $container is running"
            elif [ "$status" = "not found" ]; then
                continue
            else
                verify_fail "Container $container status: $status"
                FAILED_SERVICES+=("$container")
            fi
        done
    done
}

verify_https_endpoints() {
    report_verification_status "endpoints" "Checking HTTPS endpoints"
    local domain="$(wopr_setting_get "domain" 2>/dev/null || echo "")"
    if [ -z "$domain" ]; then
        verify_warn "Cannot check HTTPS endpoints: domain not configured"
        return
    fi

    declare -A app_subdomains=(
        ["authentik"]="auth"
        ["nextcloud"]="cloud"
        ["vaultwarden"]="vault"
        ["freshrss"]="rss"
        ["ntfy"]="ntfy"
        ["uptime-kuma"]="status"
        ["prometheus"]="metrics"
        ["grafana"]="grafana"
        ["mealie"]="recipes"
        ["immich"]="photos"
        ["jellyfin"]="media"
        ["home-assistant"]="home"
        ["n8n"]="auto"
        ["registry"]="registry"
    )

    check_https_endpoint "dashboard.${domain}" "/" "dashboard"

    while IFS= read -r -d "" setting_file; do
        local value="$(cat "$setting_file" 2>/dev/null)"
        if [ "$value" = "true" ]; then
            local setting_name="$(basename "$setting_file" .conf)"
            local module_name="$(echo "$setting_name" | sed "s/^module_//; s/_installed$//" | tr "_" "-")"
            local subdomain="${app_subdomains[$module_name]:-}"
            if [ -n "$subdomain" ]; then
                check_https_endpoint "${subdomain}.${domain}" "/" "$module_name"
            fi
        fi
    done < <(find /opt/wopr/settings -name "module_*_installed.conf" -print0 2>/dev/null)
}

check_https_endpoint() {
    local url="$1"
    local path="${2:-/}"
    local service_name="$3"
    local max_retries=3
    local retry_delay=5

    for ((i=1; i<=max_retries; i++)); do
        local http_code="$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout 10 --max-time 30 -k \
            "https://${url}${path}" 2>/dev/null || echo "000")"

        case "$http_code" in
            000)
                if [ $i -lt $max_retries ]; then
                    wopr_log "WARN" "Connection to https://${url} failed, retry $i/$max_retries..."
                    sleep $retry_delay; continue
                fi
                verify_fail "https://${url} - Connection failed"
                FAILED_ENDPOINTS+=("$service_name:$url")
                return 1
                ;;
            502|503|504)
                if [ $i -lt $max_retries ]; then
                    wopr_log "WARN" "https://${url} returned $http_code, retry $i/$max_retries..."
                    sleep $retry_delay; continue
                fi
                verify_fail "https://${url} - HTTP $http_code"
                FAILED_ENDPOINTS+=("$service_name:$url:$http_code")
                return 1
                ;;
            200|301|302|303|307|308|401|403)
                verify_pass "https://${url} - HTTP $http_code"
                return 0
                ;;
            *)
                verify_pass "https://${url} - HTTP $http_code"
                return 0
                ;;
        esac
    done
}

attempt_remediation() {
    if [ ${#FAILED_SERVICES[@]} -eq 0 ] && [ ${#FAILED_ENDPOINTS[@]} -eq 0 ]; then
        return 0
    fi
    report_verification_status "remediation" "Attempting to remediate ${#FAILED_SERVICES[@]} services and ${#FAILED_ENDPOINTS[@]} endpoints"
    for service in "${FAILED_SERVICES[@]}"; do
        trigger_support_plane_remediation "$service" "restart"
    done
    for endpoint_info in "${FAILED_ENDPOINTS[@]}"; do
        local service_name="$(echo "$endpoint_info" | cut -d: -f1)"
        local container_name="wopr-${service_name}"
        if podman container exists "$container_name" 2>/dev/null; then
            trigger_support_plane_remediation "$container_name" "restart"
        fi
    done
    sleep 10
    return 0
}

reverify_failed() {
    if [ ${#FAILED_SERVICES[@]} -eq 0 ] && [ ${#FAILED_ENDPOINTS[@]} -eq 0 ]; then
        return 0
    fi
    wopr_log "INFO" "Re-verifying after remediation..."
    local still_failed=0
    for service in "${FAILED_SERVICES[@]}"; do
        if [[ "$service" == wopr-* ]] && podman container exists "$service" 2>/dev/null; then
            local status="$(podman inspect --format "{{.State.Status}}" "$service" 2>/dev/null || echo "not found")"
            if [ "$status" \!= "running" ]; then
                still_failed=$((still_failed + 1))
            fi
        elif systemctl is-enabled "$service" 2>/dev/null | grep -q "enabled\|static"; then
            if \! systemctl is-active --quiet "$service" 2>/dev/null; then
                still_failed=$((still_failed + 1))
            fi
        fi
    done
    for endpoint_info in "${FAILED_ENDPOINTS[@]}"; do
        local url="$(echo "$endpoint_info" | cut -d: -f2)"
        local http_code="$(curl -s -o /dev/null -w "%{http_code}"             --connect-timeout 5 --max-time 15 -k             "https://${url}/" 2>/dev/null || echo "000")"
        if [ "$http_code" = "000" ] || [ "$http_code" = "502" ] || [ "$http_code" = "503" ] || [ "$http_code" = "504" ]; then
            still_failed=$((still_failed + 1))
        fi
    done
    return $still_failed
}

run_post_install_verification() {
    wopr_log "INFO" "Starting post-install verification..."
    report_verification_status "started" "Post-install verification started"

    verify_systemd_services
    verify_container_services
    verify_https_endpoints

    if [ ${#FAILED_SERVICES[@]} -gt 0 ] || [ ${#FAILED_ENDPOINTS[@]} -gt 0 ]; then
        wopr_log "WARN" "Found failures: ${#FAILED_SERVICES[@]} services, ${#FAILED_ENDPOINTS[@]} endpoints"
        attempt_remediation
        local still_failing=0
        still_failing=$(reverify_failed) || still_failing=$?
        if [ $still_failing -gt 0 ]; then
            wopr_log "ERROR" "$still_failing checks still failing after remediation"
            VERIFY_FAILED=$still_failing
        else
            wopr_log "OK" "All failures resolved after remediation"
            VERIFY_FAILED=0
        fi
    fi

    wopr_log "INFO" "Verification complete: $VERIFY_PASSED passed, $VERIFY_FAILED failed, $VERIFY_WARNINGS warnings"

    if [ $VERIFY_FAILED -gt 0 ]; then
        local failure_details="Services: ${FAILED_SERVICES[*]:-none}; Endpoints: ${FAILED_ENDPOINTS[*]:-none}"
        report_verification_failure "$failure_details"
        return 1
    fi

    report_verification_status "complete" "All verification checks passed"
    return 0
}

# Entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_post_install_verification
    exit $?
fi
