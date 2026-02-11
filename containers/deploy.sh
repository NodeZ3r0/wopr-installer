#!/bin/bash
# WOPR Control Plane Deployment Script
# =====================================
#
# Deploys the containerized control plane to a Linux host.
#
# Usage:
#   ./deploy.sh                    # Full deployment
#   ./deploy.sh --build-only       # Just build the image
#   ./deploy.sh --update           # Pull latest and restart
#
# Prerequisites:
#   - Podman installed
#   - Root or podman-socket access
#   - .env file configured

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="ghcr.io/woprsystems/control-plane"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ============================================
# PREFLIGHT CHECKS
# ============================================
preflight() {
    log "Running preflight checks..."

    # Check podman
    if ! command -v podman &>/dev/null; then
        error "Podman not found. Install with: dnf install podman"
        exit 1
    fi

    # Check .env
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        error ".env file not found at $PROJECT_ROOT/.env"
        error "Copy .env.example and fill in your secrets"
        exit 1
    fi

    # Check required env vars
    source "$PROJECT_ROOT/.env"
    local missing=()
    [[ -z "${STRIPE_TEST_SECRET_KEY:-}" ]] && missing+=("STRIPE_TEST_SECRET_KEY")
    [[ -z "${HETZNER_API_TOKEN:-}" ]] && missing+=("HETZNER_API_TOKEN")
    [[ -z "${DATABASE_URL:-}" ]] && missing+=("DATABASE_URL")

    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required environment variables:"
        for var in "${missing[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi

    log "Preflight checks passed!"
}

# ============================================
# BUILD IMAGE
# ============================================
build_image() {
    log "Building container image..."

    cd "$PROJECT_ROOT"

    local build_date=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local version=$(cat VERSION 2>/dev/null || echo "1.0.0")

    podman build \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        -t "${IMAGE_NAME}:${git_commit}" \
        -f containers/control-plane/Containerfile \
        --build-arg VERSION="$version" \
        --build-arg BUILD_DATE="$build_date" \
        --build-arg GIT_COMMIT="$git_commit" \
        .

    log "Image built: ${IMAGE_NAME}:${IMAGE_TAG}"
}

# ============================================
# INSTALL SYSTEMD UNITS
# ============================================
install_systemd() {
    log "Installing systemd units..."

    local quadlet_dir="/etc/containers/systemd"
    local env_dir="/etc/wopr"

    # Create directories
    mkdir -p "$quadlet_dir" "$env_dir"

    # Copy quadlet files
    cp "$SCRIPT_DIR/systemd/wopr-orc.container" "$quadlet_dir/"
    cp "$SCRIPT_DIR/systemd/wopr-provider-health.container" "$quadlet_dir/"
    cp "$SCRIPT_DIR/systemd/wopr-provider-health.timer" "$quadlet_dir/"

    # Copy environment file
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        cp "$PROJECT_ROOT/.env" "$env_dir/orchestrator.env"
        chmod 600 "$env_dir/orchestrator.env"
    fi

    # Reload systemd
    systemctl daemon-reload

    log "Systemd units installed!"
}

# ============================================
# START SERVICES
# ============================================
start_services() {
    log "Starting WOPR services..."

    # Start orchestrator
    systemctl enable --now wopr-orc.service

    # Start health monitor timer
    systemctl enable --now wopr-provider-health.timer

    # Wait for health
    log "Waiting for orchestrator to be healthy..."
    local attempts=0
    while [[ $attempts -lt 30 ]]; do
        if curl -sf http://localhost:8001/api/health &>/dev/null; then
            log "Orchestrator is healthy!"
            return 0
        fi
        sleep 2
        attempts=$((attempts + 1))
    done

    warn "Orchestrator health check timed out. Check logs: journalctl -u wopr-orc"
}

# ============================================
# STATUS
# ============================================
show_status() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           WOPR Control Plane Deployment Status               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${GREEN}Services:${NC}"
    systemctl status wopr-orc.service --no-pager | head -5 || true
    echo ""

    echo -e "${GREEN}Health Check:${NC}"
    curl -s http://localhost:8001/api/health | jq . 2>/dev/null || echo "  Not responding"
    echo ""

    echo -e "${GREEN}Timer Status:${NC}"
    systemctl list-timers wopr-provider-health.timer --no-pager || true
    echo ""

    echo -e "${GREEN}Useful Commands:${NC}"
    echo "  journalctl -u wopr-orc -f              # Follow logs"
    echo "  systemctl restart wopr-orc             # Restart orchestrator"
    echo "  podman logs -f wopr-orc                # Container logs"
    echo "  curl localhost:8001/api/health         # Health check"
    echo ""
}

# ============================================
# MAIN
# ============================================
main() {
    case "${1:-}" in
        --build-only)
            preflight
            build_image
            ;;
        --update)
            log "Updating WOPR Control Plane..."
            podman pull "${IMAGE_NAME}:${IMAGE_TAG}" || build_image
            systemctl restart wopr-orc.service
            show_status
            ;;
        --status)
            show_status
            ;;
        *)
            preflight
            build_image
            install_systemd
            start_services
            show_status
            ;;
    esac
}

main "$@"
