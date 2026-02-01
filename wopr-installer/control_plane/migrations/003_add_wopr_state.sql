-- 003: Key-value state table for orchestrator (round-robin counter, etc.)
CREATE TABLE IF NOT EXISTS wopr_state (
    key   VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the round-robin counter
INSERT INTO wopr_state (key, value) VALUES ('rr_counter', '0')
ON CONFLICT (key) DO NOTHING;
