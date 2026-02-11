"""
WOPR Scaleway Provider Adapter
==============================

Scaleway integration via their REST API.

Scaleway (part of Iliad Group) offers:
- Strong EU presence (France, Netherlands, Poland)
- GDPR compliant infrastructure
- Competitive pricing
- ARM64 instances (Ampere)
- Object storage, managed databases
- Good environmental practices

API Docs: https://developers.scaleway.com/
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


# Scaleway status mapping
SCALEWAY_STATUS_MAP = {
    "running": InstanceStatus.RUNNING,
    "stopped": InstanceStatus.STOPPED,
    "stopping": InstanceStatus.RUNNING,
    "starting": InstanceStatus.PROVISIONING,
    "locked": InstanceStatus.ERROR,
}

# Scaleway pricing (EUR/month, approximate)
SCALEWAY_PRICES_EUR = {
    "DEV1-S": 7.99,
    "DEV1-M": 15.99,
    "DEV1-L": 31.99,
    "DEV1-XL": 47.99,
    "GP1-XS": 39.99,
    "GP1-S": 79.99,
    "GP1-M": 159.99,
    "GP1-L": 319.99,
    # ARM instances (Ampere) - great value
    "AMP2-C1": 7.00,
    "AMP2-C2": 14.00,
    "AMP2-C4": 28.00,
    "AMP2-C8": 56.00,
}

EUR_TO_USD = 1.10


@register_provider
class ScalewayProvider(WOPRProviderInterface):
    """
    Scaleway provider adapter.

    Features:
    - EU-focused with strong privacy stance
    - GDPR compliant
    - ARM64 instances available
    - Competitive pricing
    - Good sustainability practices
    """

    PROVIDER_ID = "scaleway"
    PROVIDER_NAME = "Scaleway"
    PROVIDER_WEBSITE = "https://www.scaleway.com"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    API_BASE_URL = "https://api.scaleway.com"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize Scaleway provider.

        Args:
            api_token: Scaleway API secret key
            organization_id: Scaleway organization ID (required)
            project_id: Scaleway project ID (optional, uses default)
            zone: Default zone (e.g., 'fr-par-1', 'nl-ams-1')
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "scaleway",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_token = api_token
        self.organization_id = kwargs.get("organization_id", "")
        self.project_id = kwargs.get("project_id", "")
        self.default_zone = kwargs.get("zone", "fr-par-1")

        if not self.organization_id:
            raise ProviderError("scaleway", "organization_id is required")

        self.client = httpx.Client(
            headers={
                "X-Auth-Token": self.api_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate Scaleway credentials."""
        try:
            response = self.client.get(
                f"{self.API_BASE_URL}/account/v3/projects",
                params={"organization_id": self.organization_id}
            )
            if response.status_code == 401:
                raise ProviderAuthError("scaleway", "Invalid API token")
            response.raise_for_status()

            # Set default project if not specified
            if not self.project_id:
                data = response.json()
                projects = data.get("projects", [])
                if projects:
                    self.project_id = projects[0].get("id", "")

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("scaleway", f"Connection error: {e}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make an authenticated API request."""
        zone = zone or self.default_zone

        try:
            url = f"{self.API_BASE_URL}{endpoint}"
            response = self.client.request(
                method=method,
                url=url,
                json=data,
            )

            if response.status_code == 401:
                raise ProviderAuthError("scaleway", "Authentication failed")
            if response.status_code == 404:
                raise ProviderResourceError("scaleway", f"Resource not found")

            response.raise_for_status()
            return response.json() if response.content else {}

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("scaleway", f"API error: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available Scaleway instance types."""
        try:
            response = self._make_request(
                "GET",
                f"/instance/v1/zones/{self.default_zone}/products/servers"
            )
            servers = response.get("servers", {})
            plans = []

            for server_type, details in servers.items():
                cores = details.get("ncpus", 1)
                ram_mb = details.get("ram", 0)
                ram_gb = ram_mb // (1024 * 1024 * 1024)

                price_eur = SCALEWAY_PRICES_EUR.get(server_type, cores * 10)
                price_usd = price_eur * EUR_TO_USD

                plan = Plan(
                    id=server_type,
                    name=server_type,
                    cpu=cores,
                    ram_gb=ram_gb,
                    disk_gb=details.get("volumes_constraint", {}).get("min_size", 0) // (1024 * 1024 * 1024),
                    bandwidth_tb=None,  # Scaleway has per-GB pricing for egress
                    price_monthly_usd=round(price_usd, 2),
                    price_hourly_usd=round(price_usd / 730, 4),
                    provider=self.PROVIDER_ID,
                )

                if tier is None or plan.meets_tier(tier):
                    plans.append(plan)

            return sorted(plans, key=lambda p: p.price_monthly_usd)

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("scaleway", f"Failed to list plans: {e}")

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    def list_regions(self) -> List[Region]:
        """List available Scaleway zones."""
        # Scaleway zones are well-known, API doesn't list them easily
        return [
            Region(id="fr-par-1", name="Paris 1", country="FR", city="Paris",
                   available=True, features=["ipv6", "cloud-init", "arm64"]),
            Region(id="fr-par-2", name="Paris 2", country="FR", city="Paris",
                   available=True, features=["ipv6", "cloud-init", "arm64"]),
            Region(id="fr-par-3", name="Paris 3", country="FR", city="Paris",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="nl-ams-1", name="Amsterdam 1", country="NL", city="Amsterdam",
                   available=True, features=["ipv6", "cloud-init", "arm64"]),
            Region(id="nl-ams-2", name="Amsterdam 2", country="NL", city="Amsterdam",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="nl-ams-3", name="Amsterdam 3", country="NL", city="Amsterdam",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="pl-waw-1", name="Warsaw 1", country="PL", city="Warsaw",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="pl-waw-2", name="Warsaw 2", country="PL", city="Warsaw",
                   available=True, features=["ipv6", "cloud-init"]),
        ]

    # =========================================
    # INSTANCE PROVISIONING (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new Scaleway instance."""
        # TODO: Implement full provisioning
        raise ProviderError("scaleway", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a Scaleway instance."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("scaleway", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
