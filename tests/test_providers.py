"""
Tests for WOPR VPS Providers
==============================

Tests provider interface compliance and plan mapping.
"""

import pytest
from control_plane.providers.base import (
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Region,
    Instance,
    InstanceStatus,
    ProvisionConfig,
)


class TestProvisionConfig:
    """Test ProvisionConfig dataclass."""

    def test_default_tags(self):
        """Default tags are applied."""
        config = ProvisionConfig(
            name="test-server",
            region="ash",
            plan_id="cx22",
            ssh_keys=[],
        )
        assert "wopr" in config.tags
        assert "sovereign-suite" in config.tags

    def test_bundle_tag(self):
        """Bundle tag is added."""
        config = ProvisionConfig(
            name="test-server",
            region="ash",
            plan_id="cx22",
            ssh_keys=[],
            wopr_bundle="sovereign-starter",
        )
        assert "bundle:sovereign-starter" in config.tags

    def test_default_image(self):
        """Default image is debian-12."""
        config = ProvisionConfig(
            name="test-server",
            region="ash",
            plan_id="cx22",
            ssh_keys=[],
        )
        assert config.image == "debian-12"


class TestResourceTier:
    """Test ResourceTier enum."""

    def test_low_tier_requirements(self):
        assert ResourceTier.LOW.min_cpu == 2
        assert ResourceTier.LOW.min_ram_gb == 4
        assert ResourceTier.LOW.min_disk_gb == 40

    def test_high_tier_requirements(self):
        assert ResourceTier.HIGH.min_cpu == 8
        assert ResourceTier.HIGH.min_ram_gb == 16
        assert ResourceTier.HIGH.min_disk_gb == 200


class TestPlan:
    """Test Plan dataclass."""

    def test_meets_tier(self):
        """Plan correctly checks tier compliance."""
        plan = Plan(
            id="cx32",
            name="CX32",
            cpu=4,
            ram_gb=8,
            disk_gb=80,
        )
        assert plan.meets_tier(ResourceTier.LOW) is True
        assert plan.meets_tier(ResourceTier.MEDIUM) is True
        assert plan.meets_tier(ResourceTier.HIGH) is False

    def test_plan_str(self):
        """Plan string representation."""
        plan = Plan(
            id="cx22",
            name="CX22",
            cpu=2,
            ram_gb=4,
            disk_gb=40,
            price_monthly_usd=4.17,
        )
        s = str(plan)
        assert "CX22" in s
        assert "4.17" in s


class TestInstanceStatus:
    """Test instance status values."""

    def test_all_statuses_exist(self):
        """All expected statuses are defined."""
        expected = ["pending", "provisioning", "running", "stopped", "rebooting", "error", "unknown"]
        for status_name in expected:
            assert hasattr(InstanceStatus, status_name.upper())


class TestMockProvider:
    """Test mock provider for interface compliance."""

    def test_mock_provision(self, mock_provider):
        """Mock provider provisions and returns instance."""
        config = ProvisionConfig(
            name="test",
            region="ash",
            plan_id="cx22",
            ssh_keys=[],
        )
        instance = mock_provider.provision(config)
        assert instance.id is not None
        assert instance.ip_address is not None

    def test_mock_destroy(self, mock_provider):
        """Mock provider destroys instance."""
        assert mock_provider.destroy("inst-123") is True

    def test_mock_get_instance(self, mock_provider):
        """Mock provider returns instance by ID."""
        instance = mock_provider.get_instance("inst-123")
        assert instance is not None
        assert instance.id == "inst-123"
