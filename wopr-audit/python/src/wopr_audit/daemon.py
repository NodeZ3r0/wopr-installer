import asyncio
from wopr_audit.schema import AuditEvent, EventType, Severity
from wopr_audit.storage.base import BaseStorage
from wopr_audit.context import get_correlation_id

_storage: BaseStorage | None = None
_service_name: str = "unknown"
_hooks: list = []


def configure(service_name: str, storage: BaseStorage, hooks: list | None = None):
    global _storage, _service_name, _hooks
    _storage = storage
    _service_name = service_name
    _hooks = hooks or []
    asyncio.run(storage.init())


async def audit_action(action: str, severity: Severity = Severity.INFO,
                       event_type: EventType = EventType.SYSTEM, **kwargs):
    if not _storage:
        return
    event = AuditEvent(
        service=_service_name,
        event_type=event_type,
        action=action,
        severity=severity,
        correlation_id=get_correlation_id(),
        **kwargs,
    )
    await _storage.store(event)
    for hook in _hooks:
        try:
            await hook.process(event)
        except Exception:
            pass


def audit_action_sync(action: str, severity: Severity = Severity.INFO,
                      event_type: EventType = EventType.SYSTEM, **kwargs):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(audit_action(action, severity, event_type, **kwargs))
        else:
            loop.run_until_complete(audit_action(action, severity, event_type, **kwargs))
    except RuntimeError:
        asyncio.run(audit_action(action, severity, event_type, **kwargs))
