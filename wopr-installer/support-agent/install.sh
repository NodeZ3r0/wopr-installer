#!/bin/bash
#
# WOPR Support Agent Installation Script
# Installs the support agent as a systemd service on the host
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/wopr/support-agent"
CONFIG_DIR="/etc/wopr"
LOG_DIR="/var/log/wopr"
DATA_DIR="/var/lib/wopr/support-agent"
SERVICE_NAME="wopr-support-agent"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    # Python 3.9+
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 9 ]]; then
        log_error "Python 3.9+ is required (found $PYTHON_VERSION)"
        exit 1
    fi

    log_success "Python $PYTHON_VERSION found"

    # systemd
    if ! command -v systemctl &> /dev/null; then
        log_error "systemd is required but not found"
        exit 1
    fi
    log_success "systemd found"

    # journalctl
    if ! command -v journalctl &> /dev/null; then
        log_error "journalctl is required but not found"
        exit 1
    fi
    log_success "journalctl found"
}

# Create directories
create_directories() {
    log_info "Creating directories..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"

    chmod 755 "$INSTALL_DIR"
    chmod 755 "$CONFIG_DIR"
    chmod 755 "$LOG_DIR"
    chmod 700 "$DATA_DIR"

    log_success "Directories created"
}

# Install Python virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."

    cd "$INSTALL_DIR"

    # Create venv if it doesn't exist
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi

    # Activate and install dependencies
    source venv/bin/activate
    pip install --upgrade pip wheel
    pip install -r requirements.txt

    deactivate

    log_success "Virtual environment configured"
}

# Copy files
copy_files() {
    log_info "Copying files..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    cp "$SCRIPT_DIR/wopr_support_agent.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/config.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

    chmod 644 "$INSTALL_DIR"/*.py
    chmod 644 "$INSTALL_DIR/requirements.txt"

    log_success "Files copied"
}

# Create default environment file
create_env_file() {
    log_info "Creating environment configuration..."

    ENV_FILE="$CONFIG_DIR/support-agent.env"

    if [[ ! -f "$ENV_FILE" ]]; then
        cat > "$ENV_FILE" << 'EOF'
# WOPR Support Agent Configuration
# Customize these values for your environment

# Brain API connection
WOPR_BRAIN_URL=http://localhost:8420

# API key for authentication (generate a secure key)
WOPR_BRAIN_KEY=

# Unique identifier for this beacon (defaults to hostname)
# WOPR_BEACON_ID=my-server-01

# Logging level (DEBUG, INFO, WARNING, ERROR)
WOPR_LOG_LEVEL=INFO
EOF

        chmod 600 "$ENV_FILE"
        log_success "Environment file created: $ENV_FILE"
        log_warn "Please edit $ENV_FILE to configure the agent"
    else
        log_info "Environment file already exists, skipping"
    fi
}

# Install systemd service
install_service() {
    log_info "Installing systemd service..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    cp "$SCRIPT_DIR/wopr-support-agent.service" /etc/systemd/system/

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    log_success "Service installed and enabled"
}

# Start service
start_service() {
    log_info "Starting service..."

    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Service started successfully"
    else
        log_error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME"
        exit 1
    fi
}

# Show status
show_status() {
    echo ""
    echo "=========================================="
    echo "  WOPR Support Agent Installation Complete"
    echo "=========================================="
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Configuration file:     $CONFIG_DIR/support-agent.env"
    echo "Log directory:          $LOG_DIR"
    echo "Data directory:         $DATA_DIR"
    echo ""
    echo "Useful commands:"
    echo "  systemctl status $SERVICE_NAME   - Check status"
    echo "  systemctl restart $SERVICE_NAME  - Restart agent"
    echo "  journalctl -u $SERVICE_NAME -f   - Follow logs"
    echo ""
    echo "Memory usage:"
    systemctl show "$SERVICE_NAME" --property=MemoryCurrent 2>/dev/null || true
    echo ""
}

# Uninstall function
uninstall() {
    log_warn "Uninstalling WOPR Support Agent..."

    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f /etc/systemd/system/wopr-support-agent.service
    systemctl daemon-reload

    log_info "Service removed. Files at $INSTALL_DIR were NOT deleted."
    log_info "To fully remove, run: rm -rf $INSTALL_DIR"
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "  WOPR Support Agent Installer"
    echo "=========================================="
    echo ""

    case "${1:-install}" in
        install)
            check_root
            check_dependencies
            create_directories
            copy_files
            setup_venv
            create_env_file
            install_service
            start_service
            show_status
            ;;
        uninstall)
            check_root
            uninstall
            ;;
        *)
            echo "Usage: $0 {install|uninstall}"
            exit 1
            ;;
    esac
}

main "$@"
