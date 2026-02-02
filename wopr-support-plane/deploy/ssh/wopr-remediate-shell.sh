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

CMD="${SSH_ORIGINAL_COMMAND}"

# Deny any shell metacharacters that could chain or escape commands
if echo "$CMD" | grep -qE '[;|&`$(){}\\]|>>'; then
    logger -t wopr-support "REMEDIATE BLOCKED (metachar): user=$(whoami) cmd=${CMD}"
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
            logger -t wopr-support "REMEDIATE BLOCKED (bad arg): user=$(whoami) arg=${arg}"
            echo "ERROR: Argument contains disallowed characters: ${arg}"
            exit 1
        fi
    done
}

# Allowed service names for systemctl restart/reload
ALLOWED_SERVICES="caddy|docker|wopr-.*|authentik-.*|postgresql|redis|nebula"

case "$BASE" in
    # === Diagnostic commands (read-only) ===
    cat)
        validate_args
        for arg in "${WORDS[@]:1}"; do
            case "$arg" in
                -*) ;;
                /var/log/*|/etc/*) ;;
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
            logs|ps) ;; # read-only
            stats)
                if [[ "$CMD" != *"--no-stream"* ]]; then
                    echo "ERROR: docker stats requires --no-stream flag."
                    exit 1
                fi
                ;;
            compose)
                # Only allow: docker compose -p wopr restart <service>
                #              docker compose -p wopr up -d <service>
                #              docker compose -p wopr down <service>
                COMPOSE_ACTION="${WORDS[4]:-}"
                PROJECT="${WORDS[3]:-}"
                if [[ "${WORDS[2]:-}" != "-p" ]] || [[ "$PROJECT" != "wopr" ]]; then
                    echo "ERROR: docker compose must use '-p wopr'."
                    exit 1
                fi
                case "$COMPOSE_ACTION" in
                    restart|up|down|pull) ;;
                    *)
                        echo "ERROR: Only docker compose restart/up/down/pull allowed."
                        exit 1
                        ;;
                esac
                ;;
            *)
                echo "ERROR: Only docker logs/ps/stats/compose allowed."
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
        SERVICE="${WORDS[2]:-}"
        case "$SUB" in
            # Read-only
            is-active|list-units|status) ;;
            # Remediation - restricted to allowed services
            restart|reload)
                if [ -z "$SERVICE" ]; then
                    echo "ERROR: Service name required."
                    exit 1
                fi
                if ! echo "$SERVICE" | grep -qE "^(${ALLOWED_SERVICES})$"; then
                    echo "ERROR: Service '${SERVICE}' not in allowed list."
                    exit 1
                fi
                ;;
            *)
                echo "ERROR: Only systemctl status/is-active/list-units/restart/reload allowed."
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
    uname|grep)
        validate_args
        ;;

    # === Remediation-only commands ===
    redis-cli)
        validate_args
        SUB="${WORDS[1]:-}"
        case "$SUB" in
            FLUSHDB|FLUSHALL) ;;
            *)
                echo "ERROR: Only 'redis-cli FLUSHDB' and 'redis-cli FLUSHALL' allowed."
                exit 1
                ;;
        esac
        ;;
    caddy)
        validate_args
        SUB="${WORDS[1]:-}"
        case "$SUB" in
            reload|trust|validate) ;;
            *)
                echo "ERROR: Only 'caddy reload/trust/validate' allowed."
                exit 1
                ;;
        esac
        ;;
    systemd-resolve)
        validate_args
        if [[ "${WORDS[1]:-}" != "--flush-caches" ]]; then
            echo "ERROR: Only 'systemd-resolve --flush-caches' allowed."
            exit 1
        fi
        ;;

    *)
        logger -t wopr-support "REMEDIATE DENIED: user=$(whoami) cmd=${CMD}"
        echo "ERROR: Command not permitted for remediation tier."
        echo "Allowed: all diagnostic commands plus systemctl restart/reload,"
        echo "  docker compose (wopr project), redis-cli FLUSHDB, caddy reload/trust/validate"
        exit 1
        ;;
esac

# Execute the validated command
logger -t wopr-support "REMEDIATE EXEC: user=$(whoami) cmd=${CMD}"
exec "${WORDS[@]}"
