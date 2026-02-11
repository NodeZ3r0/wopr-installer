#!/bin/bash
#=================================================
# WOPR MODULE: NetBird
# Version: 1.0
# Purpose: Deploy NetBird WireGuard mesh VPN
# License: AGPL-3.0
#
# IMPORTANT: NetBird requires a management.json config file
# with a DataStoreEncryptionKey that must be a base64-encoded
# 32-byte key. Generate with: openssl rand -base64 32
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

NETBIRD_IMAGE="docker.io/netbirdio/management:latest"
NETBIRD_SIGNAL_IMAGE="docker.io/netbirdio/signal:latest"
NETBIRD_COTURN_IMAGE="docker.io/coturn/coturn:latest"
NETBIRD_DASHBOARD_IMAGE="docker.io/netbirdio/dashboard:latest"
NETBIRD_PORT=33073
NETBIRD_SIGNAL_PORT=10000
NETBIRD_DATA_DIR="${WOPR_DATA_DIR}/netbird"
NETBIRD_SERVICE_MGMT="wopr-netbird-management"
NETBIRD_SERVICE_SIGNAL="wopr-netbird-signal"
NETBIRD_SERVICE_DASHBOARD="wopr-netbird-dashboard"

wopr_deploy_netbird() {
    wopr_log "INFO" "Deploying NetBird VPN..."

    local domain=$(wopr_setting_get "domain")

    # Check if already installed
    if systemctl is-active --quiet "$NETBIRD_SERVICE_MGMT" 2>/dev/null; then
        wopr_log "INFO" "NetBird is already running"
        return 0
    fi

    # Create directories
    mkdir -p "${NETBIRD_DATA_DIR}/management"
    mkdir -p "${NETBIRD_DATA_DIR}/signal"
    mkdir -p "${NETBIRD_DATA_DIR}/letsencrypt"

    # Generate encryption key - MUST be base64-encoded 32 bytes
    # openssl rand -base64 32 produces a 44-char string that decodes to exactly 32 bytes
    local encryption_key=$(wopr_setting_get "netbird_encryption_key")
    if [ -z "$encryption_key" ]; then
        encryption_key=$(openssl rand -base64 32)
        wopr_setting_set "netbird_encryption_key" "$encryption_key"
        wopr_log "INFO" "Generated NetBird encryption key (base64 32-byte)"
    fi

    # Get Authentik OIDC configuration for NetBird
    local authentik_url="https://auth.${domain}"
    local client_id=$(wopr_setting_get "oidc_netbird_client_id")
    local client_secret=$(wopr_setting_get "oidc_netbird_client_secret")

    if [ -z "$client_id" ]; then
        client_id="wopr-netbird"
        client_secret=$(wopr_random_string 64)
        wopr_setting_set "oidc_netbird_client_id" "$client_id"
        wopr_setting_set "oidc_netbird_client_secret" "$client_secret"

        # Register with Authentik if available
        if systemctl is-active --quiet "wopr-authentik-server" 2>/dev/null; then
            wopr_authentik_register_app "NetBird VPN" "netbird" "vpn" || \
                wopr_log "WARN" "Authentik registration deferred for NetBird"
        fi
    fi

    # Create management.json config
    # The DataStoreEncryptionKey MUST be base64 that decodes to exactly 32 bytes
    cat > "${NETBIRD_DATA_DIR}/management.json" <<EOF
{
  "Stuns": [
    {
      "Proto": "udp",
      "URI": "stun:stun.${domain}:3478"
    }
  ],
  "TURNConfig": {
    "Turns": [
      {
        "Proto": "udp",
        "URI": "turn:turn.${domain}:3478",
        "Username": "wopr",
        "Password": "${client_secret:0:32}"
      }
    ],
    "CredentialsTTL": "12h",
    "Secret": "secret",
    "TimeBasedCredentials": false
  },
  "Signal": {
    "Proto": "https",
    "URI": "signal.${domain}:443"
  },
  "Datadir": "/var/lib/netbird/",
  "DataStoreEncryptionKey": "${encryption_key}",
  "HttpConfig": {
    "Address": "0.0.0.0:${NETBIRD_PORT}",
    "AuthIssuer": "${authentik_url}/application/o/netbird/",
    "AuthAudience": "${client_id}",
    "AuthKeysLocation": "${authentik_url}/application/o/netbird/jwks/",
    "AuthUserIDClaim": "",
    "CertFile": "",
    "CertKey": "",
    "IdpSignKeyRefreshEnabled": true,
    "OIDCConfigEndpoint": "${authentik_url}/application/o/netbird/.well-known/openid-configuration"
  },
  "IdpManagerConfig": {
    "ManagerType": "authentik",
    "ClientConfig": {
      "Issuer": "${authentik_url}/application/o/netbird/",
      "TokenEndpoint": "${authentik_url}/application/o/token/",
      "ClientID": "${client_id}",
      "ClientSecret": "${client_secret}",
      "GrantType": "client_credentials"
    },
    "ExtraConfig": {
      "Password": "",
      "Username": ""
    }
  },
  "DeviceAuthorizationFlow": {
    "Provider": "hosted",
    "ProviderConfig": {
      "Audience": "${client_id}",
      "ClientID": "${client_id}",
      "ClientSecret": "${client_secret}",
      "Domain": "auth.${domain}",
      "TokenEndpoint": "${authentik_url}/application/o/token/",
      "DeviceAuthEndpoint": "${authentik_url}/application/o/device/",
      "Scope": "openid profile email"
    }
  },
  "PKCEAuthorizationFlow": {
    "ProviderConfig": {
      "Audience": "${client_id}",
      "ClientID": "${client_id}",
      "ClientSecret": "${client_secret}",
      "AuthorizationEndpoint": "${authentik_url}/application/o/authorize/",
      "TokenEndpoint": "${authentik_url}/application/o/token/",
      "Scope": "openid profile email",
      "RedirectURLs": [
        "http://localhost:53000"
      ],
      "UseIDToken": false
    }
  }
}
EOF

    chmod 600 "${NETBIRD_DATA_DIR}/management.json"

    # Pull images
    wopr_log "INFO" "Pulling NetBird images..."
    wopr_container_pull "$NETBIRD_IMAGE"
    wopr_container_pull "$NETBIRD_SIGNAL_IMAGE"
    wopr_container_pull "$NETBIRD_DASHBOARD_IMAGE"

    # Create systemd service for NetBird Management
    cat > "/etc/systemd/system/${NETBIRD_SERVICE_MGMT}.service" <<EOF
[Unit]
Description=WOPR NetBird Management
After=network.target wopr-authentik-server.service
Wants=wopr-authentik-server.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_MGMT}
ExecStartPre=-/usr/bin/podman rm ${NETBIRD_SERVICE_MGMT}

ExecStart=/usr/bin/podman run --rm \\
    --name ${NETBIRD_SERVICE_MGMT} \\
    --network ${WOPR_NETWORK} \\
    -v ${NETBIRD_DATA_DIR}/management.json:/etc/netbird/management.json:ro \\
    -v ${NETBIRD_DATA_DIR}/management:/var/lib/netbird:Z \\
    -p 127.0.0.1:${NETBIRD_PORT}:${NETBIRD_PORT} \\
    ${NETBIRD_IMAGE} \\
    --config /etc/netbird/management.json

ExecStop=/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_MGMT}

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd service for NetBird Signal
    cat > "/etc/systemd/system/${NETBIRD_SERVICE_SIGNAL}.service" <<EOF
[Unit]
Description=WOPR NetBird Signal
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_SIGNAL}
ExecStartPre=-/usr/bin/podman rm ${NETBIRD_SERVICE_SIGNAL}

ExecStart=/usr/bin/podman run --rm \\
    --name ${NETBIRD_SERVICE_SIGNAL} \\
    --network ${WOPR_NETWORK} \\
    -v ${NETBIRD_DATA_DIR}/signal:/var/lib/netbird:Z \\
    -p 127.0.0.1:${NETBIRD_SIGNAL_PORT}:80 \\
    ${NETBIRD_SIGNAL_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_SIGNAL}

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd service for NetBird Dashboard
    cat > "/etc/systemd/system/${NETBIRD_SERVICE_DASHBOARD}.service" <<EOF
[Unit]
Description=WOPR NetBird Dashboard
After=network.target ${NETBIRD_SERVICE_MGMT}.service
Requires=${NETBIRD_SERVICE_MGMT}.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_DASHBOARD}
ExecStartPre=-/usr/bin/podman rm ${NETBIRD_SERVICE_DASHBOARD}

ExecStart=/usr/bin/podman run --rm \\
    --name ${NETBIRD_SERVICE_DASHBOARD} \\
    --network ${WOPR_NETWORK} \\
    -e NETBIRD_MGMT_API_ENDPOINT=https://vpn.${domain}:443 \\
    -e NETBIRD_MGMT_GRPC_API_ENDPOINT=https://vpn.${domain}:443 \\
    -e AUTH_AUDIENCE=${client_id} \\
    -e AUTH_CLIENT_ID=${client_id} \\
    -e AUTH_CLIENT_SECRET=${client_secret} \\
    -e AUTH_AUTHORITY=${authentik_url}/application/o/netbird/ \\
    -e USE_AUTH0=false \\
    -e AUTH_SUPPORTED_SCOPES="openid profile email" \\
    -e NETBIRD_TOKEN_SOURCE=idToken \\
    -p 127.0.0.1:8011:80 \\
    ${NETBIRD_DASHBOARD_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${NETBIRD_SERVICE_DASHBOARD}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start services
    systemctl daemon-reload
    systemctl enable "$NETBIRD_SERVICE_MGMT"
    systemctl enable "$NETBIRD_SERVICE_SIGNAL"
    systemctl enable "$NETBIRD_SERVICE_DASHBOARD"
    systemctl start "$NETBIRD_SERVICE_SIGNAL"
    systemctl start "$NETBIRD_SERVICE_MGMT"

    # Wait for management to be ready
    wopr_log "INFO" "Waiting for NetBird Management..."
    if wopr_wait_for_port "127.0.0.1" "$NETBIRD_PORT" 120; then
        wopr_log "OK" "NetBird Management is running on port $NETBIRD_PORT"
    else
        wopr_log "WARN" "NetBird Management may still be starting"
    fi

    # Start dashboard
    systemctl start "$NETBIRD_SERVICE_DASHBOARD"

    # Add Caddy routes
    wopr_caddy_add_route "vpn" "$NETBIRD_PORT"
    wopr_caddy_add_route "signal" "$NETBIRD_SIGNAL_PORT"

    # Record installation
    wopr_setting_set "module_netbird_installed" "true"
    wopr_setting_set "netbird_port" "$NETBIRD_PORT"
    wopr_setting_set "netbird_url" "https://vpn.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "netbird"

    wopr_log "OK" "NetBird deployed successfully"
    wopr_log "INFO" "Management API: https://vpn.${domain}"
    wopr_log "INFO" "Signal Server: https://signal.${domain}"
}

wopr_remove_netbird() {
    wopr_log "INFO" "Removing NetBird..."

    systemctl stop "$NETBIRD_SERVICE_DASHBOARD" 2>/dev/null || true
    systemctl stop "$NETBIRD_SERVICE_SIGNAL" 2>/dev/null || true
    systemctl stop "$NETBIRD_SERVICE_MGMT" 2>/dev/null || true
    systemctl disable "$NETBIRD_SERVICE_DASHBOARD" 2>/dev/null || true
    systemctl disable "$NETBIRD_SERVICE_SIGNAL" 2>/dev/null || true
    systemctl disable "$NETBIRD_SERVICE_MGMT" 2>/dev/null || true
    rm -f "/etc/systemd/system/${NETBIRD_SERVICE_MGMT}.service"
    rm -f "/etc/systemd/system/${NETBIRD_SERVICE_SIGNAL}.service"
    rm -f "/etc/systemd/system/${NETBIRD_SERVICE_DASHBOARD}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "vpn"
    wopr_caddy_remove_route "signal"

    wopr_log "INFO" "NetBird removed (data preserved)"
}

wopr_status_netbird() {
    local mgmt_status="stopped"
    local signal_status="stopped"

    if systemctl is-active --quiet "$NETBIRD_SERVICE_MGMT" 2>/dev/null; then
        mgmt_status="running"
    fi

    if systemctl is-active --quiet "$NETBIRD_SERVICE_SIGNAL" 2>/dev/null; then
        signal_status="running"
    fi

    if [ "$mgmt_status" = "running" ] && [ "$signal_status" = "running" ]; then
        echo "running"
    elif [ "$mgmt_status" = "running" ] || [ "$signal_status" = "running" ]; then
        echo "partial"
    else
        echo "stopped"
    fi
}
