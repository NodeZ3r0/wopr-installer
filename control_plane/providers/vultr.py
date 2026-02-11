"""
WOPR Vultr Provider Adapter
===========================

Vultr integration via Apache Libcloud.

Vultr offers:
- 32+ datacenter locations worldwide
- Competitive pricing starting at $2.50/mo
- Fast provisioning
- Good global coverage for mesh distribution

Requires: pip install apache-libcloud
"""

from typing import List, Optional
from .libcloud_base import LibcloudBaseProvider, LIBCLOUD_AVAILABLE
from .base import Plan, ProviderError
from .registry import register_provider

if LIBCLOUD_AVAILABLE:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.base import NodeImage


# Vultr pricing (approximate USD/month)
VULTR_PRICES = {
    "vc2-1c-1gb": 5.00,
    "vc2-1c-2gb": 10.00,
    "vc2-2c-4gb": 20.00,
    "vc2-4c-8gb": 40.00,
    "vc2-6c-16gb": 80.00,
    "vc2-8c-32gb": 160.00,
    "vc2-16c-64gb": 320.00,
    "vc2-24c-96gb": 640.00,
}


@register_provider
class VultrProvider(LibcloudBaseProvider):
    """
    Vultr provider adapter.

    Features:
    - 32+ global datacenters
    - Hourly billing
    - Fast provisioning
    - Good for geographic distribution
    """

    PROVIDER_ID = "vultr"
    PROVIDER_NAME = "Vultr"
    PROVIDER_WEBSITE = "https://www.vultr.com"
    LIBCLOUD_PROVIDER = LibcloudProvider.VULTR if LIBCLOUD_AVAILABLE else None

    def _create_driver(self, driver_cls):
        """Create Vultr driver."""
        return driver_cls(self.api_token)

    def _get_plan_price(self, size) -> float:
        """Get Vultr plan price."""
        # Try to match by ID first
        if size.id in VULTR_PRICES:
            return VULTR_PRICES[size.id]

        # Estimate based on resources
        ram_gb = size.ram / 1024 if size.ram else 0
        estimated = ram_gb * 5  # ~$5/GB RAM rough estimate
        return max(5.0, estimated)

    def _get_image(self, image_name: str) -> Optional[NodeImage]:
        """Get Vultr image."""
        image_map = {
            "debian-12": "Debian 12 x64",
            "ubuntu-22.04": "Ubuntu 22.04 LTS x64",
            "ubuntu-24.04": "Ubuntu 24.04 LTS x64",
        }

        search_name = image_map.get(image_name, image_name)

        for image in self.driver.list_images():
            if search_name.lower() in image.name.lower():
                return image

        return None

    def list_plans(self, tier=None) -> List[Plan]:
        """List Vultr plans with accurate CPU info."""
        sizes = self.driver.list_sizes()
        plans = []

        for size in sizes:
            # Parse Vultr size name for CPU count (e.g., "vc2-2c-4gb")
            cpu = 1
            if hasattr(size, "extra") and "vcpu_count" in size.extra:
                cpu = size.extra["vcpu_count"]
            elif "-" in size.id:
                parts = size.id.split("-")
                for part in parts:
                    if part.endswith("c") and part[:-1].isdigit():
                        cpu = int(part[:-1])
                        break

            ram_gb = size.ram / 1024 if size.ram else 0

            plan = Plan(
                id=size.id,
                name=size.name,
                cpu=cpu,
                ram_gb=int(ram_gb),
                disk_gb=size.disk or 0,
                bandwidth_tb=size.bandwidth / 1024 if size.bandwidth else None,
                price_monthly_usd=self._get_plan_price(size),
                provider=self.PROVIDER_ID,
            )

            if tier is None or plan.meets_tier(tier):
                plans.append(plan)

        return sorted(plans, key=lambda p: p.price_monthly_usd)
