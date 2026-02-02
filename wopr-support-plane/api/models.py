"""Pydantic request/response models for the Support Gateway API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Diagnostics ---


class ServiceStatus(BaseModel):
    name: str
    active: bool
    status: str
    uptime: str | None = None


class BeaconHealthResponse(BaseModel):
    beacon_id: str
    status: str
    uptime: str | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    disk_percent: float | None = None
    services: list[ServiceStatus] = []


class BeaconSummary(BaseModel):
    beacon_id: str
    nebula_ip: str
    hostname: str | None = None
    status: str = "unknown"


class BeaconLogsRequest(BaseModel):
    service: str | None = None
    lines: int = Field(default=100, ge=1, le=1000)
    since: str | None = None  # systemd time spec, e.g. "1 hour ago"


class BeaconLogsResponse(BaseModel):
    beacon_id: str
    service: str | None = None
    lines: list[str]
    truncated: bool = False


# --- Remediation ---


class RemediationAction(BaseModel):
    id: str
    name: str
    description: str | None = None
    required_tier: str
    is_enabled: bool
    risk_level: str


class RemediationRequest(BaseModel):
    action_id: str
    parameters: dict[str, str] = {}


class RemediationResponse(BaseModel):
    action_id: str
    status: str
    output: str
    executed_at: datetime


# --- Breakglass ---


class BreakglassRequest(BaseModel):
    reason: str = Field(..., min_length=20)
    duration_minutes: int | None = None


class BreakglassResponse(BaseModel):
    session_id: str
    expires_at: datetime
    ssh_certificate: str
    ssh_user: str = "wopr-breakglass"
    beacon_ip: str


class BreakglassSession(BaseModel):
    id: str
    user_uid: str
    username: str | None = None
    target_beacon_id: str
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None
    reason: str
    status: str


class BreakglassRevokeRequest(BaseModel):
    reason: str = Field(default="Manual revocation")


# --- Audit ---


class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime
    user_uid: str
    username: str | None = None
    email: str | None = None
    action: str
    target_beacon_id: str | None = None
    access_tier: str
    request_method: str | None = None
    request_path: str | None = None
    response_status: int | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = {}


class AuditLogQuery(BaseModel):
    user_uid: str | None = None
    beacon_id: str | None = None
    access_tier: str | None = None
    action: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
