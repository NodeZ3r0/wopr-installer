#!/usr/bin/env bash
# WOPR Support Plane - Diagnostic Restricted Shell
# Deploy to: /usr/local/bin/wopr-diag-shell
# Only allows read-only diagnostic commands.
set -euo pipefail

# Log the command for audit trail
logger -t wopr-support "DIAG: user=$(whoami) cmd=${SSH_ORIGINAL_COMMAND:-interactive}"

# If no command provided, deny interactive shell
if [ -z "${SSH_ORIGINAL_COMMAND:-}" ]; then
    echo "ERROR: Interactive shell not permitted for diagnostic tier."
    echo "Provide a command via SSH, e.g.: ssh wopr-diag@beacon 'uptime'"
    exit 1
fi

# Allowed command prefixes (read-only operations only)
ALLOWED_COMMANDS=(
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
)

CMD="${SSH_ORIGINAL_COMMAND}"

# Check if the command starts with any allowed prefix
for allowed in "${ALLOWED_COMMANDS[@]}"; do
    if [[ "$CMD" == "$allowed"* ]] || [[ "$CMD" == "$allowed" ]]; then
        # Deny any shell metacharacters that could escape the restricted command
        if echo "$CMD" | grep -qE '[;|&`$()]'; then
            logger -t wopr-support "DIAG BLOCKED (metachar): user=$(whoami) cmd=${CMD}"
            echo "ERROR: Shell metacharacters not permitted."
            exit 1
        fi
        # Execute the allowed command
        exec bash -c "$CMD"
    fi
done

logger -t wopr-support "DIAG DENIED: user=$(whoami) cmd=${CMD}"
echo "ERROR: Command not permitted for diagnostic tier."
echo "Allowed commands: cat, df, docker logs/ps/stats, free, hostname,"
echo "  ip addr/route, journalctl, ls, ss, systemctl status/list-units,"
echo "  top, uname, uptime, who"
exit 1
