#!/usr/bin/env bash
set -e
root="/opt/wopr_ai_dashboard"
mkdir -p "$root/test-server"
cd "$root/test-server"
# Auto-deploy test $(date)

# 00-nebula-install.sh
cat >00-nebula-install.sh <<'SH'
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
SH

# 01-base.sh
cat >01-base.sh <<'SH'
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
SH

chmod +x ./*.sh
echo "[OK] Test suite written to $PWD"
