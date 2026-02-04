import time
import hashlib
from uuid import uuid4
import asyncio
from wopr_audit.schema import AuditEvent, EventType, Severity
from wopr_audit.storage.base import BaseStorage
from wopr_audit.context import set_correlation_id


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


def init_flask_audit(app, *, service_name: str, storage: BaseStorage,
                     hooks=None, skip_paths=None):
    from flask import request, g

    _skip = set(skip_paths or ["/health", "/healthz", "/favicon.ico"])
    _hooks = hooks or []

    @app.before_request
    def _audit_before():
        if request.path in _skip:
            return
        g._audit_start = time.monotonic()
        g._audit_correlation = request.headers.get("X-Correlation-ID", str(uuid4()))
        set_correlation_id(g._audit_correlation)

    @app.after_request
    def _audit_after(response):
        if request.path in _skip or not hasattr(g, "_audit_start"):
            return response

        duration_ms = int((time.monotonic() - g._audit_start) * 1000)
        severity = Severity.INFO
        if response.status_code >= 500:
            severity = Severity.ERROR
        elif response.status_code >= 400:
            severity = Severity.WARNING

        body_hash = None
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.data:
            body_hash = hashlib.sha256(request.data).hexdigest()

        event = AuditEvent(
            service=service_name,
            event_type=EventType.API_REQUEST,
            action=f"{request.method} {request.path}",
            severity=severity,
            request_ip=request.remote_addr,
            request_method=request.method,
            request_path=request.path,
            request_body_hash=body_hash,
            response_status=response.status_code,
            duration_ms=duration_ms,
            correlation_id=g._audit_correlation,
        )

        try:
            _run_async(storage.store(event))
            for hook in _hooks:
                _run_async(hook.process(event))
        except Exception:
            pass

        return response

    # Initialize storage
    _run_async(storage.init())
