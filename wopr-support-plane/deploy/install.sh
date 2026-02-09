#!/bin/bash
# WOPR Support Gateway - Installation Script for nodez3r0
set -e

echo "=== WOPR Support Gateway Installation ==="

# Create directory
mkdir -p /opt/wopr-support-plane
cd /opt/wopr-support-plane

# Copy files (assumes you've synced the repo)
# rsync -av --exclude='.git' --exclude='venv' --exclude='__pycache__' \
#     /path/to/wopr-support-plane/ /opt/wopr-support-plane/

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvicorn[standard]

# Create .env if not exists
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql://wopr:wopr@localhost:5432/wopr_support

# SSH CA
SSH_CA_URL=http://127.0.0.1:8444

# Ollama for AI suggestions (local)
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=phi3:mini

# AI Engine URL - beacon AI engine exposed via Caddy
# Each beacon exposes ai-engine.{domain} with IP allowlist for nodez3r0
AI_ENGINE_URL=https://ai-engine.testbeacon.wopr.systems

# Logging
LOG_LEVEL=INFO

# CORS origins
CORS_ORIGINS=https://support.wopr.systems,https://orc.wopr.systems

# Server binding
SUPPORT_GW_HOST=127.0.0.1
SUPPORT_GW_PORT=8443
EOF
    echo "Created .env with testbeacon AI engine URL"
fi

# Install systemd service
cp deploy/systemd/wopr-support-gateway.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable wopr-support-gateway

# Install Caddy config
cp deploy/caddy/support.wopr.systems.caddy /etc/caddy/sites-enabled/
caddy fmt --overwrite /etc/caddy/Caddyfile 2>/dev/null || true

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit /opt/wopr-support-plane/.env with your database credentials"
echo "2. Create the database: createdb wopr_support"
echo "3. Run migrations: psql wopr_support < db/migrations/001_initial_schema.sql"
echo "4. Start the service: systemctl start wopr-support-gateway"
echo "5. Reload Caddy: systemctl reload caddy"
echo "6. Add DNS record: support.wopr.systems -> nodez3r0 IP"
echo ""
echo "Dashboard will be available at: https://support.wopr.systems/escalations"
