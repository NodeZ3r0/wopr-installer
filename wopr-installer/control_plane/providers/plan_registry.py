"""
WOPR Plan Registry
==================

Centralized registry mapping VPS provider plans to WOPR resource tiers.
Organized by geographic region with US market focus.

This ensures:
- Consistent plan selection across providers
- No vendor lock-in (multiple options per region)
- User choice based on location preference

Updated: January 2026
Target Market: USA (v1.0)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from .base import ResourceTier, Plan


class GeoRegion(Enum):
    """Geographic regions for datacenter selection."""
    # USA Regions
    US_WEST = "us-west"           # California, Oregon, Washington
    US_CENTRAL = "us-central"     # Texas, Illinois, Colorado
    US_EAST = "us-east"           # New York, New Jersey, Virginia, Georgia

    # International (available but not primary focus for v1)
    CANADA = "canada"
    EUROPE_WEST = "europe-west"   # UK, Netherlands, Germany, France
    ASIA_PACIFIC = "asia-pacific" # Singapore, Tokyo, Sydney


@dataclass
class Datacenter:
    """Represents a provider's datacenter location."""
    id: str                       # Provider's region/location ID
    name: str                     # Human-readable name
    city: str
    state_country: str
    geo_region: GeoRegion
    latency_from_us_ms: int = 0   # Approximate latency from central US


@dataclass
class RecommendedPlan:
    """A recommended plan for a specific provider and tier."""
    provider: str
    plan_id: str
    plan_name: str
    tier: ResourceTier
    cpu: int
    ram_gb: int
    disk_gb: int
    price_monthly_usd: float
    bandwidth_tb: Optional[float] = None
    notes: str = ""


@dataclass
class ProviderProfile:
    """Complete profile of a VPS provider for WOPR."""
    id: str
    name: str
    website: str
    datacenters: List[Datacenter]
    plans: Dict[ResourceTier, RecommendedPlan]
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    signup_url: str = ""
    api_docs_url: str = ""


# ============================================
# PROVIDER PROFILES WITH US DATACENTERS
# ============================================

HETZNER_PROFILE = ProviderProfile(
    id="hetzner",
    name="Hetzner Cloud",
    website="https://www.hetzner.com/cloud",
    signup_url="https://accounts.hetzner.com/signUp",
    api_docs_url="https://docs.hetzner.cloud/",
    datacenters=[
        Datacenter(
            id="ash",
            name="Ashburn, VA",
            city="Ashburn",
            state_country="Virginia, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=20
        ),
        Datacenter(
            id="hil",
            name="Hillsboro, OR",
            city="Hillsboro",
            state_country="Oregon, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=50
        ),
    ],
    plans={
        ResourceTier.LOW: RecommendedPlan(
            provider="hetzner",
            plan_id="cpx11",
            plan_name="CPX11",
            tier=ResourceTier.LOW,
            cpu=2,
            ram_gb=2,
            disk_gb=40,
            price_monthly_usd=4.49,
            bandwidth_tb=20.0,
            notes="AMD EPYC, NVMe SSD, 20TB traffic included"
        ),
        ResourceTier.MEDIUM: RecommendedPlan(
            provider="hetzner",
            plan_id="cpx21",
            plan_name="CPX21",
            tier=ResourceTier.MEDIUM,
            cpu=3,
            ram_gb=4,
            disk_gb=80,
            price_monthly_usd=8.49,
            bandwidth_tb=20.0,
            notes="AMD EPYC, good for creator/developer bundles"
        ),
        ResourceTier.HIGH: RecommendedPlan(
            provider="hetzner",
            plan_id="cpx31",
            plan_name="CPX31",
            tier=ResourceTier.HIGH,
            cpu=4,
            ram_gb=8,
            disk_gb=160,
            price_monthly_usd=15.99,
            bandwidth_tb=20.0,
            notes="AMD EPYC, professional bundle capable"
        ),
        ResourceTier.VERY_HIGH: RecommendedPlan(
            provider="hetzner",
            plan_id="cpx41",
            plan_name="CPX41",
            tier=ResourceTier.VERY_HIGH,
            cpu=8,
            ram_gb=16,
            disk_gb=240,
            price_monthly_usd=29.99,
            bandwidth_tb=20.0,
            notes="AMD EPYC, high workloads"
        ),
    },
    pros=[
        "Best price/performance ratio",
        "20TB traffic included",
        "Fast NVMe storage",
        "US datacenters (Ashburn VA, Hillsboro OR)",
    ],
    cons=[
        "Fewer US locations than competitors",
        "No managed services",
    ],
)

VULTR_PROFILE = ProviderProfile(
    id="vultr",
    name="Vultr",
    website="https://www.vultr.com",
    signup_url="https://www.vultr.com/register/",
    api_docs_url="https://www.vultr.com/api/",
    datacenters=[
        # US West
        Datacenter(
            id="lax",
            name="Los Angeles, CA",
            city="Los Angeles",
            state_country="California, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=30
        ),
        Datacenter(
            id="sjc",
            name="Silicon Valley, CA",
            city="San Jose",
            state_country="California, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=35
        ),
        Datacenter(
            id="sea",
            name="Seattle, WA",
            city="Seattle",
            state_country="Washington, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=45
        ),
        # US Central
        Datacenter(
            id="dfw",
            name="Dallas, TX",
            city="Dallas",
            state_country="Texas, USA",
            geo_region=GeoRegion.US_CENTRAL,
            latency_from_us_ms=15
        ),
        Datacenter(
            id="ord",
            name="Chicago, IL",
            city="Chicago",
            state_country="Illinois, USA",
            geo_region=GeoRegion.US_CENTRAL,
            latency_from_us_ms=20
        ),
        # US East
        Datacenter(
            id="ewr",
            name="New Jersey",
            city="Newark",
            state_country="New Jersey, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=25
        ),
        Datacenter(
            id="atl",
            name="Atlanta, GA",
            city="Atlanta",
            state_country="Georgia, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=20
        ),
        Datacenter(
            id="mia",
            name="Miami, FL",
            city="Miami",
            state_country="Florida, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=30
        ),
    ],
    plans={
        ResourceTier.LOW: RecommendedPlan(
            provider="vultr",
            plan_id="vc2-1c-2gb",
            plan_name="Cloud Compute 2GB",
            tier=ResourceTier.LOW,
            cpu=1,
            ram_gb=2,
            disk_gb=55,
            price_monthly_usd=10.00,
            bandwidth_tb=2.0,
            notes="Entry level, good for light personal use"
        ),
        ResourceTier.MEDIUM: RecommendedPlan(
            provider="vultr",
            plan_id="vc2-2c-4gb",
            plan_name="Cloud Compute 4GB",
            tier=ResourceTier.MEDIUM,
            cpu=2,
            ram_gb=4,
            disk_gb=80,
            price_monthly_usd=20.00,
            bandwidth_tb=3.0,
            notes="Good for creator/developer with moderate workloads"
        ),
        ResourceTier.HIGH: RecommendedPlan(
            provider="vultr",
            plan_id="vc2-4c-8gb",
            plan_name="Cloud Compute 8GB",
            tier=ResourceTier.HIGH,
            cpu=4,
            ram_gb=8,
            disk_gb=160,
            price_monthly_usd=40.00,
            bandwidth_tb=4.0,
            notes="Professional bundle capable"
        ),
        ResourceTier.VERY_HIGH: RecommendedPlan(
            provider="vultr",
            plan_id="vc2-6c-16gb",
            plan_name="Cloud Compute 16GB",
            tier=ResourceTier.VERY_HIGH,
            cpu=6,
            ram_gb=16,
            disk_gb=320,
            price_monthly_usd=80.00,
            bandwidth_tb=5.0,
            notes="Heavy workloads, video conferencing"
        ),
    },
    pros=[
        "8 US datacenter locations",
        "Hourly billing",
        "Fast provisioning",
        "Good for latency-sensitive apps",
    ],
    cons=[
        "Higher price than Hetzner",
        "Bandwidth limits on lower tiers",
    ],
)

DIGITALOCEAN_PROFILE = ProviderProfile(
    id="digitalocean",
    name="DigitalOcean",
    website="https://www.digitalocean.com",
    signup_url="https://cloud.digitalocean.com/registrations/new",
    api_docs_url="https://docs.digitalocean.com/reference/api/",
    datacenters=[
        # US West
        Datacenter(
            id="sfo3",
            name="San Francisco 3",
            city="San Francisco",
            state_country="California, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=35
        ),
        # US East
        Datacenter(
            id="nyc1",
            name="New York 1",
            city="New York",
            state_country="New York, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=25
        ),
        Datacenter(
            id="nyc3",
            name="New York 3",
            city="New York",
            state_country="New York, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=25
        ),
    ],
    plans={
        ResourceTier.LOW: RecommendedPlan(
            provider="digitalocean",
            plan_id="s-1vcpu-2gb",
            plan_name="Basic 2GB",
            tier=ResourceTier.LOW,
            cpu=1,
            ram_gb=2,
            disk_gb=50,
            price_monthly_usd=12.00,
            bandwidth_tb=2.0,
            notes="Minimum viable for personal bundle"
        ),
        ResourceTier.MEDIUM: RecommendedPlan(
            provider="digitalocean",
            plan_id="s-2vcpu-4gb",
            plan_name="Basic 4GB",
            tier=ResourceTier.MEDIUM,
            cpu=2,
            ram_gb=4,
            disk_gb=80,
            price_monthly_usd=24.00,
            bandwidth_tb=4.0,
            notes="Good for creator/developer bundles"
        ),
        ResourceTier.HIGH: RecommendedPlan(
            provider="digitalocean",
            plan_id="s-4vcpu-8gb",
            plan_name="Basic 8GB",
            tier=ResourceTier.HIGH,
            cpu=4,
            ram_gb=8,
            disk_gb=160,
            price_monthly_usd=48.00,
            bandwidth_tb=5.0,
            notes="Professional bundle capable"
        ),
        ResourceTier.VERY_HIGH: RecommendedPlan(
            provider="digitalocean",
            plan_id="s-8vcpu-16gb",
            plan_name="Basic 16GB",
            tier=ResourceTier.VERY_HIGH,
            cpu=8,
            ram_gb=16,
            disk_gb=320,
            price_monthly_usd=96.00,
            bandwidth_tb=6.0,
            notes="Heavy workloads"
        ),
    },
    pros=[
        "Excellent documentation",
        "Clean UI and API",
        "Managed services available",
        "Good developer experience",
    ],
    cons=[
        "Only 3 US locations",
        "Higher price point",
    ],
)

LINODE_PROFILE = ProviderProfile(
    id="linode",
    name="Linode (Akamai)",
    website="https://www.linode.com",
    signup_url="https://login.linode.com/signup",
    api_docs_url="https://www.linode.com/docs/api/",
    datacenters=[
        # US West
        Datacenter(
            id="us-lax",
            name="Los Angeles, CA",
            city="Los Angeles",
            state_country="California, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=30
        ),
        Datacenter(
            id="us-sea",
            name="Seattle, WA",
            city="Seattle",
            state_country="Washington, USA",
            geo_region=GeoRegion.US_WEST,
            latency_from_us_ms=45
        ),
        # US Central
        Datacenter(
            id="us-ord",
            name="Chicago, IL",
            city="Chicago",
            state_country="Illinois, USA",
            geo_region=GeoRegion.US_CENTRAL,
            latency_from_us_ms=20
        ),
        Datacenter(
            id="us-central",
            name="Dallas, TX",
            city="Dallas",
            state_country="Texas, USA",
            geo_region=GeoRegion.US_CENTRAL,
            latency_from_us_ms=15
        ),
        # US East
        Datacenter(
            id="us-east",
            name="Newark, NJ",
            city="Newark",
            state_country="New Jersey, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=25
        ),
        Datacenter(
            id="us-southeast",
            name="Atlanta, GA",
            city="Atlanta",
            state_country="Georgia, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=20
        ),
        Datacenter(
            id="us-mia",
            name="Miami, FL",
            city="Miami",
            state_country="Florida, USA",
            geo_region=GeoRegion.US_EAST,
            latency_from_us_ms=30
        ),
    ],
    plans={
        ResourceTier.LOW: RecommendedPlan(
            provider="linode",
            plan_id="g6-nanode-1",
            plan_name="Nanode 1GB",
            tier=ResourceTier.LOW,
            cpu=1,
            ram_gb=1,
            disk_gb=25,
            price_monthly_usd=5.00,
            bandwidth_tb=1.0,
            notes="Budget option, may need upgrade for full bundle"
        ),
        ResourceTier.MEDIUM: RecommendedPlan(
            provider="linode",
            plan_id="g6-standard-2",
            plan_name="Linode 4GB",
            tier=ResourceTier.MEDIUM,
            cpu=2,
            ram_gb=4,
            disk_gb=80,
            price_monthly_usd=20.00,
            bandwidth_tb=4.0,
            notes="Good for creator/developer bundles"
        ),
        ResourceTier.HIGH: RecommendedPlan(
            provider="linode",
            plan_id="g6-standard-4",
            plan_name="Linode 8GB",
            tier=ResourceTier.HIGH,
            cpu=4,
            ram_gb=8,
            disk_gb=160,
            price_monthly_usd=40.00,
            bandwidth_tb=5.0,
            notes="Professional bundle capable"
        ),
        ResourceTier.VERY_HIGH: RecommendedPlan(
            provider="linode",
            plan_id="g6-standard-6",
            plan_name="Linode 16GB",
            tier=ResourceTier.VERY_HIGH,
            cpu=6,
            ram_gb=16,
            disk_gb=320,
            price_monthly_usd=80.00,
            bandwidth_tb=8.0,
            notes="Heavy workloads"
        ),
    },
    pros=[
        "7 US datacenter locations",
        "Part of Akamai network",
        "Predictable billing",
        "Good stability track record",
    ],
    cons=[
        "UI less polished than competitors",
        "Nanode tier very limited",
    ],
)


# ============================================
# PROVIDER REGISTRY
# ============================================

# All provider profiles (US-focused for v1)
PROVIDERS: Dict[str, ProviderProfile] = {
    "hetzner": HETZNER_PROFILE,
    "vultr": VULTR_PROFILE,
    "digitalocean": DIGITALOCEAN_PROFILE,
    "linode": LINODE_PROFILE,
}

# Bundle to tier mapping
BUNDLE_TIERS = {
    "personal": ResourceTier.LOW,
    "creator": ResourceTier.MEDIUM,
    "developer": ResourceTier.MEDIUM,
    "professional": ResourceTier.HIGH,
}


class PlanRegistry:
    """
    Central registry for WOPR-compatible VPS plans.

    Organized by geographic region for US users with
    choice across multiple providers per region.
    """

    @classmethod
    def get_providers(cls) -> Dict[str, ProviderProfile]:
        """Get all provider profiles."""
        return PROVIDERS

    @classmethod
    def get_provider(cls, provider_id: str) -> Optional[ProviderProfile]:
        """Get a specific provider profile."""
        return PROVIDERS.get(provider_id)

    @classmethod
    def list_providers(cls) -> List[Dict]:
        """List all providers with summary info."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "website": p.website,
                "us_datacenters": len([dc for dc in p.datacenters
                                       if dc.geo_region.value.startswith("us-")]),
                "pros": p.pros,
                "cons": p.cons,
            }
            for p in PROVIDERS.values()
        ]

    # =========================================
    # GEOGRAPHIC QUERIES
    # =========================================

    @classmethod
    def get_datacenters_by_region(
        cls,
        geo_region: GeoRegion
    ) -> List[Tuple[str, Datacenter]]:
        """
        Get all datacenters in a geographic region.

        Returns:
            List of (provider_id, datacenter) tuples
        """
        results = []
        for provider_id, profile in PROVIDERS.items():
            for dc in profile.datacenters:
                if dc.geo_region == geo_region:
                    results.append((provider_id, dc))
        return results

    @classmethod
    def get_us_datacenters(cls) -> Dict[str, List[Tuple[str, Datacenter]]]:
        """
        Get all US datacenters organized by region.

        Returns:
            Dict mapping region name to list of (provider_id, datacenter)
        """
        return {
            "US West (CA, OR, WA)": cls.get_datacenters_by_region(GeoRegion.US_WEST),
            "US Central (TX, IL)": cls.get_datacenters_by_region(GeoRegion.US_CENTRAL),
            "US East (NY, NJ, VA, GA, FL)": cls.get_datacenters_by_region(GeoRegion.US_EAST),
        }

    @classmethod
    def get_nearest_datacenter(
        cls,
        user_region: GeoRegion,
        provider_id: Optional[str] = None
    ) -> Optional[Tuple[str, Datacenter]]:
        """
        Get the nearest datacenter to a user's region.

        Args:
            user_region: User's geographic region
            provider_id: Specific provider (any if None)

        Returns:
            (provider_id, datacenter) tuple or None
        """
        candidates = cls.get_datacenters_by_region(user_region)

        if provider_id:
            candidates = [(pid, dc) for pid, dc in candidates if pid == provider_id]

        if candidates:
            # Sort by latency
            return min(candidates, key=lambda x: x[1].latency_from_us_ms)

        return None

    # =========================================
    # PLAN QUERIES
    # =========================================

    @classmethod
    def get_plan(
        cls,
        provider_id: str,
        tier: ResourceTier
    ) -> Optional[RecommendedPlan]:
        """Get a specific plan by provider and tier."""
        profile = PROVIDERS.get(provider_id)
        if profile:
            return profile.plans.get(tier)
        return None

    @classmethod
    def get_plan_for_bundle(
        cls,
        provider_id: str,
        bundle: str
    ) -> Optional[RecommendedPlan]:
        """Get the recommended plan for a bundle."""
        tier = BUNDLE_TIERS.get(bundle)
        if tier:
            return cls.get_plan(provider_id, tier)
        return None

    @classmethod
    def compare_plans_for_tier(
        cls,
        tier: ResourceTier
    ) -> List[Dict]:
        """
        Compare plans for a tier across all providers.

        Returns:
            List sorted by price (cheapest first)
        """
        comparisons = []
        for provider_id, profile in PROVIDERS.items():
            plan = profile.plans.get(tier)
            if plan:
                comparisons.append({
                    "provider_id": provider_id,
                    "provider_name": profile.name,
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "cpu": plan.cpu,
                    "ram_gb": plan.ram_gb,
                    "disk_gb": plan.disk_gb,
                    "bandwidth_tb": plan.bandwidth_tb,
                    "price_monthly_usd": plan.price_monthly_usd,
                    "us_datacenters": len([dc for dc in profile.datacenters
                                           if dc.geo_region.value.startswith("us-")]),
                    "notes": plan.notes,
                })
        return sorted(comparisons, key=lambda x: x["price_monthly_usd"])

    @classmethod
    def compare_plans_for_bundle(cls, bundle: str) -> List[Dict]:
        """Compare plans for a bundle across all providers."""
        tier = BUNDLE_TIERS.get(bundle)
        if tier:
            return cls.compare_plans_for_tier(tier)
        return []

    @classmethod
    def get_cheapest_for_bundle(
        cls,
        bundle: str,
        geo_region: Optional[GeoRegion] = None
    ) -> Optional[Dict]:
        """
        Get the cheapest option for a bundle.

        Args:
            bundle: WOPR bundle name
            geo_region: Preferred region (optional)

        Returns:
            Dict with provider, plan, and datacenter info
        """
        comparisons = cls.compare_plans_for_bundle(bundle)
        if not comparisons:
            return None

        # If region preference, filter to providers with that region
        if geo_region:
            region_providers = set()
            for provider_id, profile in PROVIDERS.items():
                for dc in profile.datacenters:
                    if dc.geo_region == geo_region:
                        region_providers.add(provider_id)

            filtered = [c for c in comparisons if c["provider_id"] in region_providers]
            if filtered:
                comparisons = filtered

        result = comparisons[0]

        # Add datacenter info
        if geo_region:
            dc_info = cls.get_nearest_datacenter(geo_region, result["provider_id"])
            if dc_info:
                result["recommended_datacenter"] = {
                    "id": dc_info[1].id,
                    "name": dc_info[1].name,
                    "city": dc_info[1].city,
                }

        return result

    # =========================================
    # PRICING ESTIMATES
    # =========================================

    @classmethod
    def estimate_cost(
        cls,
        bundle: str,
        provider_id: Optional[str] = None
    ) -> Dict:
        """
        Estimate monthly cost for a bundle.

        Args:
            bundle: Bundle name
            provider_id: Specific provider (cheapest if None)
        """
        tier = BUNDLE_TIERS.get(bundle)
        if not tier:
            return {"error": f"Unknown bundle: {bundle}"}

        if provider_id:
            profile = PROVIDERS.get(provider_id)
            if not profile:
                return {"error": f"Unknown provider: {provider_id}"}
            plan = profile.plans.get(tier)
            if not plan:
                return {"error": f"No plan for tier {tier.value}"}
        else:
            cheapest = cls.get_cheapest_for_bundle(bundle)
            if not cheapest:
                return {"error": "No plans available"}
            provider_id = cheapest["provider_id"]
            profile = PROVIDERS[provider_id]
            plan = profile.plans[tier]

        return {
            "bundle": bundle,
            "tier": tier.value,
            "provider": {
                "id": provider_id,
                "name": profile.name,
            },
            "plan": {
                "id": plan.plan_id,
                "name": plan.plan_name,
                "cpu": plan.cpu,
                "ram_gb": plan.ram_gb,
                "disk_gb": plan.disk_gb,
                "bandwidth_tb": plan.bandwidth_tb,
            },
            "pricing": {
                "monthly_usd": plan.price_monthly_usd,
                "annual_usd": round(plan.price_monthly_usd * 12, 2),
            },
            "us_datacenters": [
                {"id": dc.id, "name": dc.name, "region": dc.geo_region.value}
                for dc in profile.datacenters
                if dc.geo_region.value.startswith("us-")
            ],
            "notes": plan.notes,
        }

    # =========================================
    # USER CHOICE HELPERS
    # =========================================

    @classmethod
    def get_user_choices(cls, bundle: str) -> Dict:
        """
        Get all choices for a user selecting hosting.

        Organized by US region for easy selection.
        """
        tier = BUNDLE_TIERS.get(bundle)
        if not tier:
            return {"error": f"Unknown bundle: {bundle}"}

        choices = {
            "bundle": bundle,
            "tier": tier.value,
            "regions": {},
        }

        for region_name, region_enum in [
            ("US West", GeoRegion.US_WEST),
            ("US Central", GeoRegion.US_CENTRAL),
            ("US East", GeoRegion.US_EAST),
        ]:
            region_options = []

            for provider_id, profile in PROVIDERS.items():
                plan = profile.plans.get(tier)
                if not plan:
                    continue

                datacenters = [
                    dc for dc in profile.datacenters
                    if dc.geo_region == region_enum
                ]

                if datacenters:
                    region_options.append({
                        "provider": {
                            "id": provider_id,
                            "name": profile.name,
                        },
                        "plan": {
                            "id": plan.plan_id,
                            "name": plan.plan_name,
                            "price_monthly_usd": plan.price_monthly_usd,
                            "cpu": plan.cpu,
                            "ram_gb": plan.ram_gb,
                            "disk_gb": plan.disk_gb,
                        },
                        "datacenters": [
                            {"id": dc.id, "name": dc.name, "city": dc.city}
                            for dc in datacenters
                        ],
                    })

            # Sort by price
            region_options.sort(key=lambda x: x["plan"]["price_monthly_usd"])
            choices["regions"][region_name] = region_options

        return choices

    @classmethod
    def format_choices_for_display(cls, bundle: str) -> str:
        """Format choices as a readable string for CLI/UI."""
        choices = cls.get_user_choices(bundle)

        if "error" in choices:
            return choices["error"]

        lines = [
            f"Hosting Options for {bundle.title()} Bundle",
            f"Tier: {choices['tier']}",
            "=" * 50,
            "",
        ]

        for region_name, options in choices["regions"].items():
            if not options:
                continue

            lines.append(f"📍 {region_name}")
            lines.append("-" * 30)

            for opt in options:
                plan = opt["plan"]
                dcs = ", ".join(dc["city"] for dc in opt["datacenters"])
                lines.append(
                    f"  {opt['provider']['name']:20} "
                    f"${plan['price_monthly_usd']:>6.2f}/mo  "
                    f"{plan['cpu']}vCPU/{plan['ram_gb']}GB  "
                    f"[{dcs}]"
                )
            lines.append("")

        return "\n".join(lines)
