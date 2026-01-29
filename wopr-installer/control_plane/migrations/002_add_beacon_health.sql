-- Migration 002: Add health monitoring columns to beacons
-- =======================================================

ALTER TABLE beacons
    ADD COLUMN IF NOT EXISTS last_health_check TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_health_status VARCHAR(20) DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS idx_beacons_health ON beacons(last_health_status)
    WHERE status = 'active';
