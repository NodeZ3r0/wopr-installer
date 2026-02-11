"""
WOPR Exoscale Provider Adapter
==============================

Exoscale integration via their API.

Exoscale (Swiss) offers:
- Swiss privacy laws and neutrality
- GDPR and Swiss data protection
- No backdoors policy
- EU datacenters (Switzerland, Germany, Austria, Bulgaria)
- Good for compliance-heavy deployments

API Docs: https://community.exoscale.com/documentation/compute/

Note: Exoscale uses a CloudStack-compatible API.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import hmac
import base64
import time

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


# Exoscale status mapping
EXOSCALE_STATUS_MAP = {
    "running": InstanceStatus.RUNNING,
    "stopped": InstanceStatus.STOPPED,
    "starting": InstanceStatus.PROVISIONING,
    "stopping": InstanceStatus.RUNNING,
    "destroyed": InstanceStatus.STOPPED,  # Destroyed maps to stopped
}

# Exoscale pricing (CHF/month, approximate)
EXOSCALE_PRICES_CHF = {
    "micro": 11.00,
    "tiny": 22.00,
    "small": 44.00,
    "medium": 88.00,
    "large": 176.00,
    "extra-large": 352.00,
    "huge": 704.00,
    "mega": 1408.00,
    "titan": 2816.00,
}

CHF_TO_USD = 1.12


@register_provider
class ExoscaleProvider(WOPRProviderInterface):
    """
    Exoscale provider adapter.

    Features:
    - Swiss privacy and neutrality
    - GDPR + Swiss data protection
    - No backdoors policy
    - Multiple EU regions
    - CloudStack-compatible API
    """

    PROVIDER_ID = "exoscale"
    PROVIDER_NAME = "Exoscale"
    PROVIDER_WEBSITE = "https://www.exoscale.com"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    API_BASE_URL = "https://api.exoscale.com/v2"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize Exoscale provider.

        Args:
            api_token: Exoscale API key
            api_secret: Exoscale API secret (required)
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "exoscale",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_key = api_token
        self.api_secret = kwargs.get("api_secret", "")

        if not self.api_secret:
            raise ProviderError("exoscale", "api_secret is required")

        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        self._validate_credentials()

    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Generate Exoscale API v2 signature headers."""
        timestamp = str(int(time.time()))
        expires = str(int(time.time()) + 600)  # 10 minutes

        # Build signature string
        string_to_sign = f"{method} {path}\n{body}\n{expires}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        sig_b64 = base64.b64encode(signature).decode('utf-8')

        return {
            "EXO-Authorization": f"EXO2-HMAC-SHA256 credential={self.api_key},expires={expires},signature={sig_b64}"
        }

    def _validate_credentials(self) -> None:
        """Validate Exoscale credentials."""
        try:
            headers = self._sign_request("GET", "/zone")
            response = self.client.get("/zone", headers=headers)
            if response.status_code == 401:
                raise ProviderAuthError("exoscale", "Invalid API credentials")
            response.raise_for_status()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("exoscale", f"Connection error: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available Exoscale instance types."""
        # Exoscale instance types
        plans_data = [
            {"id": "micro", "name": "Micro", "cpu": 1, "ram": 1, "disk": 10},
            {"id": "tiny", "name": "Tiny", "cpu": 1, "ram": 2, "disk": 20},
            {"id": "small", "name": "Small", "cpu": 2, "ram": 4, "disk": 40},
            {"id": "medium", "name": "Medium", "cpu": 4, "ram": 8, "disk": 100},
            {"id": "large", "name": "Large", "cpu": 4, "ram": 16, "disk": 200},
            {"id": "extra-large", "name": "Extra Large", "cpu": 8, "ram": 32, "disk": 400},
            {"id": "huge", "name": "Huge", "cpu": 16, "ram": 64, "disk": 800},
        ]

        plans = []
        for p in plans_data:
            price_chf = EXOSCALE_PRICES_CHF.get(p["id"], p["cpu"] * 20)
            price_usd = price_chf * CHF_TO_USD

            plan = Plan(
                id=p["id"],
                name=p["name"],
                cpu=p["cpu"],
                ram_gb=p["ram"],
                disk_gb=p["disk"],
                bandwidth_tb=None,  # Pay per GB
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
        """List available Exoscale zones."""
        return [
            Region(id="ch-gva-2", name="Geneva", country="CH", city="Geneva",
                   available=True, features=["ipv6", "cloud-init", "swiss-privacy"]),
            Region(id="ch-dk-2", name="Zurich", country="CH", city="Zurich",
                   available=True, features=["ipv6", "cloud-init", "swiss-privacy"]),
            Region(id="de-fra-1", name="Frankfurt", country="DE", city="Frankfurt",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="de-muc-1", name="Munich", country="DE", city="Munich",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="at-vie-1", name="Vienna", country="AT", city="Vienna",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="at-vie-2", name="Vienna 2", country="AT", city="Vienna",
                   available=True, features=["ipv6", "cloud-init"]),
            Region(id="bg-sof-1", name="Sofia", country="BG", city="Sofia",
                   available=True, features=["ipv6", "cloud-init"]),
        ]

    # =========================================
    # INSTANCE OPERATIONS (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new Exoscale instance."""
        raise ProviderError("exoscale", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy an Exoscale instance."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("exoscale", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
