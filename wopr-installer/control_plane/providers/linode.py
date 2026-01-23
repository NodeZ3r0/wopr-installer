"""
WOPR Linode (Akamai) Provider Adapter
=====================================

Linode integration via Apache Libcloud.

Linode (now part of Akamai) offers:
- Predictable billing
- Enterprise reliability
- Large global footprint via Akamai
- Good documentation

Requires: pip install apache-libcloud
"""

from typing import List, Optional
from .libcloud_base import LibcloudBaseProvider, LIBCLOUD_AVAILABLE
from .base import Plan, ProviderError
from .registry import register_provider

if LIBCLOUD_AVAILABLE:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.base import NodeImage


# Linode pricing (USD/month)
LINODE_PRICES = {
    "g6-nanode-1": 5.00,
    "g6-standard-1": 10.00,
    "g6-standard-2": 20.00,
    "g6-standard-4": 40.00,
    "g6-standard-6": 80.00,
    "g6-standard-8": 160.00,
    "g6-standard-16": 320.00,
    "g6-standard-20": 400.00,
    "g6-standard-24": 480.00,
    "g6-standard-32": 640.00,
}


@register_provider
class LinodeProvider(LibcloudBaseProvider):
    """
    Linode (Akamai Cloud) provider adapter.

    Features:
    - Part of Akamai network
    - Predictable pricing
    - Good stability track record
    - Large datacenter footprint
    """

    PROVIDER_ID = "linode"
    PROVIDER_NAME = "Linode (Akamai)"
    PROVIDER_WEBSITE = "https://www.linode.com"
    LIBCLOUD_PROVIDER = LibcloudProvider.LINODE if LIBCLOUD_AVAILABLE else None

    def _create_driver(self, driver_cls):
        """Create Linode driver."""
        return driver_cls(self.api_token)

    def _get_plan_price(self, size) -> float:
        """Get Linode plan price."""
        # Linode provides price
        if hasattr(size, "price") and size.price:
            return float(size.price)

        # Try lookup
        if size.id in LINODE_PRICES:
            return LINODE_PRICES[size.id]

        # Estimate based on RAM
        ram_gb = size.ram / 1024 if size.ram else 0
        return max(5.0, ram_gb * 5)

    def _get_image(self, image_name: str) -> Optional[NodeImage]:
        """Get Linode image."""
        image_map = {
            "debian-12": "linode/debian12",
            "ubuntu-22.04": "linode/ubuntu22.04",
            "ubuntu-24.04": "linode/ubuntu24.04",
        }

        search_id = image_map.get(image_name, image_name)

        for image in self.driver.list_images():
            if image.id == search_id:
                return image
            if search_id in image.id or search_id in image.name.lower():
                return image

        return None

    def list_plans(self, tier=None) -> List[Plan]:
        """List Linode plans."""
        sizes = self.driver.list_sizes()
        plans = []

        for size in sizes:
            # Linode sizes have vcpus in extra
            cpu = 1
            if hasattr(size, "extra"):
                cpu = size.extra.get("vcpus", 1)

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
