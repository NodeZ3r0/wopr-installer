"""Beacon Registry - Multi-beacon support for WOPR Support Plane.

Beacons auto-register with the lighthouse when they come online.
The support-plane can then query any beacon's AI engine for escalations.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import SupportUser, TIER_REMEDIATE, TIER_BREAKGLASS, require_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/beacons", tags=["Beacon Registry"])


class BeaconRegistration(BaseModel):
    """Beacon registration payload - sent by beacon on startup."""
    beacon_id: str = Field(..., description="Unique beacon identifier")
    domain: str = Field(..., description="Beacon domain (e.g., testbeacon.wopr.systems)")
    ai_engine_url: str = Field(..., description="AI engine URL (e.g., https://ai-engine.testbeacon.wopr.systems)")
    public_ip: Optional[str] = Field(None, description="Beacon public IP (auto-detected if not provided)")
    bundle_id: str = Field(..., description="Bundle ID (e.g., sovereign-developer)")
    version: str = Field("1.0.0", description="WOPR installer version")


class BeaconInfo(BaseModel):
    """Beacon info returned by registry."""
    beacon_id: str
    domain: str
    ai_engine_url: str
    public_ip: str
    bundle_id: str
    version: str
    registered_at: str
    last_seen: str
    status: str  # online, offline, degraded


class BeaconHeartbeat(BaseModel):
    """Beacon heartbeat payload."""
    beacon_id: str
    ai_engine_status: str  # running, stopped, error
    services_healthy: int
    services_total: int


@router.post("/register")
async def register_beacon(
    body: BeaconRegistration,
    request: Request,
):
    """Register a new beacon or update existing registration.

    Called by beacons on startup. No auth required - uses IP validation.
    """
    db = request.app.state.db

    # Get client IP
    client_ip = request.client.host
    if body.public_ip:
        # Validate provided IP matches request IP (prevent spoofing)
        if body.public_ip != client_ip:
            logger.warning(
                "Beacon %s IP mismatch: claimed %s, actual %s",
                body.beacon_id, body.public_ip, client_ip
            )

    public_ip = body.public_ip or client_ip

    # Upsert beacon (use now() for timestamps)
    await db.execute("""
        INSERT INTO beacons (beacon_id, domain, ai_engine_url, public_ip, bundle_id, version, registered_at, last_seen, status)
        VALUES ($1, $2, $3, $4, $5, $6, now(), now(), 'online')
        ON CONFLICT (beacon_id) DO UPDATE SET
            domain = $2,
            ai_engine_url = $3,
            public_ip = $4,
            bundle_id = $5,
            version = $6,
            last_seen = now(),
            status = 'online'
    """, body.beacon_id, body.domain, body.ai_engine_url, public_ip, body.bundle_id, body.version)

    logger.info("Beacon registered: %s (%s) at %s", body.beacon_id, body.domain, public_ip)

    return {
        "status": "registered",
        "beacon_id": body.beacon_id,
        "lighthouse_ip": "159.203.138.7",  # nodez3r0 IP for beacon to allowlist
        "message": f"Add {public_ip} to your AI engine Caddy allowlist"
    }


@router.post("/heartbeat")
async def beacon_heartbeat(
    body: BeaconHeartbeat,
    request: Request,
):
    """Update beacon heartbeat - called periodically by beacons."""
    db = request.app.state.db

    status = "online"
    if body.ai_engine_status != "running":
        status = "degraded"

    result = await db.execute("""
        UPDATE beacons SET last_seen = now(), status = $1
        WHERE beacon_id = $2
    """, status, body.beacon_id)

    if "UPDATE 0" in str(result):
        raise HTTPException(404, f"Beacon {body.beacon_id} not registered")

    return {"status": "ok", "beacon_status": status}


@router.get("/", response_model=list[BeaconInfo])
async def list_beacons(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """List all registered beacons."""
    db = request.app.state.db

    rows = await db.fetch("""
        SELECT beacon_id, domain, ai_engine_url, public_ip, bundle_id, version,
               registered_at, last_seen, status
        FROM beacons
        ORDER BY domain
    """)

    return [BeaconInfo(**dict(row)) for row in rows]


@router.get("/{beacon_id}")
async def get_beacon(
    beacon_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get beacon details."""
    db = request.app.state.db

    row = await db.fetchrow("""
        SELECT beacon_id, domain, ai_engine_url, public_ip, bundle_id, version,
               registered_at, last_seen, status
        FROM beacons WHERE beacon_id = $1
    """, beacon_id)

    if not row:
        raise HTTPException(404, f"Beacon {beacon_id} not found")

    return BeaconInfo(**dict(row))


@router.get("/{beacon_id}/ai/status")
async def get_beacon_ai_status(
    beacon_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get AI engine status for a specific beacon."""
    db = request.app.state.db

    row = await db.fetchrow("SELECT ai_engine_url FROM beacons WHERE beacon_id = $1", beacon_id)
    if not row:
        raise HTTPException(404, f"Beacon {beacon_id} not found")

    ai_url = row["ai_engine_url"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{ai_url}/api/v1/ai/status")
            resp.raise_for_status()
            return {"beacon_id": beacon_id, **resp.json()}
    except httpx.ConnectError:
        return {"beacon_id": beacon_id, "status": "unreachable", "error": "Connection failed"}
    except Exception as e:
        return {"beacon_id": beacon_id, "status": "error", "error": str(e)}


@router.get("/{beacon_id}/ai/escalations")
async def get_beacon_escalations(
    beacon_id: str,
    request: Request,
    status: str = "pending",
    limit: int = 50,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get escalations from a specific beacon's AI engine."""
    db = request.app.state.db

    row = await db.fetchrow("SELECT ai_engine_url FROM beacons WHERE beacon_id = $1", beacon_id)
    if not row:
        raise HTTPException(404, f"Beacon {beacon_id} not found")

    ai_url = row["ai_engine_url"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{ai_url}/api/v1/ai/escalations",
                params={"status": status, "limit": limit}
            )
            resp.raise_for_status()
            escalations = resp.json()
            # Add beacon_id to each escalation
            for esc in escalations:
                esc["beacon_id"] = beacon_id
            return escalations
    except httpx.ConnectError:
        raise HTTPException(502, f"Beacon {beacon_id} AI engine unreachable")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)


@router.post("/{beacon_id}/ai/escalations/{esc_id}/approve")
async def approve_beacon_escalation(
    beacon_id: str,
    esc_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Approve an escalation on a specific beacon."""
    db = request.app.state.db

    row = await db.fetchrow("SELECT ai_engine_url FROM beacons WHERE beacon_id = $1", beacon_id)
    if not row:
        raise HTTPException(404, f"Beacon {beacon_id} not found")

    ai_url = row["ai_engine_url"]

    logger.warning("Escalation %s on beacon %s approved by %s (%s)",
                   esc_id, beacon_id, user.username, user.uid)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{ai_url}/api/v1/ai/escalations/{esc_id}/approve")
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(502, f"Beacon {beacon_id} AI engine unreachable")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)


@router.post("/{beacon_id}/ai/escalations/{esc_id}/reject")
async def reject_beacon_escalation(
    beacon_id: str,
    esc_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_BREAKGLASS)),
):
    """Reject an escalation on a specific beacon."""
    db = request.app.state.db

    row = await db.fetchrow("SELECT ai_engine_url FROM beacons WHERE beacon_id = $1", beacon_id)
    if not row:
        raise HTTPException(404, f"Beacon {beacon_id} not found")

    ai_url = row["ai_engine_url"]

    logger.info("Escalation %s on beacon %s rejected by %s (%s)",
                esc_id, beacon_id, user.username, user.uid)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{ai_url}/api/v1/ai/escalations/{esc_id}/reject")
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(502, f"Beacon {beacon_id} AI engine unreachable")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)


# Aggregate endpoint - get escalations from ALL beacons
@router.get("/all/escalations")
async def get_all_escalations(
    request: Request,
    status: str = "pending",
    limit: int = 100,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Get escalations from ALL registered beacons (aggregated view)."""
    db = request.app.state.db

    beacons = await db.fetch("SELECT beacon_id, ai_engine_url, domain FROM beacons WHERE status != 'offline'")

    all_escalations = []
    errors = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for beacon in beacons:
            try:
                resp = await client.get(
                    f"{beacon['ai_engine_url']}/api/v1/ai/escalations",
                    params={"status": status, "limit": limit}
                )
                resp.raise_for_status()
                escalations = resp.json()
                for esc in escalations:
                    esc["beacon_id"] = beacon["beacon_id"]
                    esc["beacon_domain"] = beacon["domain"]
                all_escalations.extend(escalations)
            except Exception as e:
                errors.append({"beacon_id": beacon["beacon_id"], "error": str(e)})

    # Sort by created_at descending
    all_escalations.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {
        "escalations": all_escalations[:limit],
        "total": len(all_escalations),
        "beacons_queried": len(beacons),
        "errors": errors if errors else None
    }
