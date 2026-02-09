-- WOPR Support Plane - Initial Schema
-- Run this on first deployment

-- Breakglass sessions
CREATE TABLE IF NOT EXISTS breakglass_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    beacon_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    ended_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_breakglass_status ON breakglass_sessions(status);
CREATE INDEX IF NOT EXISTS idx_breakglass_beacon ON breakglass_sessions(beacon_id);
CREATE INDEX IF NOT EXISTS idx_breakglass_user ON breakglass_sessions(user_id);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id TEXT,
    username TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    details JSONB,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

-- Beacon registry (multi-beacon support)
CREATE TABLE IF NOT EXISTS beacons (
    beacon_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    ai_engine_url TEXT NOT NULL,
    public_ip TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'online'
);

CREATE INDEX IF NOT EXISTS idx_beacons_status ON beacons(status);
CREATE INDEX IF NOT EXISTS idx_beacons_domain ON beacons(domain);
