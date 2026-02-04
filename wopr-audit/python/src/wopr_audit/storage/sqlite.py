import json
from pathlib import Path
from wopr_audit.schema import AuditEvent
from wopr_audit.storage.base import BaseStorage

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
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
    metadata TEXT DEFAULT '{}',
    correlation_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_service ON audit_log (service);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log (severity);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log (event_type);
"""

INSERT_SQL = """
INSERT INTO audit_log (id, timestamp, service, environment, event_type, action,
    severity, user_uid, username, email, access_tier, request_ip, request_method,
    request_path, request_body_hash, response_status, duration_ms, target_resource,
    metadata, correlation_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._db = None

    async def init(self) -> None:
        import aiosqlite
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(CREATE_TABLE)
        await self._db.commit()

    async def store(self, event: AuditEvent) -> None:
        if not self._db:
            await self.init()
        await self._db.execute(INSERT_SQL, (
            event.id, event.timestamp.isoformat(), event.service, event.environment,
            event.event_type.value, event.action, event.severity.value,
            event.user_uid, event.username, event.email, event.access_tier,
            event.request_ip, event.request_method, event.request_path,
            event.request_body_hash, event.response_status, event.duration_ms,
            event.target_resource, json.dumps(event.metadata), event.correlation_id,
        ))
        await self._db.commit()

    async def query(self, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        if not self._db:
            await self.init()
        where_parts = []
        params = []
        if filters:
            for key, val in filters.items():
                if key in ("service", "event_type", "severity", "user_uid", "correlation_id"):
                    where_parts.append(f"{key} = ?")
                    params.append(val)
        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
        sql = f"SELECT * FROM audit_log{where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = await self._db.execute(sql, params)
        results = []
        async for row in rows:
            data = dict(zip([d[0] for d in rows.description], row))
            data["metadata"] = json.loads(data.get("metadata", "{}"))
            results.append(AuditEvent(**data))
        return results

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
