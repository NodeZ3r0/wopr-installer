"""
Tests for the WOPR API endpoints
==================================

Tests FastAPI endpoints in main.py.
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check_basic(self, test_client):
        """Health endpoint returns 200 with basic info."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "providers" in data
        assert "timestamp" in data

    def test_health_check_fields(self, test_client):
        """Health check includes all expected fields."""
        response = test_client.get("/api/health")
        data = response.json()
        expected_fields = [
            "status", "timestamp", "providers",
            "stripe_configured", "webhook_configured",
            "database_connected", "email_configured",
            "dns_configured", "pdf_configured",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


class TestProvidersEndpoint:
    """Test the providers endpoint."""

    def test_list_providers(self, test_client):
        """Providers endpoint returns list."""
        response = test_client.get("/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)


class TestProvisionEndpoint:
    """Test the provision endpoint."""

    def test_provision_invalid_provider(self, test_client):
        """Provision with invalid provider returns 400."""
        response = test_client.post(
            "/api/provision",
            json={
                "bundle": "sovereign-starter",
                "tier": 1,
                "email": "test@example.com",
                "username": "testuser",
                "display_name": "Test User",
                "provider": "nonexistent",
                "region": "ash",
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_provision_invalid_email(self, test_client):
        """Provision with invalid email returns 422."""
        response = test_client.post(
            "/api/provision",
            json={
                "bundle": "sovereign-starter",
                "tier": 1,
                "email": "not-an-email",
                "username": "testuser",
                "display_name": "Test User",
                "provider": "hetzner",
                "region": "ash",
            },
        )
        assert response.status_code == 422

    def test_provision_invalid_tier(self, test_client):
        """Provision with invalid tier returns 422."""
        response = test_client.post(
            "/api/provision",
            json={
                "bundle": "sovereign-starter",
                "tier": 99,
                "email": "test@example.com",
                "username": "testuser",
                "display_name": "Test User",
                "provider": "hetzner",
                "region": "ash",
            },
        )
        assert response.status_code == 422

    def test_provision_invalid_username(self, test_client):
        """Provision with invalid username returns 422."""
        response = test_client.post(
            "/api/provision",
            json={
                "bundle": "sovereign-starter",
                "tier": 1,
                "email": "test@example.com",
                "username": "a",  # Too short
                "display_name": "Test User",
                "provider": "hetzner",
                "region": "ash",
            },
        )
        assert response.status_code == 422


class TestStatusEndpoint:
    """Test the provisioning status endpoint."""

    def test_status_not_found(self, test_client):
        """Status for nonexistent job returns 404."""
        response = test_client.get("/api/provision/nonexistent-job/status")
        assert response.status_code == 404


class TestWebhookEndpoint:
    """Test the Stripe webhook endpoint."""

    def test_webhook_no_secret(self, test_client):
        """Webhook without signature returns error."""
        response = test_client.post(
            "/api/webhook/stripe",
            content=b"{}",
            headers={"stripe-signature": "fake_sig"},
        )
        # Should fail with 400 (invalid signature) or 500 (no webhook secret)
        assert response.status_code in (400, 500)
