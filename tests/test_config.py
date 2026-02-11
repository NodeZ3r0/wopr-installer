"""
Tests for WOPR Configuration
==============================

Tests centralized config loading.
"""

import os
import pytest
from unittest.mock import patch
from control_plane.config import WOPRConfig, StripeConfig, CloudflareConfig, ProviderTokens


class TestWOPRConfig:
    """Test config loading."""

    def test_defaults(self):
        """Default config has sensible values."""
        config = WOPRConfig()
        assert config.wopr_domain == "wopr.systems"
        assert config.log_level == "INFO"
        assert config.log_format == "json"

    def test_from_env(self):
        """Config loads from environment variables."""
        env = {
            "STRIPE_SECRET_KEY": "sk_test_123",
            "CLOUDFLARE_API_TOKEN": "cf_token",
            "CLOUDFLARE_ZONE_ID": "zone_123",
            "HETZNER_API_TOKEN": "hetzner_token",
            "WOPR_DOMAIN": "custom.domain",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=False):
            config = WOPRConfig.from_env()
            assert config.stripe.secret_key == "sk_test_123"
            assert config.cloudflare.api_token == "cf_token"
            assert config.cloudflare.zone_id == "zone_123"
            assert config.providers.hetzner == "hetzner_token"
            assert config.wopr_domain == "custom.domain"
            assert config.log_level == "DEBUG"

    def test_cors_origins_from_env(self):
        """CORS origins parsed from comma-separated string."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://a.com,https://b.com"}):
            config = WOPRConfig.from_env()
            assert "https://a.com" in config.cors_origins
            assert "https://b.com" in config.cors_origins


class TestProviderTokens:
    """Test provider token detection."""

    def test_available_providers_none(self):
        """No tokens = no providers."""
        tokens = ProviderTokens()
        assert tokens.available_providers() == []

    def test_available_providers_hetzner(self):
        """Hetzner token detected."""
        tokens = ProviderTokens(hetzner="token123")
        providers = tokens.available_providers()
        assert "hetzner" in providers
        assert len(providers) == 1

    def test_available_providers_multiple(self):
        """Multiple tokens detected."""
        tokens = ProviderTokens(
            hetzner="h_token",
            digitalocean="do_token",
            vultr="v_token",
        )
        providers = tokens.available_providers()
        assert len(providers) == 3
        assert "hetzner" in providers
        assert "digitalocean" in providers
        assert "vultr" in providers


class TestCloudflareConfig:
    """Test Cloudflare config validation."""

    def test_not_configured(self):
        """Empty config reports not configured."""
        cf = CloudflareConfig()
        assert cf.is_configured is False

    def test_configured(self):
        """Full config reports configured."""
        cf = CloudflareConfig(api_token="token", zone_id="zone")
        assert cf.is_configured is True

    def test_partial_not_configured(self):
        """Partial config reports not configured."""
        cf = CloudflareConfig(api_token="token")
        assert cf.is_configured is False
