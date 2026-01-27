"""
WOPR Bundles Module

Defines bundle structure, pricing, and the Beacon provisioning system.

Bundle Architecture:
- BundleType: SOVEREIGN (7 suites) or MICRO (17 bundles)
- StorageTier: 1 (50GB), 2 (200GB), 3 (500GB+)
- Each bundle has fixed modules, tier only affects resources

Sovereign Suites (7):
- Starter, Creator, Developer, Professional, Family, Small Business, Enterprise

Micro Bundles (17):
- Personal Productivity, Meeting Room, Privacy Pack, Writer's Studio,
  Artist Storefront, Podcaster, Freelancer, Musician, Family Hub, Photographer,
  Bookkeeper, Video Creator, Contractor, Realtor, Educator, Therapist, Legal
"""

from .tiers import (
    # Core types
    BundleType,
    StorageTier,
    SovereignSuiteID,
    MicroBundleID,
    # Storage tier info
    StorageTierLimits,
    STORAGE_TIERS,
    get_storage_tier,
    # Pricing
    BundlePricing,
    SOVEREIGN_PRICING,
    MICRO_PRICING,
    get_sovereign_price,
    get_micro_price,
)

from .manifests import (
    # Manifest types
    BundleManifest,
    CORE_INFRASTRUCTURE,
    # Sovereign Suites
    SOVEREIGN_BUNDLES,
    SOVEREIGN_STARTER,
    SOVEREIGN_CREATOR,
    SOVEREIGN_DEVELOPER,
    SOVEREIGN_PROFESSIONAL,
    SOVEREIGN_FAMILY,
    SOVEREIGN_SMALL_BUSINESS,
    SOVEREIGN_ENTERPRISE,
    # Micro Bundles
    MICRO_BUNDLES,
    MICRO_PERSONAL_PRODUCTIVITY,
    MICRO_MEETING_ROOM,
    MICRO_PRIVACY_PACK,
    MICRO_WRITER_STUDIO,
    MICRO_ARTIST_STOREFRONT,
    MICRO_PODCASTER,
    MICRO_FREELANCER,
    MICRO_MUSICIAN,
    MICRO_FAMILY_HUB,
    MICRO_PHOTOGRAPHER,
    MICRO_BOOKKEEPER,
    MICRO_VIDEO_CREATOR,
    MICRO_CONTRACTOR,
    MICRO_REALTOR,
    MICRO_EDUCATOR,
    MICRO_THERAPIST,
    MICRO_LEGAL,
    # Lookup functions
    get_sovereign_bundle,
    get_micro_bundle,
    get_bundle,
    get_modules_for_bundle,
    parse_checkout_bundle,
)

from .beacon_provisioner import (
    BeaconProvisioner,
    BeaconInstance,
    ProvisioningRequest,
    ProvisioningStatus,
    ProvisioningProgress,
    handle_stripe_webhook,
    create_provisioning_api,
)

from .stripe_checkout import (
    StripeCheckout,
    StripePriceMapping,
    load_price_mapping,
    create_checkout_api,
)

__all__ = [
    # Bundle Types
    "BundleType",
    "StorageTier",
    "SovereignSuiteID",
    "MicroBundleID",

    # Storage Tiers
    "StorageTierLimits",
    "STORAGE_TIERS",
    "get_storage_tier",

    # Pricing
    "BundlePricing",
    "SOVEREIGN_PRICING",
    "MICRO_PRICING",
    "get_sovereign_price",
    "get_micro_price",

    # Manifests
    "BundleManifest",
    "CORE_INFRASTRUCTURE",
    "SOVEREIGN_BUNDLES",
    "MICRO_BUNDLES",

    # Sovereign Suites
    "SOVEREIGN_STARTER",
    "SOVEREIGN_CREATOR",
    "SOVEREIGN_DEVELOPER",
    "SOVEREIGN_PROFESSIONAL",
    "SOVEREIGN_FAMILY",
    "SOVEREIGN_SMALL_BUSINESS",
    "SOVEREIGN_ENTERPRISE",

    # Micro Bundles
    "MICRO_PERSONAL_PRODUCTIVITY",
    "MICRO_MEETING_ROOM",
    "MICRO_PRIVACY_PACK",
    "MICRO_WRITER_STUDIO",
    "MICRO_ARTIST_STOREFRONT",
    "MICRO_PODCASTER",
    "MICRO_FREELANCER",
    "MICRO_MUSICIAN",
    "MICRO_FAMILY_HUB",
    "MICRO_PHOTOGRAPHER",
    "MICRO_BOOKKEEPER",
    "MICRO_VIDEO_CREATOR",
    "MICRO_CONTRACTOR",
    "MICRO_REALTOR",
    "MICRO_EDUCATOR",
    "MICRO_THERAPIST",
    "MICRO_LEGAL",

    # Lookup functions
    "get_sovereign_bundle",
    "get_micro_bundle",
    "get_bundle",
    "get_modules_for_bundle",
    "parse_checkout_bundle",

    # Beacon Provisioner
    "BeaconProvisioner",
    "BeaconInstance",
    "ProvisioningRequest",
    "ProvisioningStatus",
    "ProvisioningProgress",
    "handle_stripe_webhook",
    "create_provisioning_api",

    # Stripe Checkout
    "StripeCheckout",
    "StripePriceMapping",
    "load_price_mapping",
    "create_checkout_api",
]
