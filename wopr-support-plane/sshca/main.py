"""WOPR SSH Certificate Authority - FastAPI application."""

import logging
from pathlib import Path

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from sshca.config import SSHCAConfig
from sshca.signer import generate_keypair, sign_user_key

logger = logging.getLogger(__name__)

app = FastAPI(
    title="WOPR SSH Certificate Authority",
    description="Issues short-lived SSH certificates for support access",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# Auth group constants (same as gateway)
GROUP_DIAG = "wopr-support-diag"
GROUP_REMEDIATE = "wopr-support-remediate"
GROUP_BREAKGLASS = "wopr-support-breakglass"

TIER_GROUPS = {
    "diag": GROUP_DIAG,
    "remediate": GROUP_REMEDIATE,
    "breakglass": GROUP_BREAKGLASS,
}


class SignRequest(BaseModel):
    beacon_id: str
    tier: str  # "diag", "remediate", "breakglass"
    public_key: str | None = None  # If None, we generate an ephemeral keypair
    breakglass_session_id: str | None = None


class SignResponse(BaseModel):
    certificate: str
    private_key: str | None = None  # Only if we generated the keypair
    serial: str
    valid_seconds: int
    principals: list[str]


@app.on_event("startup")
async def startup():
    config = SSHCAConfig.from_env()
    app.state.config = config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Validate CA key exists
    if not Path(config.ca_private_key_path).exists():
        logger.error("CA private key not found: %s", config.ca_private_key_path)
        raise RuntimeError(f"CA key missing: {config.ca_private_key_path}")

    # Database pool (for breakglass session validation)
    app.state.db = await asyncpg.create_pool(
        config.database_url,
        min_size=1,
        max_size=5,
    )

    logger.info("SSH CA started on %s:%d", config.host, config.port)


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "db"):
        await app.state.db.close()


def _validate_auth_headers(request: Request) -> tuple[str, str, str, list[str]]:
    """Validate Authentik headers from Caddy."""
    uid = request.headers.get("X-Authentik-UID", "")
    username = request.headers.get("X-Authentik-Username", "")
    email = request.headers.get("X-Authentik-Email", "")
    groups_raw = request.headers.get("X-Authentik-Groups", "")

    if not uid:
        raise HTTPException(status_code=401, detail="Missing authentication")

    groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
    return uid, username, email, groups


@app.post("/api/v1/sign", response_model=SignResponse)
async def sign_certificate(body: SignRequest, request: Request):
    """Sign an SSH public key for support access to a beacon."""
    uid, username, email, groups = _validate_auth_headers(request)
    config = app.state.config
    db = app.state.db

    # Validate tier
    if body.tier not in ("diag", "remediate", "breakglass"):
        raise HTTPException(status_code=400, detail="Invalid tier")

    # Check user has the required group for requested tier
    required_group = TIER_GROUPS[body.tier]
    if required_group not in groups:
        raise HTTPException(
            status_code=403,
            detail=f"User lacks {required_group} group for {body.tier} tier",
        )

    # For breakglass, validate the session exists and is active
    if body.tier == "breakglass":
        if not body.breakglass_session_id:
            raise HTTPException(
                status_code=400,
                detail="breakglass_session_id required for breakglass tier",
            )
        session = await db.fetchrow(
            "SELECT status FROM breakglass_sessions WHERE id = $1::uuid AND status = 'active'",
            body.breakglass_session_id,
        )
        if not session:
            raise HTTPException(
                status_code=403,
                detail="No active breakglass session found",
            )

    # Determine certificate parameters based on tier
    if body.tier == "diag":
        validity = config.cert_validity_diag
        principals = config.allowed_principals_diag
        force_command = config.force_command_diag
    elif body.tier == "remediate":
        validity = config.cert_validity_remediate
        principals = config.allowed_principals_remediate
        force_command = config.force_command_remediate
    else:  # breakglass
        validity = config.cert_validity_breakglass
        principals = config.allowed_principals_breakglass
        force_command = config.force_command_breakglass

    # Generate ephemeral keypair if no public key provided
    private_key = None
    import tempfile

    if body.public_key:
        pubkey = body.public_key
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            private_key, pubkey = await generate_keypair(tmpdir)

    # Build identity string for audit trail
    identity = f"wopr-support-{username}-{body.beacon_id}-{body.tier}"

    # Sign the certificate
    certificate, serial = await sign_user_key(
        ca_key_path=config.ca_private_key_path,
        user_pubkey=pubkey,
        identity=identity,
        principals=principals,
        validity_seconds=validity,
        force_command=force_command,
    )

    logger.info(
        "Certificate issued: user=%s tier=%s beacon=%s serial=%d validity=%ds",
        username, body.tier, body.beacon_id, serial, validity,
    )

    return SignResponse(
        certificate=certificate,
        private_key=private_key,
        serial=str(serial),
        valid_seconds=validity,
        principals=principals,
    )


@app.get("/api/v1/ca-public-key")
async def get_ca_public_key():
    """Return the CA public key. Beacons need this for TrustedUserCAKeys."""
    config = app.state.config
    pubkey_path = Path(config.ca_public_key_path)
    if not pubkey_path.exists():
        raise HTTPException(status_code=500, detail="CA public key not found")
    return {"public_key": pubkey_path.read_text().strip()}


@app.get("/api/health")
async def health():
    """Health check."""
    config = app.state.config
    ca_ok = Path(config.ca_private_key_path).exists()
    db_ok = False
    try:
        await app.state.db.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if (ca_ok and db_ok) else "degraded",
        "service": "sshca",
        "ca_key": "present" if ca_ok else "missing",
        "database": "connected" if db_ok else "disconnected",
    }
