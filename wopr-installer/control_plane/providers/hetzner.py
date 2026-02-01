"""
WOPR Hetzner Cloud Provider Adapter
===================================

Official Hetzner Cloud integration using hcloud-python SDK.

Hetzner offers excellent price/performance, especially for EU users.
Their API is well-documented and the SDK is maintained by Hetzner.

Requires: pip install hcloud
Docs: https://hcloud-python.readthedocs.io/
API: https://docs.hetzner.cloud/
"""

from typing import List, Optional, Dict
from datetime import datetime

from .base import (
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Region,
    Instance,
    InstanceStatus,
    ProvisionConfig,
    ProviderError,
    ProviderAuthError,
    ProviderResourceError,
)
from .registry import register_provider

try:
    from hcloud import Client
    from hcloud.servers import Server, ServerCreatePublicNetwork
    from hcloud.server_types import ServerType
    from hcloud.locations import Location
    from hcloud.images import Image
    from hcloud.ssh_keys import SSHKey
    HCLOUD_AVAILABLE = True
except ImportError:
    HCLOUD_AVAILABLE = False
    Client = None


# Mapping of Hetzner server statuses to WOPR statuses
HETZNER_STATUS_MAP = {
    "initializing": InstanceStatus.PROVISIONING,
    "starting": InstanceStatus.PROVISIONING,
    "running": InstanceStatus.RUNNING,
    "stopping": InstanceStatus.RUNNING,
    "off": InstanceStatus.STOPPED,
    "deleting": InstanceStatus.PENDING,
    "rebuilding": InstanceStatus.PROVISIONING,
    "migrating": InstanceStatus.RUNNING,
    "unknown": InstanceStatus.UNKNOWN,
}


# Hetzner plan prices (EUR, approximate - check current pricing)
# Format: plan_name -> monthly_eur
HETZNER_PRICES_EUR = {
    "cx22": 3.79,
    "cx32": 7.59,
    "cx42": 14.99,
    "cx52": 29.99,
    "cpx11": 4.49,
    "cpx21": 8.49,
    "cpx31": 15.99,
    "cpx41": 29.99,
    "cpx51": 64.99,
    "cax11": 3.79,
    "cax21": 6.49,
    "cax31": 12.49,
    "cax41": 23.99,
}

# EUR to USD conversion (approximate)
EUR_TO_USD = 1.10


@register_provider
class HetznerProvider(WOPRProviderInterface):
    """
    Hetzner Cloud provider adapter.

    Features:
    - Excellent EU pricing and performance
    - US datacenter available (Ashburn, VA)
    - ARM64 (Ampere) servers available
    - IPv6 included
    - 20TB traffic included
    """

    PROVIDER_ID = "hetzner"
    PROVIDER_NAME = "Hetzner Cloud"
    PROVIDER_WEBSITE = "https://www.hetzner.com/cloud"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    # Hetzner images for WOPR
    DEFAULT_IMAGES = {
        "debian-12": "debian-12",
        "ubuntu-22.04": "ubuntu-22.04",
        "ubuntu-24.04": "ubuntu-24.04",
    }

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize Hetzner provider.

        Args:
            api_token: Hetzner Cloud API token
        """
        if not HCLOUD_AVAILABLE:
            raise ProviderError(
                "hetzner",
                "hcloud-python not installed. Run: pip install hcloud"
            )

        self.api_token = api_token
        self.client: Optional[Client] = None
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate Hetzner API token."""
        try:
            self.client = Client(token=self.api_token)
            # Test the connection by listing locations
            self.client.locations.get_all()
        except Exception as e:
            raise ProviderAuthError(
                "hetzner",
                f"Invalid API token or connection error: {e}"
            )

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available Hetzner server types."""
        server_types = self.client.server_types.get_all()
        plans = []

        for st in server_types:
            # Skip deprecated types
            if st.deprecated:
                continue

            # Get price (Hetzner returns prices per location)
            price_eur = HETZNER_PRICES_EUR.get(st.name.lower(), 0)
            price_usd = price_eur * EUR_TO_USD

            plan = Plan(
                id=st.name,
                name=st.description or st.name,
                cpu=st.cores,
                ram_gb=int(st.memory),
                disk_gb=st.disk,
                bandwidth_tb=20.0,  # Hetzner includes 20TB
                price_monthly_usd=round(price_usd, 2),
                price_hourly_usd=round(price_usd / 730, 4),  # ~730 hours/month
                provider=self.PROVIDER_ID,
                available_regions=[loc.name for loc in self.client.locations.get_all()],
            )

            # Filter by tier if specified
            if tier is None or plan.meets_tier(tier):
                plans.append(plan)

        return sorted(plans, key=lambda p: p.price_monthly_usd)

    def get_recommended_plan(self, tier: ResourceTier) -> Optional[Plan]:
        """
        Get recommended Hetzner plan for a tier.

        Hetzner recommendations:
        - LOW: CX22 (shared vCPU, great value)
        - MEDIUM: CX32 or CPX21 (dedicated for better performance)
        - HIGH: CX42 or CPX31
        - VERY_HIGH: CX52 or CPX41
        """
        recommendations = {
            ResourceTier.LOW: "cx22",
            ResourceTier.MEDIUM: "cx32",
            ResourceTier.HIGH: "cx42",
            ResourceTier.VERY_HIGH: "cx52",
        }

        rec_name = recommendations.get(tier)
        if rec_name:
            plans = self.list_plans(tier=tier)
            for plan in plans:
                if plan.id.lower() == rec_name:
                    return plan

        return self.get_cheapest_plan(tier)

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    def list_regions(self) -> List[Region]:
        """List available Hetzner locations."""
        locations = self.client.locations.get_all()
        regions = []

        for loc in locations:
            regions.append(Region(
                id=loc.name,
                name=loc.description or loc.name,
                country=loc.country,
                city=loc.city,
                available=True,
                features=["ipv6", "cloud-init", "snapshots"],
            ))

        return regions

    # =========================================
    # INSTANCE PROVISIONING
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new Hetzner server."""
        try:
            # Get server type
            server_type = self.client.server_types.get_by_name(config.plan_id)
            if not server_type:
                raise ProviderResourceError(
                    "hetzner",
                    f"Server type not found: {config.plan_id}"
                )

            # Get location
            location = self.client.locations.get_by_name(config.region)
            if not location:
                raise ProviderResourceError(
                    "hetzner",
                    f"Location not found: {config.region}"
                )

            # Get image
            image_name = self.DEFAULT_IMAGES.get(config.image, config.image)
            image = self.client.images.get_by_name_and_architecture(
                name=image_name,
                architecture=server_type.architecture
            )
            if not image:
                raise ProviderResourceError(
                    "hetzner",
                    f"Image not found: {config.image}"
                )

            # Get SSH keys
            ssh_keys = []
            for key_id in config.ssh_keys:
                key = self.client.ssh_keys.get_by_name(key_id)
                if key:
                    ssh_keys.append(key)
                else:
                    # Try by ID
                    try:
                        key = self.client.ssh_keys.get_by_id(int(key_id))
                        if key:
                            ssh_keys.append(key)
                    except (ValueError, Exception):
                        pass

            # Prepare labels (Hetzner's version of tags)
            labels = {}
            for tag in config.tags:
                if ":" in tag:
                    key, value = tag.split(":", 1)
                    labels[key] = value
                else:
                    labels[tag] = "true"

            # Add WOPR metadata
            if config.wopr_customer_id:
                labels["wopr-customer"] = config.wopr_customer_id[:63]
            if config.wopr_bundle:
                labels["wopr-bundle"] = config.wopr_bundle[:63]
            if config.wopr_customer_email:
                labels["wopr-email"] = config.wopr_customer_email[:63]
            if config.wopr_customer_name:
                # Hetzner labels: alphanumeric, dashes, underscores, dots only
                safe_name = config.wopr_customer_name.replace(" ", "-")
                labels["wopr-name"] = safe_name[:63]
            labels["managed-by"] = "wopr-systems"

            # Create server
            response = self.client.servers.create(
                name=config.name,
                server_type=server_type,
                image=image,
                location=location,
                ssh_keys=ssh_keys if ssh_keys else None,
                user_data=config.user_data,
                labels=labels,
                public_net=ServerCreatePublicNetwork(
                    enable_ipv4=True,
                    enable_ipv6=True,
                ),
            )

            server = response.server

            return Instance(
                id=str(server.id),
                provider=self.PROVIDER_ID,
                name=server.name,
                status=HETZNER_STATUS_MAP.get(server.status, InstanceStatus.UNKNOWN),
                region=config.region,
                plan=config.plan_id,
                ip_address=server.public_net.ipv4.ip if server.public_net.ipv4 else None,
                ipv6_address=server.public_net.ipv6.ip if server.public_net.ipv6 else None,
                created_at=server.created,
                wopr_instance_id=config.metadata.get("wopr_instance_id"),
                metadata={"labels": labels},
            )

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to provision server: {e}")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a Hetzner server."""
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if not server:
                return True  # Already gone

            server.delete()
            return True
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to destroy server: {e}")

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get a Hetzner server by ID."""
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if not server:
                return None

            return Instance(
                id=str(server.id),
                provider=self.PROVIDER_ID,
                name=server.name,
                status=HETZNER_STATUS_MAP.get(server.status, InstanceStatus.UNKNOWN),
                region=server.datacenter.location.name,
                plan=server.server_type.name,
                ip_address=server.public_net.ipv4.ip if server.public_net.ipv4 else None,
                ipv6_address=server.public_net.ipv6.ip if server.public_net.ipv6 else None,
                created_at=server.created,
                metadata={"labels": server.labels},
            )
        except Exception:
            return None

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List all Hetzner servers."""
        try:
            # Build label selector if tags provided
            label_selector = None
            if tags:
                selectors = []
                for tag in tags:
                    if ":" in tag:
                        selectors.append(tag.replace(":", "="))
                    else:
                        selectors.append(tag)
                label_selector = ",".join(selectors)

            servers = self.client.servers.get_all(label_selector=label_selector)

            instances = []
            for server in servers:
                instances.append(Instance(
                    id=str(server.id),
                    provider=self.PROVIDER_ID,
                    name=server.name,
                    status=HETZNER_STATUS_MAP.get(server.status, InstanceStatus.UNKNOWN),
                    region=server.datacenter.location.name,
                    plan=server.server_type.name,
                    ip_address=server.public_net.ipv4.ip if server.public_net.ipv4 else None,
                    ipv6_address=server.public_net.ipv6.ip if server.public_net.ipv6 else None,
                    created_at=server.created,
                    metadata={"labels": server.labels},
                ))

            return instances
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to list servers: {e}")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get status of a Hetzner server."""
        instance = self.get_instance(instance_id)
        return instance.status if instance else InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start a Hetzner server."""
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if server:
                server.power_on()
                return True
            return False
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to start server: {e}")

    def stop(self, instance_id: str) -> bool:
        """Stop a Hetzner server."""
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if server:
                server.power_off()
                return True
            return False
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to stop server: {e}")

    def reboot(self, instance_id: str) -> bool:
        """Reboot a Hetzner server."""
        try:
            server = self.client.servers.get_by_id(int(instance_id))
            if server:
                server.reboot()
                return True
            return False
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to reboot server: {e}")

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys in Hetzner account."""
        try:
            keys = self.client.ssh_keys.get_all()
            return [
                {
                    "id": str(key.id),
                    "name": key.name,
                    "fingerprint": key.fingerprint,
                }
                for key in keys
            ]
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to list SSH keys: {e}")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add an SSH key to Hetzner account."""
        try:
            key = self.client.ssh_keys.create(name=name, public_key=public_key)
            return str(key.id)
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to add SSH key: {e}")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove an SSH key from Hetzner account."""
        try:
            key = self.client.ssh_keys.get_by_id(int(key_id))
            if key:
                key.delete()
                return True
            return False
        except Exception as e:
            raise ProviderError("hetzner", f"Failed to remove SSH key: {e}")
