import { randomUUID } from "crypto";

export const EventType = {
  API_REQUEST: "api_request",
  AUTH: "auth",
  DATA_ACCESS: "data_access",
  ERROR: "error",
  ADMIN_ACTION: "admin_action",
  REMEDIATION: "remediation",
  SYSTEM: "system",
};

export const Severity = {
  INFO: "info",
  WARNING: "warning",
  ERROR: "error",
  CRITICAL: "critical",
};

export function createEvent(fields) {
  return {
    id: randomUUID(),
    timestamp: new Date().toISOString(),
    service: "unknown",
    environment: "production",
    event_type: EventType.API_REQUEST,
    action: "",
    severity: Severity.INFO,
    user_uid: null,
    username: null,
    email: null,
    access_tier: null,
    request_ip: null,
    request_method: null,
    request_path: null,
    request_body_hash: null,
    response_status: null,
    duration_ms: null,
    target_resource: null,
    metadata: {},
    correlation_id: null,
    ...fields,
  };
}
