"""
WOPR BuyVM (FranTech) Provider Adapter
======================================

BuyVM/FranTech integration.

BuyVM (owned by FranTech Solutions) offers:
- Independent, privacy-focused hosting
- DDoS protection included
- Unmetered bandwidth
- Multiple locations (US, EU)
- Good reputation in privacy community
- Affordable "slice" VPS options

Known for standing up for customer privacy and
refusing unreasonable government demands.

Website: https://buyvm.net/
"""

from typing import List, Optional, Dict, Any
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
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# BuyVM status mapping
BUYVM_STATUS_MAP = {
    "online": InstanceStatus.RUNNING,
    "offline": InstanceStatus.STOPPED,
    "installing": InstanceStatus.PROVISIONING,
    "suspended": InstanceStatus.ERROR,
}

# BuyVM pricing (USD/month) - very competitive
BUYVM_PRICES_USD = {
    # Slice VPS (KVM)
    "slice-512": 2.00,
    "slice-1024": 3.50,
    "slice-2048": 7.00,
    "slice-4096": 15.00,
    "slice-8192": 30.00,
    "slice-12288": 45.00,
    "slice-16384": 60.00,
}


@register_provider
class BuyVMProvider(WOPRProviderInterface):
    """
    BuyVM (FranTech) provider adapter.

    Features:
    - Independent, privacy-focused company
    - DDoS protection included (Path.net)
    - Unmetered bandwidth
    - NVMe storage
    - Anycast DNS
    - Good for privacy-conscious deployments
    """

    PROVIDER_ID = "buyvm"
    PROVIDER_NAME = "BuyVM (FranTech)"
    PROVIDER_WEBSITE = "https://buyvm.net"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    # BuyVM uses Stallion panel, API access may be limited
    API_BASE_URL = "https://manage.buyvm.net/api"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize BuyVM provider.

        Args:
            api_token: BuyVM API key (from Stallion panel)
            api_hash: API hash for authentication
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "buyvm",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_key = api_token
        self.api_hash = kwargs.get("api_hash", "")

        self.client = httpx.Client(
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate BuyVM credentials."""
        # BuyVM's Stallion API is limited - basic validation
        if not self.api_key:
            raise ProviderAuthError("buyvm", "API key is required")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available BuyVM plans."""
        # BuyVM Slice VPS plans
        plans_data = [
            {"id": "slice-512", "name": "Slice 512", "cpu": 1, "ram": 0.5, "disk": 10},
            {"id": "slice-1024", "name": "Slice 1024", "cpu": 1, "ram": 1, "disk": 20},
            {"id": "slice-2048", "name": "Slice 2048", "cpu": 1, "ram": 2, "disk": 40},
            {"id": "slice-4096", "name": "Slice 4096", "cpu": 2, "ram": 4, "disk": 80},
            {"id": "slice-8192", "name": "Slice 8192", "cpu": 4, "ram": 8, "disk": 160},
            {"id": "slice-12288", "name": "Slice 12288", "cpu": 4, "ram": 12, "disk": 240},
            {"id": "slice-16384", "name": "Slice 16384", "cpu": 6, "ram": 16, "disk": 320},
        ]

        plans = []
        for p in plans_data:
            price_usd = BUYVM_PRICES_USD.get(p["id"], p["ram"] * 5)

            plan = Plan(
                id=p["id"],
                name=p["name"],
                cpu=p["cpu"],
                ram_gb=int(p["ram"]) if p["ram"] >= 1 else 1,
                disk_gb=p["disk"],
                bandwidth_tb=None,  # Unmetered
                price_monthly_usd=price_usd,
                price_hourly_usd=round(price_usd / 730, 4),
                provider=self.PROVIDER_ID,
            )

            if tier is None or plan.meets_tier(tier):
                plans.append(plan)

        return sorted(plans, key=lambda p: p.price_monthly_usd)

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    def list_regions(self) -> List[Region]:
        """List available BuyVM locations."""
        return [
            Region(id="us-lv", name="Las Vegas", country="US", city="Las Vegas",
                   available=True, features=["ipv6", "ddos-protection", "unmetered"]),
            Region(id="us-ny", name="New York", country="US", city="New York",
                   available=True, features=["ipv6", "ddos-protection", "unmetered"]),
            Region(id="us-mia", name="Miami", country="US", city="Miami",
                   available=True, features=["ipv6", "ddos-protection", "unmetered"]),
            Region(id="lu", name="Luxembourg", country="LU", city="Roost",
                   available=True, features=["ipv6", "ddos-protection", "unmetered"]),
        ]

    # =========================================
    # INSTANCE OPERATIONS (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new BuyVM instance."""
        raise ProviderError("buyvm", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a BuyVM instance."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("buyvm", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
