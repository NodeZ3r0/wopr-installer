#!/usr/bin/env bash
# WOPR Support Plane - Beacon SSH Setup
# Configures a beacon to trust the WOPR Support CA and creates support user accounts.
# Run this on each beacon that should accept support access.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CA_PUB_URL="${CA_PUB_URL:-}"

echo "=== WOPR Support Plane - Beacon SSH Setup ==="

# Step 1: Fetch CA public key
echo "[1/6] Installing CA public key..."
if [ -n "$CA_PUB_URL" ]; then
    curl -fsSL "${CA_PUB_URL}/api/v1/ca-public-key" | jq -r '.public_key' > /etc/ssh/wopr-support-ca.pub
elif [ -f "${SCRIPT_DIR}/wopr-support-ca.pub" ]; then
    cp "${SCRIPT_DIR}/wopr-support-ca.pub" /etc/ssh/wopr-support-ca.pub
else
    echo "ERROR: No CA public key source. Set CA_PUB_URL or place wopr-support-ca.pub in ${SCRIPT_DIR}/"
    exit 1
fi
chmod 0644 /etc/ssh/wopr-support-ca.pub
echo "    CA public key installed to /etc/ssh/wopr-support-ca.pub"

# Step 2: Create support user accounts
echo "[2/6] Creating support user accounts..."
for user in wopr-diag wopr-remediate wopr-breakglass; do
    if ! id "$user" &>/dev/null; then
        useradd --system --shell /bin/bash --no-create-home "$user"
        echo "    Created user: $user"
    else
        echo "    User already exists: $user"
    fi
done

# Step 3: Set up authorized principals
echo "[3/6] Configuring authorized principals..."
install -d -m 0755 /etc/ssh/auth_principals

echo "wopr-diag" > /etc/ssh/auth_principals/wopr-diag
echo -e "wopr-diag\nwopr-remediate" > /etc/ssh/auth_principals/wopr-remediate
echo -e "wopr-diag\nwopr-remediate\nwopr-breakglass\nroot" > /etc/ssh/auth_principals/wopr-breakglass
echo "wopr-diag" > /etc/ssh/auth_principals/root  # Allow breakglass root via principal

chmod 0644 /etc/ssh/auth_principals/*
echo "    Authorized principals configured."

# Step 4: Install restricted shells
echo "[4/6] Installing restricted shells..."
cp "${SCRIPT_DIR}/wopr-diag-shell.sh" /usr/local/bin/wopr-diag-shell
cp "${SCRIPT_DIR}/wopr-remediate-shell.sh" /usr/local/bin/wopr-remediate-shell
chmod 0755 /usr/local/bin/wopr-diag-shell
chmod 0755 /usr/local/bin/wopr-remediate-shell
echo "    Restricted shells installed."

# Step 5: Deploy sshd config
echo "[5/6] Deploying SSH configuration..."
install -d -m 0755 /etc/ssh/sshd_config.d
cp "${SCRIPT_DIR}/sshd_config.d/wopr-support-ca.conf" /etc/ssh/sshd_config.d/wopr-support-ca.conf
chmod 0644 /etc/ssh/sshd_config.d/wopr-support-ca.conf
echo "    SSH configuration deployed."

# Step 6: Validate and reload sshd
echo "[6/6] Validating and reloading SSH daemon..."
if sshd -t; then
    systemctl reload sshd
    echo "    SSH daemon reloaded successfully."
else
    echo "ERROR: SSH configuration validation failed!"
    echo "    Removing support CA config to prevent lockout..."
    rm -f /etc/ssh/sshd_config.d/wopr-support-ca.conf
    echo "    Config removed. Fix the issue and re-run this script."
    exit 1
fi

echo ""
echo "=== Beacon SSH setup complete ==="
echo "This beacon now trusts the WOPR Support CA."
echo "Support users: wopr-diag (read-only), wopr-remediate (limited), wopr-breakglass (full)"
