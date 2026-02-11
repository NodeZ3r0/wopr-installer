"""
WOPR Netcup Provider Adapter
============================

Netcup integration via their SCP (Server Control Panel) API.

Netcup (German) offers:
- Excellent price/performance ratio
- German data privacy (GDPR)
- Eco-friendly datacenter
- Good network connectivity
- No overselling policy

API Docs: https://www.netcup-wiki.de/wiki/Server_Control_Panel_(SCP)_API

Note: Netcup uses an XML-RPC style API (JSON-RPC), different from REST.
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


# Netcup status mapping
NETCUP_STATUS_MAP = {
    "online": InstanceStatus.RUNNING,
    "offline": InstanceStatus.STOPPED,
    "installing": InstanceStatus.PROVISIONING,
}

# Netcup pricing (EUR/month)
NETCUP_PRICES_EUR = {
    # Root Server (VPS)
    "RS 1000 G10": 7.99,
    "RS 2000 G10": 11.99,
    "RS 4000 G10": 17.99,
    "RS 8000 G10": 26.99,
    # VPS
    "VPS 1000 G10": 4.99,
    "VPS 2000 G10": 7.99,
    "VPS 3000 G10": 11.99,
    "VPS 4000 G10": 17.99,
}

EUR_TO_USD = 1.10


@register_provider
class NetcupProvider(WOPRProviderInterface):
    """
    Netcup provider adapter.

    Features:
    - Excellent value German hosting
    - Eco-friendly datacenter (Nuremberg)
    - No overselling
    - GDPR compliant
    - Good peering
    """

    PROVIDER_ID = "netcup"
    PROVIDER_NAME = "Netcup"
    PROVIDER_WEBSITE = "https://www.netcup.de"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = False  # Uses custom image install
    SUPPORTS_SSH_KEYS = True

    API_ENDPOINT = "https://www.servercontrolpanel.de/SCP/WSEndUser"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize Netcup provider.

        Args:
            api_token: Netcup API password
            customer_id: Netcup customer number
            api_key: Netcup API key
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "netcup",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_password = api_token
        self.customer_id = kwargs.get("customer_id", "")
        self.api_key = kwargs.get("api_key", "")

        if not self.customer_id or not self.api_key:
            raise ProviderError(
                "netcup",
                "customer_id and api_key are required"
            )

        self.client = httpx.Client(timeout=30.0)
        self._session_id: Optional[str] = None
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate Netcup credentials via login."""
        try:
            # Netcup uses JSON-RPC style API
            payload = {
                "action": "login",
                "param": {
                    "customernumber": self.customer_id,
                    "apikey": self.api_key,
                    "apipassword": self.api_password,
                }
            }
            response = self.client.post(
                self.API_ENDPOINT,
                json=payload,
            )
            data = response.json()

            if data.get("status") != "success":
                raise ProviderAuthError(
                    "netcup",
                    data.get("longmessage", "Login failed")
                )

            self._session_id = data.get("responsedata", {}).get("apisessionid")

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("netcup", f"Connection error: {e}")

    def _make_request(self, action: str, params: Dict = None) -> Dict[str, Any]:
        """Make an authenticated API request."""
        if not self._session_id:
            self._validate_credentials()

        try:
            payload = {
                "action": action,
                "param": {
                    "customernumber": self.customer_id,
                    "apikey": self.api_key,
                    "apisessionid": self._session_id,
                    **(params or {})
                }
            }

            response = self.client.post(self.API_ENDPOINT, json=payload)
            data = response.json()

            if data.get("status") != "success":
                raise ProviderError(
                    "netcup",
                    data.get("longmessage", "API request failed")
                )

            return data.get("responsedata", {})

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("netcup", f"API error: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available Netcup plans."""
        # Netcup plans are product-based, return known plans
        plans_data = [
            {"id": "VPS1000", "name": "VPS 1000 G10", "cpu": 2, "ram": 4, "disk": 80},
            {"id": "VPS2000", "name": "VPS 2000 G10", "cpu": 4, "ram": 8, "disk": 160},
            {"id": "VPS3000", "name": "VPS 3000 G10", "cpu": 6, "ram": 12, "disk": 240},
            {"id": "VPS4000", "name": "VPS 4000 G10", "cpu": 8, "ram": 16, "disk": 320},
            {"id": "RS1000", "name": "RS 1000 G10", "cpu": 2, "ram": 8, "disk": 120},
            {"id": "RS2000", "name": "RS 2000 G10", "cpu": 4, "ram": 16, "disk": 240},
        ]

        plans = []
        for p in plans_data:
            price_eur = NETCUP_PRICES_EUR.get(p["name"], 10.0)
            price_usd = price_eur * EUR_TO_USD

            plan = Plan(
                id=p["id"],
                name=p["name"],
                cpu=p["cpu"],
                ram_gb=p["ram"],
                disk_gb=p["disk"],
                bandwidth_tb=None,  # Included in plan
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
        """List available Netcup regions."""
        # Netcup primarily operates from Nuremberg, Germany
        return [
            Region(
                id="nuremberg",
                name="Nuremberg",
                country="DE",
                city="Nuremberg",
                available=True,
                features=["ipv6", "ddos-protection"],
            ),
        ]

    # =========================================
    # INSTANCE OPERATIONS (STUB)
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new Netcup instance."""
        raise ProviderError("netcup", "Full provisioning not yet implemented - stub only")

    def destroy(self, instance_id: str) -> bool:
        """Destroy a Netcup instance."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List instances."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get instance status."""
        return InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start instance."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def stop(self, instance_id: str) -> bool:
        """Stop instance."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def reboot(self, instance_id: str) -> bool:
        """Reboot instance."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add SSH key."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove SSH key."""
        raise ProviderError("netcup", "Not yet implemented - stub only")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
