"""AI Remediation Engine proxy routes.

Proxies requests to the standalone WOPR AI Remediation Engine
running on localhost:9100. Requires TIER_REMEDIATE for read access,
TIER_BREAKGLASS for approve/reject/trigger actions.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from api.auth import SupportUser, TIER_REMEDIATE, TIER_BREAKGLASS, require_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Remediation"])

# Dashboard router (no /api/v1/ai prefix)
dashboard_router = APIRouter(tags=["AI Dashboard"])

# AI Engine URL - can point to local or remote beacon via Nebula
# For multi-beacon: future enhancement to route by beacon_id
AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://127.0.0.1:9100")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

# Template path
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class SuggestionRequest(BaseModel):
    service: str
    error_summary: str


class Suggestion(BaseModel):
    action: str
    confidence: float
    rationale: str


# Known remediation actions and their descriptions
REMEDIATION_KNOWLEDGE = {
    "restart_service": {
        "description": "Restart the systemd service",
        "applies_to": ["service_failed", "process_killed", "timeout", "connection_refused"],
        "risk": "low",
    },
    "restart_container": {
        "description": "Restart the Podman container",
        "applies_to": ["container_crash", "oom", "service_failed"],
        "risk": "low",
    },
    "clear_tmp": {
        "description": "Clear temporary files to free disk space",
        "applies_to": ["disk_full", "no_space"],
        "risk": "low",
    },
    "rotate_logs": {
        "description": "Force log rotation to free space",
        "applies_to": ["disk_full", "log_overflow"],
        "risk": "low",
    },
    "check_memory": {
        "description": "Check memory usage and identify memory hogs",
        "applies_to": ["out_of_memory", "oom", "high_memory"],
        "risk": "low",
    },
    "check_certificates": {
        "description": "Check SSL/TLS certificate validity and expiration",
        "applies_to": ["ssl_error", "certificate_expired", "tls_handshake"],
        "risk": "low",
    },
    "reload_caddy": {
        "description": "Reload Caddy reverse proxy configuration",
        "applies_to": ["502_error", "proxy_error", "routing_error"],
        "risk": "low",
    },
    "configure_woodpecker_forge": {
        "description": "Configure Woodpecker CI to connect to Forgejo",
        "applies_to": ["woodpecker_forge_missing", "ci_config_error"],
        "risk": "medium",
    },
    "investigate_permissions": {
        "description": "Investigate and fix file/directory permissions",
        "applies_to": ["permission_denied", "access_denied", "eacces"],
        "risk": "medium",
    },
    "investigate_auth_failure": {
        "description": "Investigate authentication failures and token issues",
        "applies_to": ["auth_failure", "unauthorized", "invalid_token"],
        "risk": "medium",
    },
    "pull_container_image": {
        "description": "Pull latest container image version",
        "applies_to": ["image_not_found", "pull_error", "version_mismatch"],
        "risk": "medium",
    },
}


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{AI_ENGINE_URL}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(502, "AI Engine unavailable")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)


async def _proxy_post(path: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{AI_ENGINE_URL}{path}")
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(502, "AI Engine unavailable")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)


@router.get("/status")
async def ai_status(user: SupportUser = Depends(require_tier(TIER_REMEDIATE))):
    """Get AI engine status including Ollama availability and stats."""
    return await _proxy_get("/api/v1/ai/status")


@router.get("/escalations")
async def ai_escalations(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """List AI escalations (pending, approved, rejected)."""
    return await _proxy_get("/api/v1/ai/escalations", {"status": status, "limit": limit})


@router.post("/escalations/{esc_id}/approve")
async def ai_approve(
    esc_id: str,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Approve a pending AI escalation (breakglass tier required)."""
    logger.warning("AI escalation %s approved by %s (%s)", esc_id, user.username, user.uid)
    return await _proxy_post(f"/api/v1/ai/escalations/{esc_id}/approve")


@router.post("/escalations/{esc_id}/reject")
async def ai_reject(
    esc_id: str,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Reject a pending AI escalation (breakglass tier required)."""
    logger.info("AI escalation %s rejected by %s (%s)", esc_id, user.username, user.uid)
    return await _proxy_post(f"/api/v1/ai/escalations/{esc_id}/reject")


@router.post("/analyze-now")
async def ai_analyze_now(
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Trigger an immediate analysis cycle (breakglass tier required)."""
    logger.warning("Manual AI analysis triggered by %s (%s)", user.username, user.uid)
    return await _proxy_post("/api/v1/ai/analyze-now")


@router.get("/history")
async def ai_history(
    limit: int = Query(20, ge=1, le=100),
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get analysis run history."""
    return await _proxy_get("/api/v1/ai/history", {"limit": limit})


@router.get("/actions")
async def ai_actions(
    limit: int = Query(50, ge=1, le=200),
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get auto-action execution history."""
    return await _proxy_get("/api/v1/ai/actions", {"limit": limit})


@router.post("/suggest-remediation")
async def suggest_remediation(
    body: SuggestionRequest,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Generate AI-powered remediation suggestions for an error.

    Returns 3 ranked suggestions with confidence scores and rationale.
    Uses local Ollama if available, falls back to rule-based suggestions.
    """
    suggestions = []

    error_lower = body.error_summary.lower()
    service_lower = body.service.lower()

    # Try Ollama for intelligent suggestions
    try:
        suggestions = await _get_ollama_suggestions(body.service, body.error_summary)
    except Exception as e:
        logger.warning("Ollama suggestions failed, using rule-based: %s", e)

    # Fall back to rule-based if Ollama didn't return enough
    if len(suggestions) < 3:
        rule_suggestions = _get_rule_based_suggestions(body.service, body.error_summary)
        # Merge, avoiding duplicates
        existing_actions = {s.action for s in suggestions}
        for rs in rule_suggestions:
            if rs.action not in existing_actions and len(suggestions) < 3:
                suggestions.append(rs)

    # Ensure we have at least 3 suggestions
    while len(suggestions) < 3:
        suggestions.append(Suggestion(
            action="investigate_manually",
            confidence=0.3,
            rationale="Manual investigation recommended - error pattern not recognized"
        ))

    return {"suggestions": suggestions[:3]}


async def _get_ollama_suggestions(service: str, error_summary: str) -> list[Suggestion]:
    """Query Ollama for intelligent remediation suggestions."""
    prompt = f"""You are a WOPR AI remediation assistant. Analyze this error and suggest 3 remediation actions.

Service: {service}
Error: {error_summary}

Available actions:
- restart_service: Restart the systemd service
- restart_container: Restart the Podman container
- clear_tmp: Clear temporary files
- rotate_logs: Force log rotation
- check_memory: Check memory usage
- check_certificates: Check SSL certificates
- reload_caddy: Reload Caddy proxy
- configure_woodpecker_forge: Configure Woodpecker CI forge connection
- investigate_permissions: Fix permission issues
- investigate_auth_failure: Debug authentication
- pull_container_image: Pull latest container image

Respond with exactly 3 suggestions in this JSON format:
[
  {{"action": "action_name", "confidence": 0.85, "rationale": "Brief explanation"}},
  {{"action": "action_name", "confidence": 0.70, "rationale": "Brief explanation"}},
  {{"action": "action_name", "confidence": 0.50, "rationale": "Brief explanation"}}
]

Only output valid JSON, no other text."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": os.environ.get("OLLAMA_MODEL", "phi3:mini"),
                "prompt": prompt,
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Parse the response
        import json
        response_text = data.get("response", "[]")

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        parsed = json.loads(response_text.strip())

        return [
            Suggestion(
                action=s.get("action", "investigate_manually"),
                confidence=min(max(float(s.get("confidence", 0.5)), 0.0), 1.0),
                rationale=s.get("rationale", "AI-generated suggestion")
            )
            for s in parsed[:3]
        ]


def _get_rule_based_suggestions(service: str, error_summary: str) -> list[Suggestion]:
    """Generate rule-based suggestions when Ollama is unavailable."""
    suggestions = []
    error_lower = error_summary.lower()

    # Pattern matching for common errors
    patterns = [
        (["forge not configured", "woodpecker"], "configure_woodpecker_forge", 0.9,
         "Woodpecker needs to be connected to Forgejo to function"),
        (["out of memory", "oom", "cannot allocate"], "check_memory", 0.85,
         "Memory exhaustion detected - need to identify memory-hungry processes"),
        (["disk full", "no space left"], "clear_tmp", 0.9,
         "Disk space exhausted - clearing temp files may help"),
        (["connection refused", "econnrefused"], "restart_service", 0.8,
         "Service not responding - restart may restore connectivity"),
        (["permission denied", "eacces", "403"], "investigate_permissions", 0.75,
         "Permission error detected - may need file/directory permission fixes"),
        (["certificate", "ssl", "tls", "x509"], "check_certificates", 0.8,
         "SSL/TLS error - certificates may need renewal or verification"),
        (["timeout", "timed out"], "restart_service", 0.7,
         "Timeout suggests service is hung or overloaded"),
        (["killed", "sigkill", "exit code 137"], "restart_container", 0.85,
         "Process was killed (likely OOM) - container restart needed"),
        (["unauthorized", "invalid token", "auth"], "investigate_auth_failure", 0.8,
         "Authentication failure - tokens or credentials may need refresh"),
        (["failed to start", "service failed"], "restart_service", 0.75,
         "Service failed to start - restart with fresh state"),
    ]

    for keywords, action, confidence, rationale in patterns:
        if any(kw in error_lower for kw in keywords):
            suggestions.append(Suggestion(
                action=action,
                confidence=confidence,
                rationale=rationale
            ))

    # Add generic suggestions if we don't have enough
    if len(suggestions) < 3:
        if "wopr-" in service.lower() or service.lower().endswith(".service"):
            suggestions.append(Suggestion(
                action="restart_service",
                confidence=0.5,
                rationale="Generic service restart often resolves transient issues"
            ))

    if len(suggestions) < 3:
        suggestions.append(Suggestion(
            action="rotate_logs",
            confidence=0.4,
            rationale="Log rotation can help with disk space and logging issues"
        ))

    # Sort by confidence
    suggestions.sort(key=lambda x: x.confidence, reverse=True)
    return suggestions[:3]


# Dashboard routes (served at root, not /api/v1/ai)
@dashboard_router.get("/", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Serve the WOPR Admin Suite index page."""
    template_path = TEMPLATES_DIR / "admin-index.html"

    if not template_path.exists():
        raise HTTPException(500, "Admin index template not found")

    return HTMLResponse(content=template_path.read_text())


@dashboard_router.get("/escalations", response_class=HTMLResponse)
async def escalations_dashboard(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Serve the AI Escalations dashboard HTML."""
    template_path = TEMPLATES_DIR / "escalations.html"

    if not template_path.exists():
        raise HTTPException(500, "Dashboard template not found")

    return HTMLResponse(content=template_path.read_text())
