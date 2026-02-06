"""
WOPR 1984 Hosting Provider Adapter
==================================

1984 Hosting integration via their API.

1984 Hosting (Icelandic) offers:
- Named after George Orwell's novel - privacy is in their DNA
- Iceland's strong privacy laws
- Free speech hosting
- 100% green energy
- No DMCA jurisdiction
- Accepts cryptocurrency

They're famous for hosting WikiLeaks and other privacy-critical sites.

Website: https://1984hosting.com/
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


# 1984 Hosting status mapping
HOSTING1984_STATUS_MAP = {
    "running": InstanceStatus.RUNNING,
    "stopped": InstanceStatus.STOPPED,
    "provisioning": InstanceStatus.PROVISIONING,
}

# 1984 Hosting pricing (EUR/month)
HOSTING1984_PRICES_EUR = {
    "VPS-Small": 9.95,
    "VPS-Medium": 19.95,
    "VPS-Large": 39.95,
    "VPS-XLarge": 79.95,
}

EUR_TO_USD = 1.10


@register_provider
class Hosting1984Provider(WOPRProviderInterface):
    """
    1984 Hosting provider adapter.

    Features:
    - Icelandic privacy laws (strongest in world)
    - Named after Orwell - privacy is core mission
    - 100% renewable energy
    - No DMCA jurisdiction
    - Free speech hosting
    - Accepts Bitcoin/crypto
    """

    PROVIDER_ID = "1984hosting"
    PROVIDER_NAME = "1984 Hosting"
    PROVIDER_WEBSITE = "https://1984hosting.com"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    API_BASE_URL = "https://api.1984hosting.com/v1"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize 1984 Hosting provider.

        Args:
            api_token: 1984 Hosting API key
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "1984hosting",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_token = api_token
        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate 1984 Hosting credentials."""
        try:
            response = self.client.get("/account")
            if response.status_code == 401:
                raise ProviderAuthError("1984hosting", "Invalid API token")
            response.raise_for_status()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("1984hosting", f"Connection error: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available 1984 Hosting plans."""
        # Plans based on their VPS offerings
        plans_data = [
            {"id": "vps-small", "name": "VPS-Small", "cpu": 1, "ram": 2, "disk": 30},
            {"id": "vps-medium", "name": "VPS-Medium", "cpu": 2, "ram": 4, "disk": 60},
            {"id": "vps-large", "name": "VPS-Large", "cpu": 4, "ram": 8, "disk": 120},
            {"id": "vps-xlarge", "name": "VPS-XLarge", "cpu": 8, "ram": 16, "disk": 240},
        ]

        plans = []
        for p in plans_data:
            price_eur = HOSTING1984_PRICES_EUR.get(p["name"], p["cpu"] * 10)
            price_usd = price_eur * EUR_TO_USD

            plan = Plan(
                id=p["id"],
                name=p["name"],
                cpu=p["cpu"],
                ram_gb=p["ram"],
                disk_gb=p["disk"],
                bandwidth_tb=None,  # Generous bandwidth included
                price_monthly_usd=round(price_usd, 2),
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
        """List available 1984 Hosting regions."""
        return [
            Region(
                id="is-rvk",
                name="Reykjavik",
                country="IS",
                city="Reykjavik",
                available=True,
                features=["ipv6", "cloud-init", "privacy", "green-energy"],
            ),
        ]

    # =========================================
    # INSTANCE OPERATIONS (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new 1984 Hosting instance."""
        raise ProviderError("1984hosting", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a 1984 Hosting instance."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("1984hosting", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
