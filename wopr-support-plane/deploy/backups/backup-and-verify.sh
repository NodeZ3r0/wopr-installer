#!/usr/bin/env bash
# WOPR Support Plane - Caddy Backup & Verify
# Creates timestamped backups of Caddy configuration before any changes.
# Fail-fast: exits non-zero if any backup step fails.
set -euo pipefail

BACKUP_BASE="/var/backups/wopr-caddy"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

echo "=== WOPR Caddy Backup: ${TIMESTAMP} ==="

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# 1. Backup Caddyfile
if [ ! -f /etc/caddy/Caddyfile ]; then
    echo "FATAL: /etc/caddy/Caddyfile not found. Cannot proceed."
    exit 1
fi
cp /etc/caddy/Caddyfile "${BACKUP_DIR}/Caddyfile"
echo "[OK] Caddyfile backed up"

# 2. Full tarball of /etc/caddy/
tar czf "${BACKUP_DIR}/caddy-full.tar.gz" -C /etc caddy/
echo "[OK] Full /etc/caddy/ tarball created"

# 3. Backup systemd overrides if they exist
if [ -d /etc/systemd/system/caddy.service.d ]; then
    tar czf "${BACKUP_DIR}/caddy-systemd-overrides.tar.gz" -C /etc/systemd/system caddy.service.d/
    echo "[OK] Caddy systemd overrides backed up"
else
    echo "[SKIP] No caddy.service.d overrides found"
fi

# 4. Verification - all backups must be non-empty
echo ""
echo "=== Verifying backups ==="
MANIFEST="${BACKUP_DIR}/manifest.sha256"
FAILED=0

for f in "${BACKUP_DIR}"/*; do
    [ "$(basename "$f")" = "manifest.sha256" ] && continue
    if [ ! -s "$f" ]; then
        echo "FAIL: ${f} is empty!"
        FAILED=1
    else
        sha256sum "$f" >> "${MANIFEST}"
        SIZE=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null)
        echo "[OK] $(basename "$f") (${SIZE} bytes)"
    fi
done

if [ "$FAILED" -ne 0 ]; then
    echo "FATAL: One or more backup files are empty. Aborting."
    exit 1
fi

echo ""
echo "=== Backup complete ==="
echo "Location: ${BACKUP_DIR}"
echo "Manifest: ${MANIFEST}"

# Write latest pointer for rollback scripts
echo "${BACKUP_DIR}" > "${BACKUP_BASE}/latest"
echo "Latest pointer updated."
