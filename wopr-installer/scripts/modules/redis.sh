#!/bin/bash
#=================================================
# WOPR MODULE: Redis
# Version: 1.0
# Purpose: Deploy Redis cache for WOPR services
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

REDIS_IMAGE="docker.io/library/redis:7-alpine"
REDIS_PORT=6379
REDIS_DATA_DIR="${WOPR_DATA_DIR}/redis"
REDIS_SERVICE="wopr-redis"

wopr_deploy_redis() {
    wopr_log "INFO" "Deploying Redis..."

    # Check if already installed
    if systemctl is-active --quiet "$REDIS_SERVICE" 2>/dev/null; then
        wopr_log "INFO" "Redis is already running"
        return 0
    fi

    # Create data directory
    mkdir -p "${REDIS_DATA_DIR}/data"

    # Pull the image
    wopr_log "INFO" "Pulling Redis image..."
    wopr_container_pull "$REDIS_IMAGE"

    # Create Redis configuration
    cat > "${REDIS_DATA_DIR}/redis.conf" <<EOF
# WOPR Redis Configuration
bind 127.0.0.1
port 6379
daemonize no

# Persistence
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec

# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Security
protected-mode yes

# Logging
loglevel notice
EOF

    # Create systemd service
    cat > "/etc/systemd/system/${REDIS_SERVICE}.service" <<EOF
[Unit]
Description=WOPR Redis Cache
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${REDIS_SERVICE}
ExecStartPre=-/usr/bin/podman rm ${REDIS_SERVICE}

ExecStart=/usr/bin/podman run --rm \\
    --name ${REDIS_SERVICE} \\
    -v ${REDIS_DATA_DIR}/data:/data:Z \\
    -v ${REDIS_DATA_DIR}/redis.conf:/usr/local/etc/redis/redis.conf:ro,Z \\
    -p 127.0.0.1:${REDIS_PORT}:6379 \\
    ${REDIS_IMAGE} \\
    redis-server /usr/local/etc/redis/redis.conf

ExecStop=/usr/bin/podman stop -t 10 ${REDIS_SERVICE}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start
    systemctl daemon-reload
    systemctl enable "$REDIS_SERVICE"
    systemctl start "$REDIS_SERVICE"

    # Wait for Redis to be ready
    wopr_log "INFO" "Waiting for Redis to be ready..."
    wopr_wait_for_port "127.0.0.1" "$REDIS_PORT" 30

    # Verify Redis is responding
    if podman exec "$REDIS_SERVICE" redis-cli ping | grep -q "PONG"; then
        wopr_log "OK" "Redis is responding"
    else
        wopr_log "ERROR" "Redis is not responding"
        return 1
    fi

    # Record installation
    wopr_setting_set "module_redis_installed" "true"
    wopr_setting_set "module_redis_version" "7"
    wopr_setting_set "redis_port" "$REDIS_PORT"
    wopr_defcon_log "MODULE_DEPLOYED" "redis"

    wopr_log "OK" "Redis deployed successfully"
}

wopr_remove_redis() {
    wopr_log "INFO" "Removing Redis..."

    systemctl stop "$REDIS_SERVICE" 2>/dev/null || true
    systemctl disable "$REDIS_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${REDIS_SERVICE}.service"
    systemctl daemon-reload

    # Note: Data is preserved in ${REDIS_DATA_DIR}
    wopr_log "INFO" "Redis removed (data preserved)"
}

wopr_status_redis() {
    if systemctl is-active --quiet "$REDIS_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Get Redis connection URL
wopr_redis_url() {
    echo "redis://127.0.0.1:${REDIS_PORT}/0"
}
