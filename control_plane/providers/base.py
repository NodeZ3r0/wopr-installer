"""
WOPR Provider Base Classes and Interfaces
==========================================

Defines the abstract interface that all VPS providers must implement.
This ensures consistent behavior across providers and prevents vendor lock-in.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class ResourceTier(Enum):
    """WOPR resource tiers as defined in the manifest."""
    LOW = "low"           # >=2 vCPU, >=4GB RAM, >=40GB disk
    MEDIUM = "medium"     # >=4 vCPU, >=8GB RAM, >=80GB disk
    HIGH = "high"         # >=8 vCPU, >=16GB RAM, >=200GB disk
    VERY_HIGH = "very_high"  # >=16 vCPU, >=32GB RAM, >=500GB disk

    @property
    def min_cpu(self) -> int:
        return {
            ResourceTier.LOW: 2,
            ResourceTier.MEDIUM: 4,
            ResourceTier.HIGH: 8,
            ResourceTier.VERY_HIGH: 16,
        }[self]

    @property
    def min_ram_gb(self) -> int:
        return {
            ResourceTier.LOW: 4,
            ResourceTier.MEDIUM: 8,
            ResourceTier.HIGH: 16,
            ResourceTier.VERY_HIGH: 32,
        }[self]

    @property
    def min_disk_gb(self) -> int:
        return {
            ResourceTier.LOW: 40,
            ResourceTier.MEDIUM: 80,
            ResourceTier.HIGH: 200,
            ResourceTier.VERY_HIGH: 500,
        }[self]


class InstanceStatus(Enum):
    """Standard instance states across all providers."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    REBOOTING = "rebooting"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class Region:
    """Represents a provider region/datacenter."""
    id: str
    name: str
    country: str
    city: Optional[str] = None
    available: bool = True
    features: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} ({self.country})"


@dataclass
class Plan:
    """Represents a VPS plan/size from a provider."""
    id: str
    name: str
    cpu: int
    ram_gb: int
    disk_gb: int
    bandwidth_tb: Optional[float] = None
    price_monthly_usd: float = 0.0
    price_hourly_usd: Optional[float] = None
    provider: str = ""
    available_regions: List[str] = field(default_factory=list)

    def meets_tier(self, tier: ResourceTier) -> bool:
        """Check if this plan meets the minimum requirements for a tier."""
        return (
            self.cpu >= tier.min_cpu and
            self.ram_gb >= tier.min_ram_gb and
            self.disk_gb >= tier.min_disk_gb
        )

    def __str__(self) -> str:
        return f"{self.name}: {self.cpu}vCPU, {self.ram_gb}GB RAM, {self.disk_gb}GB disk (${self.price_monthly_usd}/mo)"


@dataclass
class Instance:
    """Represents a provisioned VPS instance."""
    id: str
    provider: str
    name: str
    status: InstanceStatus
    region: str
    plan: str
    ip_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    created_at: Optional[datetime] = None
    wopr_instance_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.name} ({self.provider}): {self.ip_address} [{self.status.value}]"


@dataclass
class ProvisionConfig:
    """Configuration for provisioning a new VPS."""
    name: str
    region: str
    plan_id: str
    ssh_keys: List[str]
    image: str = "debian-12"
    user_data: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    wopr_bundle: Optional[str] = None
    wopr_customer_id: Optional[str] = None
    wopr_customer_email: Optional[str] = None
    wopr_customer_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tags:
            self.tags = ["wopr", "sovereign-suite"]
        if self.wopr_bundle:
            self.tags.append(f"bundle:{self.wopr_bundle}")


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, provider: str, message: str, details: Optional[Dict] = None):
        self.provider = provider
        self.message = message
        self.details = details or {}
        super().__init__(f"[{provider}] {message}")


class ProviderAuthError(ProviderError):
    """Authentication/authorization error."""
    pass


class ProviderQuotaError(ProviderError):
    """Quota/limit exceeded error."""
    pass


class ProviderResourceError(ProviderError):
    """Resource not found or unavailable error."""
    pass


class WOPRProviderInterface(ABC):
    """
    Abstract interface for VPS providers.

    All provider adapters must implement this interface to ensure
    consistent behavior across the WOPR provisioning system.

    This abstraction layer enables:
    - Multi-vendor provisioning (no lock-in)
    - Consistent API across providers
    - Easy addition of new providers
    - Provider-agnostic orchestration
    """

    # Provider metadata (override in subclasses)
    PROVIDER_ID: str = "base"
    PROVIDER_NAME: str = "Base Provider"
    PROVIDER_WEBSITE: str = ""
    SUPPORTS_IPV6: bool = True
    SUPPORTS_CLOUD_INIT: bool = True
    SUPPORTS_SSH_KEYS: bool = True

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize the provider adapter.

        Args:
            api_token: API token/key for authentication
            **kwargs: Provider-specific configuration
        """
        self.api_token = api_token
        self._validate_credentials()

    @abstractmethod
    def _validate_credentials(self) -> None:
        """
        Validate that the provided credentials are valid.

        Raises:
            ProviderAuthError: If credentials are invalid
        """
        pass

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    @abstractmethod
    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """
        List available VPS plans.

        Args:
            tier: Optional filter to only return plans meeting this tier

        Returns:
            List of available Plan objects
        """
        pass

    def get_cheapest_plan(self, tier: ResourceTier) -> Optional[Plan]:
        """
        Get the cheapest plan that meets a resource tier.

        Args:
            tier: Minimum resource tier required

        Returns:
            Cheapest Plan meeting requirements, or None
        """
        plans = self.list_plans(tier=tier)
        if not plans:
            return None
        return min(plans, key=lambda p: p.price_monthly_usd)

    def get_recommended_plan(self, tier: ResourceTier) -> Optional[Plan]:
        """
        Get the recommended plan for a resource tier.

        Default implementation returns cheapest plan.
        Providers can override for smarter recommendations.

        Args:
            tier: Target resource tier

        Returns:
            Recommended Plan, or None
        """
        return self.get_cheapest_plan(tier)

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    @abstractmethod
    def list_regions(self) -> List[Region]:
        """
        List available regions/datacenters.

        Returns:
            List of available Region objects
        """
        pass

    def get_region(self, region_id: str) -> Optional[Region]:
        """
        Get a specific region by ID.

        Args:
            region_id: Region identifier

        Returns:
            Region object or None if not found
        """
        for region in self.list_regions():
            if region.id == region_id:
                return region
        return None

    def get_regions_by_country(self, country: str) -> List[Region]:
        """
        Get regions in a specific country.

        Args:
            country: Country code (e.g., "US", "DE")

        Returns:
            List of regions in that country
        """
        return [r for r in self.list_regions() if r.country.upper() == country.upper()]

    # =========================================
    # INSTANCE PROVISIONING
    # =========================================

    @abstractmethod
    def provision(self, config: ProvisionConfig) -> Instance:
        """
        Provision a new VPS instance.

        Args:
            config: Provisioning configuration

        Returns:
            Newly created Instance

        Raises:
            ProviderError: If provisioning fails
        """
        pass

    @abstractmethod
    def destroy(self, instance_id: str) -> bool:
        """
        Destroy/delete a VPS instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            True if successful

        Raises:
            ProviderError: If destruction fails
        """
        pass

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    @abstractmethod
    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """
        Get details for a specific instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            Instance object or None if not found
        """
        pass

    @abstractmethod
    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """
        List all instances, optionally filtered by tags.

        Args:
            tags: Optional list of tags to filter by

        Returns:
            List of Instance objects
        """
        pass

    @abstractmethod
    def get_status(self, instance_id: str) -> InstanceStatus:
        """
        Get the current status of an instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            Current InstanceStatus
        """
        pass

    @abstractmethod
    def start(self, instance_id: str) -> bool:
        """
        Start a stopped instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def stop(self, instance_id: str) -> bool:
        """
        Stop a running instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def reboot(self, instance_id: str) -> bool:
        """
        Reboot an instance.

        Args:
            instance_id: Provider's instance ID

        Returns:
            True if successful
        """
        pass

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    @abstractmethod
    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """
        List SSH keys registered with the provider.

        Returns:
            List of dicts with 'id', 'name', 'fingerprint'
        """
        pass

    @abstractmethod
    def add_ssh_key(self, name: str, public_key: str) -> str:
        """
        Add an SSH key to the provider account.

        Args:
            name: Name for the key
            public_key: SSH public key content

        Returns:
            Provider's key ID
        """
        pass

    @abstractmethod
    def remove_ssh_key(self, key_id: str) -> bool:
        """
        Remove an SSH key from the provider account.

        Args:
            key_id: Provider's key ID

        Returns:
            True if successful
        """
        pass

    # =========================================
    # UTILITY METHODS
    # =========================================

    def wait_for_ready(self, instance_id: str, timeout: int = 300, poll_interval: int = 5) -> bool:
        """
        Wait for an instance to be ready (running with IP).

        Args:
            instance_id: Provider's instance ID
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status checks

        Returns:
            True if instance is ready, False if timeout
        """
        import time

        elapsed = 0
        while elapsed < timeout:
            instance = self.get_instance(instance_id)
            if instance and instance.status == InstanceStatus.RUNNING and instance.ip_address:
                return True
            time.sleep(poll_interval)
            elapsed += poll_interval

        return False

    def generate_instance_name(self, prefix: str = "wopr") -> str:
        """
        Generate a unique instance name.

        Args:
            prefix: Name prefix

        Returns:
            Unique instance name
        """
        short_id = str(uuid.uuid4())[:8]
        return f"{prefix}-{short_id}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ({self.PROVIDER_ID})>"
