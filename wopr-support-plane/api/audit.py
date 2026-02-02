"""Audit logging middleware and helpers."""

import hashlib
import time

import asyncpg
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


async def audit_log(
    db: asyncpg.Pool,
    user_uid: str,
    username: str,
    email: str,
    action: str,
    access_tier: str,
    request: Request,
    response_status: int,
    duration_ms: int,
    target_beacon_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert an audit log entry."""
    body_bytes = getattr(request.state, "_body_cache", b"")
    body_hash = hashlib.sha256(body_bytes).hexdigest() if body_bytes else None

    client_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else None
    )

    await db.execute(
        """
        INSERT INTO audit_log
            (user_uid, username, email, action, target_beacon_id, access_tier,
             request_ip, request_method, request_path, request_body_hash,
             response_status, duration_ms, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        user_uid,
        username,
        email,
        action,
        target_beacon_id,
        access_tier,
        client_ip,
        request.method,
        str(request.url.path),
        body_hash,
        response_status,
        duration_ms,
        metadata or {},
    )


class AuditMiddleware(BaseHTTPMiddleware):
    """Captures request body and timing for audit logging."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Cache request body for hashing (only for mutation methods)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            body = await request.body()
            request.state._body_cache = body
        else:
            request.state._body_cache = b""

        request.state._start_time = time.monotonic()
        response = await call_next(request)
        request.state._duration_ms = int(
            (time.monotonic() - request.state._start_time) * 1000
        )

        return response
