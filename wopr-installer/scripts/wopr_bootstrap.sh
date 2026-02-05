#!/bin/bash
#=================================================
# WOPR BOOTSTRAP WITH SELF-HEALING
# Version: 1.0
# Purpose: Wrapper that runs installer with retry logic,
#          AI-assisted debugging, and support ticket creation
#
# Usage: This script is called by cloud-init instead of wopr_install.sh directly.
#        It handles failures gracefully with up to 5 retry attempts.
#=================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_FILE="/etc/wopr/bootstrap.json"
WOPR_LOG="/var/log/wopr/installer.log"
RETRY_LOG="/var/log/wopr/retry.log"
RETRIES_PER_MODEL=5
SUPPORT_EMAIL="stephen.falken@wopr.systems"

# AI models to try in order (smaller/faster first, then larger/smarter)
# Tier 1: tinyllama (1.1B params) - fast, low memory
# Tier 2: mistral (7B params) - good balance
# Tier 3: phi3:medium (14B params) - most capable
AI_MODELS=("tinyllama" "mistral" "phi3:medium")
CURRENT_MODEL_INDEX=0
CURRENT_MODEL="${AI_MODELS[0]}"

#=================================================
# HELPER FUNCTIONS
#=================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$RETRY_LOG"
    echo "[$timestamp] [$level] $message" >&2
}

get_orchestrator_url() {
    if [ -f "$BOOTSTRAP_FILE" ]; then
        jq -r '.orchestrator_url // empty' "$BOOTSTRAP_FILE"
    fi
}

get_job_id() {
    if [ -f "$BOOTSTRAP_FILE" ]; then
        jq -r '.job_id // empty' "$BOOTSTRAP_FILE"
    fi
}

get_domain() {
    if [ -f "$BOOTSTRAP_FILE" ]; then
        jq -r '.domain // empty' "$BOOTSTRAP_FILE"
    fi
}

#=================================================
# STATUS REPORTING
#=================================================

report_status() {
    local status="$1"
    local message="${2:-}"
    local retry_count="${3:-0}"

    local orc_url=$(get_orchestrator_url)
    local job_id=$(get_job_id)

    if [ -n "$orc_url" ] && [ -n "$job_id" ]; then
        curl -sf -X POST "${orc_url}/api/v1/provision/${job_id}/status" \
            -H "Content-Type: application/json" \
            -d "{\"status\": \"$status\", \"message\": \"$message\", \"retry_count\": $retry_count}" \
            2>/dev/null || true
    fi
}

#=================================================
# AI SELF-HEAL (uses local Ollama if available)
#=================================================

ai_analyze_failure() {
    local error_log="$1"
    local last_lines=$(tail -100 "$WOPR_LOG" 2>/dev/null || echo "No log available")

    # Check if Ollama is running
    if ! curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
        log "WARN" "Ollama not available for AI analysis"
        return 1
    fi

    log "INFO" "Analyzing failure with AI model: ${CURRENT_MODEL}..."

    # Create prompt for AI analysis
    local prompt="You are a WOPR installer debugger. Analyze this error and suggest a fix.

ERROR LOG:
${last_lines}

Respond with ONLY a bash command or short script that might fix the issue.
If unfixable, respond with: UNFIXABLE: <reason>
Keep response under 500 chars."

    # Call Ollama with current model
    local response=$(curl -s http://127.0.0.1:11434/api/generate \
        -d "{\"model\": \"${CURRENT_MODEL}\", \"prompt\": \"$prompt\", \"stream\": false}" \
        2>/dev/null | jq -r '.response // empty' | head -c 500)

    if [ -n "$response" ] && ! echo "$response" | grep -q "^UNFIXABLE"; then
        log "INFO" "AI (${CURRENT_MODEL}) suggested fix: $response"
        echo "$response"
        return 0
    else
        log "WARN" "AI (${CURRENT_MODEL}) could not suggest a fix: $response"
        return 1
    fi
}

switch_ai_model() {
    CURRENT_MODEL_INDEX=$((CURRENT_MODEL_INDEX + 1))
    if [ $CURRENT_MODEL_INDEX -ge ${#AI_MODELS[@]} ]; then
        log "WARN" "No more AI models to try"
        return 1
    fi
    CURRENT_MODEL="${AI_MODELS[$CURRENT_MODEL_INDEX]}"
    log "INFO" "Switching to AI model: ${CURRENT_MODEL}"

    # Pull the new model
    log "INFO" "Pulling model ${CURRENT_MODEL}..."
    curl -s http://127.0.0.1:11434/api/pull -d "{\"name\":\"${CURRENT_MODEL}\"}" >/dev/null 2>&1

    # Wait for pull to complete (simple check)
    local count=0
    while [ $count -lt 120 ]; do
        if curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | grep -q "\"${CURRENT_MODEL}\""; then
            log "OK" "Model ${CURRENT_MODEL} ready"
            return 0
        fi
        sleep 5
        count=$((count + 5))
    done

    log "WARN" "Model ${CURRENT_MODEL} may not be ready, continuing anyway"
    return 0
}

attempt_ai_fix() {
    local fix_script="$1"

    if [ -z "$fix_script" ]; then
        return 1
    fi

    log "INFO" "Attempting AI-suggested fix..."

    # Save the fix script
    echo "$fix_script" > /tmp/wopr_ai_fix.sh
    chmod +x /tmp/wopr_ai_fix.sh

    # Execute with timeout and capture output
    if timeout 60 bash /tmp/wopr_ai_fix.sh >> "$RETRY_LOG" 2>&1; then
        log "OK" "AI fix executed successfully"
        return 0
    else
        log "WARN" "AI fix failed"
        return 1
    fi
}

#=================================================
# SUPPORT TICKET CREATION
#=================================================

send_support_ticket() {
    local domain=$(get_domain)
    local job_id=$(get_job_id)
    local orc_url=$(get_orchestrator_url)

    log "ERROR" "Max retries ($MAX_RETRIES) exceeded. Creating support ticket..."

    # Gather diagnostic info
    local diag_info=$(cat << DIAGEOF
WOPR Installation Failed - Support Ticket
==========================================

Job ID: ${job_id}
Domain: ${domain}
Timestamp: $(date -Iseconds)
Retry Count: $MAX_RETRIES
Server IP: $(hostname -I | awk '{print $1}')
Kernel: $(uname -r)
Memory: $(free -h | grep Mem | awk '{print $2}')
Disk: $(df -h / | tail -1 | awk '{print $4}') available

Last 50 lines of installer log:
--------------------------------
$(tail -50 "$WOPR_LOG" 2>/dev/null || echo "Log not available")

Last 20 lines of retry log:
---------------------------
$(tail -20 "$RETRY_LOG" 2>/dev/null || echo "Retry log not available")

Container status:
-----------------
$(podman ps -a 2>/dev/null || echo "Podman not available")

Failed services:
----------------
$(systemctl list-units --state=failed 'wopr-*' 2>/dev/null || echo "No failed wopr services")

DIAGEOF
)

    # Save diagnostic file
    local diag_file="/var/log/wopr/support_ticket_${job_id}.txt"
    echo "$diag_info" > "$diag_file"

    # Try to send via orchestrator API
    if [ -n "$orc_url" ] && [ -n "$job_id" ]; then
        curl -sf -X POST "${orc_url}/api/v1/provision/${job_id}/support-ticket" \
            -H "Content-Type: application/json" \
            -d "{\"email\": \"$SUPPORT_EMAIL\", \"subject\": \"Installation Failed: ${domain}\", \"body\": $(jq -Rs . <<< "$diag_info")}" \
            2>/dev/null && {
            log "OK" "Support ticket sent via orchestrator"
            return 0
        }
    fi

    # Fallback: try direct email via mailx/sendmail
    if command -v mail &> /dev/null; then
        echo "$diag_info" | mail -s "WOPR Installation Failed: ${domain}" "$SUPPORT_EMAIL" && {
            log "OK" "Support ticket sent via mail"
            return 0
        }
    fi

    # Fallback: try ntfy if available
    if curl -s http://127.0.0.1:8092/health > /dev/null 2>&1; then
        curl -s -X POST "http://127.0.0.1:8092/wopr-support" \
            -H "Title: Installation Failed: ${domain}" \
            -H "Priority: urgent" \
            -H "Tags: warning,wopr,installer" \
            -d "Job: ${job_id}
Max retries exceeded. Check ${diag_file} for details.
Email: ${SUPPORT_EMAIL}" 2>/dev/null && {
            log "OK" "Support notification sent via ntfy"
        }
    fi

    log "WARN" "Support ticket saved to $diag_file (manual review needed)"
    return 1
}

#=================================================
# MAIN INSTALLER LOOP
#=================================================

run_installer() {
    local total_retries=0
    local model_retries=0
    local max_total=$((RETRIES_PER_MODEL * ${#AI_MODELS[@]}))

    mkdir -p /var/log/wopr

    log "INFO" "Starting WOPR bootstrap with self-healing"
    log "INFO" "Strategy: ${RETRIES_PER_MODEL} tries per model, ${#AI_MODELS[@]} models = ${max_total} max attempts"
    report_status "installing" "Starting installation" "0"

    while [ $total_retries -lt $max_total ]; do
        total_retries=$((total_retries + 1))
        model_retries=$((model_retries + 1))

        log "INFO" "=== Attempt $total_retries (model: ${CURRENT_MODEL}, model try: $model_retries/$RETRIES_PER_MODEL) ==="
        report_status "installing" "Attempt $total_retries - AI: ${CURRENT_MODEL}" "$total_retries"

        # Run the actual installer
        if "${SCRIPT_DIR}/wopr_install.sh" --non-interactive --confirm-all 2>&1 | tee -a "$WOPR_LOG"; then
            log "OK" "Installation completed successfully on attempt $total_retries"
            report_status "complete" "Installation successful" "$total_retries"
            return 0
        fi

        local exit_code=$?
        log "ERROR" "Installation failed with exit code $exit_code"

        # Check if we should switch models
        if [ $model_retries -ge $RETRIES_PER_MODEL ]; then
            log "INFO" "Exhausted $RETRIES_PER_MODEL attempts with ${CURRENT_MODEL}"
            if switch_ai_model; then
                model_retries=0
                report_status "retrying" "Switching to AI model: ${CURRENT_MODEL}" "$total_retries"
            else
                # No more models to try
                break
            fi
        fi

        # Don't retry if we've exhausted everything
        if [ $total_retries -ge $max_total ]; then
            break
        fi

        report_status "retrying" "Attempt $total_retries failed, AI analyzing..." "$total_retries"

        # Try AI-assisted debugging
        local ai_fix=""
        if ai_fix=$(ai_analyze_failure "$WOPR_LOG"); then
            if attempt_ai_fix "$ai_fix"; then
                log "INFO" "AI fix applied (${CURRENT_MODEL}), retrying installation..."
                sleep 5
                continue
            fi
        fi

        # No AI fix available, try basic recovery steps
        log "INFO" "Attempting basic recovery before retry..."
        perform_basic_recovery

        # Wait before retry (shorter waits, we have more attempts now)
        local wait_time=$((model_retries * 15))
        log "INFO" "Waiting ${wait_time}s before retry..."
        sleep "$wait_time"
    done

    # All retries exhausted across all models
    log "ERROR" "All $total_retries attempts exhausted across ${#AI_MODELS[@]} AI models"
    report_status "failed" "All retries exhausted" "$total_retries"
    send_support_ticket

    return 1
}

perform_basic_recovery() {
    # Stop all wopr services cleanly
    log "INFO" "Stopping all WOPR services..."
    systemctl stop 'wopr-*' 2>/dev/null || true

    # Kill stale conmon processes (containers stuck in "Stopping")
    pkill -9 conmon 2>/dev/null || true
    sleep 2

    # Force remove ALL containers - clean slate for retry
    log "INFO" "Removing all containers for clean retry..."
    podman stop -a -t 5 2>/dev/null || true
    podman rm -af 2>/dev/null || true

    # Reset failed systemd units
    for svc in $(systemctl list-units --state=failed 'wopr-*' --no-legend 2>/dev/null | awk '{print $1}'); do
        log "INFO" "Resetting failed service: $svc"
        systemctl reset-failed "$svc" 2>/dev/null || true
    done
}

#=================================================
# OLLAMA INSTALLATION (needed for AI self-heal)
#=================================================

install_ollama_for_debug() {
    log "INFO" "Installing Ollama for AI-assisted debugging..."

    # Skip if already running
    if curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
        log "OK" "Ollama already running"
        return 0
    fi

    # Install podman if needed (should be there but just in case)
    if ! command -v podman &> /dev/null; then
        apt-get update -qq && apt-get install -y -qq podman >/dev/null 2>&1
    fi

    # Create data dir
    mkdir -p /var/lib/wopr/ollama

    # Create wopr-network if not exists
    podman network exists wopr-network 2>/dev/null || \
        podman network create wopr-network >/dev/null 2>&1

    # Pull and run Ollama
    log "INFO" "Pulling Ollama image..."
    podman pull docker.io/ollama/ollama:latest >/dev/null 2>&1 || {
        log "WARN" "Failed to pull Ollama - AI debug will be unavailable"
        return 1
    }

    # Create systemd service for Ollama
    cat > /etc/systemd/system/wopr-ollama.service << 'SVCEOF'
[Unit]
Description=WOPR Ollama (AI Debug)
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=5
ExecStartPre=-/usr/bin/podman stop -t 5 wopr-ollama
ExecStartPre=-/usr/bin/podman rm -f wopr-ollama
ExecStart=/usr/bin/podman run --rm \
    --name wopr-ollama \
    --network wopr-network \
    -v /var/lib/wopr/ollama:/root/.ollama:Z \
    -p 127.0.0.1:11434:11434 \
    docker.io/ollama/ollama:latest
ExecStop=/usr/bin/podman stop -t 5 wopr-ollama

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    systemctl enable wopr-ollama >/dev/null 2>&1
    systemctl start wopr-ollama

    # Wait for Ollama to be ready
    log "INFO" "Waiting for Ollama to start..."
    local count=0
    while [ $count -lt 30 ]; do
        if curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
            log "OK" "Ollama is ready"

            # Pull a small model for debugging
            log "INFO" "Pulling tinyllama model for AI debug..."
            curl -s http://127.0.0.1:11434/api/pull -d '{"name":"tinyllama"}' >/dev/null 2>&1 &
            # Don't wait - let it pull in background while installer runs

            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    log "WARN" "Ollama failed to start - AI debug will be unavailable"
    return 1
}

#=================================================
# ENTRY POINT
#=================================================

main() {
    # Ensure we have bootstrap.json
    if [ ! -f "$BOOTSTRAP_FILE" ]; then
        log "ERROR" "Bootstrap file not found: $BOOTSTRAP_FILE"
        exit 1
    fi

    mkdir -p /var/log/wopr

    # Ensure all scripts are executable (git checkout can reset permissions)
    chmod +x "${SCRIPT_DIR}"/*.sh "${SCRIPT_DIR}"/modules/*.sh 2>/dev/null || true

    # Install Ollama FIRST so AI can help debug any failures
    install_ollama_for_debug || true

    run_installer
}

main "$@"
