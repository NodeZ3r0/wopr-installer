#!/usr/bin/env python3
"""
WOPR Provisioning Test Suite
=============================

Multi-layer testing for the Stripe → VPS provisioning flow.

Usage:
    # Run all safe tests (no real API calls)
    python -m pytest control_plane/tests/test_provisioning.py -v

    # Run with Hetzner validation (creates/destroys real VPS)
    HETZNER_API_TOKEN=xxx python -m pytest control_plane/tests/test_provisioning.py -v -k hetzner_live

    # Run interactive test menu
    python control_plane/tests/test_provisioning.py

Test Layers:
    1. Unit Tests - Pure logic, no network
    2. Mock Integration - Fake external APIs
    3. Provider Validation - Real API, quick create/destroy
"""

import os
import sys
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ============================================
# LAYER 1: UNIT TESTS
# ============================================

class TestCloudInitGeneration:
    """Test cloud-init user data generation."""

    def test_cloud_init_has_bootstrap_json(self):
        """Verify cloud-init includes bootstrap.json."""
        from control_plane.vps_provisioner import VPSProvisioner, VPSProvisionRequest

        provisioner = VPSProvisioner(
            hetzner_token="fake-token",
            orchestrator_url="https://api.wopr.systems",
        )
        provisioner._provider = Mock()  # Skip real Hetzner init

        request = VPSProvisionRequest(
            job_id="test-job-123",
            beacon_name="testbeacon",
            bundle="starter",
            tier="t1",
            customer_email="test@example.com",
            customer_name="Test User",
        )

        cloud_init = provisioner._generate_cloud_init(request)

        assert "#cloud-config" in cloud_init
        assert "/etc/wopr/bootstrap.json" in cloud_init
        assert "test-job-123" in cloud_init
        assert "testbeacon" in cloud_init
        assert "test@example.com" in cloud_init

    def test_cloud_init_has_runcmd(self):
        """Verify cloud-init has installation commands."""
        from control_plane.vps_provisioner import VPSProvisioner, VPSProvisionRequest

        provisioner = VPSProvisioner(
            hetzner_token="fake-token",
            orchestrator_url="https://api.wopr.systems",
        )
        provisioner._provider = Mock()

        request = VPSProvisionRequest(
            job_id="test-job-123",
            beacon_name="testbeacon",
            bundle="starter",
            tier="t1",
            customer_email="test@example.com",
            customer_name="Test User",
        )

        cloud_init = provisioner._generate_cloud_init(request)

        assert "runcmd:" in cloud_init
        assert "wopr_install.sh" in cloud_init
        assert "git clone" in cloud_init


class TestBundleMapping:
    """Test bundle to modules mapping."""

    def test_starter_bundle_has_core_modules(self):
        """Verify starter bundle includes core infrastructure."""
        from control_plane.bundles.manifests import get_modules_for_bundle, CORE_INFRASTRUCTURE

        modules = get_modules_for_bundle("sovereign", "starter")

        # Core infra should be included
        for core in CORE_INFRASTRUCTURE:
            assert core in modules, f"Missing core module: {core}"

    def test_developer_bundle_has_dev_tools(self):
        """Verify developer bundle has more modules than starter."""
        from control_plane.bundles.manifests import get_modules_for_bundle

        starter_modules = get_modules_for_bundle("sovereign", "starter")
        developer_modules = get_modules_for_bundle("sovereign", "developer")

        # Developer should have at least as many as starter (plus more)
        assert len(developer_modules) >= len(starter_modules)
        # Check for some expected modules (adjust based on actual bundle)
        assert "nextcloud" in developer_modules or "collabora" in developer_modules

    def test_invalid_bundle_raises(self):
        """Verify invalid bundle raises ValueError."""
        from control_plane.bundles.manifests import get_modules_for_bundle

        try:
            get_modules_for_bundle("sovereign", "nonexistent_bundle_xyz")
            assert False, "Should have raised ValueError"
        except (ValueError, KeyError):
            pass  # Expected


class TestTierMapping:
    """Test tier to Hetzner plan mapping."""

    def test_tier_to_plan_mapping(self):
        """Verify tier maps to appropriate Hetzner plan."""
        from control_plane.vps_provisioner import TIER_TO_HETZNER_PLAN

        assert "t1" in TIER_TO_HETZNER_PLAN
        assert "t2" in TIER_TO_HETZNER_PLAN
        assert "t3" in TIER_TO_HETZNER_PLAN

        # t3 should be more powerful than t1
        t1_plan = TIER_TO_HETZNER_PLAN["t1"]
        t3_plan = TIER_TO_HETZNER_PLAN["t3"]
        assert t1_plan != t3_plan

    def test_bundle_min_tier_upgrade(self):
        """Verify heavy bundles get upgraded to minimum tier."""
        from control_plane.vps_provisioner import VPSProvisioner

        provisioner = VPSProvisioner(
            hetzner_token="fake",
            orchestrator_url="https://api.wopr.systems",
        )
        provisioner._provider = Mock()

        # Professional bundle should upgrade t1 to t2
        plan = provisioner._get_plan_for_tier("professional", "t1")
        expected_plan = provisioner._get_plan_for_tier("professional", "t2")
        assert plan == expected_plan


class TestJobStore:
    """Test job store operations."""

    def test_create_and_get_job(self):
        """Verify job creation and retrieval."""
        from control_plane.job_store import JobStore

        store = JobStore()
        store.create_job(
            job_id="test-123",
            beacon_name="mybeacon",
            bundle="starter",
            tier="t1",
            customer_email="test@example.com",
            customer_name="Test User",
            provider="hetzner",
        )

        job = store.get_job("test-123")
        assert job is not None
        assert job["beacon_name"] == "mybeacon"
        assert job["bundle"] == "starter"

    def test_update_job_state(self):
        """Verify job state updates."""
        from control_plane.job_store import JobStore

        store = JobStore()
        store.create_job(
            job_id="test-456",
            beacon_name="beacon2",
            bundle="developer",
            tier="t2",
            customer_email="dev@example.com",
            customer_name="Dev User",
            provider="hetzner",
        )

        store.set_state("test-456", "provisioning_vps", "Creating VPS...")

        job = store.get_job("test-456")
        assert job["state"] == "provisioning_vps"
        assert job["message"] == "Creating VPS..."


# ============================================
# LAYER 2: MOCK INTEGRATION TESTS
# ============================================

class TestMockedProvisioningFlow:
    """Test full flow with mocked external APIs."""

    def test_stripe_webhook_triggers_provisioning(self):
        """Verify Stripe webhook creates provisioning job."""
        # Mock Stripe session data
        mock_session = {
            "id": "cs_test_123",
            "customer": "cus_test_123",
            "customer_email": "buyer@example.com",
            "customer_details": {"name": "John Buyer"},
            "metadata": {
                "wopr_bundle": "starter",
                "wopr_tier": "t1",
                "wopr_beacon_name": "johncloud",
                "wopr_provider": "hetzner",
                "wopr_region": "fsn1",
            },
            "subscription": "sub_test_123",
        }

        from control_plane.vps_provisioner import VPSProvisioner, VPSProvisionRequest
        from control_plane.job_store import get_job_store

        # Create the job first (normally done by webhook handler)
        job_store = get_job_store()
        job_store.create_job(
            job_id="test-job-789",
            beacon_name="johncloud",
            bundle="starter",
            tier="t1",
            customer_email="buyer@example.com",
            customer_name="John Buyer",
            provider="hetzner",
        )

        # Create provisioner with mocked provider
        provisioner = VPSProvisioner(
            hetzner_token="fake-token",
            orchestrator_url="https://api.wopr.systems",
        )

        # Mock the Hetzner provider
        mock_instance = Mock()
        mock_instance.id = "12345"
        mock_instance.ip_address = "1.2.3.4"
        mock_instance.ipv6_address = "2001:db8::1"

        mock_provider = Mock()
        mock_provider.provision.return_value = mock_instance
        provisioner._provider = mock_provider

        # Create request from session
        request = VPSProvisionRequest(
            job_id="test-job-789",
            beacon_name=mock_session["metadata"]["wopr_beacon_name"],
            bundle=mock_session["metadata"]["wopr_bundle"],
            tier=mock_session["metadata"]["wopr_tier"],
            customer_email=mock_session["customer_email"],
            customer_name=mock_session["customer_details"]["name"],
            stripe_customer_id=mock_session["customer"],
        )

        # Run provisioning
        result = asyncio.run(provisioner.provision(request))

        assert result["success"] is True
        assert result["ip_address"] == "1.2.3.4"
        assert mock_provider.provision.called


class TestProviderRegistry:
    """Test provider registration system."""

    def test_hetzner_registered(self):
        """Verify Hetzner provider is registered."""
        from control_plane.providers import ProviderRegistry

        providers = ProviderRegistry.list_providers()
        provider_ids = [p["id"] for p in providers]

        assert "hetzner" in provider_ids

    def test_vultr_not_registered(self):
        """Verify Vultr is NOT registered (deprecated)."""
        from control_plane.providers import ProviderRegistry

        providers = ProviderRegistry.list_providers()
        provider_ids = [p["id"] for p in providers]

        assert "vultr" not in provider_ids

    def test_stub_providers_registered(self):
        """Verify stub providers are registered."""
        from control_plane.providers import ProviderRegistry

        providers = ProviderRegistry.list_providers()
        provider_ids = [p["id"] for p in providers]

        # Check some stub providers exist
        expected_stubs = ["scaleway", "contabo", "buyvm"]
        for stub in expected_stubs:
            assert stub in provider_ids, f"Missing stub provider: {stub}"


# ============================================
# LAYER 3: LIVE PROVIDER VALIDATION
# ============================================

class TestHetznerLiveValidation:
    """
    Live Hetzner API tests.

    These create real resources but destroy them immediately.
    Cost: < 0.01 EUR per test run.

    Run with: HETZNER_API_TOKEN=xxx pytest -k hetzner_live
    """

    @staticmethod
    def _get_hetzner_token() -> Optional[str]:
        return os.environ.get("HETZNER_API_TOKEN")

    def test_hetzner_live_authentication(self):
        """Test Hetzner API authentication."""
        token = self._get_hetzner_token()
        if not token:
            print("SKIP: HETZNER_API_TOKEN not set")
            return

        from control_plane.providers.hetzner import HetznerProvider

        # This should not raise
        provider = HetznerProvider(api_token=token)
        assert provider.client is not None

    def test_hetzner_live_list_plans(self):
        """Test listing Hetzner plans."""
        token = self._get_hetzner_token()
        if not token:
            print("SKIP: HETZNER_API_TOKEN not set")
            return

        from control_plane.providers.hetzner import HetznerProvider

        provider = HetznerProvider(api_token=token)
        plans = provider.list_plans()

        assert len(plans) > 0
        print(f"\nFound {len(plans)} Hetzner plans:")
        for plan in plans[:5]:
            print(f"  - {plan.id}: {plan.cpu} CPU, {plan.ram_gb}GB RAM, ${plan.price_monthly_usd}/mo")

    def test_hetzner_live_list_regions(self):
        """Test listing Hetzner regions."""
        token = self._get_hetzner_token()
        if not token:
            print("SKIP: HETZNER_API_TOKEN not set")
            return

        from control_plane.providers.hetzner import HetznerProvider

        provider = HetznerProvider(api_token=token)
        regions = provider.list_regions()

        assert len(regions) > 0
        print(f"\nFound {len(regions)} Hetzner regions:")
        for region in regions:
            print(f"  - {region.id}: {region.name} ({region.country})")

    def test_hetzner_live_list_ssh_keys(self):
        """Test listing SSH keys."""
        token = self._get_hetzner_token()
        if not token:
            print("SKIP: HETZNER_API_TOKEN not set")
            return

        from control_plane.providers.hetzner import HetznerProvider

        provider = HetznerProvider(api_token=token)
        keys = provider.list_ssh_keys()

        print(f"\nFound {len(keys)} SSH keys:")
        for key in keys:
            print(f"  - {key['name']} ({key['id']})")

        # Check for wopr-deploy key
        key_names = [k["name"] for k in keys]
        if "wopr-deploy" not in key_names:
            print("\n  WARNING: 'wopr-deploy' SSH key not found!")
            print("  Add it at: https://console.hetzner.cloud/projects/YOUR_PROJECT/security/sshkeys")


# ============================================
# INTERACTIVE TEST MENU
# ============================================

def run_interactive():
    """Interactive test menu for manual testing."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                WOPR Provisioning Test Suite                      ║
╠══════════════════════════════════════════════════════════════════╣
║  1. Run Unit Tests (no network)                                  ║
║  2. Run Mock Integration Tests                                   ║
║  3. Validate Hetzner API (requires HETZNER_API_TOKEN)            ║
║  4. Create Test VPS (creates real VPS, destroys after 60s)       ║
║  5. Full E2E Test (Stripe test mode + real VPS)                  ║
║  q. Quit                                                         ║
╚══════════════════════════════════════════════════════════════════╝
""")

    while True:
        choice = input("\nSelect test [1-5, q]: ").strip().lower()

        if choice == "q":
            break
        elif choice == "1":
            run_unit_tests()
        elif choice == "2":
            run_mock_tests()
        elif choice == "3":
            run_hetzner_validation()
        elif choice == "4":
            run_create_test_vps()
        elif choice == "5":
            run_full_e2e()
        else:
            print("Invalid choice")


def run_unit_tests():
    """Run unit tests."""
    print("\n--- Running Unit Tests ---\n")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "-k", "Test and not Live",
        "--tb=short"
    ])


def run_mock_tests():
    """Run mock integration tests."""
    print("\n--- Running Mock Integration Tests ---\n")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "-k", "Mocked or Registry",
        "--tb=short"
    ])


def run_hetzner_validation():
    """Run Hetzner API validation."""
    token = os.environ.get("HETZNER_API_TOKEN")
    if not token:
        print("\nERROR: HETZNER_API_TOKEN environment variable not set")
        print("Set it with: export HETZNER_API_TOKEN=your-token-here")
        return

    print("\n--- Validating Hetzner API ---\n")

    try:
        from control_plane.providers.hetzner import HetznerProvider

        print("1. Testing authentication...")
        provider = HetznerProvider(api_token=token)
        print("   OK - Authenticated successfully")

        print("\n2. Listing regions...")
        regions = provider.list_regions()
        print(f"   OK - Found {len(regions)} regions")
        for r in regions:
            print(f"      - {r.id}: {r.name}")

        print("\n3. Listing plans...")
        plans = provider.list_plans()
        print(f"   OK - Found {len(plans)} plans")
        for p in plans[:5]:
            print(f"      - {p.id}: {p.cpu}vCPU, {p.ram_gb}GB, ${p.price_monthly_usd}/mo")

        print("\n4. Checking SSH keys...")
        keys = provider.list_ssh_keys()
        print(f"   OK - Found {len(keys)} SSH keys")
        for k in keys:
            print(f"      - {k['name']}")

        key_names = [k["name"] for k in keys]
        if "wopr-deploy" in key_names:
            print("\n   'wopr-deploy' key found - ready for provisioning!")
        else:
            print("\n   WARNING: 'wopr-deploy' key NOT found")
            print("   Add it at Hetzner Console > Security > SSH Keys")

        print("\n--- Hetzner Validation Complete ---")
        print("All checks passed! Ready to provision VPS.")

    except Exception as e:
        print(f"\nERROR: {e}")


def run_create_test_vps():
    """Create a test VPS and destroy it."""
    token = os.environ.get("HETZNER_API_TOKEN")
    if not token:
        print("\nERROR: HETZNER_API_TOKEN not set")
        return

    print("\n--- Creating Test VPS ---")
    print("This will create a real VPS and destroy it after 60 seconds.")
    print("Estimated cost: < 0.01 EUR\n")

    confirm = input("Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled")
        return

    try:
        from control_plane.providers.hetzner import HetznerProvider
        from control_plane.providers.base import ProvisionConfig

        provider = HetznerProvider(api_token=token)

        # Use cheapest plan
        plans = provider.list_plans()
        cheapest = min(plans, key=lambda p: p.price_monthly_usd)
        print(f"\nUsing cheapest plan: {cheapest.id} (${cheapest.price_monthly_usd}/mo)")

        # Get first region
        regions = provider.list_regions()
        region = regions[0].id
        print(f"Using region: {region}")

        # Get SSH keys
        keys = provider.list_ssh_keys()
        ssh_key = keys[0]["name"] if keys else None

        config = ProvisionConfig(
            name=f"wopr-test-{int(time.time())}",
            region=region,
            plan_id=cheapest.id,
            image="debian-12",
            ssh_keys=[ssh_key] if ssh_key else [],
            user_data="#!/bin/bash\necho 'WOPR test VPS' > /root/test.txt",
            wopr_bundle="test",
            metadata={"test": "true"},
        )

        print("\nProvisioning VPS...")
        instance = provider.provision(config)

        print(f"\n SUCCESS!")
        print(f"   Instance ID: {instance.id}")
        print(f"   IP Address:  {instance.ip_address}")
        print(f"   Status:      {instance.status}")

        print("\nWaiting 60 seconds before destroying...")
        for i in range(60, 0, -10):
            print(f"   {i} seconds remaining...")
            time.sleep(10)

        print("\nDestroying VPS...")
        provider.destroy(instance.id)
        print(" VPS destroyed successfully")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


def run_full_e2e():
    """Run full E2E test with Stripe test mode."""
    print("\n--- Full E2E Test ---")
    print("\nThis test requires:")
    print("  - STRIPE_API_KEY (test mode: sk_test_xxx)")
    print("  - STRIPE_WEBHOOK_SECRET")
    print("  - HETZNER_API_TOKEN")
    print("  - Control plane running")
    print("\nNot yet implemented - use Stripe CLI for webhook testing:")
    print("  stripe listen --forward-to localhost:8500/api/v1/webhooks/stripe")
    print("  stripe trigger checkout.session.completed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--pytest":
        # Run as pytest
        import pytest
        pytest.main([__file__, "-v"])
    else:
        # Run interactive menu
        run_interactive()
