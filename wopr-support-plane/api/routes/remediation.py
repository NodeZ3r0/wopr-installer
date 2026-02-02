"""Pre-approved remediation action endpoints."""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from api.audit import audit_log
from api.auth import SupportUser, TIER_REMEDIATE, require_tier
from api.models import RemediationAction, RemediationRequest, RemediationResponse
from api.ssh_client import execute_on_beacon

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["remediation"])


@router.get("/remediation/actions", response_model=list[RemediationAction])
async def list_remediation_actions(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """List all available remediation actions."""
    db = request.app.state.db

    rows = await db.fetch(
        """
        SELECT id, name, description, required_tier, is_enabled, risk_level
        FROM remediation_actions
        WHERE is_enabled = true
        ORDER BY risk_level, name
        """
    )
    return [RemediationAction(**dict(r)) for r in rows]


@router.post(
    "/beacons/{beacon_id}/remediate", response_model=RemediationResponse
)
async def execute_remediation(
    beacon_id: str,
    body: RemediationRequest,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_REMEDIATE)),
):
    """Execute a pre-approved remediation action on a beacon."""
    db = request.app.state.db
    start = time.monotonic()

    # Look up the action
    action = await db.fetchrow(
        "SELECT * FROM remediation_actions WHERE id = $1", body.action_id
    )
    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found")
    if not action["is_enabled"]:
        raise HTTPException(status_code=403, detail="Remediation action is disabled")

    # Check if user's tier meets the action's required tier
    if not user.has_tier(action["required_tier"]):
        raise HTTPException(
            status_code=403,
            detail=f"Action requires {action['required_tier']} tier",
        )

    # Get beacon
    beacon = await db.fetchrow(
        "SELECT nebula_ip FROM beacons WHERE beacon_id = $1", beacon_id
    )
    if not beacon:
        raise HTTPException(status_code=404, detail="Beacon not found")

    # Build the command from template with safe parameter substitution
    command = action["command_template"]
    for key, value in body.parameters.items():
        # Sanitize parameter values to prevent command injection
        safe_value = "".join(c for c in value if c.isalnum() or c in "-_.")
        command = command.replace(f"{{{key}}}", safe_value)

    # Get SSH cert for remediation tier
    import httpx

    config = request.app.state.config
    async with httpx.AsyncClient() as client:
        cert_resp = await client.post(
            f"{config.ssh_ca_url}/api/v1/sign",
            json={"beacon_id": beacon_id, "tier": "remediate"},
            headers={
                "X-Authentik-UID": request.headers.get("X-Authentik-UID", ""),
                "X-Authentik-Username": request.headers.get("X-Authentik-Username", ""),
                "X-Authentik-Email": request.headers.get("X-Authentik-Email", ""),
                "X-Authentik-Groups": request.headers.get("X-Authentik-Groups", ""),
            },
            timeout=10.0,
        )
        if cert_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to obtain SSH certificate")
        cert_data = cert_resp.json()

    # Execute on beacon
    result = await execute_on_beacon(
        beacon_ip=beacon["nebula_ip"],
        certificate_pem=cert_data["certificate"],
        private_key_pem=cert_data["private_key"],
        command=command,
        username="wopr-remediate",
        timeout=60,
    )

    duration_ms = int((time.monotonic() - start) * 1000)

    await audit_log(
        db, user.uid, user.username, user.email,
        f"remediate.{body.action_id}", user.access_tier, request,
        200 if result.exit_code == 0 else 500, duration_ms,
        target_beacon_id=beacon_id,
        metadata={
            "action_id": body.action_id,
            "parameters": body.parameters,
            "exit_code": result.exit_code,
            "risk_level": action["risk_level"],
        },
    )

    return RemediationResponse(
        action_id=body.action_id,
        status="success" if result.exit_code == 0 else "failed",
        output=result.stdout + ("\n" + result.stderr if result.stderr else ""),
        executed_at=datetime.now(timezone.utc),
    )
