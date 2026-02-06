-- Migration 004: Add per-beacon Stripe mode
-- Allows each beacon to independently use test or live Stripe mode

ALTER TABLE beacons ADD COLUMN IF NOT EXISTS stripe_mode VARCHAR(10) DEFAULT 'test';

-- Add constraint to ensure valid values
ALTER TABLE beacons ADD CONSTRAINT valid_stripe_mode
    CHECK (stripe_mode IN ('test', 'live'));

-- Index for querying beacons by stripe mode (useful for admin)
CREATE INDEX IF NOT EXISTS idx_beacons_stripe_mode ON beacons(stripe_mode);

COMMENT ON COLUMN beacons.stripe_mode IS 'Per-beacon Stripe mode: test or live';
