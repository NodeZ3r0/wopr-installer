#!/usr/bin/env bash
set -e; umask 022; export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y curl tar
NEB_VER="${NEB_VER:-1.7.2}"
TMP="/tmp/nebula-${NEB_VER}.tar.gz"
curl -fsSL "https://github.com/slackhq/nebula/releases/download/v${NEB_VER}/nebula-linux-amd64.tar.gz" -o "$TMP"
install -d /usr/local/sbin
tar -xzf "$TMP" -C /usr/local/sbin nebula nebula-cert
chmod +x /usr/local/sbin/nebula /usr/local/sbin/nebula-cert
rm -f "$TMP"
cat >/etc/systemd/system/nebula.service <<'EOFU'
[Unit]
Description=Nebula Mesh
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=/usr/local/sbin/nebula -config /etc/nebula/config.yml
Restart=always
RestartSec=2
[Install]
WantedBy=multi-user.target
EOFU
echo "[*] Nebula installed."
