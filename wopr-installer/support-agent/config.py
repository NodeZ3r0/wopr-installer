"""
WOPR Support Agent Configuration
Lightweight host-level support agent for systemd services
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Set

# ============================================================================
# BRAIN CONNECTION
# ============================================================================

BRAIN_API_URL = os.environ.get("WOPR_BRAIN_URL", "http://localhost:8420")
BRAIN_API_KEY = os.environ.get("WOPR_BRAIN_KEY", "")
BEACON_ID = os.environ.get("WOPR_BEACON_ID", os.uname().nodename if hasattr(os, 'uname') else "unknown")

# ============================================================================
# TIMING
# ============================================================================

HEALTH_BEACON_INTERVAL = 60  # seconds
QUEUE_RETRY_INTERVAL = 300   # 5 minutes
JOURNAL_POLL_TIMEOUT = 5     # seconds
COMMAND_POLL_INTERVAL = 10   # seconds

# ============================================================================
# MANAGED SERVICES
# ============================================================================

MANAGED_SERVICES: Set[str] = {
    # WOPR Services
    "wopr-api",
    "wopr-brain",
    "wopr-mesh",
    "wopr-gateway",
    "wopr-monitor",
    "wopr-auth",
    "wopr-support-agent",
    # Infrastructure
    "caddy",
    "postgresql",
    "redis",
    "redis-server",
    "docker",
}

# ============================================================================
# TIER 1: AUTO-FIX PATTERNS (Execute immediately, no approval needed)
# ============================================================================

@dataclass
class Tier1Pattern:
    """Pattern that triggers automatic remediation"""
    name: str
    patterns: List[str]
    action: str
    params: Dict = field(default_factory=dict)
    cooldown: int = 300  # Don't repeat same fix within N seconds

TIER1_PATTERNS: List[Tier1Pattern] = [
    # Connection Refused - Restart the service
    Tier1Pattern(
        name="connection_refused",
        patterns=[
            r"Connection refused",
            r"connect ECONNREFUSED",
            r"Failed to connect",
            r"connection reset by peer",
        ],
        action="restart_service",
        params={"extract_service": True},
        cooldown=300,
    ),

    # Service Failed - Restart
    Tier1Pattern(
        name="service_failed",
        patterns=[
            r"(\w+)\.service.*Failed",
            r"systemd.*(\w+).*failed",
            r"Main process exited.*code=exited",
        ],
        action="restart_service",
        params={"extract_service": True},
        cooldown=300,
    ),

    # Container Crash - Restart container
    Tier1Pattern(
        name="container_crash",
        patterns=[
            r"container.*exited",
            r"OCI runtime.*failed",
            r"docker.*container.*died",
        ],
        action="restart_container",
        params={"extract_container": True},
        cooldown=120,
    ),

    # Temp Files Full - Clear tmp
    Tier1Pattern(
        name="tmp_full",
        patterns=[
            r"No space left on device.*/tmp",
            r"/tmp.*out of space",
            r"cannot create temp file",
        ],
        action="clear_tmp",
        params={},
        cooldown=600,
    ),

    # Disk Space Low (generic)
    Tier1Pattern(
        name="disk_low",
        patterns=[
            r"No space left on device",
            r"Disk quota exceeded",
            r"filesystem.*full",
        ],
        action="clear_logs",
        params={},
        cooldown=600,
    ),

    # Caddy Reload Needed
    Tier1Pattern(
        name="caddy_config",
        patterns=[
            r"caddy.*config.*error",
            r"caddy.*reload.*required",
            r"Caddyfile.*changed",
        ],
        action="reload_caddy",
        params={},
        cooldown=60,
    ),

    # DNS Resolution Failed
    Tier1Pattern(
        name="dns_failure",
        patterns=[
            r"Temporary failure in name resolution",
            r"Name or service not known",
            r"Could not resolve host",
            r"NXDOMAIN",
        ],
        action="dns_flush",
        params={},
        cooldown=120,
    ),

    # Redis Connection Issues
    Tier1Pattern(
        name="redis_connection",
        patterns=[
            r"redis.*connection.*refused",
            r"REDIS.*ERROR.*connect",
            r"Error connecting to Redis",
        ],
        action="restart_service",
        params={"service": "redis-server"},
        cooldown=300,
    ),

    # PostgreSQL Connection Issues
    Tier1Pattern(
        name="postgres_connection",
        patterns=[
            r"could not connect to.*postgresql",
            r"postgres.*connection.*refused",
            r"FATAL.*database.*does not exist",
        ],
        action="restart_service",
        params={"service": "postgresql"},
        cooldown=300,
    ),

    # Permission Denied on Socket
    Tier1Pattern(
        name="socket_permission",
        patterns=[
            r"Permission denied.*\.sock",
            r"cannot access.*socket",
        ],
        action="fix_socket_permissions",
        params={},
        cooldown=300,
    ),
]

# ============================================================================
# TIER 2: SUGGEST PATTERNS (Needs DEFCON ONE approval)
# ============================================================================

@dataclass
class Tier2Pattern:
    """Pattern that suggests action but requires human approval"""
    name: str
    patterns: List[str]
    suggested_action: str
    description: str
    risk_level: str = "medium"  # low, medium, high

TIER2_PATTERNS: List[Tier2Pattern] = [
    Tier2Pattern(
        name="oom_killer",
        patterns=[
            r"Out of memory",
            r"OOM.*killed",
            r"oom-kill",
            r"memory.*exhausted",
        ],
        suggested_action="increase_memory_limit",
        description="Process killed due to OOM. Consider increasing memory limits.",
        risk_level="high",
    ),

    Tier2Pattern(
        name="high_load",
        patterns=[
            r"load average.*[0-9]{2,}",
            r"CPU.*100%",
            r"system.*overloaded",
        ],
        suggested_action="scale_or_restart",
        description="System under high load. May need scaling or restart.",
        risk_level="medium",
    ),

    Tier2Pattern(
        name="ssl_cert_expiry",
        patterns=[
            r"certificate.*expir",
            r"SSL.*certificate.*invalid",
            r"x509.*expired",
        ],
        suggested_action="renew_certificates",
        description="SSL certificate expiring or expired. Renewal needed.",
        risk_level="high",
    ),

    Tier2Pattern(
        name="database_corruption",
        patterns=[
            r"database.*corrupt",
            r"checksum.*mismatch",
            r"page verification failed",
        ],
        suggested_action="database_recovery",
        description="Possible database corruption detected.",
        risk_level="high",
    ),

    Tier2Pattern(
        name="security_alert",
        patterns=[
            r"authentication.*failed.*multiple",
            r"brute.*force",
            r"unauthorized.*access",
            r"suspicious.*activity",
        ],
        suggested_action="security_review",
        description="Potential security incident detected.",
        risk_level="high",
    ),
]

# ============================================================================
# TIER 3: ESCALATE PATTERNS (Create support ticket)
# ============================================================================

@dataclass
class Tier3Pattern:
    """Pattern that requires immediate escalation"""
    name: str
    patterns: List[str]
    severity: str  # critical, high, medium
    description: str

TIER3_PATTERNS: List[Tier3Pattern] = [
    Tier3Pattern(
        name="kernel_panic",
        patterns=[
            r"Kernel panic",
            r"kernel.*BUG",
            r"kernel.*Oops",
        ],
        severity="critical",
        description="Kernel-level error detected",
    ),

    Tier3Pattern(
        name="hardware_failure",
        patterns=[
            r"hardware.*error",
            r"ECC.*error",
            r"I/O error.*device",
            r"SMART.*failing",
        ],
        severity="critical",
        description="Possible hardware failure",
    ),

    Tier3Pattern(
        name="data_loss",
        patterns=[
            r"data.*loss",
            r"unrecoverable.*error",
            r"backup.*failed.*critical",
        ],
        severity="critical",
        description="Potential data loss event",
    ),

    Tier3Pattern(
        name="network_partition",
        patterns=[
            r"network.*unreachable",
            r"cluster.*split",
            r"quorum.*lost",
        ],
        severity="high",
        description="Network partition or cluster issue",
    ),
]

# ============================================================================
# QUEUE SETTINGS
# ============================================================================

QUEUE_FILE = "/var/lib/wopr/support-agent/queue.json"
QUEUE_MAX_SIZE = 1000
QUEUE_RETENTION_HOURS = 24

# ============================================================================
# SECURITY
# ============================================================================

# Commands that can be executed from brain
ALLOWED_REMOTE_COMMANDS: Set[str] = {
    "restart_service",
    "restart_container",
    "reload_caddy",
    "get_logs",
    "get_status",
    "run_diagnostic",
    "clear_tmp",
    "dns_flush",
}

# Never allow these via remote command
BLOCKED_COMMANDS: Set[str] = {
    "rm -rf /",
    "dd if=",
    "mkfs",
    "format",
    ":(){ :|:& };:",
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = os.environ.get("WOPR_LOG_LEVEL", "INFO")
LOG_FILE = "/var/log/wopr/support-agent.log"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
