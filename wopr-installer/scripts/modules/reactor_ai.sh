#!/bin/bash
#=================================================
# WOPR MODULE: Reactor AI + DEFCON ONE
# Version: 1.5
# Purpose: Deploy AI coding assistant with safety controls
# Bundle: Developer, Professional (trial available for Personal, Creator)
#
# This module deploys:
# - Ollama (local LLM runtime)
# - Reactor AI (coding assistant)
# - DEFCON ONE (protected actions gateway)
#
# Resource requirements:
# - CPU: 4+ vCPU recommended (LLM inference)
# - RAM: 8GB+ (models load into RAM)
# - Disk: 20GB+ (for model storage)
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../wopr_common.sh"

#=================================================
# MODULE INFO
#=================================================

MODULE_ID="reactor_ai"
MODULE_NAME="Reactor AI"
MODULE_VERSION="1.0.0"
MODULE_DEPENDENCIES=("ollama" "defcon_one")

#=================================================
# DEPLOY OLLAMA (Local LLM Runtime)
#=================================================

wopr_deploy_ollama() {
    wopr_log "INFO" "Deploying Ollama..."

    local data_dir="${WOPR_DATA_DIR}/ollama"
    mkdir -p "$data_dir"

    # Pull Ollama container
    wopr_container_pull "docker.io/ollama/ollama:latest"

    # Create systemd service for Ollama
    cat > /etc/systemd/system/wopr-ollama.service << EOF
[Unit]
Description=WOPR Ollama LLM Runtime
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-ollama
ExecStartPre=-/usr/bin/podman rm wopr-ollama

ExecStart=/usr/bin/podman run --rm \\
    --name wopr-ollama \\
    --network ${WOPR_NETWORK} \\
    -v ${data_dir}:/root/.ollama \\
    -p 127.0.0.1:11434:11434 \\
    docker.io/ollama/ollama:latest serve

ExecStop=/usr/bin/podman stop -t 10 wopr-ollama

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-ollama
    systemctl start wopr-ollama

    # Wait for Ollama to be ready
    wopr_log "INFO" "Waiting for Ollama to start..."
    local retries=30
    while [ $retries -gt 0 ]; do
        if curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done

    if [ $retries -eq 0 ]; then
        wopr_log "WARN" "Ollama may not be fully ready yet"
    fi

    # Pull a small default model for testing
    wopr_log "INFO" "Pulling default model (tinyllama for testing)..."
    curl -s http://127.0.0.1:11434/api/pull -d '{"name": "tinyllama"}' > /dev/null 2>&1 || true

    wopr_setting_set "ollama_installed" "true"
    wopr_setting_set "ollama_endpoint" "http://127.0.0.1:11434"

    wopr_log "OK" "Ollama deployed successfully"
}

#=================================================
# DEPLOY DEFCON ONE (Protected Actions Gateway)
#=================================================

wopr_deploy_defcon_one() {
    wopr_log "INFO" "Deploying DEFCON ONE..."

    local data_dir="${WOPR_DATA_DIR}/defcon-one"
    local build_dir="/root/wopr-build"
    mkdir -p "$data_dir"
    mkdir -p /opt/wopr-deployment-queue/{pending,approved,deployed,failed}

    local domain=$(wopr_setting_get "domain")

    # Clone or update source
    if [ ! -d "$build_dir" ]; then
        wopr_log "INFO" "Cloning WOPR source repository..."
        git clone https://vault.wopr.systems/WOPRSystems/wopr-installer.git "$build_dir" 2>&1 || {
            wopr_log "ERROR" "Failed to clone WOPR repository"
            return 1
        }
    else
        wopr_log "INFO" "Updating WOPR source..."
        (cd "$build_dir" && git pull origin main 2>&1) || true
    fi

    # Build DEFCON ONE container image from source
    wopr_log "INFO" "Building DEFCON ONE container image..."
    if [ -d "$build_dir/wopr-approval-dashboard" ]; then
        podman build -t localhost/wopr-defcon-one:latest "$build_dir/wopr-approval-dashboard" 2>&1 || {
            wopr_log "ERROR" "Failed to build DEFCON ONE image"
            return 1
        }
    else
        wopr_log "ERROR" "DEFCON ONE source not found at $build_dir/wopr-approval-dashboard"
        return 1
    fi

    # Create systemd service
    cat > /etc/systemd/system/wopr-defcon-one.service << EOF
[Unit]
Description=WOPR DEFCON ONE Approval Dashboard
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-defcon-one
ExecStartPre=-/usr/bin/podman rm wopr-defcon-one

ExecStart=/usr/bin/podman run --rm \\
    --name wopr-defcon-one \\
    --network ${WOPR_NETWORK} \\
    -v /opt/wopr-deployment-queue:/opt/wopr-deployment-queue:Z \\
    -p 127.0.0.1:8601:8080 \\
    localhost/wopr-defcon-one:latest

ExecStop=/usr/bin/podman stop -t 10 wopr-defcon-one

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-defcon-one
    systemctl start wopr-defcon-one || wopr_log "WARN" "DEFCON ONE service start deferred"

    # Configure Caddy route
    wopr_caddy_add_route "defcon.${domain}" "http://127.0.0.1:8601"

    wopr_setting_set "defcon_one_installed" "true"
    wopr_setting_set "defcon_one_url" "https://defcon.${domain}"

    wopr_defcon_log "DEFCON_ONE_DEPLOYED" "Protected actions gateway active"
    wopr_log "OK" "DEFCON ONE deployed successfully"
}

#=================================================
# DEPLOY REACTOR AI (AI Remediation Engine)
#=================================================

wopr_deploy_reactor_ai() {
    wopr_log "INFO" "Deploying Reactor AI (Remediation Engine)..."

    local data_dir="${WOPR_DATA_DIR}/ai-engine"
    local build_dir="/root/wopr-build"
    mkdir -p "$data_dir"

    local domain=$(wopr_setting_get "domain")

    # Ensure source is available
    if [ ! -d "$build_dir/ai-engine" ]; then
        wopr_log "ERROR" "AI Engine source not found. Run DEFCON ONE deployment first."
        return 1
    fi

    # Build AI Engine container image from source
    wopr_log "INFO" "Building Reactor AI (AI Engine) container image..."
    podman build -t localhost/wopr-ai-engine:latest "$build_dir/ai-engine" 2>&1 || {
        wopr_log "ERROR" "Failed to build AI Engine image"
        return 1
    }

    # Create systemd service
    cat > /etc/systemd/system/wopr-ai-engine.service << EOF
[Unit]
Description=WOPR AI Remediation Engine (Reactor AI)
After=network.target wopr-ollama.service wopr-postgresql.service
Wants=wopr-ollama.service

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-ai-engine
ExecStartPre=-/usr/bin/podman rm wopr-ai-engine

ExecStart=/usr/bin/podman run --rm \\
    --name wopr-ai-engine \\
    --network ${WOPR_NETWORK} \\
    -v ${data_dir}:/data:Z \\
    -e OLLAMA_URL=http://wopr-ollama:11434 \\
    -e OLLAMA_MODEL=phi3:mini \\
    -e AI_ENGINE_DB=/data/ai_engine.db \\
    -e SCAN_INTERVAL=300 \\
    -p 127.0.0.1:8600:8000 \\
    localhost/wopr-ai-engine:latest

ExecStop=/usr/bin/podman stop -t 10 wopr-ai-engine

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-ai-engine
    systemctl start wopr-ai-engine || wopr_log "WARN" "AI Engine service start deferred"

    # Configure Caddy route
    wopr_caddy_add_route "reactor.${domain}" "http://127.0.0.1:8600"

    wopr_setting_set "reactor_installed" "true"
    wopr_setting_set "reactor_url" "https://reactor.${domain}"

    wopr_defcon_log "REACTOR_DEPLOYED" "AI remediation engine active"
    wopr_log "OK" "Reactor AI deployed successfully"
}

#=================================================
# DEPLOY SUPPORT PLANE (Zero-Trust Support Gateway)
#=================================================

wopr_deploy_support_client() {
    # Support Client - allows beacon to receive WOPR staff support
    # NOTE: Admin escalations dashboard is LIGHTHOUSE-ONLY (not deployed here)
    wopr_log "INFO" "Deploying Support Client (beacon-side)..."

    local build_dir="/root/wopr-build"
    local domain=$(wopr_setting_get "domain")

    # Ensure source is available
    if [ ! -d "$build_dir/wopr-support-plane" ]; then
        wopr_log "ERROR" "Support Client source not found"
        return 1
    fi

    # Build Support Client container image (uses support-plane codebase with WOPR_MODE=beacon)
    wopr_log "INFO" "Building Support Client container image..."
    podman build -t localhost/wopr-support-client:latest "$build_dir/wopr-support-plane" 2>&1 || {
        wopr_log "ERROR" "Failed to build Support Client image"
        return 1
    }

    # Create systemd service (no database needed for client-only mode)
    cat > /etc/systemd/system/wopr-support-client.service << EOF
[Unit]
Description=WOPR Support Client (Receive Staff Support)
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-support-client
ExecStartPre=-/usr/bin/podman rm wopr-support-client

ExecStart=/usr/bin/podman run --rm \\
    --name wopr-support-client \\
    --network ${WOPR_NETWORK} \\
    -e WOPR_MODE=beacon \\
    -e SUPPORT_GW_HOST=0.0.0.0 \\
    -e SUPPORT_GW_PORT=8444 \\
    -e LOG_LEVEL=INFO \\
    -p 127.0.0.1:8444:8444 \\
    localhost/wopr-support-client:latest

ExecStop=/usr/bin/podman stop -t 10 wopr-support-client

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-support-client
    systemctl start wopr-support-client || wopr_log "WARN" "Support Client service start deferred"

    # Configure Caddy route for beacon owner status page only
    wopr_caddy_add_route "support.${domain}" "http://127.0.0.1:8444"

    wopr_setting_set "support_client_installed" "true"
    wopr_setting_set "support_client_url" "https://support.${domain}"

    wopr_log "OK" "Support Client deployed successfully"
}

#=================================================
# DEPLOY DEPLOYMENT QUEUE
#=================================================

wopr_deploy_deployment_queue() {
    wopr_log "INFO" "Deploying Deployment Queue..."

    local build_dir="/root/wopr-build"

    # Ensure source is available
    if [ ! -d "$build_dir/wopr-deployment-queue" ]; then
        wopr_log "ERROR" "Deployment Queue source not found"
        return 1
    fi

    # Build Deployment Queue container image
    wopr_log "INFO" "Building Deployment Queue container image..."
    podman build -t localhost/wopr-deployment-queue:latest "$build_dir/wopr-deployment-queue" 2>&1 || {
        wopr_log "ERROR" "Failed to build Deployment Queue image"
        return 1
    }

    # Create systemd service
    cat > /etc/systemd/system/wopr-deployment-queue.service << EOF
[Unit]
Description=WOPR Deployment Queue Manager
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 wopr-deployment-queue
ExecStartPre=-/usr/bin/podman rm wopr-deployment-queue

ExecStart=/usr/bin/podman run --rm \\
    --name wopr-deployment-queue \\
    --network ${WOPR_NETWORK} \\
    -v /opt/wopr-deployment-queue:/opt/wopr-deployment-queue:Z \\
    localhost/wopr-deployment-queue:latest

ExecStop=/usr/bin/podman stop -t 10 wopr-deployment-queue

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-deployment-queue
    systemctl start wopr-deployment-queue || wopr_log "WARN" "Deployment Queue service start deferred"

    wopr_setting_set "deployment_queue_installed" "true"

    wopr_log "OK" "Deployment Queue deployed successfully"
}

#=================================================
# MAIN DEPLOY FUNCTION
#=================================================

wopr_deploy_reactor_ai_bundle() {
    wopr_log "INFO" "Deploying WOPR Ops/Control Plane (Ollama + DEFCON ONE + Reactor + Support + Queue)..."

    # Check resources
    local cpu_count=$(nproc)
    local ram_gb=$(free -g | awk '/^Mem:/{print $2}')

    if [ "$cpu_count" -lt 4 ]; then
        wopr_log "WARN" "Less than 4 CPUs detected. Reactor AI may be slow."
    fi

    if [ "$ram_gb" -lt 8 ]; then
        wopr_log "WARN" "Less than 8GB RAM detected. LLM performance may be limited."
    fi

    # Deploy in order: Ollama -> DEFCON ONE -> Reactor -> Support Plane -> Deployment Queue
    wopr_deploy_ollama
    wopr_deploy_defcon_one
    wopr_deploy_reactor_ai
    wopr_deploy_support_plane
    wopr_deploy_deployment_queue

    # Log completion
    wopr_defcon_log "OPS_PLANE_COMPLETE" "cpu=$cpu_count,ram=${ram_gb}GB"

    wopr_log "OK" "WOPR Ops/Control Plane deployment complete!"
    echo ""
    echo "  Reactor AI (remediation engine): https://reactor.$(wopr_setting_get domain)"
    echo "  DEFCON ONE (approval dashboard): https://defcon.$(wopr_setting_get domain)"
    echo "  Support Plane (zero-trust gateway): https://support.$(wopr_setting_get domain)"
    echo ""
    echo "  AI doesn't get root. People do."
    echo ""
}

#=================================================
# TRIAL MODE
#=================================================

wopr_deploy_reactor_trial() {
    wopr_log "INFO" "Deploying Reactor AI trial..."

    # Same deployment but with trial tracking
    export REACTOR_TRIAL_MODE=true

    wopr_deploy_reactor_ai_bundle

    wopr_setting_set "reactor_trial_started" "$(date -Iseconds)"
    wopr_setting_set "reactor_trial_expires" "$(date -d '+90 days' -Iseconds)"

    wopr_log "OK" "Reactor AI 90-day trial activated!"
    echo ""
    echo "  Your trial includes:"
    echo "    - Ollama (local LLM runtime)"
    echo "    - Reactor AI (coding assistant)"
    echo "    - DEFCON ONE (safety controls)"
    echo ""
    echo "  Trial expires in 90 days."
    echo "  Upgrade to Developer bundle to keep these features!"
    echo ""
}

#=================================================
# ENTRY POINT
#=================================================

if [[ "${1:-}" == "trial" ]]; then
    wopr_deploy_reactor_trial
else
    wopr_deploy_reactor_ai_bundle
fi
