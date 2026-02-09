"""
WOPR Support Brain - Central AI Service
The lighthouse/orchestrator that manages beacon agents and resolves issues.

3-Tier LLM Analysis:
- Tier 1 (tinyllama): Fast, common issues, auto-fix confidence > 0.8
- Tier 2 (mistral): Medium complexity, suggest fix, needs approval
- Tier 3 (phi3:medium): Complex issues, investigate, create ticket
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import smtplib
import sqlite3
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    AnalysisTier,
    AuditLogEntry,
    BeaconInfo,
    BeaconListResponse,
    BrainConfig,
    CommandInfo,
    CommandQueueResponse,
    CommandRequest,
    CommandResultRequest,
    CommandStatus,
    HealthStatus,
    HeartbeatRequest,
    HeartbeatResponse,
    IssueDetail,
    IssueListResponse,
    IssueReport,
    IssueResponse,
    IssueSeverity,
    IssueStatus,
    LLMAnalysisResult,
    PendingCommandsResponse,
    TicketInfo,
)

# ============== Logging Setup ==============

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("support_brain.log"),
    ],
)
logger = logging.getLogger("WOPRSupportBrain")

# ============== Configuration ==============

CONFIG = BrainConfig(
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    max_auto_fixes_per_hour=int(os.getenv("MAX_AUTO_FIXES_PER_HOUR", "10")),
    heartbeat_timeout_seconds=int(os.getenv("HEARTBEAT_TIMEOUT", "300")),
    critical_threshold_seconds=int(os.getenv("CRITICAL_THRESHOLD", "600")),
    ntfy_server=os.getenv("NTFY_SERVER", "https://ntfy.sh"),
    ntfy_topic=os.getenv("NTFY_TOPIC", "wopr-support"),
    email_enabled=os.getenv("EMAIL_ENABLED", "false").lower() == "true",
    email_recipients=os.getenv("EMAIL_RECIPIENTS", "").split(",") if os.getenv("EMAIL_RECIPIENTS") else [],
    smtp_server=os.getenv("SMTP_SERVER"),
    smtp_port=int(os.getenv("SMTP_PORT", "587")),
    smtp_username=os.getenv("SMTP_USERNAME"),
    smtp_password=os.getenv("SMTP_PASSWORD"),
)

# ============== Database Setup ==============

DB_PATH = os.getenv("DB_PATH", "support_brain.db")


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Beacons table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beacons (
            beacon_id TEXT PRIMARY KEY,
            subdomain TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            hostname TEXT,
            platform TEXT,
            health_status TEXT DEFAULT 'unknown',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            uptime_seconds INTEGER,
            version TEXT,
            extra_data TEXT
        )
    """)

    # Issues table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            issue_id TEXT PRIMARY KEY,
            beacon_id TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            title TEXT NOT NULL,
            description TEXT,
            affected_service TEXT,
            error_message TEXT,
            stack_trace TEXT,
            metrics TEXT,
            context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP,
            analysis_tier TEXT,
            analysis_attempts INTEGER DEFAULT 0,
            suggested_fix TEXT,
            applied_fix TEXT,
            fix_result TEXT,
            ticket_id TEXT,
            resolution_notes TEXT,
            FOREIGN KEY (beacon_id) REFERENCES beacons(beacon_id)
        )
    """)

    # Commands table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            command_id TEXT PRIMARY KEY,
            beacon_id TEXT NOT NULL,
            issue_id TEXT,
            command_type TEXT NOT NULL,
            command TEXT NOT NULL,
            args TEXT,
            status TEXT DEFAULT 'queued',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP,
            completed_at TIMESTAMP,
            result TEXT,
            error TEXT,
            priority INTEGER DEFAULT 5,
            timeout_seconds INTEGER DEFAULT 300,
            requires_approval INTEGER DEFAULT 0,
            approved_by TEXT,
            FOREIGN KEY (beacon_id) REFERENCES beacons(beacon_id),
            FOREIGN KEY (issue_id) REFERENCES issues(issue_id)
        )
    """)

    # Analysis results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            analysis_id TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            model_name TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            confidence REAL,
            diagnosis TEXT,
            root_cause TEXT,
            suggested_fix TEXT,
            fix_command TEXT,
            is_safe_to_auto_fix INTEGER DEFAULT 0,
            requires_approval INTEGER DEFAULT 1,
            escalate INTEGER DEFAULT 0,
            escalation_reason TEXT,
            reasoning TEXT,
            tokens_used INTEGER,
            analysis_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (issue_id) REFERENCES issues(issue_id)
        )
    """)

    # Tickets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            beacon_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ntfy_sent INTEGER DEFAULT 0,
            email_sent INTEGER DEFAULT 0,
            assigned_to TEXT,
            status TEXT DEFAULT 'open',
            FOREIGN KEY (issue_id) REFERENCES issues(issue_id),
            FOREIGN KEY (beacon_id) REFERENCES beacons(beacon_id)
        )
    """)

    # Audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id TEXT PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            action_type TEXT NOT NULL,
            beacon_id TEXT,
            issue_id TEXT,
            command_id TEXT,
            actor TEXT DEFAULT 'system',
            description TEXT NOT NULL,
            details TEXT,
            ip_address TEXT
        )
    """)

    # Rate limiting table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            beacon_id TEXT NOT NULL,
            hour_bucket TEXT NOT NULL,
            auto_fix_count INTEGER DEFAULT 0,
            PRIMARY KEY (beacon_id, hour_bucket)
        )
    """)

    # Resolution patterns table (for learning)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resolution_patterns (
            pattern_id TEXT PRIMARY KEY,
            issue_type TEXT NOT NULL,
            issue_signature TEXT NOT NULL,
            successful_fix TEXT NOT NULL,
            success_count INTEGER DEFAULT 1,
            failure_count INTEGER DEFAULT 0,
            avg_confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


# ============== Rate Limiting ==============

class RateLimiter:
    """Rate limiter for auto-fixes per beacon."""

    def __init__(self, max_per_hour: int = 10):
        self.max_per_hour = max_per_hour

    def get_hour_bucket(self) -> str:
        """Get current hour bucket string."""
        return datetime.utcnow().strftime("%Y-%m-%d-%H")

    def can_auto_fix(self, beacon_id: str) -> bool:
        """Check if beacon can perform auto-fix."""
        conn = get_db()
        cursor = conn.cursor()
        hour_bucket = self.get_hour_bucket()

        cursor.execute(
            "SELECT auto_fix_count FROM rate_limits WHERE beacon_id = ? AND hour_bucket = ?",
            (beacon_id, hour_bucket)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return True
        return row["auto_fix_count"] < self.max_per_hour

    def record_auto_fix(self, beacon_id: str):
        """Record an auto-fix for rate limiting."""
        conn = get_db()
        cursor = conn.cursor()
        hour_bucket = self.get_hour_bucket()

        cursor.execute("""
            INSERT INTO rate_limits (beacon_id, hour_bucket, auto_fix_count)
            VALUES (?, ?, 1)
            ON CONFLICT(beacon_id, hour_bucket)
            DO UPDATE SET auto_fix_count = auto_fix_count + 1
        """, (beacon_id, hour_bucket))

        conn.commit()
        conn.close()

    def get_remaining(self, beacon_id: str) -> int:
        """Get remaining auto-fixes for beacon this hour."""
        conn = get_db()
        cursor = conn.cursor()
        hour_bucket = self.get_hour_bucket()

        cursor.execute(
            "SELECT auto_fix_count FROM rate_limits WHERE beacon_id = ? AND hour_bucket = ?",
            (beacon_id, hour_bucket)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return self.max_per_hour
        return max(0, self.max_per_hour - row["auto_fix_count"])


rate_limiter = RateLimiter(CONFIG.max_auto_fixes_per_hour)


# ============== Safety Checker ==============

class SafetyChecker:
    """Check commands against safety blocklist."""

    def __init__(self, blocklist: List[str]):
        self.blocklist = [cmd.lower() for cmd in blocklist]
        # Compile regex patterns for more sophisticated matching
        self.patterns = [
            re.compile(r"rm\s+(-[rf]+\s+)*(/|~|\.\.|/\*)", re.IGNORECASE),
            re.compile(r">\s*/dev/(sda|hda|nvme)", re.IGNORECASE),
            re.compile(r"(curl|wget)\s+.*\|\s*(sh|bash)", re.IGNORECASE),
            re.compile(r"(DROP|DELETE|TRUNCATE)\s+(TABLE|DATABASE|FROM)", re.IGNORECASE),
            re.compile(r"chmod\s+(-R\s+)?777\s+/", re.IGNORECASE),
            re.compile(r"mkfs\.", re.IGNORECASE),
            re.compile(r"dd\s+if=/dev/(zero|random|urandom)", re.IGNORECASE),
        ]

    def is_safe(self, command: str) -> tuple[bool, Optional[str]]:
        """
        Check if command is safe to execute.
        Returns (is_safe, reason) tuple.
        """
        cmd_lower = command.lower().strip()

        # Check against blocklist
        for blocked in self.blocklist:
            if blocked in cmd_lower:
                return False, f"Command contains blocked pattern: {blocked}"

        # Check against regex patterns
        for pattern in self.patterns:
            if pattern.search(command):
                return False, f"Command matches dangerous pattern: {pattern.pattern}"

        return True, None


safety_checker = SafetyChecker(CONFIG.safety_blocklist)


# ============== Audit Logger ==============

def log_audit(
    action_type: str,
    description: str,
    beacon_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    command_id: Optional[str] = None,
    actor: str = "system",
    details: Optional[Dict] = None,
    ip_address: Optional[str] = None,
):
    """Log an audit entry."""
    conn = get_db()
    cursor = conn.cursor()

    log_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO audit_log (log_id, action_type, beacon_id, issue_id, command_id, actor, description, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log_id,
        action_type,
        beacon_id,
        issue_id,
        command_id,
        actor,
        description,
        json.dumps(details) if details else None,
        ip_address,
    ))

    conn.commit()
    conn.close()
    logger.info(f"AUDIT [{action_type}]: {description}")


# ============== Ollama LLM Integration ==============

class OllamaAnalyzer:
    """3-Tier LLM analyzer using Ollama."""

    def __init__(self, config: BrainConfig):
        self.config = config
        self.base_url = config.ollama_base_url
        self.tiers = {tier.tier: tier for tier in config.tiers}

    async def analyze(
        self,
        issue: IssueReport,
        tier: AnalysisTier,
        attempt: int,
        previous_results: List[LLMAnalysisResult] = None,
    ) -> LLMAnalysisResult:
        """Analyze an issue using the specified tier model."""
        tier_config = self.tiers[tier]

        # Build context from previous attempts
        context = ""
        if previous_results:
            context = "\n\nPrevious analysis attempts:\n"
            for prev in previous_results:
                context += f"- {prev.tier.value} ({prev.model_name}): {prev.diagnosis}\n"
                if prev.suggested_fix:
                    context += f"  Suggested fix: {prev.suggested_fix}\n"

        # Build the prompt
        prompt = self._build_prompt(issue, tier, context)

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=tier_config.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": tier_config.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": tier_config.temperature,
                        },
                    },
                )
                response.raise_for_status()
                result = response.json()

        except httpx.TimeoutException:
            return LLMAnalysisResult(
                tier=tier,
                model_name=tier_config.model_name,
                attempt=attempt,
                confidence=0.0,
                diagnosis="Analysis timed out",
                escalate=True,
                escalation_reason="Model timeout",
                analysis_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return LLMAnalysisResult(
                tier=tier,
                model_name=tier_config.model_name,
                attempt=attempt,
                confidence=0.0,
                diagnosis=f"Analysis failed: {str(e)}",
                escalate=True,
                escalation_reason=f"API error: {str(e)}",
                analysis_time_ms=int((time.time() - start_time) * 1000),
            )

        analysis_time = int((time.time() - start_time) * 1000)

        # Parse the response
        return self._parse_response(
            result.get("response", ""),
            tier,
            tier_config,
            attempt,
            analysis_time,
            result.get("eval_count", 0),
        )

    def _build_prompt(self, issue: IssueReport, tier: AnalysisTier, context: str) -> str:
        """Build analysis prompt based on tier."""
        base_prompt = f"""You are a system operations AI assistant analyzing a technical issue.

ISSUE DETAILS:
- Type: {issue.issue_type}
- Severity: {issue.severity.value}
- Title: {issue.title}
- Description: {issue.description}
- Affected Service: {issue.affected_service or 'Unknown'}
- Error Message: {issue.error_message or 'None'}
{f'- Stack Trace: {issue.stack_trace[:500]}...' if issue.stack_trace else ''}
- Metrics: {json.dumps(issue.metrics) if issue.metrics else 'None'}
{context}
"""

        if tier == AnalysisTier.TIER_1:
            return base_prompt + """
TIER 1 ANALYSIS (Fast Resolution):
You are the first-line responder. Focus on:
1. Common, well-known issues with established fixes
2. Quick diagnosis and immediate remediation
3. Only suggest auto-fix if you are >80% confident

Respond in this exact JSON format:
{
    "diagnosis": "Brief diagnosis of the issue",
    "root_cause": "Root cause if identifiable",
    "confidence": 0.0-1.0,
    "suggested_fix": "Human-readable fix description",
    "fix_command": "Exact command to run (or null if not applicable)",
    "is_safe_to_auto_fix": true/false,
    "requires_approval": true/false,
    "escalate": true/false,
    "escalation_reason": "Why escalating (if applicable)"
}
"""

        elif tier == AnalysisTier.TIER_2:
            return base_prompt + """
TIER 2 ANALYSIS (Medium Complexity):
Previous tier could not resolve. Focus on:
1. More complex diagnostic reasoning
2. Consider multiple possible causes
3. Suggest fixes that may need human approval
4. Investigate configuration and dependency issues

Respond in this exact JSON format:
{
    "diagnosis": "Detailed diagnosis of the issue",
    "root_cause": "Identified root cause",
    "confidence": 0.0-1.0,
    "suggested_fix": "Detailed fix description",
    "fix_command": "Command(s) to run (or null)",
    "is_safe_to_auto_fix": true/false,
    "requires_approval": true/false,
    "escalate": true/false,
    "escalation_reason": "Why escalating (if applicable)",
    "reasoning": "Step-by-step reasoning"
}
"""

        else:  # TIER_3
            return base_prompt + """
TIER 3 ANALYSIS (Complex Investigation):
This issue has not been resolved by previous tiers. Focus on:
1. Deep investigation and comprehensive analysis
2. Consider edge cases and unusual scenarios
3. Provide detailed remediation plan
4. Prepare support ticket content if needed
5. This may require human intervention

Respond in this exact JSON format:
{
    "diagnosis": "Comprehensive diagnosis",
    "root_cause": "Thorough root cause analysis",
    "confidence": 0.0-1.0,
    "suggested_fix": "Detailed remediation plan",
    "fix_command": "Command(s) if applicable (or null)",
    "is_safe_to_auto_fix": false,
    "requires_approval": true,
    "escalate": true/false,
    "escalation_reason": "Reason for human escalation",
    "reasoning": "Complete analysis reasoning",
    "ticket_summary": "Summary for support ticket"
}
"""

    def _parse_response(
        self,
        response: str,
        tier: AnalysisTier,
        tier_config,
        attempt: int,
        analysis_time: int,
        tokens: int,
    ) -> LLMAnalysisResult:
        """Parse LLM response into structured result."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Fallback parsing
                data = {
                    "diagnosis": response[:500],
                    "confidence": 0.3,
                    "escalate": True,
                    "escalation_reason": "Could not parse structured response",
                }

            confidence = float(data.get("confidence", 0.5))

            # Determine if auto-fix is safe based on tier thresholds
            is_safe = data.get("is_safe_to_auto_fix", False)
            if confidence < tier_config.auto_fix_threshold:
                is_safe = False

            # Check command safety
            fix_command = data.get("fix_command")
            if fix_command:
                safe, reason = safety_checker.is_safe(fix_command)
                if not safe:
                    is_safe = False
                    data["escalation_reason"] = f"Command blocked: {reason}"

            return LLMAnalysisResult(
                tier=tier,
                model_name=tier_config.model_name,
                attempt=attempt,
                confidence=confidence,
                diagnosis=data.get("diagnosis", "Unable to diagnose"),
                root_cause=data.get("root_cause"),
                suggested_fix=data.get("suggested_fix"),
                fix_command=fix_command,
                is_safe_to_auto_fix=is_safe and confidence >= tier_config.auto_fix_threshold,
                requires_approval=data.get("requires_approval", True),
                escalate=data.get("escalate", False),
                escalation_reason=data.get("escalation_reason"),
                reasoning=data.get("reasoning"),
                tokens_used=tokens,
                analysis_time_ms=analysis_time,
            )

        except json.JSONDecodeError:
            return LLMAnalysisResult(
                tier=tier,
                model_name=tier_config.model_name,
                attempt=attempt,
                confidence=0.2,
                diagnosis=response[:500] if response else "No response from model",
                escalate=True,
                escalation_reason="Failed to parse model response",
                analysis_time_ms=analysis_time,
                tokens_used=tokens,
            )


analyzer = OllamaAnalyzer(CONFIG)


# ============== Notification Services ==============

async def send_ntfy_notification(ticket: TicketInfo):
    """Send notification via ntfy."""
    if not CONFIG.ntfy_server or not CONFIG.ntfy_topic:
        logger.warning("ntfy not configured, skipping notification")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CONFIG.ntfy_server}/{CONFIG.ntfy_topic}",
                headers={
                    "Title": f"[{ticket.severity.value.upper()}] {ticket.title}",
                    "Priority": "high" if ticket.severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL] else "default",
                    "Tags": f"warning,ticket,{ticket.severity.value}",
                },
                content=f"""Support Ticket Created

Ticket ID: {ticket.ticket_id}
Beacon: {ticket.beacon_id}
Severity: {ticket.severity.value}

{ticket.description[:500]}

View in Support Brain dashboard for details.
""",
            )
            response.raise_for_status()
            logger.info(f"ntfy notification sent for ticket {ticket.ticket_id}")
            return True
    except Exception as e:
        logger.error(f"Failed to send ntfy notification: {e}")
        return False


async def send_email_notification(ticket: TicketInfo):
    """Send notification via email."""
    if not CONFIG.email_enabled or not CONFIG.email_recipients:
        logger.warning("Email not configured, skipping notification")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[WOPR Support] [{ticket.severity.value.upper()}] {ticket.title}"
        msg["From"] = CONFIG.smtp_username or "wopr-support@localhost"
        msg["To"] = ", ".join(CONFIG.email_recipients)

        text_content = f"""
WOPR Support Brain - Ticket Created

Ticket ID: {ticket.ticket_id}
Issue ID: {ticket.issue_id}
Beacon ID: {ticket.beacon_id}
Severity: {ticket.severity.value}
Created: {ticket.created_at}

Title: {ticket.title}

Description:
{ticket.description}

---
This ticket was created after 15 failed auto-resolution attempts.
Please investigate and resolve manually.
"""

        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif;">
<h2 style="color: {'#dc3545' if ticket.severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL] else '#ffc107'};">
    WOPR Support Brain - Ticket Created
</h2>
<table style="border-collapse: collapse; margin: 20px 0;">
    <tr><td><strong>Ticket ID:</strong></td><td>{ticket.ticket_id}</td></tr>
    <tr><td><strong>Issue ID:</strong></td><td>{ticket.issue_id}</td></tr>
    <tr><td><strong>Beacon ID:</strong></td><td>{ticket.beacon_id}</td></tr>
    <tr><td><strong>Severity:</strong></td><td>{ticket.severity.value}</td></tr>
    <tr><td><strong>Created:</strong></td><td>{ticket.created_at}</td></tr>
</table>
<h3>{ticket.title}</h3>
<pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">{ticket.description}</pre>
<hr>
<p><em>This ticket was created after 15 failed auto-resolution attempts.</em></p>
</body>
</html>
"""

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(CONFIG.smtp_server, CONFIG.smtp_port) as server:
            server.starttls()
            if CONFIG.smtp_username and CONFIG.smtp_password:
                server.login(CONFIG.smtp_username, CONFIG.smtp_password)
            server.sendmail(msg["From"], CONFIG.email_recipients, msg.as_string())

        logger.info(f"Email notification sent for ticket {ticket.ticket_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


# ============== Issue Resolution Engine ==============

class ResolutionEngine:
    """Orchestrates the 3-tier issue resolution process."""

    def __init__(self):
        self.max_attempts_per_tier = 5
        self.total_max_attempts = 15

    async def process_issue(
        self,
        issue: IssueReport,
        issue_id: str,
    ) -> IssueResponse:
        """Process an issue through the 3-tier system."""
        conn = get_db()
        cursor = conn.cursor()

        # Get current state
        cursor.execute("SELECT * FROM issues WHERE issue_id = ?", (issue_id,))
        issue_row = cursor.fetchone()
        current_attempts = issue_row["analysis_attempts"] if issue_row else 0

        # Get previous analysis results
        cursor.execute(
            "SELECT * FROM analysis_results WHERE issue_id = ? ORDER BY created_at",
            (issue_id,)
        )
        previous_results = []
        for row in cursor.fetchall():
            previous_results.append(LLMAnalysisResult(
                tier=AnalysisTier(row["tier"]),
                model_name=row["model_name"],
                attempt=row["attempt"],
                confidence=row["confidence"] or 0,
                diagnosis=row["diagnosis"] or "",
                root_cause=row["root_cause"],
                suggested_fix=row["suggested_fix"],
                fix_command=row["fix_command"],
                is_safe_to_auto_fix=bool(row["is_safe_to_auto_fix"]),
                requires_approval=bool(row["requires_approval"]),
                escalate=bool(row["escalate"]),
                escalation_reason=row["escalation_reason"],
            ))

        conn.close()

        # Determine current tier based on attempts
        if current_attempts < 5:
            tier = AnalysisTier.TIER_1
            tier_attempt = current_attempts + 1
        elif current_attempts < 10:
            tier = AnalysisTier.TIER_2
            tier_attempt = current_attempts - 4
        elif current_attempts < 15:
            tier = AnalysisTier.TIER_3
            tier_attempt = current_attempts - 9
        else:
            # Max attempts reached, create ticket
            return await self._create_ticket(issue, issue_id, previous_results)

        # Update status to analyzing
        self._update_issue_status(issue_id, IssueStatus.ANALYZING, tier)

        # Perform analysis
        result = await analyzer.analyze(issue, tier, tier_attempt, previous_results)

        # Store analysis result
        self._store_analysis_result(issue_id, result)

        # Increment attempts
        self._increment_attempts(issue_id)

        # Determine next action
        if result.is_safe_to_auto_fix and result.fix_command:
            # Check rate limit
            if rate_limiter.can_auto_fix(issue.beacon_id):
                # Apply auto-fix
                return await self._apply_auto_fix(issue, issue_id, result)
            else:
                logger.warning(f"Rate limit exceeded for beacon {issue.beacon_id}")
                result.requires_approval = True

        if result.escalate or current_attempts >= 14:
            if current_attempts >= 14:
                # Create ticket after 15 attempts
                return await self._create_ticket(issue, issue_id, previous_results + [result])
            else:
                # Escalate to next tier
                return IssueResponse(
                    issue_id=issue_id,
                    status=IssueStatus.ANALYZING,
                    message=f"Escalating to {self._next_tier(tier).value}",
                    analysis_tier=tier,
                    suggested_fix=result.suggested_fix,
                    confidence=result.confidence,
                    requires_approval=True,
                )

        if result.requires_approval:
            self._update_issue_status(issue_id, IssueStatus.AWAITING_APPROVAL, tier)
            return IssueResponse(
                issue_id=issue_id,
                status=IssueStatus.AWAITING_APPROVAL,
                message="Fix suggested, awaiting approval",
                analysis_tier=tier,
                suggested_fix=result.suggested_fix,
                confidence=result.confidence,
                requires_approval=True,
            )

        # Continue analysis
        return IssueResponse(
            issue_id=issue_id,
            status=IssueStatus.ANALYZING,
            message=result.diagnosis,
            analysis_tier=tier,
            suggested_fix=result.suggested_fix,
            confidence=result.confidence,
        )

    async def _apply_auto_fix(
        self,
        issue: IssueReport,
        issue_id: str,
        result: LLMAnalysisResult,
    ) -> IssueResponse:
        """Apply an auto-fix command."""
        # Queue the command
        command_id = str(uuid.uuid4())
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO commands (command_id, beacon_id, issue_id, command_type, command, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            command_id,
            issue.beacon_id,
            issue_id,
            "auto_fix",
            result.fix_command,
            CommandStatus.QUEUED.value,
            8,  # High priority for auto-fixes
        ))

        cursor.execute("""
            UPDATE issues SET status = ?, applied_fix = ?, updated_at = CURRENT_TIMESTAMP
            WHERE issue_id = ?
        """, (IssueStatus.AUTO_FIXED.value, result.fix_command, issue_id))

        conn.commit()
        conn.close()

        # Record rate limit
        rate_limiter.record_auto_fix(issue.beacon_id)

        # Log audit
        log_audit(
            "AUTO_FIX_APPLIED",
            f"Auto-fix applied: {result.fix_command}",
            beacon_id=issue.beacon_id,
            issue_id=issue_id,
            command_id=command_id,
            details={"confidence": result.confidence, "tier": result.tier.value},
        )

        return IssueResponse(
            issue_id=issue_id,
            status=IssueStatus.AUTO_FIXED,
            message="Auto-fix command queued",
            analysis_tier=result.tier,
            suggested_fix=result.suggested_fix,
            auto_fix_applied=True,
            confidence=result.confidence,
        )

    async def _create_ticket(
        self,
        issue: IssueReport,
        issue_id: str,
        results: List[LLMAnalysisResult],
    ) -> IssueResponse:
        """Create a support ticket after max attempts."""
        ticket_id = str(uuid.uuid4())

        # Build ticket description from all analysis attempts
        description = f"""Issue: {issue.title}
Type: {issue.issue_type}
Beacon: {issue.beacon_id}
Service: {issue.affected_service or 'Unknown'}

Original Description:
{issue.description}

Error Message:
{issue.error_message or 'None'}

Analysis History ({len(results)} attempts):
"""
        for r in results:
            description += f"\n[{r.tier.value}] {r.model_name} (confidence: {r.confidence:.2f}):\n"
            description += f"  Diagnosis: {r.diagnosis}\n"
            if r.suggested_fix:
                description += f"  Suggested Fix: {r.suggested_fix}\n"
            if r.escalation_reason:
                description += f"  Escalation: {r.escalation_reason}\n"

        ticket = TicketInfo(
            ticket_id=ticket_id,
            issue_id=issue_id,
            beacon_id=issue.beacon_id,
            title=issue.title,
            description=description,
            severity=issue.severity,
            created_at=datetime.utcnow(),
        )

        # Store ticket
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tickets (ticket_id, issue_id, beacon_id, title, description, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            ticket.ticket_id,
            ticket.issue_id,
            ticket.beacon_id,
            ticket.title,
            ticket.description,
            ticket.severity.value,
        ))

        cursor.execute("""
            UPDATE issues SET status = ?, ticket_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE issue_id = ?
        """, (IssueStatus.TICKET_CREATED.value, ticket_id, issue_id))

        conn.commit()
        conn.close()

        # Send notifications
        ntfy_sent = await send_ntfy_notification(ticket)
        email_sent = await send_email_notification(ticket)

        # Update ticket notification status
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets SET ntfy_sent = ?, email_sent = ? WHERE ticket_id = ?
        """, (ntfy_sent, email_sent, ticket_id))
        conn.commit()
        conn.close()

        # Log audit
        log_audit(
            "TICKET_CREATED",
            f"Support ticket created after {len(results)} failed attempts",
            beacon_id=issue.beacon_id,
            issue_id=issue_id,
            details={"ticket_id": ticket_id, "ntfy_sent": ntfy_sent, "email_sent": email_sent},
        )

        return IssueResponse(
            issue_id=issue_id,
            status=IssueStatus.TICKET_CREATED,
            message=f"Support ticket {ticket_id} created",
            analysis_tier=AnalysisTier.TIER_3,
        )

    def _next_tier(self, current: AnalysisTier) -> AnalysisTier:
        """Get the next tier for escalation."""
        if current == AnalysisTier.TIER_1:
            return AnalysisTier.TIER_2
        elif current == AnalysisTier.TIER_2:
            return AnalysisTier.TIER_3
        return AnalysisTier.TIER_3

    def _update_issue_status(self, issue_id: str, status: IssueStatus, tier: AnalysisTier):
        """Update issue status in database."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE issues SET status = ?, analysis_tier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE issue_id = ?
        """, (status.value, tier.value, issue_id))
        conn.commit()
        conn.close()

    def _increment_attempts(self, issue_id: str):
        """Increment analysis attempts counter."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE issues SET analysis_attempts = analysis_attempts + 1, updated_at = CURRENT_TIMESTAMP
            WHERE issue_id = ?
        """, (issue_id,))
        conn.commit()
        conn.close()

    def _store_analysis_result(self, issue_id: str, result: LLMAnalysisResult):
        """Store analysis result in database."""
        conn = get_db()
        cursor = conn.cursor()

        analysis_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO analysis_results (
                analysis_id, issue_id, tier, model_name, attempt, confidence,
                diagnosis, root_cause, suggested_fix, fix_command,
                is_safe_to_auto_fix, requires_approval, escalate, escalation_reason,
                reasoning, tokens_used, analysis_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_id,
            issue_id,
            result.tier.value,
            result.model_name,
            result.attempt,
            result.confidence,
            result.diagnosis,
            result.root_cause,
            result.suggested_fix,
            result.fix_command,
            result.is_safe_to_auto_fix,
            result.requires_approval,
            result.escalate,
            result.escalation_reason,
            result.reasoning,
            result.tokens_used,
            result.analysis_time_ms,
        ))

        conn.commit()
        conn.close()


resolution_engine = ResolutionEngine()


# ============== Background Tasks ==============

async def check_beacon_health():
    """Background task to check beacon health status."""
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()

            now = datetime.utcnow()
            warning_threshold = now - timedelta(seconds=CONFIG.heartbeat_timeout_seconds)
            critical_threshold = now - timedelta(seconds=CONFIG.critical_threshold_seconds)

            # Update health status based on last_seen
            cursor.execute("""
                UPDATE beacons SET health_status = ?
                WHERE last_seen < ? AND health_status != ?
            """, (HealthStatus.OFFLINE.value, critical_threshold.isoformat(), HealthStatus.OFFLINE.value))

            cursor.execute("""
                UPDATE beacons SET health_status = ?
                WHERE last_seen < ? AND last_seen >= ? AND health_status != ?
            """, (HealthStatus.CRITICAL.value, critical_threshold.isoformat(),
                  warning_threshold.isoformat(), HealthStatus.CRITICAL.value))

            cursor.execute("""
                UPDATE beacons SET health_status = ?
                WHERE last_seen < ? AND last_seen >= ? AND health_status = ?
            """, (HealthStatus.WARNING.value, warning_threshold.isoformat(),
                  (now - timedelta(seconds=CONFIG.heartbeat_timeout_seconds // 2)).isoformat(),
                  HealthStatus.HEALTHY.value))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Health check error: {e}")

        await asyncio.sleep(60)  # Check every minute


# ============== FastAPI Application ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    init_db()
    logger.info("WOPR Support Brain starting up...")

    # Start background tasks
    health_check_task = asyncio.create_task(check_beacon_health())

    yield

    # Shutdown
    health_check_task.cancel()
    logger.info("WOPR Support Brain shutting down...")


app = FastAPI(
    title="WOPR Support Brain",
    description="Central AI service for beacon management and issue resolution",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "WOPR Support Brain", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/v1/heartbeat", response_model=HeartbeatResponse)
async def receive_heartbeat(request: HeartbeatRequest, req: Request):
    """Receive heartbeat from beacon agent."""
    conn = get_db()
    cursor = conn.cursor()

    # Determine health status based on metrics
    health_status = HealthStatus.HEALTHY
    if request.cpu_percent and request.cpu_percent > 90:
        health_status = HealthStatus.CRITICAL
    elif request.cpu_percent and request.cpu_percent > 80:
        health_status = HealthStatus.WARNING
    elif request.memory_percent and request.memory_percent > 90:
        health_status = HealthStatus.CRITICAL
    elif request.memory_percent and request.memory_percent > 80:
        health_status = HealthStatus.WARNING
    elif request.disk_percent and request.disk_percent > 95:
        health_status = HealthStatus.CRITICAL
    elif request.disk_percent and request.disk_percent > 85:
        health_status = HealthStatus.WARNING

    # Upsert beacon
    cursor.execute("""
        INSERT INTO beacons (beacon_id, subdomain, ip_address, hostname, platform, health_status,
                            cpu_percent, memory_percent, disk_percent, uptime_seconds, version, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(beacon_id) DO UPDATE SET
            subdomain = excluded.subdomain,
            ip_address = excluded.ip_address,
            hostname = excluded.hostname,
            platform = excluded.platform,
            health_status = excluded.health_status,
            last_seen = CURRENT_TIMESTAMP,
            cpu_percent = excluded.cpu_percent,
            memory_percent = excluded.memory_percent,
            disk_percent = excluded.disk_percent,
            uptime_seconds = excluded.uptime_seconds,
            version = excluded.version,
            extra_data = excluded.extra_data
    """, (
        request.beacon_id,
        request.subdomain,
        request.ip_address,
        request.hostname,
        request.platform,
        health_status.value,
        request.cpu_percent,
        request.memory_percent,
        request.disk_percent,
        request.uptime_seconds,
        request.version,
        json.dumps(request.extra_data) if request.extra_data else None,
    ))

    # Count pending commands
    cursor.execute(
        "SELECT COUNT(*) as count FROM commands WHERE beacon_id = ? AND status = ?",
        (request.beacon_id, CommandStatus.QUEUED.value)
    )
    pending_count = cursor.fetchone()["count"]

    conn.commit()
    conn.close()

    return HeartbeatResponse(
        status="ok",
        server_time=datetime.utcnow(),
        pending_commands=pending_count,
    )


@app.post("/api/v1/issues", response_model=IssueResponse)
async def report_issue(issue: IssueReport, background_tasks: BackgroundTasks, req: Request):
    """Receive and process an issue from a beacon agent."""
    issue_id = str(uuid.uuid4())

    # Store the issue
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO issues (issue_id, beacon_id, issue_type, severity, status, title, description,
                           affected_service, error_message, stack_trace, metrics, context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        issue_id,
        issue.beacon_id,
        issue.issue_type,
        issue.severity.value,
        IssueStatus.PENDING.value,
        issue.title,
        issue.description,
        issue.affected_service,
        issue.error_message,
        issue.stack_trace,
        json.dumps(issue.metrics) if issue.metrics else None,
        json.dumps(issue.context) if issue.context else None,
    ))

    conn.commit()
    conn.close()

    # Log audit
    log_audit(
        "ISSUE_REPORTED",
        f"Issue reported: {issue.title}",
        beacon_id=issue.beacon_id,
        issue_id=issue_id,
        ip_address=req.client.host if req.client else None,
        details={"issue_type": issue.issue_type, "severity": issue.severity.value},
    )

    # Process the issue
    response = await resolution_engine.process_issue(issue, issue_id)

    return response


@app.get("/api/v1/beacons", response_model=BeaconListResponse)
async def list_beacons():
    """List all beacons and their status."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM beacons ORDER BY last_seen DESC")
    rows = cursor.fetchall()

    beacons = []
    healthy = warning = critical = offline = 0

    for row in rows:
        status = HealthStatus(row["health_status"])
        if status == HealthStatus.HEALTHY:
            healthy += 1
        elif status == HealthStatus.WARNING:
            warning += 1
        elif status == HealthStatus.CRITICAL:
            critical += 1
        elif status == HealthStatus.OFFLINE:
            offline += 1

        # Count today's issues and auto-fixes
        today = datetime.utcnow().date().isoformat()
        cursor.execute(
            "SELECT COUNT(*) as count FROM issues WHERE beacon_id = ? AND DATE(created_at) = ?",
            (row["beacon_id"], today)
        )
        issues_today = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM commands WHERE beacon_id = ? AND command_type = 'auto_fix' AND DATE(created_at) = ?",
            (row["beacon_id"], today)
        )
        auto_fixes_today = cursor.fetchone()["count"]

        beacons.append(BeaconInfo(
            beacon_id=row["beacon_id"],
            subdomain=row["subdomain"],
            ip_address=row["ip_address"],
            hostname=row["hostname"],
            platform=row["platform"],
            health_status=status,
            last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
            first_seen=datetime.fromisoformat(row["first_seen"]) if row["first_seen"] else None,
            cpu_percent=row["cpu_percent"],
            memory_percent=row["memory_percent"],
            disk_percent=row["disk_percent"],
            uptime_seconds=row["uptime_seconds"],
            version=row["version"],
            issues_today=issues_today,
            auto_fixes_today=auto_fixes_today,
            extra_data=json.loads(row["extra_data"]) if row["extra_data"] else None,
        ))

    conn.close()

    return BeaconListResponse(
        total=len(beacons),
        healthy=healthy,
        warning=warning,
        critical=critical,
        offline=offline,
        beacons=beacons,
    )


@app.get("/api/v1/issues", response_model=IssueListResponse)
async def list_issues(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    beacon_id: Optional[str] = None,
    severity: Optional[str] = None,
):
    """List recent issues with optional filtering."""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM issues WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if beacon_id:
        query += " AND beacon_id = ?"
        params.append(beacon_id)
    if severity:
        query += " AND severity = ?"
        params.append(severity)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Count totals
    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status = ?", (IssueStatus.PENDING.value,))
    pending = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status = ?", (IssueStatus.RESOLVED.value,))
    resolved = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status IN (?, ?)",
                   (IssueStatus.ESCALATED.value, IssueStatus.TICKET_CREATED.value))
    escalated = cursor.fetchone()["count"]

    issues = []
    for row in rows:
        issues.append(IssueDetail(
            issue_id=row["issue_id"],
            beacon_id=row["beacon_id"],
            issue_type=row["issue_type"],
            severity=IssueSeverity(row["severity"]),
            status=IssueStatus(row["status"]),
            title=row["title"],
            description=row["description"] or "",
            affected_service=row["affected_service"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            analysis_tier=AnalysisTier(row["analysis_tier"]) if row["analysis_tier"] else None,
            analysis_attempts=row["analysis_attempts"],
            suggested_fix=row["suggested_fix"],
            applied_fix=row["applied_fix"],
            fix_result=row["fix_result"],
            ticket_id=row["ticket_id"],
            resolution_notes=row["resolution_notes"],
        ))

    conn.close()

    return IssueListResponse(
        total=len(issues),
        pending=pending,
        resolved=resolved,
        escalated=escalated,
        issues=issues,
    )


@app.post("/api/v1/commands/{beacon_id}", response_model=CommandQueueResponse)
async def queue_command(beacon_id: str, command: CommandRequest, req: Request):
    """Queue a command for a beacon to execute."""
    # Safety check
    is_safe, reason = safety_checker.is_safe(command.command)
    if not is_safe:
        log_audit(
            "COMMAND_BLOCKED",
            f"Unsafe command blocked: {reason}",
            beacon_id=beacon_id,
            ip_address=req.client.host if req.client else None,
            details={"command": command.command, "reason": reason},
        )
        raise HTTPException(status_code=400, detail=f"Command blocked: {reason}")

    command_id = str(uuid.uuid4())

    conn = get_db()
    cursor = conn.cursor()

    # Check beacon exists
    cursor.execute("SELECT beacon_id FROM beacons WHERE beacon_id = ?", (beacon_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Beacon {beacon_id} not found")

    cursor.execute("""
        INSERT INTO commands (command_id, beacon_id, command_type, command, args, priority, timeout_seconds, requires_approval)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        command_id,
        beacon_id,
        command.command_type,
        command.command,
        json.dumps(command.args) if command.args else None,
        command.priority,
        command.timeout_seconds,
        command.requires_approval,
    ))

    # Get queue position
    cursor.execute(
        "SELECT COUNT(*) as count FROM commands WHERE beacon_id = ? AND status = ?",
        (beacon_id, CommandStatus.QUEUED.value)
    )
    position = cursor.fetchone()["count"]

    conn.commit()
    conn.close()

    log_audit(
        "COMMAND_QUEUED",
        f"Command queued: {command.command_type}",
        beacon_id=beacon_id,
        command_id=command_id,
        ip_address=req.client.host if req.client else None,
    )

    return CommandQueueResponse(
        command_id=command_id,
        status=CommandStatus.QUEUED,
        message="Command queued successfully",
        position_in_queue=position,
    )


@app.get("/api/v1/commands/{beacon_id}", response_model=PendingCommandsResponse)
async def get_pending_commands(beacon_id: str):
    """Beacon polls for pending commands."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM commands
        WHERE beacon_id = ? AND status = ?
        ORDER BY priority DESC, created_at ASC
    """, (beacon_id, CommandStatus.QUEUED.value))

    rows = cursor.fetchall()

    commands = []
    for row in rows:
        # Mark as sent
        cursor.execute("""
            UPDATE commands SET status = ?, sent_at = CURRENT_TIMESTAMP
            WHERE command_id = ?
        """, (CommandStatus.SENT.value, row["command_id"]))

        commands.append(CommandInfo(
            command_id=row["command_id"],
            beacon_id=row["beacon_id"],
            command_type=row["command_type"],
            command=row["command"],
            args=json.loads(row["args"]) if row["args"] else [],
            status=CommandStatus.SENT,
            created_at=datetime.fromisoformat(row["created_at"]),
            priority=row["priority"],
            timeout_seconds=row["timeout_seconds"],
            requires_approval=bool(row["requires_approval"]),
        ))

    conn.commit()
    conn.close()

    return PendingCommandsResponse(
        beacon_id=beacon_id,
        commands=commands,
    )


@app.post("/api/v1/commands/{beacon_id}/result")
async def report_command_result(beacon_id: str, result: CommandResultRequest):
    """Beacon reports command execution result."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE commands
        SET status = ?, completed_at = CURRENT_TIMESTAMP, result = ?, error = ?
        WHERE command_id = ? AND beacon_id = ?
    """, (
        result.status.value,
        result.result,
        result.error,
        result.command_id,
        beacon_id,
    ))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Command not found")

    # If this was an auto-fix, update the related issue
    cursor.execute("SELECT issue_id FROM commands WHERE command_id = ?", (result.command_id,))
    row = cursor.fetchone()
    if row and row["issue_id"]:
        if result.status == CommandStatus.COMPLETED:
            cursor.execute("""
                UPDATE issues SET status = ?, fix_result = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE issue_id = ?
            """, (IssueStatus.RESOLVED.value, result.result, row["issue_id"]))
        elif result.status == CommandStatus.FAILED:
            cursor.execute("""
                UPDATE issues SET status = ?, fix_result = ?
                WHERE issue_id = ?
            """, (IssueStatus.FAILED.value, result.error, row["issue_id"]))

    conn.commit()
    conn.close()

    log_audit(
        "COMMAND_RESULT",
        f"Command {result.command_id} completed: {result.status.value}",
        beacon_id=beacon_id,
        command_id=result.command_id,
    )

    return {"status": "ok", "message": "Result recorded"}


@app.get("/api/v1/audit")
async def get_audit_log(limit: int = 100, offset: int = 0, action_type: Optional[str] = None):
    """Get audit log entries."""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []

    if action_type:
        query += " AND action_type = ?"
        params.append(action_type)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    logs = []
    for row in rows:
        logs.append({
            "log_id": row["log_id"],
            "timestamp": row["timestamp"],
            "action_type": row["action_type"],
            "beacon_id": row["beacon_id"],
            "issue_id": row["issue_id"],
            "command_id": row["command_id"],
            "actor": row["actor"],
            "description": row["description"],
            "details": json.loads(row["details"]) if row["details"] else None,
            "ip_address": row["ip_address"],
        })

    conn.close()

    return {"total": len(logs), "logs": logs}


@app.get("/api/v1/stats")
async def get_statistics():
    """Get system statistics."""
    conn = get_db()
    cursor = conn.cursor()

    # Beacon stats
    cursor.execute("SELECT COUNT(*) as total FROM beacons")
    total_beacons = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as count FROM beacons WHERE health_status = ?", (HealthStatus.HEALTHY.value,))
    healthy_beacons = cursor.fetchone()["count"]

    # Issue stats
    cursor.execute("SELECT COUNT(*) as total FROM issues")
    total_issues = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status = ?", (IssueStatus.RESOLVED.value,))
    resolved_issues = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status = ?", (IssueStatus.AUTO_FIXED.value,))
    auto_fixed = cursor.fetchone()["count"]

    # Today's stats
    today = datetime.utcnow().date().isoformat()
    cursor.execute("SELECT COUNT(*) as count FROM issues WHERE DATE(created_at) = ?", (today,))
    issues_today = cursor.fetchone()["count"]

    cursor.execute(
        "SELECT COUNT(*) as count FROM commands WHERE command_type = 'auto_fix' AND DATE(created_at) = ?",
        (today,)
    )
    auto_fixes_today = cursor.fetchone()["count"]

    # Ticket stats
    cursor.execute("SELECT COUNT(*) as total FROM tickets")
    total_tickets = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as count FROM tickets WHERE status = 'open'")
    open_tickets = cursor.fetchone()["count"]

    conn.close()

    return {
        "beacons": {
            "total": total_beacons,
            "healthy": healthy_beacons,
            "unhealthy": total_beacons - healthy_beacons,
        },
        "issues": {
            "total": total_issues,
            "resolved": resolved_issues,
            "auto_fixed": auto_fixed,
            "today": issues_today,
        },
        "commands": {
            "auto_fixes_today": auto_fixes_today,
        },
        "tickets": {
            "total": total_tickets,
            "open": open_tickets,
        },
    }


# ============== Main Entry Point ==============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "wopr_support_brain:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info",
    )
