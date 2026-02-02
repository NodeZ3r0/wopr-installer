#!/usr/bin/env bash
# WOPR Support Plane - Health Check
# Verifies all support plane components are operational.
# Referenced by deploy/caddy/apply-caddy-patch.sh
set -euo pipefail

FAILED=0
WARN=0

echo "=== WOPR Support Plane Health Check ==="

# Check Caddy is running
echo -n "[Caddy] "
if systemctl is-active --quiet caddy; then
    echo "PASS - running"
else
    echo "FAIL - not running"
    FAILED=$((FAILED + 1))
fi

# Check support-gateway responds
echo -n "[Support Gateway] "
if curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8443/api/health; then
    echo "PASS - responding on :8443"
else
    echo "FAIL - not responding on :8443"
    FAILED=$((FAILED + 1))
fi

# Check SSH CA responds
echo -n "[SSH CA] "
if curl -sf -o /dev/null --max-time 5 http://127.0.0.1:9444/api/health; then
    echo "PASS - responding on :9444"
else
    echo "FAIL - not responding on :9444"
    FAILED=$((FAILED + 1))
fi

# Check Nebula mesh
echo -n "[Nebula] "
if systemctl is-active --quiet nebula; then
    echo "PASS - running"
else
    echo "FAIL - not running"
    FAILED=$((FAILED + 1))
fi

# Check DNS resolution
for domain in support-gateway.wopr.systems sshca.wopr.systems; do
    echo -n "[DNS: ${domain}] "
    if host "$domain" > /dev/null 2>&1; then
        echo "PASS"
    else
        echo "WARN - DNS resolution failed"
        WARN=$((WARN + 1))
    fi
done

# Check SSH CA key exists
echo -n "[CA Key] "
if [ -f /etc/wopr-sshca/ca_key ]; then
    echo "PASS - present"
else
    echo "FAIL - /etc/wopr-sshca/ca_key not found"
    FAILED=$((FAILED + 1))
fi

# Check nftables rules loaded
echo -n "[Firewall] "
if nft list table inet wopr_support > /dev/null 2>&1; then
    echo "PASS - rules loaded"
else
    echo "WARN - wopr_support table not found"
    WARN=$((WARN + 1))
fi

# Summary
echo ""
echo "=== Results ==="
echo "Failed: ${FAILED}  Warnings: ${WARN}"

if [ "$FAILED" -ne 0 ]; then
    echo "HEALTHCHECK FAILED"
    exit 1
fi

if [ "$WARN" -ne 0 ]; then
    echo "HEALTHCHECK PASSED (with warnings)"
    exit 0
fi

echo "HEALTHCHECK PASSED"
exit 0
