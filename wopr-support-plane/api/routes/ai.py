"""AI Remediation Engine proxy routes.

Proxies requests to the standalone WOPR AI Remediation Engine
running on localhost:9100. Requires TIER_REMEDIATE for read access,
TIER_BREAKGLASS for approve/reject/trigger actions.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import SupportUser, TIER_REMEDIATE, TIER_BREAKGLASS, require_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Remediation"])

AI_ENGINE_URL = "http://127.0.0.1:9100"


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
