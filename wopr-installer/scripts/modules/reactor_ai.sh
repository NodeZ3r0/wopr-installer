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
ExecStart=/usr/bin/podman run --rm \\
    --name wopr-ollama \\
    --network \${WOPR_NETWORK} \\
    -v ${data_dir}:/root/.ollama:Z \\
    -p 127.0.0.1:11434:11434 \\
    docker.io/ollama/ollama:latest
Restart=always
RestartSec=10

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
    mkdir -p "$data_dir"
    mkdir -p "$data_dir/audit"

    local domain=$(wopr_setting_get "domain")
    local pg_password=$(wopr_setting_get "postgresql_password")

    # Generate DEFCON ONE secret key
    local defcon_secret=$(wopr_random_string 64)
    wopr_setting_set "defcon_secret_key" "$defcon_secret"

    # Pull DEFCON ONE container
    wopr_container_pull "ghcr.io/wopr/defcon-one:latest" || {
        wopr_log "WARN" "DEFCON ONE container not available, using placeholder"
        # Create placeholder for development
        wopr_setting_set "defcon_one_installed" "placeholder"
        return 0
    }

    # Create DEFCON ONE configuration
    cat > "$data_dir/config.json" << EOF
{
    "environment": "production",
    "protected_environments": ["production"],
    "protected_branches": ["main", "master", "production", "release/*"],
    "database_url": "postgresql://wopr:${pg_password}@localhost:5432/defcon_one",
    "authentik_url": "https://auth.${domain}",
    "audit_log_path": "/data/audit",
    "require_approval_for": [
        "git_push_protected",
        "git_merge_protected",
        "deploy_production",
        "write_secret",
        "infrastructure_change"
    ]
}
EOF

    # Create systemd service
    cat > /etc/systemd/system/wopr-defcon-one.service << EOF
[Unit]
Description=WOPR DEFCON ONE Protected Actions Gateway
After=network.target wopr-postgresql.service

[Service]
Type=simple
ExecStart=/usr/bin/podman run --rm \\
    --name wopr-defcon-one \\
    --network \${WOPR_NETWORK} \\
    -v ${data_dir}:/data:Z \\
    -v ${data_dir}/config.json:/app/config.json:ro \\
    -p 127.0.0.1:8081:8081 \\
    -e SECRET_KEY=${defcon_secret} \\
    -e DATABASE_URL=postgresql://wopr:${pg_password}@wopr-postgresql:5432/defcon_one \\
    ghcr.io/wopr/defcon-one:latest
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-defcon-one
    systemctl start wopr-defcon-one || wopr_log "WARN" "DEFCON ONE service start deferred"

    # Configure Caddy route
    wopr_caddy_add_route "defcon.${domain}" "http://127.0.0.1:8081"

    wopr_setting_set "defcon_one_installed" "true"
    wopr_setting_set "defcon_one_url" "https://defcon.${domain}"

    wopr_defcon_log "DEFCON_ONE_DEPLOYED" "Protected actions gateway active"
    wopr_log "OK" "DEFCON ONE deployed successfully"
}

#=================================================
# DEPLOY REACTOR AI
#=================================================

wopr_deploy_reactor_ai() {
    wopr_log "INFO" "Deploying Reactor AI..."

    local data_dir="${WOPR_DATA_DIR}/reactor"
    mkdir -p "$data_dir"
    mkdir -p "$data_dir/workspaces"

    local domain=$(wopr_setting_get "domain")
    local pg_password=$(wopr_setting_get "postgresql_password")
    local ollama_endpoint=$(wopr_setting_get "ollama_endpoint")
    local defcon_url=$(wopr_setting_get "defcon_one_url")

    # Generate Reactor secret key
    local reactor_secret=$(wopr_random_string 64)
    wopr_setting_set "reactor_secret_key" "$reactor_secret"

    # Pull Reactor container
    wopr_container_pull "ghcr.io/wopr/reactor:latest" || {
        wopr_log "WARN" "Reactor container not available, using placeholder"
        wopr_setting_set "reactor_installed" "placeholder"
        return 0
    }

    # Create Reactor configuration
    cat > "$data_dir/config.yaml" << EOF
# Reactor AI Configuration
version: "1.0"

server:
  host: "0.0.0.0"
  port: 8080

database:
  url: "postgresql://wopr:${pg_password}@wopr-postgresql:5432/reactor"

ollama:
  endpoint: "http://wopr-ollama:11434"
  default_model: "codellama"
  timeout: 120

defcon_one:
  enabled: true
  endpoint: "http://wopr-defcon-one:8081"
  require_approval_for_production: true

authentik:
  enabled: true
  issuer: "https://auth.${domain}"

workspaces:
  base_path: "/data/workspaces"
  max_per_user: 5

# Two-Lane Execution Model
execution:
  lane_a:  # Unrestricted iteration
    - code_generation
    - local_edits
    - feature_branching
    - commits_to_non_protected
    - test_execution
    - dev_server
    - staging_deploys
  lane_b:  # Protected (requires DEFCON approval)
    - merge_to_protected
    - push_to_protected
    - tag_release
    - production_deploy
    - secrets_mutation
    - infrastructure_change
EOF

    # Create systemd service
    cat > /etc/systemd/system/wopr-reactor.service << EOF
[Unit]
Description=WOPR Reactor AI Coding Assistant
After=network.target wopr-ollama.service wopr-defcon-one.service

[Service]
Type=simple
ExecStart=/usr/bin/podman run --rm \\
    --name wopr-reactor \\
    --network \${WOPR_NETWORK} \\
    -v ${data_dir}:/data:Z \\
    -v ${data_dir}/config.yaml:/app/config.yaml:ro \\
    -p 127.0.0.1:8080:8080 \\
    -e SECRET_KEY=${reactor_secret} \\
    ghcr.io/wopr/reactor:latest
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wopr-reactor
    systemctl start wopr-reactor || wopr_log "WARN" "Reactor service start deferred"

    # Configure Caddy route
    wopr_caddy_add_route "reactor.${domain}" "http://127.0.0.1:8080"

    wopr_setting_set "reactor_installed" "true"
    wopr_setting_set "reactor_url" "https://reactor.${domain}"

    wopr_defcon_log "REACTOR_DEPLOYED" "AI coding assistant active"
    wopr_log "OK" "Reactor AI deployed successfully"
}

#=================================================
# MAIN DEPLOY FUNCTION
#=================================================

wopr_deploy_reactor_ai_bundle() {
    wopr_log "INFO" "Deploying Reactor AI bundle (Ollama + DEFCON ONE + Reactor)..."

    # Check resources
    local cpu_count=$(nproc)
    local ram_gb=$(free -g | awk '/^Mem:/{print $2}')

    if [ "$cpu_count" -lt 4 ]; then
        wopr_log "WARN" "Less than 4 CPUs detected. Reactor AI may be slow."
    fi

    if [ "$ram_gb" -lt 8 ]; then
        wopr_log "WARN" "Less than 8GB RAM detected. LLM performance may be limited."
    fi

    # Deploy dependencies first
    wopr_deploy_ollama
    wopr_deploy_defcon_one

    # Deploy Reactor
    wopr_deploy_reactor_ai

    # Log completion
    wopr_defcon_log "REACTOR_BUNDLE_COMPLETE" "cpu=$cpu_count,ram=${ram_gb}GB"

    wopr_log "OK" "Reactor AI bundle deployment complete!"
    echo ""
    echo "  Reactor AI is now available at: https://reactor.$(wopr_setting_get domain)"
    echo "  DEFCON ONE dashboard: https://defcon.$(wopr_setting_get domain)"
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
