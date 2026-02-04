import aiosqlite
from api.config import DB_PATH

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    errors_found INTEGER DEFAULT 0,
    auto_fixed INTEGER DEFAULT 0,
    escalated INTEGER DEFAULT 0,
    summary TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    analysis_run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tier TEXT NOT NULL,
    service TEXT NOT NULL,
    error_summary TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TEXT,
    resolved_by TEXT,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id)
);

CREATE TABLE IF NOT EXISTS auto_actions_log (
    id TEXT PRIMARY KEY,
    analysis_run_id TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    service TEXT NOT NULL,
    action TEXT NOT NULL,
    success INTEGER NOT NULL,
    output TEXT DEFAULT '',
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON analysis_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_auto_actions_time ON auto_actions_log(executed_at);
"""

_db = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(CREATE_TABLES)
        await _db.commit()
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
