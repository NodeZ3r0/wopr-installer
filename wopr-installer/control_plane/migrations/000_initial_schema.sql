-- Migration: Initial WOPR schema
-- Version: 000
-- Date: 2026-01-29
-- Description: Core tables for provisioning, beacons, users, subscriptions, trials

-- =============================================================================
-- Schema migrations tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(10) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Auto-update timestamp trigger (reusable)
-- =============================================================================

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Users
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    authentik_user_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    username VARCHAR(255),
    stripe_customer_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe ON users(stripe_customer_id);

CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- Beacons (a user's sovereign server instance)
-- =============================================================================

CREATE TYPE beacon_status AS ENUM (
    'provisioning', 'active', 'suspended', 'maintenance', 'decommissioned'
);

CREATE TYPE beacon_provider AS ENUM (
    'hetzner', 'digitalocean', 'vultr', 'linode', 'ovh', 'byo'
);

CREATE TABLE IF NOT EXISTS beacons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(63) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    custom_domain VARCHAR(255),
    status beacon_status NOT NULL DEFAULT 'provisioning',
    provider beacon_provider NOT NULL,
    region VARCHAR(50),
    datacenter_id VARCHAR(50),
    instance_id VARCHAR(255),
    instance_ip INET,
    bundle VARCHAR(50) NOT NULL,
    storage_tier INT NOT NULL DEFAULT 1 CHECK (storage_tier BETWEEN 1 AND 3),
    modules JSONB NOT NULL DEFAULT '[]',
    dns_record_ids JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    stripe_subscription_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_beacons_owner ON beacons(owner_id);
CREATE INDEX IF NOT EXISTS idx_beacons_domain ON beacons(domain);
CREATE INDEX IF NOT EXISTS idx_beacons_status ON beacons(status);
CREATE INDEX IF NOT EXISTS idx_beacons_stripe_sub ON beacons(stripe_subscription_id);

CREATE TRIGGER trigger_beacons_updated_at
    BEFORE UPDATE ON beacons
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- Provisioning Jobs
-- =============================================================================

CREATE TYPE provisioning_state AS ENUM (
    'pending', 'payment_received', 'provisioning_vps', 'waiting_for_vps',
    'configuring_dns', 'deploying_wopr', 'generating_docs',
    'sending_welcome', 'completed', 'failed'
);

CREATE TABLE IF NOT EXISTS provisioning_jobs (
    job_id UUID PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    bundle VARCHAR(50) NOT NULL,
    storage_tier INT NOT NULL DEFAULT 1,
    provider_id VARCHAR(50) NOT NULL,
    region VARCHAR(50),
    datacenter_id VARCHAR(50),
    custom_domain VARCHAR(255),
    state provisioning_state NOT NULL DEFAULT 'pending',
    instance_id VARCHAR(255),
    instance_ip INET,
    wopr_subdomain VARCHAR(255),
    root_password VARCHAR(255),
    dns_record_ids JSONB NOT NULL DEFAULT '{}',
    error_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    beacon_id UUID REFERENCES beacons(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_state ON provisioning_jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_customer ON provisioning_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_jobs_stripe_sub ON provisioning_jobs(stripe_subscription_id);

CREATE TRIGGER trigger_jobs_updated_at
    BEFORE UPDATE ON provisioning_jobs
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- Subscriptions
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    beacon_id UUID REFERENCES beacons(id),
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL,
    bundle VARCHAR(50) NOT NULL,
    storage_tier INT NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subs_stripe ON subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_subs_status ON subscriptions(status);

CREATE TRIGGER trigger_subs_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- Trials (add-on module trials)
-- =============================================================================

CREATE TABLE IF NOT EXISTS trials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    beacon_id UUID REFERENCES beacons(id),
    trial_name VARCHAR(100) NOT NULL,
    modules JSONB NOT NULL DEFAULT '[]',
    stripe_subscription_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    converted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trials_user ON trials(user_id);
CREATE INDEX IF NOT EXISTS idx_trials_status ON trials(status);
CREATE INDEX IF NOT EXISTS idx_trials_expires ON trials(expires_at);

CREATE TRIGGER trigger_trials_updated_at
    BEFORE UPDATE ON trials
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- =============================================================================
-- Payment Failures (for dunning)
-- =============================================================================

CREATE TABLE IF NOT EXISTS payment_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id VARCHAR(255) NOT NULL,
    stripe_invoice_id VARCHAR(255),
    amount_cents INT NOT NULL DEFAULT 0,
    failure_reason TEXT,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_failures_sub ON payment_failures(subscription_id);
CREATE INDEX IF NOT EXISTS idx_failures_unresolved ON payment_failures(subscription_id) WHERE resolved = false;

COMMENT ON TABLE users IS 'WOPR platform users';
COMMENT ON TABLE beacons IS 'User sovereign server instances';
COMMENT ON TABLE provisioning_jobs IS 'Provisioning workflow state tracking';
COMMENT ON TABLE subscriptions IS 'Stripe subscription records';
COMMENT ON TABLE trials IS 'Module add-on trial tracking';
COMMENT ON TABLE payment_failures IS 'Dunning: tracks failed payment attempts';
