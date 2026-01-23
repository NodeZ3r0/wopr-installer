"""
WOPR DigitalOcean Provider Adapter
==================================

DigitalOcean integration via Apache Libcloud.

DigitalOcean offers:
- Excellent developer experience
- Well-documented API
- Managed services (if needed later)
- Good US/EU coverage

Requires: pip install apache-libcloud
"""

from typing import List, Optional
from .libcloud_base import LibcloudBaseProvider, LIBCLOUD_AVAILABLE
from .base import Plan, ProviderError
from .registry import register_provider

if LIBCLOUD_AVAILABLE:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.base import NodeImage


# DigitalOcean pricing (USD/month)
DO_PRICES = {
    "s-1vcpu-512mb-10gb": 4.00,
    "s-1vcpu-1gb": 6.00,
    "s-1vcpu-2gb": 12.00,
    "s-2vcpu-2gb": 18.00,
    "s-2vcpu-4gb": 24.00,
    "s-4vcpu-8gb": 48.00,
    "s-8vcpu-16gb": 96.00,
    "s-8vcpu-32gb": 192.00,
    "s-16vcpu-64gb": 384.00,
}


@register_provider
class DigitalOceanProvider(LibcloudBaseProvider):
    """
    DigitalOcean provider adapter.

    Features:
    - Clean API and great documentation
    - Predictable pricing
    - Good developer experience
    - Kubernetes/managed services available
    """

    PROVIDER_ID = "digitalocean"
    PROVIDER_NAME = "DigitalOcean"
    PROVIDER_WEBSITE = "https://www.digitalocean.com"
    LIBCLOUD_PROVIDER = LibcloudProvider.DIGITAL_OCEAN if LIBCLOUD_AVAILABLE else None

    def _create_driver(self, driver_cls):
        """Create DigitalOcean driver."""
        return driver_cls(self.api_token, api_version="v2")

    def _get_plan_price(self, size) -> float:
        """Get DigitalOcean plan price."""
        # DigitalOcean provides price in size.price
        if hasattr(size, "price") and size.price:
            return float(size.price)

        # Try lookup
        if size.id in DO_PRICES:
            return DO_PRICES[size.id]

        # Estimate
        ram_gb = size.ram / 1024 if size.ram else 0
        return max(4.0, ram_gb * 6)

    def _get_image(self, image_name: str) -> Optional[NodeImage]:
        """Get DigitalOcean image."""
        image_map = {
            "debian-12": "debian-12-x64",
            "ubuntu-22.04": "ubuntu-22-04-x64",
            "ubuntu-24.04": "ubuntu-24-04-x64",
        }

        search_slug = image_map.get(image_name, image_name)

        for image in self.driver.list_images():
            # DigitalOcean images have slugs
            if hasattr(image, "extra") and image.extra.get("slug") == search_slug:
                return image
            if search_slug in image.id or search_slug in image.name.lower():
                return image

        return None

    def list_plans(self, tier=None) -> List[Plan]:
        """List DigitalOcean droplet sizes."""
        sizes = self.driver.list_sizes()
        plans = []

        for size in sizes:
            # Parse size slug for CPU (e.g., "s-2vcpu-4gb")
            cpu = 1
            if hasattr(size, "extra") and "vcpus" in size.extra:
                cpu = size.extra["vcpus"]
            elif "vcpu" in size.id:
                parts = size.id.split("-")
                for part in parts:
                    if "vcpu" in part:
                        cpu_str = part.replace("vcpu", "")
                        if cpu_str.isdigit():
                            cpu = int(cpu_str)
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
