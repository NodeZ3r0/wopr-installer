#!/usr/bin/env bash
# WOPR Support Plane - Caddy Patch Apply with Canary
# 1. Runs backup
# 2. Merges support plane site blocks (append if not present)
# 3. Validates config
# 4. Reloads Caddy
# 5. Runs healthcheck
# 6. Auto-rollback on failure
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "${SCRIPT_DIR}")"
PATCH_FILE="${SCRIPT_DIR}/Caddyfile.patch"
CADDYFILE="/etc/caddy/Caddyfile"

echo "=== WOPR Support Plane: Caddy Patch Apply ==="

# Validate inputs
if [ ! -f "${PATCH_FILE}" ]; then
    echo "FATAL: Patch file not found: ${PATCH_FILE}"
    exit 1
fi

if [ ! -f "${CADDYFILE}" ]; then
    echo "FATAL: Caddyfile not found: ${CADDYFILE}"
    exit 1
fi

# Step 1: Backup
echo ""
echo "--- Step 1: Backup ---"
bash "${DEPLOY_DIR}/backups/backup-and-verify.sh"
if [ $? -ne 0 ]; then
    echo "FATAL: Backup failed. Aborting patch."
    exit 1
fi
echo "[OK] Backup complete"

# Step 2: Merge patch (append blocks that don't already exist)
echo ""
echo "--- Step 2: Applying patch ---"

SUPPORT_GW_MARKER="support-gateway.wopr.systems"
SSHCA_MARKER="sshca.wopr.systems"

NEEDS_PATCH=0

if ! grep -q "${SUPPORT_GW_MARKER}" "${CADDYFILE}"; then
    NEEDS_PATCH=1
fi

if ! grep -q "${SSHCA_MARKER}" "${CADDYFILE}"; then
    NEEDS_PATCH=1
fi

if [ "${NEEDS_PATCH}" -eq 0 ]; then
    echo "Support plane blocks already present in Caddyfile. Skipping append."
else
    echo "" >> "${CADDYFILE}"
    echo "# --- WOPR Support Plane (auto-patched $(date +%Y-%m-%d)) ---" >> "${CADDYFILE}"

    if ! grep -q "${SUPPORT_GW_MARKER}" "${CADDYFILE}"; then
        # Extract support-gateway block from patch
        sed -n '/^support-gateway\.wopr\.systems/,/^}/p' "${PATCH_FILE}" >> "${CADDYFILE}"
        echo "" >> "${CADDYFILE}"
        echo "[OK] support-gateway block appended"
    fi

    if ! grep -q "${SSHCA_MARKER}" "${CADDYFILE}"; then
        # Extract sshca block from patch
        sed -n '/^sshca\.wopr\.systems/,/^}/p' "${PATCH_FILE}" >> "${CADDYFILE}"
        echo "" >> "${CADDYFILE}"
        echo "[OK] sshca block appended"
    fi
fi

# Step 3: Validate
echo ""
echo "--- Step 3: Validating config ---"
if ! caddy validate --config "${CADDYFILE}"; then
    echo "FATAL: Config validation failed! Rolling back..."
    bash "${DEPLOY_DIR}/backups/restore-caddy-backup.sh"
    exit 1
fi
echo "[OK] Config valid"

# Step 4: Reload
echo ""
echo "--- Step 4: Reloading Caddy ---"
systemctl reload caddy
sleep 2
echo "[OK] Caddy reloaded"

# Step 5: Healthcheck
echo ""
echo "--- Step 5: Running healthcheck ---"
if ! bash "${DEPLOY_DIR}/verify/healthcheck.sh"; then
    echo "FAIL: Healthcheck failed after patch! Rolling back..."
    bash "${DEPLOY_DIR}/backups/restore-caddy-backup.sh"
    systemctl reload caddy
    echo "Rollback complete. Caddy restored to pre-patch state."
    exit 1
fi

echo ""
echo "=== Caddy patch applied successfully ==="
