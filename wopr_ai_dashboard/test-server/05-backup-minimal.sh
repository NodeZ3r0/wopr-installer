#!/usr/bin/env bash
set -e
TS="$(date +%Y%m%d_%H%M%S)"
DEST="/mnt/backups/test/${TS}"
mkdir -p "$DEST"
rsync -a /etc/nebula "$DEST/" || true
rsync -a /opt/wopr-deployment-queue "$DEST/" || true
echo "[*] Test backup created at $DEST"
