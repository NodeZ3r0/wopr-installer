import time
import hashlib
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from wopr_audit.schema import AuditEvent, EventType, Severity
from wopr_audit.storage.base import BaseStorage
from wopr_audit.context import set_correlation_id


def _default_authentik_extractor(request):
    return {
        "uid": request.headers.get("X-Authentik-Uid"),
        "username": request.headers.get("X-Authentik-Username"),
        "email": request.headers.get("X-Authentik-Email"),
        "access_tier": request.headers.get("X-Authentik-Groups"),
    }


class WOPRAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service_name: str, storage: BaseStorage,
                 user_extractor=None, hooks=None, skip_paths=None):
        super().__init__(app)
        self.service_name = service_name
        self.storage = storage
        self.user_extractor = user_extractor or _default_authentik_extractor
        self.hooks = hooks or []
        self.skip_paths = set(skip_paths or ["/health", "/healthz", "/favicon.ico"])

    async def dispatch(self, request, call_next):
        if request.url.path in self.skip_paths:
            return await call_next(request)

        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        set_correlation_id(correlation_id)

        body_hash = None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body = await request.body()
                request.state._body_cache = body
                if body:
                    body_hash = hashlib.sha256(body).hexdigest()
            except Exception:
                request.state._body_cache = b""

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        user = self.user_extractor(request)
        severity = Severity.INFO
        if response.status_code >= 500:
            severity = Severity.ERROR
        elif response.status_code >= 400:
            severity = Severity.WARNING

        event = AuditEvent(
            service=self.service_name,
            event_type=EventType.API_REQUEST,
            action=f"{request.method} {request.url.path}",
            severity=severity,
            user_uid=user.get("uid"),
            username=user.get("username"),
            email=user.get("email"),
            access_tier=user.get("access_tier"),
            request_ip=request.headers.get("X-Forwarded-For", request.client.host if request.client else None),
            request_method=request.method,
            request_path=str(request.url.path),
            request_body_hash=body_hash,
            response_status=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

        try:
            await self.storage.store(event)
        except Exception:
            pass  # audit should never crash the app

        for hook in self.hooks:
            try:
                await hook.process(event)
            except Exception:
                pass

        return response
