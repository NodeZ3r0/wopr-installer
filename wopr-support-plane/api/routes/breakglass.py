"""Emergency breakglass access endpoints."""

import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from api.audit import audit_log
from api.auth import SupportUser, TIER_BREAKGLASS, require_tier
from api.models import (
    BreakglassRequest,
    BreakglassResponse,
    BreakglassRevokeRequest,
    BreakglassSession,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["breakglass"])


@router.post("/beacons/{beacon_id}/breakglass", response_model=BreakglassResponse)
async def start_breakglass_session(
    beacon_id: str,
    body: BreakglassRequest,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Start an emergency breakglass session with full access."""
    db = request.app.state.db
    config = request.app.state.config
    start = time.monotonic()

    # Get beacon
    beacon = await db.fetchrow(
        "SELECT nebula_ip FROM beacons WHERE beacon_id = $1", beacon_id
    )
    if not beacon:
        raise HTTPException(status_code=404, detail="Beacon not found")

    # Check for existing active session on this beacon by this user
    existing = await db.fetchrow(
        """
        SELECT id FROM breakglass_sessions
        WHERE user_uid = $1 AND target_beacon_id = $2 AND status = 'active'
        """,
        user.uid, beacon_id,
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Active breakglass session already exists: {existing['id']}",
        )

    # Calculate duration with hard cap
    duration = min(
        body.duration_minutes or config.breakglass_default_minutes,
        config.breakglass_max_minutes,
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration)

    # Create session record
    session = await db.fetchrow(
        """
        INSERT INTO breakglass_sessions
            (user_uid, username, email, target_beacon_id, expires_at, reason)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        user.uid, user.username, user.email, beacon_id, expires_at, body.reason,
    )
    session_id = str(session["id"])

    # Request breakglass SSH certificate
    import httpx

    async with httpx.AsyncClient() as client:
        cert_resp = await client.post(
            f"{config.ssh_ca_url}/api/v1/sign",
            json={
                "beacon_id": beacon_id,
                "tier": "breakglass",
                "breakglass_session_id": session_id,
            },
            headers={
                "X-Authentik-UID": request.headers.get("X-Authentik-UID", ""),
                "X-Authentik-Username": request.headers.get("X-Authentik-Username", ""),
                "X-Authentik-Email": request.headers.get("X-Authentik-Email", ""),
                "X-Authentik-Groups": request.headers.get("X-Authentik-Groups", ""),
            },
            timeout=10.0,
        )
        if cert_resp.status_code != 200:
            # Roll back session
            await db.execute(
                "DELETE FROM breakglass_sessions WHERE id = $1::uuid", session_id
            )
            raise HTTPException(status_code=502, detail="Failed to obtain SSH certificate")
        cert_data = cert_resp.json()

    # Update session with cert serial
    await db.execute(
        "UPDATE breakglass_sessions SET ssh_cert_serial = $1 WHERE id = $2::uuid",
        cert_data.get("serial", ""), session_id,
    )

    duration_ms = int((time.monotonic() - start) * 1000)

    await audit_log(
        db, user.uid, user.username, user.email,
        "breakglass.session_start", user.access_tier, request,
        200, duration_ms,
        target_beacon_id=beacon_id,
        metadata={
            "session_id": session_id,
            "reason": body.reason,
            "duration_minutes": duration,
            "expires_at": expires_at.isoformat(),
        },
    )

    logger.warning(
        "BREAKGLASS SESSION STARTED: user=%s beacon=%s session=%s reason=%s expires=%s",
        user.username, beacon_id, session_id, body.reason, expires_at.isoformat(),
    )

    return BreakglassResponse(
        session_id=session_id,
        expires_at=expires_at,
        ssh_certificate=cert_data["certificate"],
        ssh_user="wopr-breakglass",
        beacon_ip=beacon["nebula_ip"],
    )


@router.get("/breakglass/sessions", response_model=list[BreakglassSession])
async def list_breakglass_sessions(
    request: Request,
    status: str | None = None,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """List breakglass sessions."""
    db = request.app.state.db

    if status:
        rows = await db.fetch(
            """
            SELECT id, user_uid, username, target_beacon_id, started_at,
                   expires_at, ended_at, reason, status
            FROM breakglass_sessions WHERE status = $1
            ORDER BY started_at DESC LIMIT 100
            """,
            status,
        )
    else:
        rows = await db.fetch(
            """
            SELECT id, user_uid, username, target_beacon_id, started_at,
                   expires_at, ended_at, reason, status
            FROM breakglass_sessions
            ORDER BY started_at DESC LIMIT 100
            """
        )

    return [BreakglassSession(**{**dict(r), "id": str(r["id"])}) for r in rows]


@router.post("/breakglass/{session_id}/revoke")
async def revoke_breakglass_session(
    session_id: str,
    body: BreakglassRevokeRequest,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Revoke an active breakglass session."""
    db = request.app.state.db
    start = time.monotonic()

    session = await db.fetchrow(
        "SELECT * FROM breakglass_sessions WHERE id = $1::uuid AND status = 'active'",
        session_id,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found")

    await db.execute(
        """
        UPDATE breakglass_sessions
        SET status = 'revoked', ended_at = now(), revoked_by = $1
        WHERE id = $2::uuid
        """,
        user.uid, session_id,
    )

    duration_ms = int((time.monotonic() - start) * 1000)

    await audit_log(
        db, user.uid, user.username, user.email,
        "breakglass.session_revoke", user.access_tier, request,
        200, duration_ms,
        target_beacon_id=session["target_beacon_id"],
        metadata={
            "session_id": session_id,
            "revoke_reason": body.reason,
            "original_user": session["user_uid"],
        },
    )

    logger.warning(
        "BREAKGLASS SESSION REVOKED: session=%s revoked_by=%s reason=%s",
        session_id, user.username, body.reason,
    )

    return {"status": "revoked", "session_id": session_id}
