#!/usr/bin/env bash
set -e; umask 022; export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl ca-certificates gnupg jq rsync python3 python3-venv python3-pip unzip
install -d -m 0755 /etc/systemd/system
cat >/etc/systemd/system/wopr-app@.service <<'EOFU'
[Unit]
Description=WOPR App - %i (mesh native)
After=network.target
[Service]
User=wopr
Group=wopr
WorkingDirectory=/opt/%i
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/opt/%i/.env
ExecStart=/opt/%i/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOFU
systemctl daemon-reload
echo "[*] Test base ready."
