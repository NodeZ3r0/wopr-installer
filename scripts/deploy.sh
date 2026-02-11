#!/bin/bash
# WOPR Orchestrator Deployment Script
# ====================================
# Usage: ./scripts/deploy.sh [target_host]
#
# Deploys the WOPR control plane to a production server.
# Assumes: systemd service "wopr-orchestrator" exists.

set -euo pipefail

TARGET="${1:-orc.wopr.systems}"
DEPLOY_DIR="/opt/wopr/control-plane"
SERVICE_NAME="wopr-orchestrator"

echo "=== WOPR Deploy to ${TARGET} ==="

# Pull latest
echo "→ Pulling latest code..."
ssh "root@${TARGET}" "cd ${DEPLOY_DIR} && git pull origin main"

# Install deps
echo "→ Installing dependencies..."
ssh "root@${TARGET}" "cd ${DEPLOY_DIR} && pip install -r requirements.txt"

# Run migrations
echo "→ Running database migrations..."
ssh "root@${TARGET}" "cd ${DEPLOY_DIR} && python scripts/migrate.py"

# Restart service
echo "→ Restarting ${SERVICE_NAME}..."
ssh "root@${TARGET}" "systemctl restart ${SERVICE_NAME}"

# Verify
echo "→ Checking health..."
sleep 3
curl -sf "https://${TARGET}/api/health" | python3 -m json.tool || echo "Health check pending..."

echo "=== Deploy complete ==="
