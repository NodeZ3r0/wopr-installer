#!/bin/bash
# WOPR Beacon Bootstrap - Auto-register with lighthouse and configure AI engine exposure
# Called during beacon provisioning after AI engine is deployed

set -e

LIGHTHOUSE_URL="${LIGHTHOUSE_URL:-https://support.wopr.systems}"
BEACON_ID="${BEACON_ID:-$(hostname)}"
BEACON_DOMAIN="${BEACON_DOMAIN:-$(hostname).wopr.systems}"
BUNDLE_ID="${BUNDLE_ID:-sovereign-developer}"
WOPR_VERSION="${WOPR_VERSION:-1.0.0}"

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me || curl -s icanhazip.com)

echo "=== WOPR Beacon Bootstrap ==="
echo "Beacon ID: $BEACON_ID"
echo "Domain: $BEACON_DOMAIN"
echo "Public IP: $PUBLIC_IP"
echo "Bundle: $BUNDLE_ID"

# Configure AI Engine Caddy route with IP allowlist for lighthouse
configure_ai_engine_caddy() {
    echo "Configuring AI Engine Caddy route..."

    # nodez3r0 (lighthouse) IP
    LIGHTHOUSE_IP="159.203.138.7"

    cat >> /etc/caddy/Caddyfile << EOF

# AI Engine API - for support.wopr.systems to fetch escalations
# Protected by IP allowlist (lighthouse only)
ai-engine.${BEACON_DOMAIN} {
    @allowed {
        remote_ip ${LIGHTHOUSE_IP}
    }
    handle @allowed {
        reverse_proxy 127.0.0.1:8600
    }
    respond 403
}
EOF

    # Reload Caddy
    caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || systemctl reload caddy
    echo "AI Engine Caddy route configured"
}

# Register with lighthouse
register_with_lighthouse() {
    echo "Registering with lighthouse at $LIGHTHOUSE_URL..."

    AI_ENGINE_URL="https://ai-engine.${BEACON_DOMAIN}"

    RESPONSE=$(curl -s -X POST "${LIGHTHOUSE_URL}/api/v1/beacons/register" \
        -H "Content-Type: application/json" \
        -d "{
            \"beacon_id\": \"${BEACON_ID}\",
            \"domain\": \"${BEACON_DOMAIN}\",
            \"ai_engine_url\": \"${AI_ENGINE_URL}\",
            \"public_ip\": \"${PUBLIC_IP}\",
            \"bundle_id\": \"${BUNDLE_ID}\",
            \"version\": \"${WOPR_VERSION}\"
        }")

    echo "Registration response: $RESPONSE"

    if echo "$RESPONSE" | grep -q '"status":"registered"'; then
        echo "Successfully registered with lighthouse"
        return 0
    else
        echo "Warning: Registration may have failed"
        return 1
    fi
}

# Setup heartbeat cron
setup_heartbeat() {
    echo "Setting up heartbeat cron..."

    cat > /etc/cron.d/wopr-beacon-heartbeat << EOF
# WOPR Beacon heartbeat - report status to lighthouse every 5 minutes
*/5 * * * * root curl -s -X POST "${LIGHTHOUSE_URL}/api/v1/beacons/heartbeat" -H "Content-Type: application/json" -d '{"beacon_id":"${BEACON_ID}","ai_engine_status":"running","services_healthy":0,"services_total":0}' > /dev/null 2>&1
EOF

    chmod 644 /etc/cron.d/wopr-beacon-heartbeat
    echo "Heartbeat cron installed"
}

# Main
main() {
    # Check if AI engine is running
    if ! systemctl is-active --quiet wopr-ai-engine 2>/dev/null; then
        echo "Warning: AI engine not running, will configure anyway"
    fi

    # Configure Caddy route
    configure_ai_engine_caddy

    # Wait for DNS propagation (Cloudflare usually fast)
    echo "Waiting for DNS propagation..."
    sleep 5

    # Register with lighthouse
    register_with_lighthouse || echo "Will retry registration on next heartbeat"

    # Setup heartbeat
    setup_heartbeat

    echo ""
    echo "=== Beacon Bootstrap Complete ==="
    echo "AI Engine URL: https://ai-engine.${BEACON_DOMAIN}"
    echo "Lighthouse: $LIGHTHOUSE_URL"
    echo ""
}

main "$@"
