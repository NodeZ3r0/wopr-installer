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
    # Create a dashboard that fetches REAL service status from the API
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
            max-width: 1400px;
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
            transition: border-color 0.2s;
        }
        .card:hover { border-color: #00ff88; }
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
            background: #333;
            color: #888;
        }
        .badge.running { background: #00ff88; color: #000; }
        .badge.stopped { background: #f44336; color: #fff; }
        .badge.starting { background: #ff9800; color: #000; }
        .badge.checking { background: #555; color: #fff; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .card p { color: #888; font-size: 0.9rem; margin-bottom: 0.5rem; }
        .card .error { color: #f44336; font-size: 0.8rem; margin-top: 0.5rem; }
        .btn {
            display: inline-block;
            margin-top: 0.5rem;
            padding: 0.5rem 1rem;
            background: #00ff88;
            color: #000;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
            transition: background 0.2s;
        }
        .btn:hover { background: #00cc6a; }
        .btn.disabled { background: #333; color: #666; pointer-events: none; }
        .status { margin-top: 2rem; }
        .status h2 { margin-bottom: 1rem; }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid #333;
        }
        .status-item .value { color: #00ff88; }
        .status-item .value.error { color: #f44336; }
        footer {
            text-align: center;
            padding: 1rem;
            color: #666;
            border-top: 1px solid #333;
        }
        .refresh-btn {
            background: transparent;
            border: 1px solid #333;
            color: #888;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .refresh-btn:hover { border-color: #00ff88; color: #00ff88; }
        .loading { text-align: center; padding: 2rem; color: #888; }
    </style>
</head>
<body>
    <header>
        <div class="logo">WOPR</div>
        <nav>
            <a href="/">Dashboard</a>
            <a href="/modules">Modules</a>
            <a href="/settings">Settings</a>
            <button class="refresh-btn" onclick="loadModules()">Refresh</button>
        </nav>
    </header>
    <main>
        <h1>Welcome to WOPR</h1>
        <p class="subtitle" id="subtitle">Checking service status...</p>

        <div class="grid" id="modules-grid">
            <div class="loading">Loading services...</div>
        </div>

        <div class="status">
            <h2>System Status</h2>
            <div class="status-item">
                <span>Domain</span>
                <span id="domain" class="value">Loading...</span>
            </div>
            <div class="status-item">
                <span>Services Running</span>
                <span id="services-running" class="value">-/-</span>
            </div>
            <div class="status-item">
                <span>Overall Health</span>
                <span id="health-status" class="value">Checking...</span>
            </div>
            <div class="status-item">
                <span>Last Check</span>
                <span id="last-check" class="value">-</span>
            </div>
        </div>
    </main>
    <footer>
        WOPR Sovereign Suite &copy; 2026
    </footer>
    <script>
        const domain = window.location.hostname.replace('dashboard.', '');
        document.getElementById('domain').textContent = domain;

        async function loadModules() {
            const grid = document.getElementById('modules-grid');
            grid.innerHTML = '<div class="loading">Checking services...</div>';

            try {
                const response = await fetch('/api/modules');
                if (!response.ok) throw new Error('API unavailable');
                const modules = await response.json();

                let running = 0;
                let total = modules.length;
                let html = '';

                modules.forEach(mod => {
                    const isRunning = mod.status === 'running';
                    if (isRunning) running++;

                    const badgeClass = isRunning ? 'running' : 'stopped';
                    const badgeText = isRunning ? 'Running' : 'Stopped';
                    const btnClass = isRunning ? '' : 'disabled';
                    const errorHtml = mod.error ? `<div class="error">${mod.error}</div>` : '';

                    html += `
                        <div class="card">
                            <h3>${mod.name} <span class="badge ${badgeClass}">${badgeText}</span></h3>
                            <p>${mod.description}</p>
                            ${errorHtml}
                            <a href="${mod.url}" class="btn ${btnClass}" target="_blank">Open</a>
                        </div>
                    `;
                });

                grid.innerHTML = html || '<div class="loading">No services found</div>';

                // Update status
                document.getElementById('services-running').textContent = `${running}/${total}`;
                const healthPct = total > 0 ? Math.round((running / total) * 100) : 0;
                const healthEl = document.getElementById('health-status');
                healthEl.textContent = `${healthPct}% Healthy`;
                healthEl.className = 'value' + (healthPct < 50 ? ' error' : '');

                document.getElementById('subtitle').textContent =
                    running === total ? 'Your Sovereign Suite is fully operational' :
                    running > 0 ? `${running} of ${total} services running` : 'Services offline';

                document.getElementById('last-check').textContent = new Date().toLocaleTimeString();

            } catch (err) {
                console.error('Failed to load modules:', err);
                grid.innerHTML = `
                    <div class="loading">
                        Failed to load service status.<br>
                        <small style="color:#f44336">${err.message}</small><br>
                        <button class="refresh-btn" style="margin-top:1rem" onclick="loadModules()">Retry</button>
                    </div>
                `;
                document.getElementById('health-status').textContent = 'Unknown';
                document.getElementById('health-status').className = 'value error';
            }
        }

        // Load on page load
        loadModules();

        // Auto-refresh every 30 seconds
        setInterval(loadModules, 30000);
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

    # Create lightweight dashboard API with REAL health checks
    cat > "$api_script" <<'APIEOF'
#!/usr/bin/env python3
"""
WOPR Dashboard API - Local Instance
Provides REAL status checks for the dashboard UI - NO LIES!
"""

import json
import subprocess
import os
import socket
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

def get_systemd_status(service_name):
    """Check if a systemd service is running."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True, text=True, timeout=5
        )
        status = result.stdout.strip()
        return status == 'active', status
    except Exception as e:
        return False, str(e)

def get_container_status(name):
    """Check podman container status."""
    try:
        result = subprocess.run(
            ['podman', 'inspect', '--format', '{{.State.Status}}', name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return 'not_found'
    except:
        return 'unknown'

def check_port_open(port, host='127.0.0.1', timeout=2):
    """Check if a port is listening."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def get_modules():
    """Get REAL status of ALL WOPR services."""
    settings = load_settings()
    domain = settings.get('domain', 'localhost')

    # All WOPR services with their details
    # Format: (systemd_service, display_name, subdomain, description, check_port)
    module_defs = [
        ('wopr-postgresql', 'PostgreSQL', None, 'Database server', 5432),
        ('wopr-redis', 'Redis', None, 'Cache server', 6379),
        ('wopr-authentik-server', 'Authentik', 'auth', 'Identity & SSO', 9000),
        ('wopr-authentik-worker', 'Authentik Worker', None, 'Background jobs', None),
        ('wopr-n8n', 'n8n', 'auto', 'Workflow automation', 5678),
        ('wopr-nextcloud', 'Nextcloud', 'files', 'File storage & sync', 80),
        ('wopr-vaultwarden', 'Vaultwarden', 'vault', 'Password manager', 8080),
        ('wopr-collabora', 'Collabora', 'office', 'Document editing', 9980),
        ('wopr-code-server', 'Code Server', 'code', 'VS Code in browser', 8443),
        ('wopr-portainer', 'Portainer', 'containers', 'Container management', 9443),
        ('wopr-openwebui', 'Open WebUI', 'ai', 'AI chat interface', 3000),
        ('wopr-forgejo', 'Forgejo', 'git', 'Git hosting', 3001),
        ('wopr-woodpecker', 'Woodpecker', 'ci', 'CI/CD pipelines', 8000),
        ('wopr-nocodb', 'NocoDB', 'db', 'Database UI', 8081),
        ('wopr-freshrss', 'FreshRSS', 'rss', 'RSS feed reader', 8082),
        ('wopr-reactor', 'Reactor', 'reactor', 'AI agent platform', 8083),
    ]

    modules = []

    for service, name, subdomain, desc, port in module_defs:
        # Check systemd service status
        is_active, status_text = get_systemd_status(service)

        # Also check container if systemd says active
        container_status = get_container_status(service)

        # Determine actual running state
        if is_active and container_status == 'running':
            status = 'running'
            error = None
        elif container_status == 'running':
            status = 'running'
            error = None
        elif status_text == 'activating':
            status = 'starting'
            error = 'Service is starting up...'
        elif container_status == 'exited':
            status = 'stopped'
            error = 'Container exited'
        elif container_status == 'not_found':
            status = 'stopped'
            error = 'Not deployed'
        else:
            status = 'stopped'
            error = f'Service: {status_text}, Container: {container_status}'

        # Optional port check for running services
        if status == 'running' and port:
            if not check_port_open(port):
                error = f'Port {port} not responding'

        module = {
            'id': service.replace('wopr-', ''),
            'name': name,
            'description': desc,
            'status': status,
            'error': error,
            'category': 'installed' if status == 'running' else 'unavailable'
        }

        # Add URL if service has a subdomain
        if subdomain:
            module['url'] = f'https://{subdomain}.{domain}'
        else:
            module['url'] = None

        modules.append(module)

    return modules

class DashboardAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/api/status':
            settings = load_settings()
            modules = get_modules()
            running = sum(1 for m in modules if m['status'] == 'running')
            total = len(modules)
            health_pct = round((running / total) * 100) if total > 0 else 0

            self._send_json({
                'status': 'healthy' if health_pct >= 80 else 'degraded' if health_pct >= 50 else 'critical',
                'domain': settings.get('domain'),
                'bundle': settings.get('bundle', 'personal'),
                'instance_id': settings.get('instance_id'),
                'services_running': running,
                'services_total': total,
                'health_percent': health_pct,
            })

        elif path == '/api/modules':
            self._send_json(get_modules())

        elif path == '/api/health':
            # Quick health check for monitoring
            modules = get_modules()
            running = sum(1 for m in modules if m['status'] == 'running')
            total = len(modules)
            self._send_json({
                'healthy': running >= (total * 0.8),
                'running': running,
                'total': total,
            })

        elif path == '/api/trials':
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
        pass  # Suppress request logging

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8090))
    server = HTTPServer(('127.0.0.1', port), DashboardAPIHandler)
    print(f'WOPR Dashboard API running on port {port}')
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
