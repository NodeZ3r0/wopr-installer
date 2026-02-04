from wopr_audit.schema import AuditEvent, Severity


class WebhookHook:
    def __init__(self, url: str, min_severity: Severity = Severity.WARNING):
        self.url = url
        self.min_severity = min_severity
        self._severity_order = {
            Severity.INFO: 0, Severity.WARNING: 1,
            Severity.ERROR: 2, Severity.CRITICAL: 3,
        }

    async def process(self, event: AuditEvent) -> None:
        if self._severity_order.get(event.severity, 0) < self._severity_order.get(self.min_severity, 0):
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.url, json={
                    "service": event.service,
                    "severity": event.severity.value,
                    "action": event.action,
                    "message": f"[{event.severity.value.upper()}] {event.service}: {event.action}",
                    "timestamp": event.timestamp.isoformat(),
                    "correlation_id": event.correlation_id,
                    "metadata": event.metadata,
                })
        except Exception:
            pass  # webhook failure should never crash the app
