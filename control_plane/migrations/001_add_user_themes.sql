-- Migration: Add user themes table for Beacon personalization
-- Version: 001
-- Date: 2026-01-24
-- Description: Stores theme preferences per-user for dashboard and per-app theming

-- User theme preferences table
CREATE TABLE IF NOT EXISTS user_themes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- User identity (from Authentik)
    user_id VARCHAR(255) NOT NULL UNIQUE,

    -- Global dashboard theme
    preset VARCHAR(50) NOT NULL DEFAULT 'reactor',

    -- Custom color overrides (JSON object)
    -- Example: {"--theme-primary": "#ff0000", "--theme-accent": "#00ff00"}
    custom_colors JSONB NOT NULL DEFAULT '{}',

    -- Per-app theme overrides
    -- Example: {"nextcloud": {"preset": "midnight"}, "ghost": {"preset": "solaris"}}
    app_overrides JSONB NOT NULL DEFAULT '{}',

    -- Which apps have theme injection enabled (opt-in for third-party apps)
    -- WOPR-native apps (defcon, brainjoos, rag) are always themed
    -- Example: ["defcon", "brainjoos", "rag", "nextcloud"]
    themed_apps JSONB NOT NULL DEFAULT '["defcon", "brainjoos", "rag"]',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_user_themes_user_id ON user_themes(user_id);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_themes_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_themes_updated_at
    BEFORE UPDATE ON user_themes
    FOR EACH ROW
    EXECUTE FUNCTION update_user_themes_timestamp();

-- Insert default theme for existing users (optional, can be run separately)
-- INSERT INTO user_themes (user_id, preset)
-- SELECT DISTINCT user_id FROM some_existing_users_table
-- ON CONFLICT (user_id) DO NOTHING;

COMMENT ON TABLE user_themes IS 'Stores user theme preferences for Beacon dashboard personalization';
COMMENT ON COLUMN user_themes.preset IS 'Theme preset ID: reactor, midnight, solaris, arctic, terminal, ember';
COMMENT ON COLUMN user_themes.custom_colors IS 'Custom CSS variable overrides as JSON object';
COMMENT ON COLUMN user_themes.app_overrides IS 'Per-app theme overrides as JSON object keyed by app_id';
COMMENT ON COLUMN user_themes.themed_apps IS 'List of app IDs that receive theme CSS injection';
