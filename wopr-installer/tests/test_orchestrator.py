"""
Tests for the WOPR Orchestrator
================================

Tests the full provisioning state machine.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from control_plane.orchestrator import WOPROrchestrator, ProvisioningState, ProvisioningJob


class TestJobCreation:
    """Test job creation and management."""

    def test_create_job(self, orchestrator):
        """Job creation returns a valid ProvisioningJob."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )

        assert job.job_id is not None
        assert job.customer_id == "cus_test"
        assert job.customer_email == "test@example.com"
        assert job.bundle == "sovereign-starter"
        assert job.provider_id == "hetzner"
        assert job.state == ProvisioningState.PENDING

    def test_get_job(self, orchestrator):
        """Can retrieve a created job."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )

        retrieved = orchestrator.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_nonexistent_job(self, orchestrator):
        """Returns None for nonexistent job."""
        assert orchestrator.get_job("nonexistent-id") is None

    def test_create_job_with_custom_domain(self, orchestrator):
        """Job creation supports custom domain."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
            custom_domain="my.domain.com",
        )

        assert job.custom_domain == "my.domain.com"


class TestProvisioningFlow:
    """Test the provisioning state machine."""

    @pytest.mark.asyncio
    async def test_provision_vps_success(self, orchestrator):
        """VPS provisioning step succeeds with mock provider."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )

        result = await orchestrator._provision_vps(job)
        assert result is True
        assert job.instance_id is not None
        assert job.instance_ip is not None

    @pytest.mark.asyncio
    async def test_provision_vps_unknown_provider(self, orchestrator):
        """VPS provisioning fails with unknown provider."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="unknown_provider",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )

        result = await orchestrator._provision_vps(job)
        assert result is False
        assert job.state == ProvisioningState.FAILED

    @pytest.mark.asyncio
    async def test_configure_dns_success(self, orchestrator, mock_cloudflare_dns):
        """DNS configuration succeeds with mock Cloudflare."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )
        job.instance_ip = "1.2.3.4"
        job.wopr_subdomain = "test-beacon"

        result = await orchestrator._configure_dns(job)
        assert result is True
        mock_cloudflare_dns.create_a_record.assert_called()

    @pytest.mark.asyncio
    async def test_configure_dns_no_cloudflare(self, mock_providers, mock_db_pool, mock_email_service, mock_doc_generator):
        """DNS configuration gracefully handles missing Cloudflare."""
        orch = WOPROrchestrator(
            providers=mock_providers,
            db_pool=mock_db_pool,
            cloudflare_dns=None,
            email_service=mock_email_service,
            doc_generator=mock_doc_generator,
            wopr_domain="test.wopr.systems",
        )
        job = orch.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )
        job.instance_ip = "1.2.3.4"
        job.wopr_subdomain = "test-beacon"

        result = await orch._configure_dns(job)
        # Should still succeed (DNS is non-fatal)
        assert result is True


class TestCloudInit:
    """Test cloud-init generation."""

    def test_generate_cloud_init(self, orchestrator):
        """Cloud-init contains required packages and firewall rules."""
        job = orchestrator.create_job(
            customer_id="cus_test",
            customer_email="test@example.com",
            bundle="sovereign-starter",
            provider_id="hetzner",
            region="ash",
            datacenter_id="ash",
            storage_tier=1,
        )
        job.wopr_subdomain = "test-beacon"

        user_data = orchestrator._generate_cloud_init(job)

        assert "#cloud-config" in user_data
        assert "podman" in user_data
        assert "iptables" in user_data
        assert "wopr-install" in user_data or "install.sh" in user_data
        assert "test-beacon" in user_data
        # Firewall rules
        assert "iptables -A INPUT -p tcp --dport 22 -j ACCEPT" in user_data
        assert "iptables -A INPUT -p tcp --dport 443 -j ACCEPT" in user_data
        assert "iptables -A INPUT -j DROP" in user_data


class TestPlanMapping:
    """Test tier-to-plan mapping."""

    def test_plan_for_hetzner(self, orchestrator):
        assert orchestrator._get_plan_for_tier(1, "hetzner") == "cx22"
        assert orchestrator._get_plan_for_tier(2, "hetzner") == "cx32"
        assert orchestrator._get_plan_for_tier(3, "hetzner") == "cx42"

    def test_plan_for_digitalocean(self, orchestrator):
        assert orchestrator._get_plan_for_tier(1, "digitalocean") == "s-2vcpu-2gb"

    def test_plan_for_unknown_provider(self, orchestrator):
        # Falls back to hetzner plans
        plan = orchestrator._get_plan_for_tier(1, "unknown")
        assert plan == "cx22"

    def test_plan_for_unknown_tier(self, orchestrator):
        # Falls back to tier 1
        plan = orchestrator._get_plan_for_tier(99, "hetzner")
        assert plan == "cx22"
