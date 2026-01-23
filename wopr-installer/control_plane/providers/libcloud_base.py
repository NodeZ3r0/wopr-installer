"""
WOPR Libcloud Base Provider
===========================

Base class for providers using Apache Libcloud.
Provides common functionality for Vultr, DigitalOcean, Linode, and OVH.

Requires: pip install apache-libcloud
Docs: https://libcloud.readthedocs.io/
"""

from typing import List, Optional, Dict, Any
from abc import abstractmethod
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
)

try:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.providers import get_driver
    from libcloud.compute.base import NodeDriver, Node, NodeSize, NodeLocation, NodeImage
    LIBCLOUD_AVAILABLE = True
except ImportError:
    LIBCLOUD_AVAILABLE = False
    LibcloudProvider = None
    get_driver = None


# Common libcloud node state mapping
LIBCLOUD_STATUS_MAP = {
    0: InstanceStatus.RUNNING,      # RUNNING
    1: InstanceStatus.REBOOTING,    # REBOOTING
    2: InstanceStatus.STOPPED,      # TERMINATED
    3: InstanceStatus.PENDING,      # PENDING
    4: InstanceStatus.UNKNOWN,      # UNKNOWN
    5: InstanceStatus.STOPPED,      # STOPPED
    6: InstanceStatus.STOPPED,      # SUSPENDED
    7: InstanceStatus.ERROR,        # ERROR
    8: InstanceStatus.STOPPED,      # PAUSED
}


class LibcloudBaseProvider(WOPRProviderInterface):
    """
    Base class for libcloud-based providers.

    Subclasses must set:
    - PROVIDER_ID
    - PROVIDER_NAME
    - PROVIDER_WEBSITE
    - LIBCLOUD_PROVIDER (from libcloud.compute.types.Provider)
    """

    LIBCLOUD_PROVIDER = None  # Must be set by subclass
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize libcloud provider.

        Args:
            api_token: Provider API token
            **kwargs: Additional driver-specific arguments
        """
        if not LIBCLOUD_AVAILABLE:
            raise ProviderError(
                self.PROVIDER_ID,
                "apache-libcloud not installed. Run: pip install apache-libcloud"
            )

        if self.LIBCLOUD_PROVIDER is None:
            raise NotImplementedError("LIBCLOUD_PROVIDER must be set by subclass")

        self.api_token = api_token
        self.driver_kwargs = kwargs
        self.driver: Optional[NodeDriver] = None
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate credentials by connecting to the provider."""
        try:
            driver_cls = get_driver(self.LIBCLOUD_PROVIDER)
            self.driver = self._create_driver(driver_cls)
            # Test connection by listing locations
            self.driver.list_locations()
        except Exception as e:
            raise ProviderAuthError(
                self.PROVIDER_ID,
                f"Failed to authenticate: {e}"
            )

    @abstractmethod
    def _create_driver(self, driver_cls) -> NodeDriver:
        """
        Create the libcloud driver instance.

        Must be implemented by subclasses to handle provider-specific
        driver initialization.
        """
        pass

    @abstractmethod
    def _get_plan_price(self, size: NodeSize) -> float:
        """
        Get monthly price for a plan in USD.

        Libcloud doesn't provide consistent pricing, so subclasses
        must implement this.
        """
        pass

    def _convert_node_to_instance(self, node: Node) -> Instance:
        """Convert libcloud Node to WOPR Instance."""
        status = LIBCLOUD_STATUS_MAP.get(node.state, InstanceStatus.UNKNOWN)

        # Get IPs
        ip_address = None
        ipv6_address = None
        if node.public_ips:
            for ip in node.public_ips:
                if ":" in ip:  # IPv6
                    ipv6_address = ip
                else:
                    ip_address = ip

        return Instance(
            id=node.id,
            provider=self.PROVIDER_ID,
            name=node.name,
            status=status,
            region=node.extra.get("location", "unknown"),
            plan=node.extra.get("size", "unknown"),
            ip_address=ip_address,
            ipv6_address=ipv6_address,
            created_at=node.created_at,
            metadata=node.extra,
        )

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available plans/sizes."""
        sizes = self.driver.list_sizes()
        plans = []

        for size in sizes:
            # Extract RAM in GB (libcloud gives MB)
            ram_gb = size.ram / 1024 if size.ram else 0

            plan = Plan(
                id=size.id,
                name=size.name,
                cpu=size.extra.get("vcpus", 1),
                ram_gb=int(ram_gb),
                disk_gb=size.disk or 0,
                bandwidth_tb=size.bandwidth / 1024 if size.bandwidth else None,
                price_monthly_usd=self._get_plan_price(size),
                provider=self.PROVIDER_ID,
            )

            if tier is None or plan.meets_tier(tier):
                plans.append(plan)

        return sorted(plans, key=lambda p: p.price_monthly_usd)

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    def list_regions(self) -> List[Region]:
        """List available regions/locations."""
        locations = self.driver.list_locations()
        regions = []

        for loc in locations:
            regions.append(Region(
                id=loc.id,
                name=loc.name,
                country=loc.country or "Unknown",
                available=True,
            ))

        return regions

    # =========================================
    # INSTANCE PROVISIONING
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new instance."""
        try:
            # Get size
            size = None
            for s in self.driver.list_sizes():
                if s.id == config.plan_id:
                    size = s
                    break
            if not size:
                raise ProviderError(self.PROVIDER_ID, f"Size not found: {config.plan_id}")

            # Get location
            location = None
            for loc in self.driver.list_locations():
                if loc.id == config.region:
                    location = loc
                    break
            if not location:
                raise ProviderError(self.PROVIDER_ID, f"Location not found: {config.region}")

            # Get image
            image = self._get_image(config.image)
            if not image:
                raise ProviderError(self.PROVIDER_ID, f"Image not found: {config.image}")

            # Create node
            node = self.driver.create_node(
                name=config.name,
                size=size,
                image=image,
                location=location,
                ex_ssh_keys=config.ssh_keys if config.ssh_keys else None,
                ex_user_data=config.user_data,
            )

            return self._convert_node_to_instance(node)

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to provision: {e}")

    @abstractmethod
    def _get_image(self, image_name: str) -> Optional[NodeImage]:
        """Get image by name. Subclasses implement provider-specific logic."""
        pass

    def destroy(self, instance_id: str) -> bool:
        """Destroy an instance."""
        try:
            node = self._get_node(instance_id)
            if node:
                return self.driver.destroy_node(node)
            return True
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to destroy: {e}")

    def _get_node(self, instance_id: str) -> Optional[Node]:
        """Get a node by ID."""
        for node in self.driver.list_nodes():
            if node.id == instance_id:
                return node
        return None

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        node = self._get_node(instance_id)
        if node:
            return self._convert_node_to_instance(node)
        return None

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List all instances."""
        nodes = self.driver.list_nodes()
        instances = [self._convert_node_to_instance(n) for n in nodes]

        # Filter by tags if provided (basic string matching)
        if tags:
            filtered = []
            for inst in instances:
                inst_tags = inst.metadata.get("tags", [])
                if any(t in inst_tags for t in tags):
                    filtered.append(inst)
            return filtered

        return instances

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        instance = self.get_instance(instance_id)
        return instance.status if instance else InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start an instance."""
        try:
            node = self._get_node(instance_id)
            if node and hasattr(self.driver, "ex_start_node"):
                return self.driver.ex_start_node(node)
            return False
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to start: {e}")

    def stop(self, instance_id: str) -> bool:
        """Stop an instance."""
        try:
            node = self._get_node(instance_id)
            if node and hasattr(self.driver, "ex_stop_node"):
                return self.driver.ex_stop_node(node)
            return False
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to stop: {e}")

    def reboot(self, instance_id: str) -> bool:
        """Reboot an instance."""
        try:
            node = self._get_node(instance_id)
            if node:
                return self.driver.reboot_node(node)
            return False
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to reboot: {e}")

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        try:
            if hasattr(self.driver, "list_key_pairs"):
                keys = self.driver.list_key_pairs()
                return [
                    {
                        "id": key.name,
                        "name": key.name,
                        "fingerprint": key.fingerprint or "",
                    }
                    for key in keys
                ]
            return []
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to list SSH keys: {e}")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add an SSH key."""
        try:
            if hasattr(self.driver, "create_key_pair"):
                key = self.driver.create_key_pair(name=name, public_key=public_key)
                return key.name
            raise ProviderError(self.PROVIDER_ID, "SSH key creation not supported")
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to add SSH key: {e}")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove an SSH key."""
        try:
            if hasattr(self.driver, "delete_key_pair"):
                for key in self.driver.list_key_pairs():
                    if key.name == key_id:
                        return self.driver.delete_key_pair(key)
            return False
        except Exception as e:
            raise ProviderError(self.PROVIDER_ID, f"Failed to remove SSH key: {e}")
