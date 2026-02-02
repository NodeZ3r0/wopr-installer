#!/usr/bin/env bash
# WOPR Support Plane - Nebula Mesh Installation
# Installs Nebula and configures the support plane node.
set -euo pipefail

NEB_VER="${NEB_VER:-1.7.2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== WOPR Support Plane - Nebula Installation ==="

# Install Nebula binary
if [ ! -f /usr/local/sbin/nebula ]; then
    echo "[1/4] Installing Nebula v${NEB_VER}..."
    TMP="/tmp/nebula-${NEB_VER}.tar.gz"
    curl -fsSL "https://github.com/slackhq/nebula/releases/download/v${NEB_VER}/nebula-linux-amd64.tar.gz" -o "$TMP"
    install -d /usr/local/sbin
    tar -xzf "$TMP" -C /usr/local/sbin nebula nebula-cert
    chmod +x /usr/local/sbin/nebula /usr/local/sbin/nebula-cert
    rm -f "$TMP"
    echo "    Nebula installed to /usr/local/sbin/"
else
    echo "[1/4] Nebula already installed, skipping."
fi

# Create config directory
echo "[2/4] Setting up configuration directory..."
install -d -m 0700 /etc/nebula

# Deploy config
echo "[3/4] Deploying Nebula configuration..."
if [ ! -f /etc/nebula/config.yml ]; then
    cp "${SCRIPT_DIR}/config.yml" /etc/nebula/config.yml
    chmod 0600 /etc/nebula/config.yml
    echo "    Config deployed to /etc/nebula/config.yml"
    echo "    IMPORTANT: Edit /etc/nebula/config.yml to set LIGHTHOUSE_PUBLIC_IP"
else
    echo "    Config already exists, skipping. Review manually if needed."
fi

# Check for certificates
echo "[4/4] Checking certificates..."
if [ ! -f /etc/nebula/support-plane.crt ] || [ ! -f /etc/nebula/support-plane.key ]; then
    echo "    WARNING: Nebula certificates not found."
    echo "    You need to generate them on the lighthouse node:"
    echo ""
    echo "      nebula-cert sign -name support-plane \\"
    echo "        -ip 10.0.0.X/8 \\"
    echo "        -groups wopr-support \\"
    echo "        -in-ca /etc/nebula/ca.crt \\"
    echo "        -in-key /etc/nebula/ca.key"
    echo ""
    echo "    Then copy support-plane.crt and support-plane.key to /etc/nebula/"
    echo "    Also copy ca.crt to /etc/nebula/ca.crt"
else
    echo "    Certificates found."
fi

# Install systemd service
if [ ! -f /etc/systemd/system/nebula.service ]; then
    cat > /etc/systemd/system/nebula.service << 'EOF'
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
EOF
    systemctl daemon-reload
    echo "    Nebula systemd service installed."
fi

echo ""
echo "=== Nebula installation complete ==="
echo "After configuring certificates, run:"
echo "  systemctl enable --now nebula"
