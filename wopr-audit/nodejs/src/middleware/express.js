import { randomUUID, createHash } from "crypto";
import { createEvent, EventType, Severity } from "../schema.js";

export function woprAudit(opts) {
  const {
    serviceName,
    storage,
    userExtractor,
    hooks = [],
    skipPaths = new Set(["/health", "/healthz", "/favicon.ico"]),
    redactPaths = [],
  } = opts;

  const defaultUserExtractor = (req) => ({
    uid: req.headers["x-authentik-uid"] || null,
    username: req.headers["x-authentik-username"] || null,
    email: req.headers["x-authentik-email"] || null,
    access_tier: req.headers["x-authentik-groups"] || null,
  });

  const extractUser = userExtractor || defaultUserExtractor;

  return (req, res, next) => {
    if (skipPaths.has(req.path)) return next();

    const start = process.hrtime.bigint();
    const correlationId = req.headers["x-correlation-id"] || randomUUID();

    res.on("finish", () => {
      const durationMs = Number((process.hrtime.bigint() - start) / 1_000_000n);
      const user = extractUser(req);

      let bodyHash = null;
      if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method) && req.body) {
        const isRedacted = redactPaths.some((p) => req.path.startsWith(p));
        if (!isRedacted) {
          const bodyStr = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
          bodyHash = createHash("sha256").update(bodyStr).digest("hex");
        }
      }

      let severity = Severity.INFO;
      if (res.statusCode >= 500) severity = Severity.ERROR;
      else if (res.statusCode >= 400) severity = Severity.WARNING;

      const event = createEvent({
        service: serviceName,
        event_type: EventType.API_REQUEST,
        action: `${req.method} ${req.path}`,
        severity,
        user_uid: user.uid,
        username: user.username,
        email: user.email,
        access_tier: user.access_tier,
        request_ip: req.headers["x-forwarded-for"] || req.ip,
        request_method: req.method,
        request_path: req.path,
        request_body_hash: bodyHash,
        response_status: res.statusCode,
        duration_ms: durationMs,
        correlation_id: correlationId,
      });

      try {
        storage.store(event);
      } catch {
        // audit should never crash the app
      }

      for (const hook of hooks) {
        try {
          hook.process(event);
        } catch {
          // hook failure should never crash the app
        }
      }
    });

    next();
  };
}
