"""
WOPR Contabo Provider Adapter
=============================

Contabo integration via their REST API.

Contabo (German) offers:
- Extremely competitive pricing
- German data privacy (GDPR)
- Good specs for the price
- EU and US datacenters
- No bandwidth limits

Note: Contabo is known for budget VPS with high specs but
sometimes slower provisioning. Good for cost-conscious deployments.

API Docs: https://api.contabo.com/
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


# Contabo status mapping
CONTABO_STATUS_MAP = {
    "running": InstanceStatus.RUNNING,
    "stopped": InstanceStatus.STOPPED,
    "installing": InstanceStatus.PROVISIONING,
    "error": InstanceStatus.ERROR,
}

# Contabo pricing (EUR/month) - famously cheap
CONTABO_PRICES_EUR = {
    # Cloud VPS
    "VPS S SSD": 4.99,
    "VPS M SSD": 8.99,
    "VPS L SSD": 14.99,
    "VPS XL SSD": 26.99,
    "VPS XXL SSD": 44.99,
    # Cloud VDS (dedicated resources)
    "VDS S": 19.99,
    "VDS M": 39.99,
    "VDS L": 59.99,
    "VDS XL": 99.99,
}

EUR_TO_USD = 1.10


@register_provider
class ContaboProvider(WOPRProviderInterface):
    """
    Contabo provider adapter.

    Features:
    - Extremely competitive pricing
    - German company (GDPR compliant)
    - High specs for the price
    - Unlimited bandwidth
    - EU and US datacenters
    """

    PROVIDER_ID = "contabo"
    PROVIDER_NAME = "Contabo"
    PROVIDER_WEBSITE = "https://contabo.com"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    API_BASE_URL = "https://api.contabo.com/v1"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize Contabo provider.

        Args:
            api_token: Contabo API key (OAuth2 bearer token)
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "contabo",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_token = api_token
        self.client_id = kwargs.get("client_id", "")
        self.client_secret = kwargs.get("client_secret", "")

        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "x-request-id": "wopr-systems",
            },
            timeout=30.0,
        )
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate Contabo credentials."""
        try:
            response = self.client.get("/compute/instances")
            if response.status_code == 401:
                raise ProviderAuthError("contabo", "Invalid API token")
            response.raise_for_status()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("contabo", f"Connection error: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available Contabo plans."""
        # Contabo plans are relatively fixed, return known plans
        plans_data = [
            {"id": "V1", "name": "VPS S SSD", "cpu": 4, "ram": 8, "disk": 200},
            {"id": "V2", "name": "VPS M SSD", "cpu": 6, "ram": 16, "disk": 400},
            {"id": "V3", "name": "VPS L SSD", "cpu": 8, "ram": 30, "disk": 800},
            {"id": "V4", "name": "VPS XL SSD", "cpu": 10, "ram": 60, "disk": 1600},
        ]

        plans = []
        for p in plans_data:
            price_eur = CONTABO_PRICES_EUR.get(p["name"], p["cpu"] * 5)
            price_usd = price_eur * EUR_TO_USD

            plan = Plan(
                id=p["id"],
                name=p["name"],
                cpu=p["cpu"],
                ram_gb=p["ram"],
                disk_gb=p["disk"],
                bandwidth_tb=None,  # Unlimited
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
        """List available Contabo regions."""
        return [
            Region(id="EU", name="European Union", country="DE", city="Nuremberg",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="US-central", name="US Central", country="US", city="St. Louis",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="US-east", name="US East", country="US", city="New York",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="US-west", name="US West", country="US", city="Seattle",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="SIN", name="Singapore", country="SG", city="Singapore",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="AUS", name="Australia", country="AU", city="Sydney",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="JPN", name="Japan", country="JP", city="Tokyo",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="UK", name="United Kingdom", country="GB", city="London",
                   available=True, features=["ipv6", "cloud-init"]),
        ]

    # =========================================
    # INSTANCE OPERATIONS (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new Contabo instance."""
        raise ProviderError("contabo", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a Contabo instance."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("contabo", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
