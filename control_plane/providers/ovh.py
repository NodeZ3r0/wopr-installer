"""
WOPR OVHcloud Provider Adapter
==============================

OVHcloud integration via Apache Libcloud.

OVHcloud offers:
- Strong EU presence and compliance
- Competitive pricing
- Free DDoS protection
- Unmetered bandwidth on many plans

Requires: pip install apache-libcloud
"""

from typing import List, Optional, Dict, Any
from .libcloud_base import LibcloudBaseProvider, LIBCLOUD_AVAILABLE
from .base import Plan, Region, ProvisionConfig, ProviderError
from .registry import register_provider

if LIBCLOUD_AVAILABLE:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.base import NodeImage


# OVH pricing (approximate EUR/month, converted to USD)
OVH_PRICES_EUR = {
    "d2-2": 3.50,
    "d2-4": 6.50,
    "d2-8": 13.00,
    "b2-7": 26.00,
    "b2-15": 52.00,
    "b2-30": 104.00,
    "b2-60": 208.00,
    "b2-120": 416.00,
}

EUR_TO_USD = 1.10


@register_provider
class OVHProvider(LibcloudBaseProvider):
    """
    OVHcloud provider adapter.

    Features:
    - Strong EU data sovereignty
    - Free always-on DDoS mitigation
    - Unmetered bandwidth on many plans
    - Good for EU compliance requirements
    """

    PROVIDER_ID = "ovh"
    PROVIDER_NAME = "OVHcloud"
    PROVIDER_WEBSITE = "https://www.ovhcloud.com"
    LIBCLOUD_PROVIDER = LibcloudProvider.OPENSTACK if LIBCLOUD_AVAILABLE else None

    # OVH uses OpenStack, needs additional config
    OVH_AUTH_URL = "https://auth.cloud.ovh.net/v3"

    def __init__(self, api_token: str, **kwargs):
        """
        Initialize OVH provider.

        Args:
            api_token: OVH application key
            project_id: OVH project/tenant ID (required)
            region: OVH region (e.g., 'GRA11', 'SBG5')
        """
        self.project_id = kwargs.get("project_id", "")
        self.ovh_region = kwargs.get("region", "GRA11")

        if not self.project_id:
            raise ProviderError("ovh", "project_id is required for OVH")

        super().__init__(api_token, **kwargs)

    def _build_customer_tags(self, config: ProvisionConfig) -> Dict[str, Any]:
        """Build OVH/OpenStack metadata for customer identity."""
        # OpenStack supports instance metadata as key-value pairs via ex_metadata
        metadata = {"managed_by": "wopr-systems"}
        if config.wopr_bundle:
            metadata["wopr_bundle"] = config.wopr_bundle
        if config.wopr_customer_id:
            metadata["wopr_customer"] = config.wopr_customer_id
        if config.wopr_customer_email:
            metadata["wopr_email"] = config.wopr_customer_email
        if config.wopr_customer_name:
            metadata["wopr_name"] = config.wopr_customer_name
        return {"ex_metadata": metadata}

    def _create_driver(self, driver_cls):
        """Create OVH driver (OpenStack-based)."""
        return driver_cls(
            self.project_id,  # username/tenant
            self.api_token,   # password/key
            ex_force_auth_url=self.OVH_AUTH_URL,
            ex_force_auth_version="3.x_password",
            ex_tenant_name=self.project_id,
            ex_force_service_region=self.ovh_region,
        )

    def _get_plan_price(self, size) -> float:
        """Get OVH plan price."""
        # Try lookup
        if size.id in OVH_PRICES_EUR:
            return OVH_PRICES_EUR[size.id] * EUR_TO_USD

        # Estimate based on RAM
        ram_gb = size.ram / 1024 if size.ram else 0
        return max(4.0, ram_gb * 4) * EUR_TO_USD

    def _get_image(self, image_name: str) -> Optional[NodeImage]:
        """Get OVH image."""
        image_map = {
            "debian-12": "Debian 12",
            "ubuntu-22.04": "Ubuntu 22.04",
            "ubuntu-24.04": "Ubuntu 24.04",
        }

        search_name = image_map.get(image_name, image_name)

        for image in self.driver.list_images():
            if search_name.lower() in image.name.lower():
                return image

        return None

    def list_regions(self) -> List[Region]:
        """List OVH regions."""
        # OVH regions are fixed - the driver doesn't list them well
        ovh_regions = [
            Region(id="GRA11", name="Gravelines", country="FR", city="Gravelines"),
            Region(id="SBG5", name="Strasbourg", country="FR", city="Strasbourg"),
            Region(id="BHS5", name="Beauharnois", country="CA", city="Beauharnois"),
            Region(id="WAW1", name="Warsaw", country="PL", city="Warsaw"),
            Region(id="DE1", name="Frankfurt", country="DE", city="Frankfurt"),
            Region(id="UK1", name="London", country="UK", city="London"),
            Region(id="SGP1", name="Singapore", country="SG", city="Singapore"),
            Region(id="SYD1", name="Sydney", country="AU", city="Sydney"),
        ]
        return ovh_regions

    def list_plans(self, tier=None) -> List[Plan]:
        """List OVH flavors."""
        sizes = self.driver.list_sizes()
        plans = []

        for size in sizes:
            cpu = size.extra.get("vcpus", 1) if hasattr(size, "extra") else 1
            ram_gb = size.ram / 1024 if size.ram else 0

            plan = Plan(
                id=size.id,
                name=size.name,
                cpu=cpu,
                ram_gb=int(ram_gb),
                disk_gb=size.disk or 0,
                bandwidth_tb=None,  # OVH has unmetered on many plans
                price_monthly_usd=self._get_plan_price(size),
                provider=self.PROVIDER_ID,
            )

            if tier is None or plan.meets_tier(tier):
                plans.append(plan)

        return sorted(plans, key=lambda p: p.price_monthly_usd)
