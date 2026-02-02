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

CMD="${SSH_ORIGINAL_COMMAND}"

# Deny any shell metacharacters that could chain or escape commands
if echo "$CMD" | grep -qE '[;|&`$(){}\\]|>>'; then
    logger -t wopr-support "DIAG BLOCKED (metachar): user=$(whoami) cmd=${CMD}"
    echo "ERROR: Shell metacharacters not permitted."
    exit 1
fi

# Split command into words for exact matching
read -ra WORDS <<< "$CMD"
BASE="${WORDS[0]:-}"

# Validate arguments only contain safe path/flag characters
validate_args() {
    local arg
    for arg in "${WORDS[@]:1}"; do
        if ! echo "$arg" | grep -qE '^[a-zA-Z0-9_./:=@, -]+$'; then
            logger -t wopr-support "DIAG BLOCKED (bad arg): user=$(whoami) arg=${arg}"
            echo "ERROR: Argument contains disallowed characters: ${arg}"
            exit 1
        fi
    done
}

case "$BASE" in
    cat)
        validate_args
        # Only allow reading from /var/log and /etc
        for arg in "${WORDS[@]:1}"; do
            case "$arg" in
                -*) ;; # flags are ok
                /var/log/*|/etc/*) ;; # safe paths
                *)
                    echo "ERROR: cat only permitted for /var/log/ and /etc/ paths."
                    exit 1
                    ;;
            esac
        done
        ;;
    df|free|hostname|uptime|who)
        validate_args
        ;;
    docker)
        validate_args
        SUB="${WORDS[1]:-}"
        case "$SUB" in
            logs|ps) ;; # read-only docker commands
            stats)
                # Only allow --no-stream
                if [[ "$CMD" != *"--no-stream"* ]]; then
                    echo "ERROR: docker stats requires --no-stream flag."
                    exit 1
                fi
                ;;
            *)
                echo "ERROR: Only 'docker logs', 'docker ps', 'docker stats --no-stream' allowed."
                exit 1
                ;;
        esac
        ;;
    ip)
        validate_args
        SUB="${WORDS[1]:-}"
        case "$SUB" in
            addr|route) ;;
            *)
                echo "ERROR: Only 'ip addr' and 'ip route' allowed."
                exit 1
                ;;
        esac
        ;;
    journalctl)
        validate_args
        ;;
    ls)
        validate_args
        ;;
    ss)
        validate_args
        ;;
    systemctl)
        validate_args
        SUB="${WORDS[1]:-}"
        case "$SUB" in
            is-active|list-units|status) ;;
            *)
                echo "ERROR: Only 'systemctl status/is-active/list-units' allowed."
                exit 1
                ;;
        esac
        ;;
    top)
        validate_args
        if [[ "$CMD" != "top -bn1"* ]]; then
            echo "ERROR: Only 'top -bn1' allowed."
            exit 1
        fi
        ;;
    uname)
        validate_args
        ;;
    grep)
        validate_args
        ;;
    *)
        logger -t wopr-support "DIAG DENIED: user=$(whoami) cmd=${CMD}"
        echo "ERROR: Command not permitted for diagnostic tier."
        echo "Allowed: cat (logs/etc), df, docker logs/ps/stats, free, hostname,"
        echo "  ip addr/route, journalctl, ls, ss, systemctl status/list-units,"
        echo "  top -bn1, uname, uptime, who"
        exit 1
        ;;
esac

# Execute the validated command
logger -t wopr-support "DIAG EXEC: user=$(whoami) cmd=${CMD}"
exec "${WORDS[@]}"
