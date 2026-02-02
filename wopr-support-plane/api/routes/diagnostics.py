"""Read-only diagnostic endpoints for beacon health and logs."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from api.audit import audit_log
from api.auth import SupportUser, TIER_DIAG, require_tier
from api.models import (
    BeaconHealthResponse,
    BeaconLogsRequest,
    BeaconLogsResponse,
    BeaconSummary,
    ServiceStatus,
)
from api.ssh_client import execute_on_beacon

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


async def _get_ssh_cert(request: Request, beacon_id: str, tier: str = "diag") -> dict:
    """Request a short-lived SSH certificate from the CA."""
    import httpx

    config = request.app.state.config
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{config.ssh_ca_url}/api/v1/sign",
            json={"beacon_id": beacon_id, "tier": tier},
            headers={
                "X-Authentik-UID": request.headers.get("X-Authentik-UID", ""),
                "X-Authentik-Username": request.headers.get("X-Authentik-Username", ""),
                "X-Authentik-Email": request.headers.get("X-Authentik-Email", ""),
                "X-Authentik-Groups": request.headers.get("X-Authentik-Groups", ""),
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"SSH CA returned {resp.status_code}: {resp.text}",
            )
        return resp.json()


@router.get("/beacons", response_model=list[BeaconSummary])
async def list_beacons(
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_DIAG)),
):
    """List beacons visible on the Nebula mesh."""
    db = request.app.state.db
    start = time.monotonic()

    # Query known beacons from the database
    rows = await db.fetch(
        "SELECT beacon_id, nebula_ip, hostname, status FROM beacons ORDER BY beacon_id"
    )
    beacons = [
        BeaconSummary(
            beacon_id=r["beacon_id"],
            nebula_ip=r["nebula_ip"],
            hostname=r.get("hostname"),
            status=r.get("status", "unknown"),
        )
        for r in rows
    ]

    await audit_log(
        db, user.uid, user.username, user.email,
        "diag.list_beacons", user.access_tier, request,
        200, int((time.monotonic() - start) * 1000),
    )
    return beacons


@router.get("/beacons/{beacon_id}/health", response_model=BeaconHealthResponse)
async def beacon_health(
    beacon_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_DIAG)),
):
    """Run health diagnostics on a beacon."""
    db = request.app.state.db
    start = time.monotonic()

    # Get beacon Nebula IP
    row = await db.fetchrow(
        "SELECT nebula_ip FROM beacons WHERE beacon_id = $1", beacon_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Beacon not found")

    cert_data = await _get_ssh_cert(request, beacon_id, "diag")
    result = await execute_on_beacon(
        beacon_ip=row["nebula_ip"],
        certificate_pem=cert_data["certificate"],
        private_key_pem=cert_data["private_key"],
        command=(
            "echo '---UPTIME---' && uptime && "
            "echo '---CPU---' && grep 'cpu ' /proc/stat && "
            "echo '---MEM---' && free -m | grep Mem && "
            "echo '---DISK---' && df -h / | tail -1 && "
            "echo '---SERVICES---' && systemctl list-units 'wopr-*' --no-pager --plain"
        ),
        username="wopr-diag",
    )

    # Parse output into structured response
    services = []
    lines = result.stdout.split("\n")
    in_services = False
    for line in lines:
        if "---SERVICES---" in line:
            in_services = True
            continue
        if in_services and line.strip():
            parts = line.split()
            if len(parts) >= 4:
                services.append(
                    ServiceStatus(
                        name=parts[0],
                        active=parts[2] == "running",
                        status=parts[2],
                    )
                )

    health = BeaconHealthResponse(
        beacon_id=beacon_id,
        status="healthy" if result.exit_code == 0 else "degraded",
        services=services,
    )

    await audit_log(
        db, user.uid, user.username, user.email,
        "diag.beacon_health", user.access_tier, request,
        200, int((time.monotonic() - start) * 1000),
        target_beacon_id=beacon_id,
    )
    return health


@router.get("/beacons/{beacon_id}/logs", response_model=BeaconLogsResponse)
async def beacon_logs(
    beacon_id: str,
    request: Request,
    service: str | None = None,
    lines: int = 100,
    since: str | None = None,
    user: SupportUser = Depends(require_tier(TIER_DIAG)),
):
    """Retrieve logs from a beacon."""
    db = request.app.state.db
    start = time.monotonic()

    if lines < 1 or lines > 1000:
        raise HTTPException(status_code=400, detail="lines must be 1-1000")

    row = await db.fetchrow(
        "SELECT nebula_ip FROM beacons WHERE beacon_id = $1", beacon_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Beacon not found")

    # Build journalctl command with safe parameters
    cmd_parts = ["journalctl", "--no-pager", f"-n {lines}"]
    if service:
        # Sanitize service name to prevent injection
        safe_service = "".join(c for c in service if c.isalnum() or c in "-_@.")
        cmd_parts.append(f"-u {safe_service}")
    if since:
        # Sanitize since parameter
        safe_since = "".join(c for c in since if c.isalnum() or c in " -:.")
        cmd_parts.append(f'--since "{safe_since}"')

    cert_data = await _get_ssh_cert(request, beacon_id, "diag")
    result = await execute_on_beacon(
        beacon_ip=row["nebula_ip"],
        certificate_pem=cert_data["certificate"],
        private_key_pem=cert_data["private_key"],
        command=" ".join(cmd_parts),
        username="wopr-diag",
    )

    log_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

    await audit_log(
        db, user.uid, user.username, user.email,
        "diag.beacon_logs", user.access_tier, request,
        200, int((time.monotonic() - start) * 1000),
        target_beacon_id=beacon_id,
        metadata={"service": service, "lines_requested": lines},
    )

    return BeaconLogsResponse(
        beacon_id=beacon_id,
        service=service,
        lines=log_lines,
        truncated=len(log_lines) >= lines,
    )


@router.get("/beacons/{beacon_id}/services")
async def beacon_services(
    beacon_id: str,
    request: Request,
    user: SupportUser = Depends(require_tier(TIER_DIAG)),
):
    """List all services running on a beacon."""
    db = request.app.state.db
    start = time.monotonic()

    row = await db.fetchrow(
        "SELECT nebula_ip FROM beacons WHERE beacon_id = $1", beacon_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Beacon not found")

    cert_data = await _get_ssh_cert(request, beacon_id, "diag")
    result = await execute_on_beacon(
        beacon_ip=row["nebula_ip"],
        certificate_pem=cert_data["certificate"],
        private_key_pem=cert_data["private_key"],
        command="systemctl list-units --type=service --state=running --no-pager --plain && echo '---DOCKER---' && docker ps --format '{{.Names}}\\t{{.Status}}' 2>/dev/null || true",
        username="wopr-diag",
    )

    await audit_log(
        db, user.uid, user.username, user.email,
        "diag.beacon_services", user.access_tier, request,
        200, int((time.monotonic() - start) * 1000),
        target_beacon_id=beacon_id,
    )

    return {"beacon_id": beacon_id, "output": result.stdout}
