-- 005: Custom domains table for beacon custom domain configurations
CREATE TABLE IF NOT EXISTS custom_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    beacon_id UUID NOT NULL REFERENCES beacons(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    expected_ip INET NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    ssl_issued_at TIMESTAMPTZ,
    ssl_expires_at TIMESTAMPTZ,
    last_check_at TIMESTAMPTZ,
    error_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_domains_beacon ON custom_domains(beacon_id);
CREATE INDEX IF NOT EXISTS idx_custom_domains_status ON custom_domains(status);
CREATE INDEX IF NOT EXISTS idx_custom_domains_domain ON custom_domains(domain);

-- Drop and recreate trigger to handle re-runs
DROP TRIGGER IF EXISTS trigger_custom_domains_updated_at ON custom_domains;
CREATE TRIGGER trigger_custom_domains_updated_at
    BEFORE UPDATE ON custom_domains
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

COMMENT ON TABLE custom_domains IS 'Custom domain configurations for beacons';
