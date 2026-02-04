const CREATE_TABLE = `
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
`;

const INSERT_SQL = `
INSERT INTO audit_log (id, timestamp, service, environment, event_type, action,
    severity, user_uid, username, email, access_tier, request_ip, request_method,
    request_path, request_body_hash, response_status, duration_ms, target_resource,
    metadata, correlation_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`;

export class SQLiteStorage {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.db = null;
  }

  init() {
    const Database = require("better-sqlite3");
    this.db = new Database(this.dbPath);
    this.db.pragma("journal_mode = WAL");
    this.db.exec(CREATE_TABLE);
    this._insertStmt = this.db.prepare(INSERT_SQL);
  }

  store(event) {
    if (!this.db) this.init();
    this._insertStmt.run(
      event.id, event.timestamp, event.service, event.environment,
      event.event_type, event.action, event.severity,
      event.user_uid, event.username, event.email, event.access_tier,
      event.request_ip, event.request_method, event.request_path,
      event.request_body_hash, event.response_status, event.duration_ms,
      event.target_resource, JSON.stringify(event.metadata), event.correlation_id
    );
  }

  query(filters = {}, limit = 100, offset = 0) {
    if (!this.db) this.init();
    const whereParts = [];
    const params = [];
    for (const [key, val] of Object.entries(filters)) {
      if (["service", "event_type", "severity", "user_uid", "correlation_id"].includes(key)) {
        whereParts.push(`${key} = ?`);
        params.push(val);
      }
    }
    const where = whereParts.length ? " WHERE " + whereParts.join(" AND ") : "";
    const sql = `SELECT * FROM audit_log${where} ORDER BY timestamp DESC LIMIT ? OFFSET ?`;
    params.push(limit, offset);
    const rows = this.db.prepare(sql).all(...params);
    return rows.map((r) => ({ ...r, metadata: JSON.parse(r.metadata || "{}") }));
  }

  close() {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }
}
