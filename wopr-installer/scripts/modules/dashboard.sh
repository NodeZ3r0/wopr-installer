#!/bin/bash
#=================================================
# WOPR MODULE: Dashboard
# Version: 1.0
# Purpose: Deploy WOPR Dashboard UI
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

DASHBOARD_DIR="/var/www/wopr-dashboard"
DASHBOARD_API_PORT=8090
DASHBOARD_SERVICE="wopr-dashboard-api"

wopr_deploy_dashboard() {
    wopr_log "INFO" "Deploying WOPR Dashboard..."

    local domain=$(wopr_setting_get domain)
    if [ -z "$domain" ]; then
        wopr_log "ERROR" "Domain not configured"
        return 1
    fi

    # Create dashboard directory
    mkdir -p "$DASHBOARD_DIR"

    # Check if we have pre-built dashboard files
    local source_dir="${SCRIPT_DIR}/../dashboard/build"
    if [ -d "$source_dir" ]; then
        wopr_log "INFO" "Copying pre-built dashboard files..."
        cp -r "$source_dir"/* "$DASHBOARD_DIR/"
    else
        # Check for source files to build
        local src_dir="${SCRIPT_DIR}/../dashboard"
        if [ -d "$src_dir" ] && [ -f "$src_dir/package.json" ]; then
            wopr_log "INFO" "Building dashboard from source..."
            wopr_build_dashboard "$src_dir"
        else
            # Generate placeholder dashboard
            wopr_log "INFO" "Generating placeholder dashboard..."
            wopr_generate_placeholder_dashboard
        fi
    fi

    # Deploy the dashboard API service
    wopr_deploy_dashboard_api

    # Add Caddy routes for dashboard
    wopr_log "INFO" "Configuring dashboard routes..."

    # Static dashboard files served directly by Caddy
    # API requests proxied to dashboard API service
    wopr_caddy_add_dashboard_routes "$domain"

    # Record installation
    wopr_setting_set "module_dashboard_installed" "true"
    wopr_defcon_log "MODULE_DEPLOYED" "dashboard"

    wopr_log "OK" "Dashboard deployed at https://dashboard.${domain}"
}

wopr_build_dashboard() {
    local src_dir="$1"

    # Check for Node.js
    if ! command -v node >/dev/null 2>&1; then
        wopr_log "WARN" "Node.js not found, installing..."
        # Install Node.js via NodeSource
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi

    # Build the dashboard
    cd "$src_dir"
    npm install
    npm run build

    # Copy built files
    if [ -d "build" ]; then
        cp -r build/* "$DASHBOARD_DIR/"
    else
        wopr_log "ERROR" "Dashboard build failed"
        return 1
    fi

    cd - >/dev/null
}

wopr_generate_placeholder_dashboard() {
    # Create a minimal placeholder dashboard
    cat > "$DASHBOARD_DIR/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WOPR Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            padding: 1rem 2rem;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00ff88;
        }
        nav a {
            color: #888;
            text-decoration: none;
            margin-left: 2rem;
        }
        nav a:hover { color: #00ff88; }
        main {
            flex: 1;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }
        h1 { margin-bottom: 0.5rem; }
        .subtitle { color: #888; margin-bottom: 2rem; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 1.5rem;
        }
        .card h3 {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .badge {
            font-size: 0.75rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            background: #00ff88;
            color: #000;
        }
        .badge.warning { background: #ff9800; }
        .badge.error { background: #f44336; color: #fff; }
        .card p { color: #888; font-size: 0.9rem; }
        .btn {
            display: inline-block;
            margin-top: 1rem;
            padding: 0.5rem 1rem;
            background: #00ff88;
            color: #000;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
        }
        .btn:hover { background: #00cc6a; }
        .status { margin-top: 2rem; }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid #333;
        }
        footer {
            text-align: center;
            padding: 1rem;
            color: #666;
            border-top: 1px solid #333;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">WOPR</div>
        <nav>
            <a href="/">Dashboard</a>
            <a href="/modules">Modules</a>
            <a href="/settings">Settings</a>
        </nav>
    </header>
    <main>
        <h1>Welcome to WOPR</h1>
        <p class="subtitle">Your Sovereign Suite is ready</p>

        <div class="grid">
            <div class="card">
                <h3>Files <span class="badge">Running</span></h3>
                <p>Nextcloud - File storage and sync</p>
                <a href="/files" class="btn">Open</a>
            </div>
            <div class="card">
                <h3>Passwords <span class="badge">Running</span></h3>
                <p>Vaultwarden - Password manager</p>
                <a href="/vault" class="btn">Open</a>
            </div>
            <div class="card">
                <h3>News <span class="badge">Running</span></h3>
                <p>FreshRSS - Feed reader</p>
                <a href="/rss" class="btn">Open</a>
            </div>
            <div class="card">
                <h3>Identity <span class="badge">Running</span></h3>
                <p>Authentik - Single Sign-On</p>
                <a href="/auth" class="btn">Open</a>
            </div>
        </div>

        <div class="status">
            <h2>System Status</h2>
            <div class="status-item">
                <span>Domain</span>
                <span id="domain">Loading...</span>
            </div>
            <div class="status-item">
                <span>SSL Certificate</span>
                <span>Valid</span>
            </div>
            <div class="status-item">
                <span>Last Backup</span>
                <span>Today</span>
            </div>
        </div>
    </main>
    <footer>
        WOPR Sovereign Suite &copy; 2024
    </footer>
    <script>
        document.getElementById('domain').textContent = window.location.hostname.replace('dashboard.', '');
    </script>
</body>
</html>
EOF
}

wopr_deploy_dashboard_api() {
    wopr_log "INFO" "Deploying dashboard API service..."

    # The dashboard API is part of the control plane
    # For standalone instances, we run a lightweight local API

    local api_script="/opt/wopr/dashboard_api.py"
    mkdir -p /opt/wopr

    # Create lightweight dashboard API
    cat > "$api_script" <<'APIEOF'
#!/usr/bin/env python3
"""
WOPR Dashboard API - Local Instance
Provides status and control endpoints for the dashboard UI
"""

import json
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SETTINGS_FILE = "/var/lib/wopr/settings.json"

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_container_status(name):
    try:
        result = subprocess.run(
            ['podman', 'inspect', '--format', '{{.State.Status}}', name],
            capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else 'stopped'
    except:
        return 'unknown'

def get_modules():
    settings = load_settings()
    domain = settings.get('domain', 'localhost')

    modules = []
    module_defs = [
        ('wopr-nextcloud', 'Nextcloud', 'files', 'File storage and sync'),
        ('wopr-vaultwarden', 'Vaultwarden', 'vault', 'Password manager'),
        ('wopr-freshrss', 'FreshRSS', 'rss', 'RSS feed reader'),
        ('wopr-authentik-server', 'Authentik', 'auth', 'Identity provider'),
    ]

    for container, name, subdomain, desc in module_defs:
        status = get_container_status(container)
        modules.append({
            'id': container.replace('wopr-', ''),
            'name': name,
            'description': desc,
            'status': 'running' if status == 'running' else 'stopped',
            'url': f'https://{subdomain}.{domain}',
            'category': 'installed'
        })

    return modules

class DashboardAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/api/status':
            settings = load_settings()
            self._send_json({
                'status': 'healthy',
                'domain': settings.get('domain'),
                'bundle': settings.get('bundle', 'personal'),
                'instance_id': settings.get('instance_id'),
            })

        elif path == '/api/modules':
            self._send_json(get_modules())

        elif path == '/api/trials':
            # Trials would come from control plane in production
            self._send_json([])

        elif path == '/api/billing':
            settings = load_settings()
            self._send_json({
                'bundle_id': settings.get('bundle', 'personal'),
                'monthly_cost': '14.48',
                'provider': settings.get('provider', 'unknown'),
                'region': settings.get('region', 'unknown'),
            })

        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8090))
    server = HTTPServer(('127.0.0.1', port), DashboardAPIHandler)
    print(f'Dashboard API running on port {port}')
    server.serve_forever()
APIEOF

    chmod +x "$api_script"

    # Create systemd service
    cat > "/etc/systemd/system/${DASHBOARD_SERVICE}.service" <<EOF
[Unit]
Description=WOPR Dashboard API
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=5
ExecStart=/usr/bin/python3 ${api_script}
Environment=PORT=${DASHBOARD_API_PORT}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$DASHBOARD_SERVICE"
    systemctl start "$DASHBOARD_SERVICE"

    wopr_log "OK" "Dashboard API started on port ${DASHBOARD_API_PORT}"
}

wopr_caddy_add_dashboard_routes() {
    local domain="$1"
    local dashboard_subdomain="dashboard.${domain}"

    # Add route for static dashboard files
    # This uses file_server instead of reverse_proxy
    local route_config=$(cat <<EOF
{
    "@id": "dashboard-static",
    "match": [{"host": ["${dashboard_subdomain}"]}],
    "handle": [
        {
            "handler": "subroute",
            "routes": [
                {
                    "match": [{"path": ["/api/*"]}],
                    "handle": [{
                        "handler": "reverse_proxy",
                        "upstreams": [{"dial": "127.0.0.1:${DASHBOARD_API_PORT}"}]
                    }]
                },
                {
                    "handle": [
                        {
                            "handler": "file_server",
                            "root": "${DASHBOARD_DIR}"
                        },
                        {
                            "handler": "rewrite",
                            "uri": "/index.html"
                        }
                    ]
                }
            ]
        }
    ],
    "terminal": true
}
EOF
)

    # Try adding via API first
    local response=$(curl -s -X POST "http://127.0.0.1:2019/config/apps/http/servers/srv0/routes" \
        -H "Content-Type: application/json" \
        -d "$route_config" 2>/dev/null)

    if [ $? -ne 0 ]; then
        wopr_log "WARN" "Could not add dashboard route via API, using Caddyfile"
        wopr_caddy_rebuild_config
    fi
}

wopr_remove_dashboard() {
    wopr_log "INFO" "Removing WOPR Dashboard..."

    # Stop and disable API service
    systemctl stop "$DASHBOARD_SERVICE" 2>/dev/null || true
    systemctl disable "$DASHBOARD_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${DASHBOARD_SERVICE}.service"
    systemctl daemon-reload

    # Remove dashboard files (preserve data)
    rm -rf "$DASHBOARD_DIR"

    # Remove Caddy route
    wopr_caddy_remove_route "dashboard-static"

    wopr_setting_set "module_dashboard_installed" "false"
    wopr_log "INFO" "Dashboard removed"
}

wopr_status_dashboard() {
    if systemctl is-active --quiet "$DASHBOARD_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}
