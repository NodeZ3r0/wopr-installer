import json
from wopr_audit.schema import AuditEvent
from wopr_audit.storage.base import BaseStorage

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    service TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production',
    event_type TEXT NOT NULL,
    action TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    user_uid TEXT,
    username TEXT,
    email TEXT,
    access_tier TEXT,
    request_ip TEXT,
    request_method TEXT,
    request_path TEXT,
    request_body_hash TEXT,
    response_status INTEGER,
    duration_ms INTEGER,
    target_resource TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    correlation_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_service ON audit_log (service);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log (severity);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_log (correlation_id);
"""


class PostgresStorage(BaseStorage):
    def __init__(self, pool):
        """Takes an existing asyncpg.Pool instance."""
        self._pool = pool
        self._initialized = False

    async def init(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLE)
        self._initialized = True

    async def store(self, event: AuditEvent) -> None:
        if not self._initialized:
            await self.init()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_log (id, timestamp, service, environment, event_type,
                   action, severity, user_uid, username, email, access_tier, request_ip,
                   request_method, request_path, request_body_hash, response_status,
                   duration_ms, target_resource, metadata, correlation_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)""",
                event.id, event.timestamp, event.service, event.environment,
                event.event_type.value, event.action, event.severity.value,
                event.user_uid, event.username, event.email, event.access_tier,
                event.request_ip, event.request_method, event.request_path,
                event.request_body_hash, event.response_status, event.duration_ms,
                event.target_resource, json.dumps(event.metadata), event.correlation_id,
            )

    async def query(self, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        where_parts = []
        params = []
        idx = 1
        if filters:
            for key, val in filters.items():
                if key in ("service", "event_type", "severity", "user_uid", "correlation_id"):
                    where_parts.append(f"{key} = ${idx}")
                    params.append(val)
                    idx += 1
        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM audit_log{where_clause} ORDER BY timestamp DESC LIMIT ${idx} OFFSET ${idx+1}"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        results = []
        for row in rows:
            data = dict(row)
            if isinstance(data.get("metadata"), str):
                data["metadata"] = json.loads(data["metadata"])
            results.append(AuditEvent(**data))
        return results

    async def close(self) -> None:
        pass  # Pool lifecycle managed externally
