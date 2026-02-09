"""WOPR Support Gateway - FastAPI application.

WOPR_MODE environment variable controls which routes are exposed:
- lighthouse: Full admin dashboard + all API routes (default for nodez3r0)
- beacon: Customer-facing support client only (no admin dashboard)
"""

import asyncio
import logging
import os

import asyncpg

# Determine mode: lighthouse (staff admin) or beacon (customer client)
WOPR_MODE = os.environ.get("WOPR_MODE", "lighthouse")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.audit import AuditMiddleware
from api.config import SupportGatewayConfig
from api.routes import ai, audit, beacons, breakglass, diagnostics, remediation

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="WOPR Support Gateway",
    description="Zero-trust support access for WOPR beacons",
    version="1.0.0",
    docs_url=None,  # Disable Swagger UI in production
    redoc_url=None,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditMiddleware)

# CORS — must be added at module level (before app startup)
_config = SupportGatewayConfig.from_env()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_config.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
    )


@app.on_event("startup")
async def startup():
    config = SupportGatewayConfig.from_env()
    app.state.config = config

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Database pool
    app.state.db = await asyncpg.create_pool(
        config.database_url,
        min_size=2,
        max_size=10,
    )
    logger.info("Database pool created")

    # Start background task for expiring breakglass sessions
    app.state._expire_task = asyncio.create_task(_expire_breakglass_sessions())
    logger.info("Support Gateway started on %s:%d", config.host, config.port)


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "_expire_task"):
        app.state._expire_task.cancel()
    if hasattr(app.state, "db"):
        await app.state.db.close()
    logger.info("Support Gateway shut down")


async def _expire_breakglass_sessions():
    """Background task: auto-expire breakglass sessions past their deadline."""
    while True:
        try:
            await asyncio.sleep(60)
            if not hasattr(app.state, "db"):
                continue
            result = await app.state.db.execute(
                """
                UPDATE breakglass_sessions
                SET status = 'expired', ended_at = now()
                WHERE status = 'active' AND expires_at < now()
                """
            )
            # result is like "UPDATE N"
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                logger.warning("Auto-expired %d breakglass session(s)", count)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error expiring breakglass sessions: %s", e)


# Include routers
app.include_router(diagnostics.router)
app.include_router(remediation.router)
app.include_router(breakglass.router)
app.include_router(audit.router)
app.include_router(ai.router)
app.include_router(beacons.router)  # Multi-beacon registry

# Admin dashboard only on lighthouse (WOPR staff)
# Beacons get support-client routes only
if WOPR_MODE == "lighthouse":
    app.include_router(ai.dashboard_router)  # HTML dashboard at / and /escalations
    logger.info("WOPR_MODE=lighthouse: Admin dashboard enabled")
else:
    logger.info("WOPR_MODE=beacon: Admin dashboard disabled (customer mode)")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    db_ok = False
    try:
        await app.state.db.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "support-gateway",
        "database": "connected" if db_ok else "disconnected",
    }
