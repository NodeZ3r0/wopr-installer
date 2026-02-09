"""
WOPR Support Brain - Pydantic Models
Central AI service data models for beacon management and issue resolution.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Beacon health status enumeration."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class IssueSeverity(str, Enum):
    """Issue severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    """Issue resolution status."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    AUTO_FIXED = "auto_fixed"
    AWAITING_APPROVAL = "awaiting_approval"
    ESCALATED = "escalated"
    TICKET_CREATED = "ticket_created"
    RESOLVED = "resolved"
    FAILED = "failed"


class CommandStatus(str, Enum):
    """Command execution status."""
    QUEUED = "queued"
    SENT = "sent"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class AnalysisTier(str, Enum):
    """LLM analysis tier."""
    TIER_1 = "tier_1"  # tinyllama - fast, common issues
    TIER_2 = "tier_2"  # mistral - medium complexity
    TIER_3 = "tier_3"  # phi3:medium - complex issues


# ============== Request Models ==============

class HeartbeatRequest(BaseModel):
    """Beacon heartbeat request."""
    beacon_id: str = Field(..., description="Unique beacon identifier")
    subdomain: str = Field(..., description="Subdomain the beacon monitors")
    ip_address: str = Field(..., description="Beacon IP address")
    hostname: Optional[str] = Field(None, description="Beacon hostname")
    platform: Optional[str] = Field(None, description="OS platform")
    cpu_percent: Optional[float] = Field(None, ge=0, le=100)
    memory_percent: Optional[float] = Field(None, ge=0, le=100)
    disk_percent: Optional[float] = Field(None, ge=0, le=100)
    uptime_seconds: Optional[int] = Field(None, ge=0)
    version: Optional[str] = Field(None, description="Beacon agent version")
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IssueReport(BaseModel):
    """Issue reported by a beacon agent."""
    beacon_id: str = Field(..., description="Reporting beacon ID")
    issue_type: str = Field(..., description="Type of issue (service_down, high_cpu, etc.)")
    severity: IssueSeverity = Field(default=IssueSeverity.MEDIUM)
    title: str = Field(..., description="Brief issue title")
    description: str = Field(..., description="Detailed issue description")
    affected_service: Optional[str] = Field(None, description="Name of affected service")
    error_message: Optional[str] = Field(None, description="Error message if any")
    stack_trace: Optional[str] = Field(None, description="Stack trace if available")
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    suggested_action: Optional[str] = Field(None, description="Beacon's suggested fix")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CommandRequest(BaseModel):
    """Command to be sent to a beacon."""
    command_type: str = Field(..., description="Type of command (restart, execute, config, etc.)")
    command: str = Field(..., description="Command to execute")
    args: Optional[List[str]] = Field(default_factory=list)
    timeout_seconds: Optional[int] = Field(default=300, ge=1, le=3600)
    requires_approval: bool = Field(default=False)
    priority: int = Field(default=5, ge=1, le=10)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ============== Response Models ==============

class HeartbeatResponse(BaseModel):
    """Response to beacon heartbeat."""
    status: str = Field(default="ok")
    server_time: datetime = Field(default_factory=datetime.utcnow)
    pending_commands: int = Field(default=0)
    message: Optional[str] = None


class BeaconInfo(BaseModel):
    """Beacon information and status."""
    beacon_id: str
    subdomain: str
    ip_address: str
    hostname: Optional[str] = None
    platform: Optional[str] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    uptime_seconds: Optional[int] = None
    version: Optional[str] = None
    issues_today: int = 0
    auto_fixes_today: int = 0
    extra_data: Optional[Dict[str, Any]] = None


class BeaconListResponse(BaseModel):
    """List of beacons response."""
    total: int
    healthy: int
    warning: int
    critical: int
    offline: int
    beacons: List[BeaconInfo]


class IssueResponse(BaseModel):
    """Response after issue submission."""
    issue_id: str
    status: IssueStatus
    message: str
    analysis_tier: Optional[AnalysisTier] = None
    suggested_fix: Optional[str] = None
    auto_fix_applied: bool = False
    confidence: Optional[float] = None
    requires_approval: bool = False


class IssueDetail(BaseModel):
    """Detailed issue information."""
    issue_id: str
    beacon_id: str
    issue_type: str
    severity: IssueSeverity
    status: IssueStatus
    title: str
    description: str
    affected_service: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    analysis_tier: Optional[AnalysisTier] = None
    analysis_attempts: int = 0
    suggested_fix: Optional[str] = None
    applied_fix: Optional[str] = None
    fix_result: Optional[str] = None
    ticket_id: Optional[str] = None
    resolution_notes: Optional[str] = None


class IssueListResponse(BaseModel):
    """List of issues response."""
    total: int
    pending: int
    resolved: int
    escalated: int
    issues: List[IssueDetail]


class CommandInfo(BaseModel):
    """Command information."""
    command_id: str
    beacon_id: str
    command_type: str
    command: str
    args: List[str] = []
    status: CommandStatus
    created_at: datetime
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    priority: int = 5
    timeout_seconds: int = 300
    requires_approval: bool = False
    approved_by: Optional[str] = None


class CommandQueueResponse(BaseModel):
    """Response when queuing a command."""
    command_id: str
    status: CommandStatus
    message: str
    position_in_queue: int


class PendingCommandsResponse(BaseModel):
    """Pending commands for a beacon to poll."""
    beacon_id: str
    commands: List[CommandInfo]


class CommandResultRequest(BaseModel):
    """Beacon reporting command execution result."""
    command_id: str
    status: CommandStatus
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None


# ============== Analysis Models ==============

class LLMAnalysisResult(BaseModel):
    """Result from LLM analysis."""
    tier: AnalysisTier
    model_name: str
    attempt: int
    confidence: float = Field(ge=0, le=1)
    diagnosis: str
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    fix_command: Optional[str] = None
    is_safe_to_auto_fix: bool = False
    requires_approval: bool = True
    escalate: bool = False
    escalation_reason: Optional[str] = None
    reasoning: Optional[str] = None
    tokens_used: Optional[int] = None
    analysis_time_ms: Optional[int] = None


class TicketInfo(BaseModel):
    """Support ticket information."""
    ticket_id: str
    issue_id: str
    beacon_id: str
    title: str
    description: str
    severity: IssueSeverity
    created_at: datetime
    ntfy_sent: bool = False
    email_sent: bool = False
    assigned_to: Optional[str] = None
    status: str = "open"


# ============== Audit Models ==============

class AuditLogEntry(BaseModel):
    """Audit log entry for actions."""
    log_id: str
    timestamp: datetime
    action_type: str
    beacon_id: Optional[str] = None
    issue_id: Optional[str] = None
    command_id: Optional[str] = None
    actor: str = "system"  # system, api, admin, etc.
    description: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None


# ============== Configuration Models ==============

class TierConfig(BaseModel):
    """Configuration for an LLM tier."""
    tier: AnalysisTier
    model_name: str
    max_attempts: int = 5
    auto_fix_threshold: float = 0.8
    timeout_seconds: int = 60
    temperature: float = 0.3


class BrainConfig(BaseModel):
    """Support Brain configuration."""
    ollama_base_url: str = "http://localhost:11434"
    max_auto_fixes_per_hour: int = 10
    heartbeat_timeout_seconds: int = 300
    critical_threshold_seconds: int = 600
    ntfy_server: Optional[str] = None
    ntfy_topic: Optional[str] = None
    email_enabled: bool = False
    email_recipients: List[str] = []
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    tiers: List[TierConfig] = [
        TierConfig(
            tier=AnalysisTier.TIER_1,
            model_name="tinyllama",
            max_attempts=5,
            auto_fix_threshold=0.8,
            timeout_seconds=30,
            temperature=0.2
        ),
        TierConfig(
            tier=AnalysisTier.TIER_2,
            model_name="mistral",
            max_attempts=5,
            auto_fix_threshold=0.7,
            timeout_seconds=60,
            temperature=0.3
        ),
        TierConfig(
            tier=AnalysisTier.TIER_3,
            model_name="phi3:medium",
            max_attempts=5,
            auto_fix_threshold=0.6,
            timeout_seconds=120,
            temperature=0.4
        ),
    ]
    safety_blocklist: List[str] = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf .",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "dd if=/dev/random",
        "> /dev/sda",
        "chmod -R 777 /",
        "chown -R",
        "DROP TABLE",
        "DROP DATABASE",
        "DELETE FROM",
        "TRUNCATE TABLE",
        "FORMAT C:",
        "del /f /s /q",
        "shutdown",
        "reboot",
        "init 0",
        "init 6",
        "halt",
        "poweroff",
        "curl | sh",
        "wget | sh",
        "curl | bash",
        "wget | bash",
        "> /etc/passwd",
        "> /etc/shadow",
        "passwd root",
        "usermod",
        "userdel",
        "groupdel",
    ]
