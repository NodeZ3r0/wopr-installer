-- WOPR Support Plane - Initial Schema
-- Migration: 001_initial_schema.sql

BEGIN;

-- Known beacons on the Nebula mesh
CREATE TABLE IF NOT EXISTS beacons (
    beacon_id       TEXT PRIMARY KEY,
    nebula_ip       INET NOT NULL,
    hostname        TEXT,
    status          TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN ('healthy', 'degraded', 'offline', 'unknown')),
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_beacons_status ON beacons (status);

-- Audit log: every action through the support gateway
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_uid        TEXT NOT NULL,
    username        TEXT,
    email           TEXT,
    action          TEXT NOT NULL,
    target_beacon_id TEXT,
    access_tier     TEXT NOT NULL CHECK (access_tier IN ('diag', 'remediate', 'breakglass')),
    request_ip      INET,
    request_method  TEXT,
    request_path    TEXT,
    request_body_hash TEXT,
    response_status INTEGER,
    duration_ms     INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_audit_log_timestamp ON audit_log (timestamp);
CREATE INDEX idx_audit_log_user_uid ON audit_log (user_uid);
CREATE INDEX idx_audit_log_beacon ON audit_log (target_beacon_id);
CREATE INDEX idx_audit_log_tier ON audit_log (access_tier);

-- Breakglass sessions: emergency full-access tracking
CREATE TABLE IF NOT EXISTS breakglass_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_uid        TEXT NOT NULL,
    username        TEXT,
    email           TEXT,
    target_beacon_id TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    reason          TEXT NOT NULL CHECK (char_length(reason) >= 20),
    ssh_cert_serial TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'revoked')),
    revoked_by      TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT breakglass_expiry_check CHECK (expires_at > started_at)
);

CREATE INDEX idx_breakglass_status ON breakglass_sessions (status);
CREATE INDEX idx_breakglass_user ON breakglass_sessions (user_uid);
CREATE INDEX idx_breakglass_beacon ON breakglass_sessions (target_beacon_id);

-- Remediation actions: registry of pre-approved commands
CREATE TABLE IF NOT EXISTS remediation_actions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    command_template TEXT NOT NULL,
    required_tier   TEXT NOT NULL DEFAULT 'remediate' CHECK (required_tier IN ('remediate', 'breakglass')),
    is_enabled      BOOLEAN NOT NULL DEFAULT true,
    risk_level      TEXT NOT NULL DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
