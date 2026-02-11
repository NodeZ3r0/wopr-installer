"""
WOPR UpCloud Provider Adapter
==============================

UpCloud integration using direct REST API calls via httpx.

UpCloud is NOT in Apache Libcloud, so this adapter uses their REST API directly.
UpCloud offers excellent performance with their MaxIOPS storage technology.

API Docs: https://developers.upcloud.com/
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
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


# Mapping of UpCloud server statuses to WOPR statuses
UPCLOUD_STATUS_MAP = {
    "started": InstanceStatus.RUNNING,
    "stopped": InstanceStatus.STOPPED,
    "maintenance": InstanceStatus.PROVISIONING,
    "error": InstanceStatus.ERROR,
}


# UpCloud plan pricing (USD, approximate monthly)
UPCLOUD_PRICES = {
    "1xCPU-2GB": 13.00,
    "2xCPU-4GB": 29.00,
    "4xCPU-8GB": 57.00,
    "6xCPU-16GB": 106.00,
    "8xCPU-32GB": 210.00,
}


# UpCloud image mapping
UPCLOUD_IMAGES = {
    "debian-12": "Debian GNU/Linux 12 (Bookworm)",
    "ubuntu-22.04": "Ubuntu Server 22.04 LTS (Jammy Jellyfish)",
    "ubuntu-24.04": "Ubuntu Server 24.04 LTS (Noble Numbat)",
}


@register_provider
class UpCloudProvider(WOPRProviderInterface):
    """
    UpCloud provider adapter using REST API.

    Features:
    - MaxIOPS storage technology
    - US datacenters (Chicago, New York)
    - IPv6 support
    - Hourly billing
    - Cloud-init support
    """

    PROVIDER_ID = "upcloud"
    PROVIDER_NAME = "UpCloud"
    PROVIDER_WEBSITE = "https://upcloud.com"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = True
    SUPPORTS_SSH_KEYS = True

    API_BASE_URL = "https://api.upcloud.com/1.3"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize UpCloud provider.

        Args:
            api_token: UpCloud credentials in "username:password" format
        """
        if not HTTPX_AVAILABLE:
            raise ProviderError(
                "upcloud",
                "httpx not installed. Run: pip install httpx"
            )

        self.api_token = api_token
        self.username, self.password = self._parse_credentials(api_token)
        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            auth=(self.username, self.password),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        self._validate_credentials()

    def _parse_credentials(self, api_token: str) -> tuple:
        """Parse username:password from api_token."""
        if ":" not in api_token:
            raise ProviderAuthError(
                "upcloud",
                "API token must be in 'username:password' format"
            )
        parts = api_token.split(":", 1)
        return parts[0], parts[1]

    def _validate_credentials(self) -> None:
        """Validate UpCloud credentials."""
        try:
            response = self.client.get("/account")
            if response.status_code == 401:
                raise ProviderAuthError(
                    "upcloud",
                    "Invalid credentials"
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderAuthError(
                    "upcloud",
                    "Invalid API credentials"
                )
            raise ProviderError(
                "upcloud",
                f"API error during validation: {e}"
            )
        except Exception as e:
            raise ProviderError(
                "upcloud",
                f"Connection error: {e}"
            )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated API request."""
        try:
            response = self.client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
            )

            if response.status_code == 401:
                raise ProviderAuthError("upcloud", "Authentication failed")

            if response.status_code == 404:
                raise ProviderResourceError("upcloud", f"Resource not found: {endpoint}")

            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("error_message", error_msg)
            except Exception:
                pass
            raise ProviderError("upcloud", f"API error: {error_msg}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Request failed: {e}")

    # =========================================
    # PLAN MANAGEMENT
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """List available UpCloud server plans."""
        try:
            response = self._make_request("GET", "/plan")
            plans_data = response.get("plans", {}).get("plan", [])

            plans = []
            for plan_data in plans_data:
                plan_id = plan_data.get("name", "")

                # Parse plan name (e.g., "1xCPU-2GB")
                cores = plan_data.get("core_number", 0)
                memory_mb = plan_data.get("memory_amount", 0)
                memory_gb = memory_mb // 1024
                storage_gb = plan_data.get("storage_size", 0)

                # Get price from our mapping or calculate approximate
                price_monthly = UPCLOUD_PRICES.get(plan_id, cores * 10 + memory_gb * 5)

                plan = Plan(
                    id=plan_id,
                    name=plan_id,
                    cpu=cores,
                    ram_gb=memory_gb,
                    disk_gb=storage_gb,
                    bandwidth_tb=None,  # UpCloud charges separately for traffic
                    price_monthly_usd=price_monthly,
                    price_hourly_usd=round(price_monthly / 730, 4),
                    provider=self.PROVIDER_ID,
                    available_regions=self._get_available_zones(),
                )

                # Filter by tier if specified
                if tier is None or plan.meets_tier(tier):
                    plans.append(plan)

            return sorted(plans, key=lambda p: p.price_monthly_usd)

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to list plans: {e}")

    def _get_available_zones(self) -> List[str]:
        """Get list of available zone IDs."""
        try:
            response = self._make_request("GET", "/zone")
            zones_data = response.get("zones", {}).get("zone", [])
            return [zone.get("id", "") for zone in zones_data]
        except Exception:
            return []

    # =========================================
    # REGION MANAGEMENT
    # =========================================

    def list_regions(self) -> List[Region]:
        """List available UpCloud zones."""
        try:
            response = self._make_request("GET", "/zone")
            zones_data = response.get("zones", {}).get("zone", [])

            regions = []
            for zone in zones_data:
                zone_id = zone.get("id", "")
                description = zone.get("description", zone_id)

                # Parse country and city from zone ID
                # Examples: us-chi1 (Chicago), us-nyc1 (New York)
                country = "US"
                city = None

                if zone_id.startswith("us-chi"):
                    city = "Chicago"
                elif zone_id.startswith("us-nyc"):
                    city = "New York"
                elif zone_id.startswith("fi-"):
                    country = "FI"
                    city = "Helsinki"
                elif zone_id.startswith("de-"):
                    country = "DE"
                    city = "Frankfurt"
                elif zone_id.startswith("nl-"):
                    country = "NL"
                    city = "Amsterdam"
                elif zone_id.startswith("sg-"):
                    country = "SG"
                    city = "Singapore"
                elif zone_id.startswith("uk-"):
                    country = "GB"
                    city = "London"
                elif zone_id.startswith("es-"):
                    country = "ES"
                    city = "Madrid"
                elif zone_id.startswith("au-"):
                    country = "AU"
                    city = "Sydney"
                elif zone_id.startswith("pl-"):
                    country = "PL"
                    city = "Warsaw"

                regions.append(Region(
                    id=zone_id,
                    name=description,
                    country=country,
                    city=city,
                    available=True,
                    features=["ipv6", "cloud-init", "snapshots", "maxiops"],
                ))

            return regions

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to list regions: {e}")

    # =========================================
    # INSTANCE PROVISIONING
    # =========================================

    def provision(self, config: ProvisionConfig) -> Instance:
        """Provision a new UpCloud server."""
        try:
            # Get storage image
            image_name = UPCLOUD_IMAGES.get(config.image, config.image)

            # Build server request
            server_data = {
                "server": {
                    "zone": config.region,
                    "title": config.name,
                    "hostname": config.name,
                    "plan": config.plan_id,
                    "storage_devices": {
                        "storage_device": [
                            {
                                "action": "clone",
                                "storage": image_name,
                                "title": f"{config.name}-disk",
                                "size": 40,  # Default 40GB, plan determines actual size
                                "tier": "maxiops",
                            }
                        ]
                    },
                    "login_user": {
                        "create_password": "no",
                        "username": "root",
                    },
                }
            }

            # Add SSH keys if provided
            if config.ssh_keys:
                ssh_keys_list = []
                for key in config.ssh_keys:
                    # Try to find key by name or ID
                    existing_keys = self.list_ssh_keys()
                    for existing_key in existing_keys:
                        if existing_key["id"] == key or existing_key["name"] == key:
                            ssh_keys_list.append(key)
                            break

                if ssh_keys_list:
                    server_data["server"]["login_user"]["ssh_keys"] = {
                        "ssh_key": ssh_keys_list
                    }

            # Add user_data (cloud-init) if provided
            if config.user_data:
                # UpCloud supports user_data in storage device
                server_data["server"]["storage_devices"]["storage_device"][0]["user_data"] = config.user_data

            # Add metadata/tags with customer identity
            metadata = {"managed-by": "wopr-systems"}
            for tag in config.tags:
                if ":" in tag:
                    key, value = tag.split(":", 1)
                    metadata[key] = value
                else:
                    metadata[tag] = "true"

            if config.wopr_customer_id:
                metadata["wopr-customer"] = config.wopr_customer_id
            if config.wopr_bundle:
                metadata["wopr-bundle"] = config.wopr_bundle
            if config.wopr_customer_email:
                metadata["wopr-email"] = config.wopr_customer_email
            if config.wopr_customer_name:
                metadata["wopr-name"] = config.wopr_customer_name
                # Include customer name in server title for dashboard visibility
                server_data["server"]["title"] = f"{config.name} ({config.wopr_customer_name})"

            # UpCloud uses metadata field — enable metadata service
            if metadata:
                server_data["server"]["metadata"] = "yes"

            # UpCloud labels (key-value pairs for filtering)
            labels = []
            for k, v in metadata.items():
                labels.append({"key": k, "value": str(v)[:255]})
            if labels:
                server_data["server"]["labels"] = {"label": labels}

            # Create server
            response = self._make_request("POST", "/server", data=server_data)
            server = response.get("server", {})

            # Extract instance information
            server_uuid = server.get("uuid", "")
            state = server.get("state", "maintenance")

            # Get IP addresses
            ip_address = None
            ipv6_address = None

            ip_addresses = server.get("ip_addresses", {}).get("ip_address", [])
            for ip in ip_addresses:
                if ip.get("family") == "IPv4" and ip.get("access") == "public":
                    ip_address = ip.get("address")
                elif ip.get("family") == "IPv6" and ip.get("access") == "public":
                    ipv6_address = ip.get("address")

            return Instance(
                id=server_uuid,
                provider=self.PROVIDER_ID,
                name=config.name,
                status=UPCLOUD_STATUS_MAP.get(state, InstanceStatus.PROVISIONING),
                region=config.region,
                plan=config.plan_id,
                ip_address=ip_address,
                ipv6_address=ipv6_address,
                created_at=datetime.now(),
                wopr_instance_id=config.metadata.get("wopr_instance_id"),
                metadata=metadata,
            )

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to provision server: {e}")

    def destroy(self, instance_id: str) -> bool:
        """Destroy an UpCloud server."""
        try:
            # First stop the server if it's running
            try:
                instance = self.get_instance(instance_id)
                if instance and instance.status == InstanceStatus.RUNNING:
                    self.stop(instance_id)
                    # Wait a bit for server to stop
                    time.sleep(5)
            except Exception:
                pass

            # Delete the server
            self._make_request("DELETE", f"/server/{instance_id}?storages=1")
            return True

        except ProviderResourceError:
            # Already deleted
            return True
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to destroy server: {e}")

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get an UpCloud server by UUID."""
        try:
            response = self._make_request("GET", f"/server/{instance_id}")
            server = response.get("server", {})

            if not server:
                return None

            # Parse server data
            state = server.get("state", "unknown")
            zone = server.get("zone", "")
            plan = server.get("plan", "")
            title = server.get("title", "")

            # Get IP addresses
            ip_address = None
            ipv6_address = None

            ip_addresses = server.get("ip_addresses", {}).get("ip_address", [])
            for ip in ip_addresses:
                if ip.get("family") == "IPv4" and ip.get("access") == "public":
                    ip_address = ip.get("address")
                elif ip.get("family") == "IPv6" and ip.get("access") == "public":
                    ipv6_address = ip.get("address")

            return Instance(
                id=instance_id,
                provider=self.PROVIDER_ID,
                name=title,
                status=UPCLOUD_STATUS_MAP.get(state, InstanceStatus.UNKNOWN),
                region=zone,
                plan=plan,
                ip_address=ip_address,
                ipv6_address=ipv6_address,
                created_at=None,
                metadata={},
            )

        except ProviderResourceError:
            return None
        except Exception:
            return None

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List all UpCloud servers."""
        try:
            response = self._make_request("GET", "/server")
            servers_data = response.get("servers", {}).get("server", [])

            instances = []
            for server in servers_data:
                server_uuid = server.get("uuid", "")

                # Get full server details
                instance = self.get_instance(server_uuid)
                if instance:
                    # Filter by tags if provided
                    # UpCloud doesn't have built-in tag filtering, so we do it client-side
                    if tags:
                        # Check if server matches all tags
                        match = True
                        for tag in tags:
                            if ":" in tag:
                                key, value = tag.split(":", 1)
                                if instance.metadata.get(key) != value:
                                    match = False
                                    break
                            else:
                                if tag not in instance.metadata:
                                    match = False
                                    break

                        if match:
                            instances.append(instance)
                    else:
                        instances.append(instance)

            return instances

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to list servers: {e}")

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get status of an UpCloud server."""
        instance = self.get_instance(instance_id)
        return instance.status if instance else InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Start an UpCloud server."""
        try:
            self._make_request("POST", f"/server/{instance_id}/start")
            return True
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to start server: {e}")

    def stop(self, instance_id: str) -> bool:
        """Stop an UpCloud server."""
        try:
            data = {"stop_server": {"stop_type": "soft", "timeout": 60}}
            self._make_request("POST", f"/server/{instance_id}/stop", data=data)
            return True
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to stop server: {e}")

    def reboot(self, instance_id: str) -> bool:
        """Reboot an UpCloud server."""
        try:
            self._make_request("POST", f"/server/{instance_id}/restart")
            return True
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to reboot server: {e}")

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List SSH keys in UpCloud account."""
        try:
            response = self._make_request("GET", "/account")
            account_data = response.get("account", {})
            ssh_keys_data = account_data.get("ssh_keys", {}).get("ssh_key", [])

            keys = []
            for key in ssh_keys_data:
                keys.append({
                    "id": key.get("title", ""),
                    "name": key.get("title", ""),
                    "fingerprint": "",  # UpCloud doesn't provide fingerprint in list
                })

            return keys

        except Exception as e:
            raise ProviderError("upcloud", f"Failed to list SSH keys: {e}")

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Add an SSH key to UpCloud account."""
        try:
            # UpCloud manages SSH keys through account settings
            # This is a simplified implementation
            # In practice, keys are added via the web UI or account API
            raise ProviderError(
                "upcloud",
                "Adding SSH keys via API requires account-level permissions. "
                "Please add keys via the UpCloud control panel."
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to add SSH key: {e}")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Remove an SSH key from UpCloud account."""
        try:
            # UpCloud manages SSH keys through account settings
            # This is a simplified implementation
            raise ProviderError(
                "upcloud",
                "Removing SSH keys via API requires account-level permissions. "
                "Please remove keys via the UpCloud control panel."
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("upcloud", f"Failed to remove SSH key: {e}")

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if hasattr(self, 'client'):
            self.client.close()
