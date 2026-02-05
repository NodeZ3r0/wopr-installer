#!/bin/bash
#=================================================
# WOPR COMMON HELPER FUNCTIONS
# Version: 1.5
# Purpose: Shared utilities for all WOPR installer scripts
# License: AGPL-3.0
#=================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#=================================================
# LOGGING
#=================================================

WOPR_LOG_FILE="/var/log/wopr/installer.log"

wopr_log() {
    local level="${1:-INFO}"
    local message="${2:-}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    mkdir -p /var/log/wopr
    echo "[$timestamp] [$level] $message" >> "$WOPR_LOG_FILE"

    # Write to stderr so log output never contaminates command substitutions
    case "$level" in
        INFO)  echo -e "${BLUE}[INFO]${NC} $message" >&2 ;;
        OK)    echo -e "${GREEN}[OK]${NC} $message" >&2 ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" >&2 ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
        *)     echo "[$level] $message" >&2 ;;
    esac
}

wopr_die() {
    wopr_log "ERROR" "$1"
    exit 1
}

wopr_progress() {
    local step="$1"
    local total="${2:-1}"
    local message="$3"
    echo -e "${BLUE}[$step/$total]${NC} $message"
    wopr_log "INFO" "[$step/$total] $message"
}

#=================================================
# SYSTEM DETECTION
#=================================================

wopr_detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        WOPR_OS_ID="$ID"
        WOPR_OS_VERSION="$VERSION_ID"
        WOPR_OS_CODENAME="${VERSION_CODENAME:-}"
        wopr_log "INFO" "Detected OS: $WOPR_OS_ID $WOPR_OS_VERSION"
    else
        wopr_die "Cannot detect OS. /etc/os-release not found."
    fi
}

wopr_detect_arch() {
    WOPR_ARCH=$(uname -m)
    case "$WOPR_ARCH" in
        x86_64)  WOPR_ARCH="amd64" ;;
        aarch64) WOPR_ARCH="arm64" ;;
        *)       wopr_die "Unsupported architecture: $WOPR_ARCH" ;;
    esac
    wopr_log "INFO" "Detected architecture: $WOPR_ARCH"
}

wopr_detect_resources() {
    WOPR_CPU_COUNT=$(nproc)
    WOPR_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    WOPR_RAM_GB=$((WOPR_RAM_KB / 1024 / 1024))
    WOPR_DISK_GB=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')

    wopr_log "INFO" "Detected resources: ${WOPR_CPU_COUNT} vCPU, ${WOPR_RAM_GB}GB RAM, ${WOPR_DISK_GB}GB disk"
}

wopr_validate_resources() {
    local tier="$1"
    local required_cpu required_ram required_disk

    case "$tier" in
        low)       required_cpu=2;  required_ram=4;  required_disk=40 ;;
        medium)    required_cpu=4;  required_ram=8;  required_disk=80 ;;
        high)      required_cpu=8;  required_ram=16; required_disk=200 ;;
        very_high) required_cpu=16; required_ram=32; required_disk=500 ;;
        *)         wopr_die "Unknown resource tier: $tier" ;;
    esac

    local errors=0

    if [ "$WOPR_CPU_COUNT" -lt "$required_cpu" ]; then
        wopr_log "ERROR" "Insufficient CPU: have $WOPR_CPU_COUNT, need $required_cpu"
        errors=$((errors + 1))
    fi

    if [ "$WOPR_RAM_GB" -lt "$required_ram" ]; then
        wopr_log "ERROR" "Insufficient RAM: have ${WOPR_RAM_GB}GB, need ${required_ram}GB"
        errors=$((errors + 1))
    fi

    if [ "$WOPR_DISK_GB" -lt "$required_disk" ]; then
        wopr_log "ERROR" "Insufficient disk: have ${WOPR_DISK_GB}GB, need ${required_disk}GB"
        errors=$((errors + 1))
    fi

    if [ "$errors" -gt 0 ]; then
        return 1
    fi

    wopr_log "OK" "Resource validation passed for tier: $tier"
    return 0
}

#=================================================
# CONFIGURATION MANAGEMENT
#=================================================

WOPR_CONFIG_DIR="/etc/wopr"
WOPR_DATA_DIR="/var/lib/wopr"
WOPR_INSTALL_DIR="/opt/wopr"
WOPR_NETWORK="wopr-network"

wopr_setting_get() {
    local key="$1"
    local config_file="${WOPR_CONFIG_DIR}/settings.json"

    if [ -f "$config_file" ]; then
        jq -r ".$key // empty" "$config_file"
    fi
}

wopr_setting_set() {
    local key="$1"
    local value="$2"
    local config_file="${WOPR_CONFIG_DIR}/settings.json"

    mkdir -p "$WOPR_CONFIG_DIR"

    if [ ! -f "$config_file" ]; then
        echo '{}' > "$config_file"
    fi

    local tmp=$(mktemp)
    jq ".$key = \"$value\"" "$config_file" > "$tmp" && mv "$tmp" "$config_file"
    wopr_log "INFO" "Setting saved: $key"
}

wopr_instance_id() {
    local id_file="${WOPR_CONFIG_DIR}/instance_id"

    if [ -f "$id_file" ]; then
        cat "$id_file"
    else
        local new_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
        mkdir -p "$WOPR_CONFIG_DIR"
        echo "$new_id" > "$id_file"
        echo "$new_id"
    fi
}

#=================================================
# TEMPLATE RENDERING
#=================================================

wopr_render_template() {
    local template="$1"
    local destination="$2"

    if [ ! -f "$template" ]; then
        wopr_die "Template not found: $template"
    fi

    local content=$(cat "$template")

    # Replace WOPR placeholders
    content="${content//__INSTANCE_ID__/$(wopr_instance_id)}"
    content="${content//__INSTALL_DIR__/$WOPR_INSTALL_DIR}"
    content="${content//__DATA_DIR__/$WOPR_DATA_DIR}"
    content="${content//__CONFIG_DIR__/$WOPR_CONFIG_DIR}"
    content="${content//__DOMAIN__/$(wopr_setting_get domain)}"

    echo "$content" > "$destination"
    wopr_log "INFO" "Rendered template: $template -> $destination"
}

#=================================================
# SERVICE MANAGEMENT
#=================================================

wopr_systemd_add() {
    local service_name="$1"
    local template="${2:-}"

    if [ -n "$template" ]; then
        wopr_render_template "$template" "/etc/systemd/system/${service_name}.service"
    fi

    systemctl daemon-reload
    systemctl enable "$service_name"
    wopr_log "INFO" "Systemd service added: $service_name"
}

wopr_systemd_start() {
    local service_name="$1"
    systemctl start "$service_name"
    wopr_log "OK" "Service started: $service_name"
}

wopr_systemd_stop() {
    local service_name="$1"
    systemctl stop "$service_name" || true
    wopr_log "INFO" "Service stopped: $service_name"
}

wopr_systemd_remove() {
    local service_name="$1"
    systemctl stop "$service_name" 2>/dev/null || true
    systemctl disable "$service_name" 2>/dev/null || true
    rm -f "/etc/systemd/system/${service_name}.service"
    systemctl daemon-reload
    wopr_log "INFO" "Systemd service removed: $service_name"
}

#=================================================
# PODMAN / CONTAINER MANAGEMENT
#=================================================

wopr_container_pull() {
    local image="$1"
    podman pull "$image"
    wopr_log "INFO" "Pulled container image: $image"
}

wopr_container_run() {
    local name="$1"
    shift
    podman run -d --name "$name" "$@"
    wopr_log "OK" "Container started: $name"
}

wopr_container_stop() {
    local name="$1"
    podman stop "$name" 2>/dev/null || true
    podman rm "$name" 2>/dev/null || true
    wopr_log "INFO" "Container stopped: $name"
}

#=================================================
# CADDY MANAGEMENT (via API)
#=================================================

WOPR_CADDY_API="http://127.0.0.1:2019"

wopr_caddy_config_get() {
    curl -s "${WOPR_CADDY_API}/config/"
}

wopr_caddy_config_set() {
    local config_file="$1"
    curl -s -X POST "${WOPR_CADDY_API}/load" \
        -H "Content-Type: application/json" \
        -d @"$config_file"
    wopr_log "INFO" "Caddy configuration loaded"
}

wopr_caddy_snapshot() {
    local snapshot_dir="${WOPR_DATA_DIR}/caddy/snapshots"
    local timestamp=$(date '+%Y%m%d_%H%M%S')

    mkdir -p "$snapshot_dir"
    wopr_caddy_config_get > "${snapshot_dir}/${timestamp}.json"
    wopr_log "INFO" "Caddy config snapshot saved: ${timestamp}.json"
}

wopr_caddy_add_route() {
    # Add a reverse proxy route to Caddy
    # Usage: wopr_caddy_add_route <subdomain> <upstream_port> [upstream_host]
    local subdomain="$1"
    local upstream_port="$2"
    local upstream_host="${3:-127.0.0.1}"
    local domain=$(wopr_setting_get domain)

    if [ -z "$domain" ]; then
        wopr_die "Domain not configured. Cannot add Caddy route."
    fi

    local full_domain="${subdomain}.${domain}"
    local upstream="http://${upstream_host}:${upstream_port}"

    # Build the route configuration
    local route_config=$(cat <<EOF
{
    "@id": "wopr-${subdomain}",
    "match": [{"host": ["${full_domain}"]}],
    "handle": [{
        "handler": "reverse_proxy",
        "upstreams": [{"dial": "${upstream_host}:${upstream_port}"}]
    }],
    "terminal": true
}
EOF
)

    # Add route to Caddy via API
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        "${WOPR_CADDY_API}/config/apps/http/servers/srv0/routes" \
        -H "Content-Type: application/json" \
        -d "$route_config")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        wopr_log "OK" "Caddy route added: ${full_domain} -> ${upstream}"
        # Save route info for tracking
        wopr_setting_set "route_${subdomain}" "${upstream}"
    else
        wopr_log "WARN" "Failed to add Caddy route via API. Rebuilding Caddyfile..."
        wopr_caddy_rebuild_config
    fi
}

wopr_caddy_remove_route() {
    # Remove a route from Caddy by subdomain
    local subdomain="$1"

    local response=$(curl -s -w "\n%{http_code}" -X DELETE \
        "${WOPR_CADDY_API}/id/wopr-${subdomain}")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        wopr_log "OK" "Caddy route removed: ${subdomain}"
    else
        wopr_log "WARN" "Route not found or already removed: ${subdomain}"
    fi
}

wopr_caddy_list_routes() {
    # List all WOPR-managed routes
    curl -s "${WOPR_CADDY_API}/config/apps/http/servers/srv0/routes" | \
        jq -r '.[] | select(.["@id"] | startswith("wopr-")) | .["@id"]' 2>/dev/null || echo "No routes configured"
}

wopr_caddy_rebuild_config() {
    # Rebuild Caddyfile from settings and restart
    # This is the fallback method when API calls fail
    local domain=$(wopr_setting_get domain)
    local caddyfile="/etc/caddy/Caddyfile"

    cat > "$caddyfile" <<EOF
{
    admin 127.0.0.1:2019
    email admin@${domain}
}

# Default site
${domain} {
    respond "WOPR Sovereign Suite" 200
}

EOF

    # Add routes from settings
    local routes=$(grep -o '"route_[^"]*"' "${WOPR_CONFIG_DIR}/settings.json" 2>/dev/null | tr -d '"' || true)
    for route_key in $routes; do
        local subdomain="${route_key#route_}"
        local upstream=$(wopr_setting_get "$route_key")
        if [ -n "$upstream" ]; then
            cat >> "$caddyfile" <<EOF
${subdomain}.${domain} {
    reverse_proxy ${upstream}
}

EOF
        fi
    done

    systemctl reload caddy
    wopr_log "OK" "Caddy configuration rebuilt"
}

wopr_caddy_add_route_with_auth() {
    # Add a route with Authentik forward auth
    # Usage: wopr_caddy_add_route_with_auth <subdomain> <upstream_port> [upstream_host]
    local subdomain="$1"
    local upstream_port="$2"
    local upstream_host="${3:-127.0.0.1}"
    local domain=$(wopr_setting_get domain)
    local authentik_port=$(wopr_setting_get "authentik_port" || echo "9000")

    if [ -z "$domain" ]; then
        wopr_die "Domain not configured. Cannot add Caddy route."
    fi

    local full_domain="${subdomain}.${domain}"

    # Build route config with forward auth
    local route_config=$(cat <<EOF
{
    "@id": "wopr-${subdomain}",
    "match": [{"host": ["${full_domain}"]}],
    "handle": [
        {
            "handler": "forward_auth",
            "uri": "http://127.0.0.1:${authentik_port}/outpost.goauthentik.io/auth/caddy",
            "copy_headers": ["X-Authentik-Username", "X-Authentik-Groups", "X-Authentik-Email", "X-Authentik-Uid"]
        },
        {
            "handler": "reverse_proxy",
            "upstreams": [{"dial": "${upstream_host}:${upstream_port}"}]
        }
    ],
    "terminal": true
}
EOF
)

    local response=$(curl -s -w "\n%{http_code}" -X POST \
        "${WOPR_CADDY_API}/config/apps/http/servers/srv0/routes" \
        -H "Content-Type: application/json" \
        -d "$route_config")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        wopr_log "OK" "Caddy route with auth added: ${full_domain}"
        wopr_setting_set "route_${subdomain}" "http://${upstream_host}:${upstream_port}"
    else
        wopr_log "ERROR" "Failed to add authenticated Caddy route: ${full_domain}"
        return 1
    fi
}

#=================================================
# AUTHENTIK MANAGEMENT
#=================================================

WOPR_AUTHENTIK_API="http://127.0.0.1:9000/api/v3"
WOPR_AUTHENTIK_TOKEN=""

wopr_authentik_set_token() {
    # Set the API token for Authentik calls
    WOPR_AUTHENTIK_TOKEN="$1"
    wopr_setting_set "authentik_token" "$1"
}

wopr_authentik_get_token() {
    # Get the stored API token
    if [ -z "$WOPR_AUTHENTIK_TOKEN" ]; then
        WOPR_AUTHENTIK_TOKEN=$(wopr_setting_get "authentik_token")
    fi
    echo "$WOPR_AUTHENTIK_TOKEN"
}

wopr_authentik_api() {
    # Make an authenticated API call to Authentik
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"
    local token=$(wopr_authentik_get_token)

    if [ -z "$token" ]; then
        wopr_log "ERROR" "Authentik API token not configured"
        return 1
    fi

    local curl_args=(
        -s
        -X "$method"
        -H "Authorization: Bearer ${token}"
        -H "Content-Type: application/json"
        -H "Accept: application/json"
    )

    if [ -n "$data" ]; then
        curl_args+=(-d "$data")
    fi

    curl "${curl_args[@]}" "${WOPR_AUTHENTIK_API}${endpoint}"
}

wopr_authentik_wait_ready() {
    # Wait for Authentik to be ready
    local timeout="${1:-120}"
    local count=0

    wopr_log "INFO" "Waiting for Authentik to be ready..."

    while [ "$count" -lt "$timeout" ]; do
        # Try container-direct first (avoids netavark port forwarding issues)
        if podman exec wopr-authentik-server curl -s http://localhost:9000/-/health/ready/ 2>/dev/null | grep -q "ok"; then
            wopr_log "OK" "Authentik is ready"
            return 0
        fi
        # Fallback to host port
        if curl -s "http://127.0.0.1:9000/-/health/ready/" 2>/dev/null | grep -q "ok"; then
            wopr_log "OK" "Authentik is ready (via host port)"
            return 0
        fi
        sleep 2
        count=$((count + 2))
    done

    wopr_log "ERROR" "Timeout waiting for Authentik"
    return 1
}

wopr_authentik_create_provider() {
    # Create an OAuth2/OpenID Connect provider
    # Usage: wopr_authentik_create_provider <name> <client_id> <redirect_uri>
    local name="$1"
    local client_id="$2"
    local redirect_uri="$3"
    local client_secret=$(wopr_random_string 64)

    # First, get the default authorization and invalidation flow UUIDs
    local auth_flow_uuid=""
    local invalidation_flow_uuid=""

    # Get authorization flow UUID (implicit consent)
    local flows_response=$(wopr_authentik_api GET "/flows/instances/?slug=default-provider-authorization-implicit-consent")
    auth_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')

    # Get invalidation flow UUID
    flows_response=$(wopr_authentik_api GET "/flows/instances/?slug=default-provider-invalidation-flow")
    invalidation_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')

    # If we can't find the flows, try default slugs
    if [ -z "$auth_flow_uuid" ]; then
        flows_response=$(wopr_authentik_api GET "/flows/instances/?designation=authorization")
        auth_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')
    fi
    if [ -z "$invalidation_flow_uuid" ]; then
        flows_response=$(wopr_authentik_api GET "/flows/instances/?designation=invalidation")
        invalidation_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')
    fi

    # Build provider data with correct redirect_uris format (array of objects)
    local provider_data=$(cat <<EOF
{
    "name": "${name}",
    "authorization_flow": "${auth_flow_uuid}",
    "invalidation_flow": "${invalidation_flow_uuid}",
    "client_type": "confidential",
    "client_id": "${client_id}",
    "client_secret": "${client_secret}",
    "redirect_uris": [{"matching_mode": "strict", "url": "${redirect_uri}"}],
    "signing_key": null,
    "access_code_validity": "minutes=1",
    "access_token_validity": "minutes=5",
    "refresh_token_validity": "days=30",
    "sub_mode": "hashed_user_id",
    "include_claims_in_id_token": true
}
EOF
)

    local response=$(wopr_authentik_api POST "/providers/oauth2/" "$provider_data")
    local provider_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$provider_pk" ]; then
        wopr_log "OK" "Authentik OAuth2 provider created: ${name} (pk=${provider_pk})"
        # Store the client secret for the app
        wopr_setting_set "authentik_${client_id}_secret" "$client_secret"
        echo "$provider_pk"
    else
        # Check if provider already exists
        local error_msg=$(echo "$response" | jq -r '.client_id[0] // .name[0] // .detail // empty')
        if echo "$error_msg" | grep -qi "already exists\|unique"; then
            wopr_log "INFO" "Provider already exists: ${name}, looking up existing pk..."
            local existing=$(wopr_authentik_api GET "/providers/oauth2/?client_id=${client_id}")
            provider_pk=$(echo "$existing" | jq -r '.results[0].pk // empty')
            if [ -n "$provider_pk" ]; then
                wopr_log "OK" "Found existing provider: ${name} (pk=${provider_pk})"
                echo "$provider_pk"
                return 0
            fi
        fi
        wopr_log "ERROR" "Failed to create Authentik provider: ${name}"
        echo "$response" | jq -r '.detail // .non_field_errors // .' >&2
        return 1
    fi
}

wopr_authentik_create_app() {
    # Create an application in Authentik
    # Usage: wopr_authentik_create_app <name> <slug> <provider_pk> <launch_url>
    local name="$1"
    local slug="$2"
    local provider_pk="$3"
    local launch_url="$4"

    local app_data=$(cat <<EOF
{
    "name": "${name}",
    "slug": "${slug}",
    "provider": ${provider_pk},
    "meta_launch_url": "${launch_url}",
    "open_in_new_tab": true
}
EOF
)

    local response=$(wopr_authentik_api POST "/core/applications/" "$app_data")
    local app_slug=$(echo "$response" | jq -r '.slug // empty')

    if [ -n "$app_slug" ]; then
        wopr_log "OK" "Authentik application created: ${name}"
        echo "$app_slug"
    else
        wopr_log "ERROR" "Failed to create Authentik app: ${name}"
        echo "$response" | jq -r '.detail // .non_field_errors // .' >&2
        return 1
    fi
}

wopr_authentik_register_app() {
    # Complete flow: create provider + app for an application
    # Usage: wopr_authentik_register_app <app_name> <app_slug> <subdomain>
    local app_name="$1"
    local app_slug="$2"
    local subdomain="$3"
    local domain=$(wopr_setting_get domain)

    local client_id="wopr-${app_slug}"
    local app_url="https://${subdomain}.${domain}"
    local redirect_uri="${app_url}/oauth/callback"

    wopr_log "INFO" "Registering ${app_name} with Authentik SSO..."

    # Create the OAuth2 provider
    local provider_pk=$(wopr_authentik_create_provider "${app_name} Provider" "$client_id" "$redirect_uri")
    if [ -z "$provider_pk" ]; then
        return 1
    fi

    # Create the application
    local result=$(wopr_authentik_create_app "$app_name" "$app_slug" "$provider_pk" "$app_url")
    if [ -z "$result" ]; then
        return 1
    fi

    # Store app info for later use
    wopr_setting_set "authentik_app_${app_slug}_client_id" "$client_id"
    wopr_setting_set "authentik_app_${app_slug}_provider_pk" "$provider_pk"

    wopr_log "OK" "App registered with Authentik: ${app_name} at ${app_url}"
}

wopr_authentik_create_group() {
    # Create a group in Authentik
    local group_name="$1"

    local group_data=$(cat <<EOF
{
    "name": "${group_name}",
    "is_superuser": false
}
EOF
)

    local response=$(wopr_authentik_api POST "/core/groups/" "$group_data")
    local group_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$group_pk" ]; then
        wopr_log "OK" "Authentik group created: ${group_name}"
        echo "$group_pk"
    else
        # Group might already exist
        wopr_log "INFO" "Group may already exist: ${group_name}"
    fi
}

wopr_authentik_add_user_to_group() {
    # Add a user to a group
    local user_pk="$1"
    local group_name="$2"

    # Get group pk by name
    local group_pk=$(wopr_authentik_api GET "/core/groups/?name=${group_name}" | jq -r '.results[0].pk // empty')

    if [ -z "$group_pk" ]; then
        wopr_log "ERROR" "Group not found: ${group_name}"
        return 1
    fi

    local response=$(wopr_authentik_api POST "/core/groups/${group_pk}/add_user/" "{\"pk\": ${user_pk}}")
    wopr_log "OK" "User ${user_pk} added to group ${group_name}"
}

wopr_authentik_setup_wopr_groups() {
    # Create standard WOPR groups
    local bundle=$(wopr_setting_get bundle)

    wopr_log "INFO" "Setting up WOPR groups in Authentik..."

    # Bundle groups
    wopr_authentik_create_group "wopr-personal"
    wopr_authentik_create_group "wopr-creator"
    wopr_authentik_create_group "wopr-developer"
    wopr_authentik_create_group "wopr-professional"

    # App access groups
    wopr_authentik_create_group "nextcloud-users"
    wopr_authentik_create_group "vaultwarden-users"
    wopr_authentik_create_group "freshrss-users"

    # DEFCON ONE roles
    wopr_authentik_create_group "defcon-observers"
    wopr_authentik_create_group "defcon-contributors"
    wopr_authentik_create_group "defcon-operators"

    wopr_log "OK" "WOPR groups created in Authentik"
}

wopr_authentik_create_user() {
    # Create a user in Authentik
    # Usage: wopr_authentik_create_user <username> <email> <name> [password]
    local username="$1"
    local email="$2"
    local name="$3"
    local password="${4:-$(wopr_random_string 24)}"

    local user_data=$(cat <<EOF
{
    "username": "${username}",
    "name": "${name}",
    "email": "${email}",
    "is_active": true,
    "groups": []
}
EOF
)

    local response=$(wopr_authentik_api POST "/core/users/" "$user_data")
    local user_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$user_pk" ]; then
        wopr_log "OK" "Authentik user created: ${username} (pk=${user_pk})"

        # Set the user's password
        local password_data=$(cat <<EOF
{
    "password": "${password}"
}
EOF
)
        wopr_authentik_api POST "/core/users/${user_pk}/set_password/" "$password_data"

        # Store password for display
        wopr_setting_set "user_${username}_password" "$password"
        echo "$user_pk"
    else
        local error=$(echo "$response" | jq -r '.username[0] // .detail // "Unknown error"')
        if echo "$error" | grep -qi "already exists"; then
            wopr_log "INFO" "User already exists: ${username}"
            # Get existing user pk
            local existing=$(wopr_authentik_api GET "/core/users/?username=${username}")
            echo "$existing" | jq -r '.results[0].pk // empty'
        else
            wopr_log "ERROR" "Failed to create user: ${username} - ${error}"
            return 1
        fi
    fi
}

wopr_authentik_setup_initial_user() {
    # Create the initial owner/admin user for the WOPR instance
    local admin_email=$(wopr_setting_get "admin_email")
    local domain=$(wopr_setting_get "domain")
    local bundle=$(wopr_setting_get "bundle")

    if [ -z "$admin_email" ]; then
        admin_email="admin@${domain}"
    fi

    # Extract username from email
    local username="${admin_email%%@*}"
    local name="${username^}"  # Capitalize first letter

    wopr_log "INFO" "Creating initial WOPR user: ${username}"

    local user_pk=$(wopr_authentik_create_user "$username" "$admin_email" "$name WOPR Admin")

    if [ -n "$user_pk" ]; then
        # Add to appropriate bundle group
        wopr_authentik_add_user_to_group "$user_pk" "wopr-${bundle}"

        # Add to app access groups based on bundle
        wopr_authentik_add_user_to_group "$user_pk" "nextcloud-users"
        wopr_authentik_add_user_to_group "$user_pk" "vaultwarden-users"
        wopr_authentik_add_user_to_group "$user_pk" "freshrss-users"

        wopr_setting_set "wopr_user_pk" "$user_pk"
        wopr_setting_set "wopr_username" "$username"

        local password=$(wopr_setting_get "user_${username}_password")
        wopr_log "OK" "Initial WOPR user created"
        wopr_log "INFO" "Login: ${username} / ${password}"
    fi
}

#=================================================
# BACKUP / SNAPSHOT
#=================================================

wopr_snapshot_create() {
    local name="${1:-manual}"
    local snapshot_dir="${WOPR_DATA_DIR}/snapshots"
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local snapshot_path="${snapshot_dir}/${timestamp}_${name}"

    mkdir -p "$snapshot_path"

    # Save current state
    cp -r "$WOPR_CONFIG_DIR" "${snapshot_path}/config"
    wopr_caddy_snapshot

    # Save container states
    podman ps -a --format json > "${snapshot_path}/containers.json"

    wopr_log "OK" "Snapshot created: $snapshot_path"
    echo "$snapshot_path"
}

wopr_snapshot_restore() {
    local snapshot_path="$1"

    if [ ! -d "$snapshot_path" ]; then
        wopr_die "Snapshot not found: $snapshot_path"
    fi

    wopr_log "INFO" "Restoring snapshot: $snapshot_path"
    # Restore implementation here
}

#=================================================
# DEFCON ONE INTEGRATION
#=================================================

WOPR_DEFCON_URL="${WOPR_DEFCON_URL:-}"

wopr_defcon_log() {
    local action="$1"
    local details="${2:-}"

    local entry=$(jq -n \
        --arg instance "$(wopr_instance_id)" \
        --arg action "$action" \
        --arg details "$details" \
        --arg timestamp "$(date -Iseconds)" \
        '{instance: $instance, action: $action, details: $details, timestamp: $timestamp}')

    # Local audit log
    mkdir -p "${WOPR_DATA_DIR}/audit"
    echo "$entry" >> "${WOPR_DATA_DIR}/audit/actions.jsonl"

    # Remote log if configured
    if [ -n "$WOPR_DEFCON_URL" ]; then
        curl -s -X POST "${WOPR_DEFCON_URL}/api/audit" \
            -H "Content-Type: application/json" \
            -d "$entry" || true
    fi
}

wopr_require_confirmation() {
    local action="$1"
    local message="${2:-Proceed with $action?}"

    wopr_defcon_log "CONFIRMATION_REQUESTED" "$action"

    echo -e "${YELLOW}[CONFIRMATION REQUIRED]${NC} $message"
    read -p "Type 'yes' to confirm: " response

    if [ "$response" != "yes" ]; then
        wopr_defcon_log "CONFIRMATION_DENIED" "$action"
        wopr_die "User declined: $action"
    fi

    wopr_defcon_log "CONFIRMATION_GRANTED" "$action"
}

#=================================================
# UTILITY FUNCTIONS
#=================================================

wopr_random_string() {
    local length="${1:-32}"
    tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c "$length"
}

wopr_wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout="${3:-30}"

    local count=0
    while [ "$count" -lt "$timeout" ]; do
        # Try nc first, then bash /dev/tcp as fallback
        if nc -z "$host" "$port" 2>/dev/null; then
            wopr_log "OK" "Port $host:$port is ready"
            return 0
        fi
        if (echo > "/dev/tcp/${host}/${port}") 2>/dev/null; then
            wopr_log "OK" "Port $host:$port is ready (tcp check)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    wopr_log "ERROR" "Timeout waiting for $host:$port"
    return 1
}

wopr_download() {
    local url="$1"
    local dest="$2"

    curl -fsSL "$url" -o "$dest"
    wopr_log "INFO" "Downloaded: $url -> $dest"
}

#=================================================
# INITIALIZATION
#=================================================

wopr_init() {
    wopr_detect_os
    wopr_detect_arch
    wopr_detect_resources

    mkdir -p "$WOPR_CONFIG_DIR"
    mkdir -p "$WOPR_DATA_DIR"
    mkdir -p "$WOPR_INSTALL_DIR"
    mkdir -p /var/log/wopr

    wopr_log "INFO" "WOPR common helpers initialized"
}

# Auto-init when sourced
wopr_init
