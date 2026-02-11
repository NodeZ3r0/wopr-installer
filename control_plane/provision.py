"""
WOPR VPS Provisioner
====================

Main orchestrator for VPS provisioning across multiple providers.

This module provides:
- Multi-provider VPS provisioning
- Automatic plan selection based on bundle
- SSH bootstrap and WOPR deployment
- Integration with billing webhooks
- DEFCON ONE audit logging

Usage:
    provisioner = WOPRProvisioner()
    provisioner.add_provider("hetzner", api_token="...")

    instance = provisioner.provision_for_bundle(
        bundle="personal",
        domain="mycloud.example.com",
        customer_id="cust_123"
    )
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
import os
import uuid

from providers import (
    ProviderRegistry,
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Instance,
    InstanceStatus,
    ProvisionConfig,
    ProviderError,
)
from providers.plan_registry import PlanRegistry


@dataclass
class ProvisionResult:
    """Result of a provisioning operation."""
    success: bool
    instance: Optional[Instance]
    provider: str
    plan: str
    error: Optional[str] = None
    wopr_instance_id: Optional[str] = None
    bootstrap_status: str = "pending"


class WOPRProvisioner:
    """
    Main WOPR VPS provisioning orchestrator.

    Handles multi-provider provisioning with automatic
    plan selection, bootstrap, and deployment.
    """

    # Bundle to tier mapping
    BUNDLE_TIERS = {
        "personal": ResourceTier.LOW,
        "creator": ResourceTier.MEDIUM,
        "developer": ResourceTier.MEDIUM,
        "professional": ResourceTier.HIGH,
    }

    def __init__(self, config_dir: str = "/etc/wopr"):
        """
        Initialize the provisioner.

        Args:
            config_dir: Directory for configuration and credentials
        """
        self.config_dir = config_dir
        self.providers: Dict[str, WOPRProviderInterface] = {}
        self.default_ssh_key: Optional[str] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from disk."""
        config_file = os.path.join(self.config_dir, "provisioner.json")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
                self.default_ssh_key = config.get("default_ssh_key")

    def _save_config(self) -> None:
        """Save configuration to disk."""
        os.makedirs(self.config_dir, exist_ok=True)
        config_file = os.path.join(self.config_dir, "provisioner.json")
        with open(config_file, "w") as f:
            json.dump({
                "default_ssh_key": self.default_ssh_key,
                "providers": list(self.providers.keys()),
            }, f, indent=2)

    # =========================================
    # PROVIDER MANAGEMENT
    # =========================================

    def add_provider(
        self,
        provider_id: str,
        api_token: str,
        **kwargs
    ) -> WOPRProviderInterface:
        """
        Add and configure a VPS provider.

        Args:
            provider_id: Provider identifier (e.g., 'hetzner', 'vultr')
            api_token: API token for authentication
            **kwargs: Provider-specific configuration

        Returns:
            Configured provider instance

        Raises:
            ProviderError: If provider setup fails
        """
        provider = ProviderRegistry.instantiate(provider_id, api_token, **kwargs)
        self.providers[provider_id] = provider
        self._save_config()
        return provider

    def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider from the provisioner."""
        if provider_id in self.providers:
            del self.providers[provider_id]
            self._save_config()
            return True
        return False

    def list_providers(self) -> List[str]:
        """List configured providers."""
        return list(self.providers.keys())

    def get_provider(self, provider_id: str) -> Optional[WOPRProviderInterface]:
        """Get a specific provider instance."""
        return self.providers.get(provider_id)

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    def set_default_ssh_key(self, key_name: str) -> None:
        """Set the default SSH key for provisioning."""
        self.default_ssh_key = key_name
        self._save_config()

    def ensure_ssh_key(
        self,
        provider_id: str,
        key_name: str,
        public_key: str
    ) -> str:
        """
        Ensure an SSH key exists on a provider.

        Args:
            provider_id: Provider to add key to
            key_name: Name for the key
            public_key: SSH public key content

        Returns:
            Provider's key ID
        """
        provider = self.providers.get(provider_id)
        if not provider:
            raise ProviderError(provider_id, "Provider not configured")

        # Check if key already exists
        existing_keys = provider.list_ssh_keys()
        for key in existing_keys:
            if key["name"] == key_name:
                return key["id"]

        # Add new key
        return provider.add_ssh_key(key_name, public_key)

    # =========================================
    # PLAN SELECTION
    # =========================================

    def get_recommended_plan(
        self,
        bundle: str,
        provider_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the recommended plan for a bundle.

        Args:
            bundle: WOPR bundle name
            provider_id: Specific provider (cheapest if None)

        Returns:
            Dict with plan details
        """
        return PlanRegistry.estimate_monthly_cost(bundle, provider_id)

    def compare_bundle_prices(self, bundle: str) -> List[Dict]:
        """
        Compare prices for a bundle across all providers.

        Args:
            bundle: WOPR bundle name

        Returns:
            List of provider/plan options sorted by price
        """
        tier = self.BUNDLE_TIERS.get(bundle)
        if not tier:
            return []

        comparisons = PlanRegistry.compare_tier_prices(tier)
        return [
            {
                "provider": provider,
                "plan_id": plan.plan_id,
                "plan_name": plan.plan_name,
                "price_monthly_usd": plan.price_monthly_usd,
                "cpu": plan.cpu,
                "ram_gb": plan.ram_gb,
                "disk_gb": plan.disk_gb,
            }
            for provider, plan in comparisons
        ]

    # =========================================
    # PROVISIONING
    # =========================================

    def provision(
        self,
        provider_id: str,
        name: str,
        region: str,
        plan_id: str,
        ssh_keys: List[str] = None,
        image: str = "debian-12",
        user_data: str = None,
        wopr_bundle: str = None,
        customer_id: str = None,
    ) -> ProvisionResult:
        """
        Provision a new VPS instance.

        Args:
            provider_id: Provider to use
            name: Instance name
            region: Region/datacenter
            plan_id: Provider plan ID
            ssh_keys: SSH key names/IDs
            image: OS image
            user_data: Cloud-init user data
            wopr_bundle: WOPR bundle to install
            customer_id: Customer ID for billing

        Returns:
            ProvisionResult with instance details
        """
        provider = self.providers.get(provider_id)
        if not provider:
            return ProvisionResult(
                success=False,
                instance=None,
                provider=provider_id,
                plan=plan_id,
                error=f"Provider not configured: {provider_id}"
            )

        # Use default SSH key if none provided
        if not ssh_keys and self.default_ssh_key:
            ssh_keys = [self.default_ssh_key]

        # Generate WOPR instance ID
        wopr_instance_id = str(uuid.uuid4())

        # Build provision config
        config = ProvisionConfig(
            name=name,
            region=region,
            plan_id=plan_id,
            ssh_keys=ssh_keys or [],
            image=image,
            user_data=user_data,
            wopr_bundle=wopr_bundle,
            wopr_customer_id=customer_id,
            metadata={
                "wopr_instance_id": wopr_instance_id,
                "provisioned_at": datetime.now().isoformat(),
            }
        )

        try:
            instance = provider.provision(config)
            instance.wopr_instance_id = wopr_instance_id

            return ProvisionResult(
                success=True,
                instance=instance,
                provider=provider_id,
                plan=plan_id,
                wopr_instance_id=wopr_instance_id,
            )

        except ProviderError as e:
            return ProvisionResult(
                success=False,
                instance=None,
                provider=provider_id,
                plan=plan_id,
                error=str(e),
            )

    def provision_for_bundle(
        self,
        bundle: str,
        domain: str,
        customer_id: str,
        provider_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> ProvisionResult:
        """
        Provision a VPS for a specific WOPR bundle.

        Automatically selects the best plan based on bundle requirements.

        Args:
            bundle: WOPR bundle (personal, creator, developer, professional)
            domain: Primary domain for the instance
            customer_id: Customer ID for billing
            provider_id: Specific provider (auto-select if None)
            region: Specific region (auto-select if None)

        Returns:
            ProvisionResult with instance details
        """
        # Get tier for bundle
        tier = self.BUNDLE_TIERS.get(bundle)
        if not tier:
            return ProvisionResult(
                success=False,
                instance=None,
                provider="",
                plan="",
                error=f"Unknown bundle: {bundle}"
            )

        # Select provider and plan
        if provider_id:
            if provider_id not in self.providers:
                return ProvisionResult(
                    success=False,
                    instance=None,
                    provider=provider_id,
                    plan="",
                    error=f"Provider not configured: {provider_id}"
                )
            plan = PlanRegistry.get_recommended_plan(provider_id, tier)
        else:
            # Find cheapest configured provider
            best_price = float("inf")
            best_provider = None
            best_plan = None

            for pid in self.providers:
                plan = PlanRegistry.get_recommended_plan(pid, tier)
                if plan and plan.price_monthly_usd < best_price:
                    best_price = plan.price_monthly_usd
                    best_provider = pid
                    best_plan = plan

            if not best_provider:
                return ProvisionResult(
                    success=False,
                    instance=None,
                    provider="",
                    plan="",
                    error="No providers configured with suitable plans"
                )

            provider_id = best_provider
            plan = best_plan

        # Select region if not specified
        if not region:
            provider = self.providers[provider_id]
            regions = provider.list_regions()
            if regions:
                region = regions[0].id
            else:
                return ProvisionResult(
                    success=False,
                    instance=None,
                    provider=provider_id,
                    plan=plan.plan_id,
                    error="No regions available"
                )

        # Generate instance name
        short_id = str(uuid.uuid4())[:8]
        name = f"wopr-{bundle}-{short_id}"

        # Generate cloud-init user data for WOPR bootstrap
        user_data = self._generate_user_data(bundle, domain, customer_id)

        # Provision
        return self.provision(
            provider_id=provider_id,
            name=name,
            region=region,
            plan_id=plan.plan_id,
            image="debian-12",
            user_data=user_data,
            wopr_bundle=bundle,
            customer_id=customer_id,
        )

    def _generate_user_data(
        self,
        bundle: str,
        domain: str,
        customer_id: str
    ) -> str:
        """Generate cloud-init user data for WOPR bootstrap."""
        return f"""#cloud-config
package_update: true
package_upgrade: true

packages:
  - curl
  - wget
  - git
  - jq

write_files:
  - path: /etc/wopr/bootstrap.json
    content: |
      {{
        "bundle": "{bundle}",
        "domain": "{domain}",
        "customer_id": "{customer_id}",
        "provisioned_at": "{datetime.now().isoformat()}"
      }}

runcmd:
  - mkdir -p /opt/wopr
  - curl -fsSL https://install.wopr.systems/bootstrap.sh | bash -s -- --bundle {bundle} --domain {domain}
"""

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    def list_instances(
        self,
        provider_id: Optional[str] = None
    ) -> List[Instance]:
        """
        List all WOPR instances.

        Args:
            provider_id: Specific provider (all if None)

        Returns:
            List of Instance objects
        """
        instances = []

        providers_to_check = [provider_id] if provider_id else list(self.providers.keys())

        for pid in providers_to_check:
            provider = self.providers.get(pid)
            if provider:
                try:
                    provider_instances = provider.list_instances(tags=["wopr"])
                    instances.extend(provider_instances)
                except ProviderError:
                    pass

        return instances

    def get_instance(
        self,
        provider_id: str,
        instance_id: str
    ) -> Optional[Instance]:
        """Get a specific instance."""
        provider = self.providers.get(provider_id)
        if provider:
            return provider.get_instance(instance_id)
        return None

    def destroy_instance(
        self,
        provider_id: str,
        instance_id: str
    ) -> bool:
        """Destroy an instance."""
        provider = self.providers.get(provider_id)
        if provider:
            return provider.destroy(instance_id)
        return False

    # =========================================
    # DISTRIBUTED PROVISIONING
    # =========================================

    def provision_distributed(
        self,
        bundle: str,
        domain: str,
        customer_id: str,
        count: int = 3,
    ) -> List[ProvisionResult]:
        """
        Provision nodes across multiple providers for distribution.

        Args:
            bundle: WOPR bundle
            domain: Primary domain
            customer_id: Customer ID
            count: Number of nodes to provision

        Returns:
            List of ProvisionResult objects
        """
        tier = self.BUNDLE_TIERS.get(bundle)
        if not tier:
            return []

        # Get distribution suggestions
        suggestions = PlanRegistry.suggest_distribution(tier, count)

        results = []
        for i, (provider_id, plan) in enumerate(suggestions):
            if provider_id not in self.providers:
                continue

            # Generate unique subdomain for each node
            node_domain = f"node{i+1}.{domain}"

            result = self.provision_for_bundle(
                bundle=bundle,
                domain=node_domain,
                customer_id=customer_id,
                provider_id=provider_id,
            )
            results.append(result)

        return results
