"""Audit log query endpoints. Breakglass tier only."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import SupportUser, TIER_BREAKGLASS, require_tier
from api.models import AuditLogEntry, BreakglassSession

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogEntry])
async def query_audit_logs(
    request: Request,
    user_uid: str | None = None,
    beacon_id: str | None = None,
    access_tier: str | None = None,
    action: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Query the audit log. Only breakglass-tier users can access."""
    db = request.app.state.db

    conditions = []
    params = []
    idx = 1

    if user_uid:
        conditions.append(f"user_uid = ${idx}")
        params.append(user_uid)
        idx += 1
    if beacon_id:
        conditions.append(f"target_beacon_id = ${idx}")
        params.append(beacon_id)
        idx += 1
    if access_tier:
        conditions.append(f"access_tier = ${idx}")
        params.append(access_tier)
        idx += 1
    if action:
        conditions.append(f"action LIKE ${idx}")
        params.append(f"%{action}%")
        idx += 1
    if since:
        conditions.append(f"timestamp >= ${idx}::timestamptz")
        params.append(since)
        idx += 1
    if until:
        conditions.append(f"timestamp <= ${idx}::timestamptz")
        params.append(until)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])

    rows = await db.fetch(
        f"""
        SELECT id, timestamp, user_uid, username, email, action,
               target_beacon_id, access_tier, request_method, request_path,
               response_status, duration_ms, metadata
        FROM audit_log
        {where}
        ORDER BY timestamp DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )

    return [AuditLogEntry(**{**dict(r), "id": str(r["id"])}) for r in rows]


@router.get("/logs/{log_id}", response_model=AuditLogEntry)
async def get_audit_entry(
    log_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Get a single audit log entry."""
    db = request.app.state.db

    row = await db.fetchrow(
        """
        SELECT id, timestamp, user_uid, username, email, action,
               target_beacon_id, access_tier, request_method, request_path,
               response_status, duration_ms, metadata
        FROM audit_log WHERE id = $1::uuid
        """,
        log_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return AuditLogEntry(**{**dict(row), "id": str(row["id"])})


@router.get("/sessions", response_model=list[BreakglassSession])
async def list_all_sessions(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """List all breakglass sessions (for audit review)."""
    db = request.app.state.db

    rows = await db.fetch(
        """
        SELECT id, user_uid, username, target_beacon_id, started_at,
               expires_at, ended_at, reason, status
        FROM breakglass_sessions
        ORDER BY started_at DESC
        LIMIT 500
        """
    )
    return [BreakglassSession(**{**dict(r), "id": str(r["id"])}) for r in rows]
