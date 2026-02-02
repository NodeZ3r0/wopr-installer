#!/usr/bin/env bash
# WOPR Support Plane - Apply nftables Firewall Rules
# Validates and applies rules with automatic rollback on failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_FILE="${SCRIPT_DIR}/support-plane.nft"
DEST="/etc/nftables.d/wopr-support-plane.conf"
BACKUP="/var/backups/wopr/nftables-backup-$(date +%s).nft"

echo "=== WOPR Support Plane - Firewall Configuration ==="

# Validate rules file exists
if [ ! -f "$RULES_FILE" ]; then
    echo "ERROR: Rules file not found: ${RULES_FILE}"
    exit 1
fi

# Backup current ruleset
install -d /var/backups/wopr
echo "[1/4] Backing up current firewall rules..."
nft list ruleset > "$BACKUP"
echo "    Backup saved to ${BACKUP}"

# Validate new rules (dry run)
echo "[2/4] Validating new rules..."
if ! nft -c -f "$RULES_FILE"; then
    echo "ERROR: Rule validation failed. No changes made."
    exit 1
fi
echo "    Validation passed."

# Create nftables.d directory if needed
install -d /etc/nftables.d

# Deploy rules
echo "[3/4] Deploying rules to ${DEST}..."
cp "$RULES_FILE" "$DEST"
chmod 0644 "$DEST"

# Apply rules
echo "[4/4] Applying firewall rules..."
if ! nft -f "$DEST"; then
    echo "ERROR: Failed to apply rules. Rolling back..."
    nft -f "$BACKUP"
    rm -f "$DEST"
    echo "    Rollback complete. Previous rules restored."
    exit 1
fi

echo ""
echo "=== Firewall rules applied successfully ==="
echo "Active rules:"
nft list table inet wopr_support
