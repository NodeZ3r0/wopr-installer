import re
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from api.config import AUDIT_DBS


# Known error patterns with pre-classified tiers (skip LLM for these)
KNOWN_PATTERNS = [
    {
        "pattern": re.compile(r"(OOM|out of memory|Cannot allocate memory)", re.I),
        "tier": "tier2_suggest",
        "action": "check_memory",
        "confidence": 0.9,
        "error_pattern": "out_of_memory",
    },
    {
        "pattern": re.compile(r"(disk full|No space left on device)", re.I),
        "tier": "tier1_auto",
        "action": "clear_tmp",
        "confidence": 0.95,
        "error_pattern": "disk_full",
    },
    {
        "pattern": re.compile(r"(ECONNREFUSED|Connection refused|connection reset)", re.I),
        "tier": "tier1_auto",
        "action": "restart_service",
        "confidence": 0.8,
        "error_pattern": "connection_refused",
    },
    {
        "pattern": re.compile(r"(SIGKILL|killed|exit code 137)", re.I),
        "tier": "tier1_auto",
        "action": "restart_service",
        "confidence": 0.85,
        "error_pattern": "process_killed",
    },
    {
        "pattern": re.compile(r"(permission denied|EACCES|403 Forbidden)", re.I),
        "tier": "tier3_escalate",
        "action": "investigate_permissions",
        "confidence": 0.7,
        "error_pattern": "permission_denied",
    },
    {
        "pattern": re.compile(r"(unauthorized|invalid token|auth.*fail)", re.I),
        "tier": "tier3_escalate",
        "action": "investigate_auth_failure",
        "confidence": 0.8,
        "error_pattern": "auth_failure",
    },
    {
        # Only match actual certificate errors, not just any mention of TLS/SSL
        "pattern": re.compile(r"(certificate (expired|invalid|error)|SSL_ERROR|CERT_.*ERROR|x509:)", re.I),
        "tier": "tier2_suggest",
        "action": "check_certificates",
        "confidence": 0.75,
        "error_pattern": "ssl_error",
    },
    {
        "pattern": re.compile(r"(timeout|timed out|ETIMEDOUT)", re.I),
        "tier": "tier1_auto",
        "action": "restart_service",
        "confidence": 0.6,
        "error_pattern": "timeout",
    },
    {
        "pattern": re.compile(r"(forge not configured|WOODPECKER_.*not.*configured)", re.I),
        "tier": "tier2_suggest",
        "action": "configure_woodpecker_forge",
        "confidence": 0.9,
        "error_pattern": "woodpecker_forge_missing",
    },
    {
        "pattern": re.compile(r"(failed to start|service failed|exit.code.[1-9])", re.I),
        "tier": "tier1_auto",
        "action": "restart_service",
        "confidence": 0.7,
        "error_pattern": "service_failed",
    },
]


def match_known_pattern(error_text: str) -> Optional[dict]:
    for kp in KNOWN_PATTERNS:
        if kp["pattern"].search(error_text):
            return {
                "tier": kp["tier"],
                "action": kp["action"],
                "confidence": kp["confidence"],
                "error_pattern": kp["error_pattern"],
                "reasoning": f"Matched known pattern: {kp['error_pattern']}",
            }
    return None


def collect_recent_errors(minutes: int = 5) -> list[dict]:
    """Collect recent error/critical events from all audit DBs."""
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    errors = []

    for service, db_path in AUDIT_DBS.items():
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE severity IN ('error', 'critical') "
                "AND timestamp > ? ORDER BY timestamp DESC LIMIT 50",
                (cutoff,),
            ).fetchall()
            for row in rows:
                errors.append({
                    "service": service,
                    "action": row["action"],
                    "severity": row["severity"],
                    "timestamp": row["timestamp"],
                    "response_status": row["response_status"],
                    "request_path": row["request_path"],
                    "duration_ms": row["duration_ms"],
                })
            conn.close()
        except Exception:
            pass  # DB might not exist or be locked

    return errors


def collect_journald_errors(minutes: int = 5) -> list[dict]:
    """Collect recent errors from systemd journal."""
    import subprocess
    errors = []
    try:
        result = subprocess.run(
            ["journalctl", "--since", f"{minutes} min ago", "-p", "err",
             "--no-pager", "-o", "json",
             "--output-fields=UNIT,_SYSTEMD_UNIT,SYSLOG_IDENTIFIER,CONTAINER_NAME,MESSAGE,_PID"],
            capture_output=True, text=True, timeout=10,
        )
        import json
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Try multiple fields to identify the service
                unit = (
                    entry.get("UNIT") or
                    entry.get("_SYSTEMD_UNIT") or
                    entry.get("CONTAINER_NAME") or
                    entry.get("SYSLOG_IDENTIFIER") or
                    "unknown"
                )
                # Clean up service name (remove .service suffix if present)
                if unit.endswith(".service"):
                    unit = unit[:-8]
                errors.append({
                    "service": unit,
                    "message": entry.get("MESSAGE", ""),
                    "source": "journald",
                })
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return errors
