from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional


class EventType(str, Enum):
    API_REQUEST = "api_request"
    AUTH = "auth"
    DATA_ACCESS = "data_access"
    ERROR = "error"
    ADMIN_ACTION = "admin_action"
    REMEDIATION = "remediation"
    SYSTEM = "system"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    environment: str = "production"
    event_type: EventType
    action: str
    severity: Severity = Severity.INFO
    user_uid: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    access_tier: Optional[str] = None
    request_ip: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    request_body_hash: Optional[str] = None
    response_status: Optional[int] = None
    duration_ms: Optional[int] = None
    target_resource: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    correlation_id: Optional[str] = None
