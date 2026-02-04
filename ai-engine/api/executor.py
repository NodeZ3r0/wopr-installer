import subprocess
import logging
from api.config import RESTARTABLE_SERVICES

logger = logging.getLogger("ai_engine.executor")


def execute_tier1_action(action: str, service: str) -> tuple[bool, str]:
    """Execute a Tier 1 auto-fix action. Returns (success, output)."""

    if action == "restart_service":
        if service not in RESTARTABLE_SERVICES:
            return False, f"Service '{service}' not in restartable list"
        try:
            result = subprocess.run(
                ["systemctl", "restart", service],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                logger.info(f"Restarted service: {service}")
                return True, f"Service {service} restarted successfully"
            return False, f"Restart failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Restart timed out"

    elif action == "clear_tmp":
        try:
            result = subprocess.run(
                ["find", "/tmp", "-type", "f", "-mtime", "+1", "-delete"],
                capture_output=True, text=True, timeout=30,
            )
            return True, "Cleared old temp files"
        except Exception as e:
            return False, str(e)

    elif action == "rotate_logs":
        try:
            result = subprocess.run(
                ["logrotate", "-f", "/etc/logrotate.conf"],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            return False, str(e)

    elif action == "check_disk_usage":
        try:
            result = subprocess.run(
                ["df", "-h"], capture_output=True, text=True, timeout=10,
            )
            return True, result.stdout
        except Exception as e:
            return False, str(e)

    elif action == "check_memory":
        try:
            result = subprocess.run(
                ["free", "-h"], capture_output=True, text=True, timeout=10,
            )
            return True, result.stdout
        except Exception as e:
            return False, str(e)

    elif action == "dns_flush":
        try:
            result = subprocess.run(
                ["systemd-resolve", "--flush-caches"],
                capture_output=True, text=True, timeout=10,
            )
            return True, "DNS cache flushed"
        except Exception as e:
            return False, str(e)

    return False, f"Unknown action: {action}"
