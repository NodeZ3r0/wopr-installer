#!/usr/bin/env bash
# WOPR Support Plane - Caddy Restore from Backup
# Restores Caddy config from the most recent (or specified) backup.
set -euo pipefail

BACKUP_BASE="/var/backups/wopr-caddy"

# Use specified backup or latest
if [ -n "${1:-}" ]; then
    BACKUP_DIR="$1"
else
    if [ ! -f "${BACKUP_BASE}/latest" ]; then
        echo "FATAL: No latest backup pointer found and no backup dir specified."
        exit 1
    fi
    BACKUP_DIR="$(cat "${BACKUP_BASE}/latest")"
fi

if [ ! -d "${BACKUP_DIR}" ]; then
    echo "FATAL: Backup directory does not exist: ${BACKUP_DIR}"
    exit 1
fi

echo "=== Restoring Caddy from: ${BACKUP_DIR} ==="

# Verify manifest integrity
if [ -f "${BACKUP_DIR}/manifest.sha256" ]; then
    echo "Verifying backup integrity..."
    cd "${BACKUP_DIR}"
    if ! sha256sum -c manifest.sha256; then
        echo "FATAL: Backup integrity check failed!"
        exit 1
    fi
    cd - > /dev/null
    echo "[OK] Integrity verified"
fi

# Restore full caddy directory
if [ -f "${BACKUP_DIR}/caddy-full.tar.gz" ]; then
    echo "Restoring /etc/caddy/ from tarball..."
    tar xzf "${BACKUP_DIR}/caddy-full.tar.gz" -C /etc/
    echo "[OK] /etc/caddy/ restored"
elif [ -f "${BACKUP_DIR}/Caddyfile" ]; then
    echo "Restoring Caddyfile only..."
    cp "${BACKUP_DIR}/Caddyfile" /etc/caddy/Caddyfile
    echo "[OK] Caddyfile restored"
else
    echo "FATAL: No restorable backup found in ${BACKUP_DIR}"
    exit 1
fi

# Restore systemd overrides if backup exists
if [ -f "${BACKUP_DIR}/caddy-systemd-overrides.tar.gz" ]; then
    tar xzf "${BACKUP_DIR}/caddy-systemd-overrides.tar.gz" -C /etc/systemd/system/
    systemctl daemon-reload
    echo "[OK] Systemd overrides restored"
fi

# Validate and reload
echo "Validating restored config..."
if ! caddy validate --config /etc/caddy/Caddyfile; then
    echo "FATAL: Restored config fails validation! Manual intervention required."
    exit 1
fi

echo "Reloading Caddy..."
systemctl reload caddy

echo ""
echo "=== Restore complete ==="
