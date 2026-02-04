const SEVERITY_ORDER = { info: 0, warning: 1, error: 2, critical: 3 };

export class WebhookHook {
  constructor(url, minSeverity = "warning") {
    this.url = url;
    this.minSeverity = minSeverity;
  }

  async process(event) {
    if ((SEVERITY_ORDER[event.severity] || 0) < (SEVERITY_ORDER[this.minSeverity] || 0)) {
      return;
    }
    try {
      const msg = `[${event.severity.toUpperCase()}] ${event.service}: ${event.action}`;
      await fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: event.service,
          severity: event.severity,
          action: event.action,
          message: msg,
          timestamp: event.timestamp,
          correlation_id: event.correlation_id,
        }),
      });
    } catch {
      // webhook failure should never crash the app
    }
  }
}
