"""
WOPR Test Fixtures
==================

Shared fixtures for all test modules.
"""

import asyncio
import os
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any
from datetime import datetime


# ============================================
# EVENT LOOP
# ============================================

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================
# CONFIG
# ============================================

@pytest.fixture
def test_config():
    """Test configuration with dummy values."""
    from control_plane.config import WOPRConfig, StripeConfig, CloudflareConfig, SMTPConfig

    return WOPRConfig(
        stripe=StripeConfig(
            secret_key="sk_test_fake",
            webhook_secret="whsec_test_fake",
            price_mode="test",
        ),
        cloudflare=CloudflareConfig(
            api_token="cf_test_fake",
            zone_id="zone_test_fake",
        ),
        smtp=SMTPConfig(
            host="localhost",
            port=587,
            user="test@test.com",
            password="test_password",
        ),
        wopr_domain="test.wopr.systems",
        job_store_path="/tmp/wopr-test-jobs",
        document_output_dir="/tmp/wopr-test-docs",
    )


# ============================================
# MOCK PROVIDERS
# ============================================

class MockInstance:
    """Mock VPS instance."""
    def __init__(self, instance_id="inst-12345", ip="1.2.3.4"):
        self.id = instance_id
        self.ip_address = ip
        self.ipv6_address = "2001:db8::1"
        self.status = "running"
        self.name = "wopr-test"
        self.public_ips = [ip]


class MockProvider:
    """Mock VPS provider."""
    PROVIDER_ID = "mock"
    PROVIDER_NAME = "Mock Provider"

    def provision(self, config):
        return MockInstance()

    def get_instance(self, instance_id):
        return MockInstance(instance_id)

    def destroy(self, instance_id):
        return True

    def list_instances(self, tags=None):
        return [MockInstance()]

    def get_status(self, instance_id):
        from control_plane.providers.base import InstanceStatus
        return InstanceStatus.RUNNING


@pytest.fixture
def mock_provider():
    """A mock VPS provider."""
    return MockProvider()


@pytest.fixture
def mock_providers():
    """Dict of mock providers."""
    return {"hetzner": MockProvider(), "digitalocean": MockProvider()}


# ============================================
# MOCK SERVICES
# ============================================

@pytest.fixture
def mock_email_service():
    """Mock email service."""
    service = MagicMock()
    service.send_welcome_email = MagicMock(return_value=True)
    service.send_payment_failed = MagicMock(return_value=True)
    service.send_trial_reminder = MagicMock(return_value=True)
    service.send_subscription_cancelled = MagicMock(return_value=True)
    return service


@pytest.fixture
def mock_doc_generator():
    """Mock PDF document generator."""
    gen = MagicMock()
    gen.generate_all_documents = MagicMock(return_value={
        "welcome_card": "/tmp/test_welcome.pdf",
        "custom_domain_guide": "/tmp/test_guide.pdf",
    })
    gen.output_dir = "/tmp/wopr-test-docs"
    return gen


@pytest.fixture
def mock_cloudflare_dns():
    """Mock Cloudflare DNS service."""
    dns = AsyncMock()
    dns.create_a_record = AsyncMock(return_value="rec_12345")
    dns.delete_record = AsyncMock(return_value=True)
    dns.delete_beacon_records = AsyncMock(return_value=2)
    dns.list_records = AsyncMock(return_value=[])
    return dns


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetchval = AsyncMock(return_value=0)
    pool.close = AsyncMock()
    return pool


# ============================================
# ORCHESTRATOR
# ============================================

@pytest.fixture
def orchestrator(mock_providers, mock_db_pool, mock_cloudflare_dns, mock_email_service, mock_doc_generator):
    """Fully mocked orchestrator."""
    from control_plane.orchestrator import WOPROrchestrator

    return WOPROrchestrator(
        providers=mock_providers,
        db_pool=mock_db_pool,
        cloudflare_dns=mock_cloudflare_dns,
        email_service=mock_email_service,
        doc_generator=mock_doc_generator,
        wopr_domain="test.wopr.systems",
        job_store_path="/tmp/wopr-test-jobs",
    )


# ============================================
# STRIPE MOCKS
# ============================================

@pytest.fixture
def stripe_checkout_event():
    """Mock Stripe checkout.session.completed event."""
    return {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "customer_email": "test@example.com",
                "subscription": "sub_test_123",
                "metadata": {
                    "bundle": "sovereign-starter",
                    "tier": "1",
                    "domain": "",
                    "username": "testuser",
                    "display_name": "Test User",
                    "provider": "hetzner",
                    "region": "ash",
                },
            }
        },
    }


@pytest.fixture
def stripe_payment_failed_event():
    """Mock Stripe invoice.payment_failed event."""
    return {
        "id": "evt_test_456",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test_456",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "amount_due": 1599,
                "last_finalization_error": {
                    "message": "Card declined",
                },
            }
        },
    }


# ============================================
# FASTAPI TEST CLIENT
# ============================================

@pytest.fixture
def test_client():
    """FastAPI test client for main.py."""
    from fastapi.testclient import TestClient

    # Patch providers and services before importing app
    with patch.dict(os.environ, {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_fake",
    }):
        from main import app
        client = TestClient(app)
        yield client
