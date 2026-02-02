#!/usr/bin/env bash
# WOPR Support Plane - Remediation Restricted Shell
# Deploy to: /usr/local/bin/wopr-remediate-shell
# Allows diagnostic commands plus approved remediation actions.
set -euo pipefail

# Log the command for audit trail
logger -t wopr-support "REMEDIATE: user=$(whoami) cmd=${SSH_ORIGINAL_COMMAND:-interactive}"

# If no command provided, deny interactive shell
if [ -z "${SSH_ORIGINAL_COMMAND:-}" ]; then
    echo "ERROR: Interactive shell not permitted for remediation tier."
    echo "Provide a command via SSH, e.g.: ssh wopr-remediate@beacon 'systemctl restart caddy'"
    exit 1
fi

# Allowed command prefixes (diagnostic + remediation)
ALLOWED_COMMANDS=(
    # Diagnostic (read-only)
    "cat "
    "df "
    "docker logs "
    "docker ps"
    "docker stats --no-stream"
    "free"
    "hostname"
    "ip addr"
    "ip route"
    "journalctl "
    "ls "
    "ss "
    "systemctl is-active "
    "systemctl list-units "
    "systemctl status "
    "top -bn1"
    "uname "
    "uptime"
    "who"
    # Remediation actions
    "systemctl restart "
    "systemctl reload "
    "docker compose -p wopr"
    "redis-cli FLUSHDB"
    "redis-cli FLUSHALL"
    "caddy reload"
    "caddy trust"
    "caddy validate"
    "systemd-resolve --flush-caches"
)

CMD="${SSH_ORIGINAL_COMMAND}"

# Check if the command starts with any allowed prefix
for allowed in "${ALLOWED_COMMANDS[@]}"; do
    if [[ "$CMD" == "$allowed"* ]] || [[ "$CMD" == "$allowed" ]]; then
        # Deny shell metacharacters that could escape the restricted command
        if echo "$CMD" | grep -qE '[;|&`$()]'; then
            logger -t wopr-support "REMEDIATE BLOCKED (metachar): user=$(whoami) cmd=${CMD}"
            echo "ERROR: Shell metacharacters not permitted."
            exit 1
        fi
        # Execute the allowed command
        logger -t wopr-support "REMEDIATE EXEC: user=$(whoami) cmd=${CMD}"
        exec bash -c "$CMD"
    fi
done

logger -t wopr-support "REMEDIATE DENIED: user=$(whoami) cmd=${CMD}"
echo "ERROR: Command not permitted for remediation tier."
echo "Allowed: all diagnostic commands plus systemctl restart/reload,"
echo "  docker compose restart, redis-cli FLUSHDB, caddy reload/trust/validate"
exit 1
