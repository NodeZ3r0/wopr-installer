from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SafetyTier(str, Enum):
    AUTO_FIX = "tier1_auto"
    SUGGEST = "tier2_suggest"
    ESCALATE = "tier3_escalate"


class AnalysisStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EscalationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AnalysisRun(BaseModel):
    id: str
    started_at: str
    completed_at: Optional[str] = None
    status: AnalysisStatus = AnalysisStatus.RUNNING
    errors_found: int = 0
    auto_fixed: int = 0
    escalated: int = 0
    summary: str = ""


class Escalation(BaseModel):
    id: str
    analysis_run_id: str
    created_at: str
    tier: SafetyTier
    service: str
    error_summary: str
    proposed_action: str
    confidence: float
    status: EscalationStatus = EscalationStatus.PENDING
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class AIDecision(BaseModel):
    tier: SafetyTier
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    service: str
    error_pattern: str


class EngineStatus(BaseModel):
    running: bool
    ollama_available: bool
    model: str
    last_run: Optional[str] = None
    total_runs: int = 0
    total_auto_fixes: int = 0
    total_escalations: int = 0
    rate_limit_remaining: int = 10
