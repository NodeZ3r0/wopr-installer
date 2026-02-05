"""
WOPR Beacon Storage Tier Definitions

Storage tiers determine resource allocation (storage, RAM, etc.)
They apply WITHIN each bundle - every bundle has 3 storage tiers.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StorageTier(Enum):
    """Storage tier levels - apply to ALL bundles"""
    TIER_1 = 1  # 50GB
    TIER_2 = 2  # 200GB
    TIER_3 = 3  # 500GB+


@dataclass
class StorageTierLimits:
    """Resource limits for a storage tier"""
    tier: StorageTier
    storage_gb: int
    ram_mb: int
    max_users: int
    backup_retention_days: int
    description: str


# =============================================================================
# Storage Tier Definitions (same across all bundles)
# =============================================================================

STORAGE_TIERS: dict[StorageTier, StorageTierLimits] = {
    StorageTier.TIER_1: StorageTierLimits(
        tier=StorageTier.TIER_1,
        storage_gb=50,
        ram_mb=4096,
        max_users=5,
        backup_retention_days=7,
        description="50GB storage",
    ),
    StorageTier.TIER_2: StorageTierLimits(
        tier=StorageTier.TIER_2,
        storage_gb=200,
        ram_mb=8192,
        max_users=25,
        backup_retention_days=30,
        description="200GB storage",
    ),
    StorageTier.TIER_3: StorageTierLimits(
        tier=StorageTier.TIER_3,
        storage_gb=500,
        ram_mb=16384,
        max_users=100,
        backup_retention_days=90,
        description="500GB+ storage",
    ),
}


def get_storage_tier(tier: StorageTier | int) -> StorageTierLimits:
    """Get storage tier limits by tier ID"""
    if isinstance(tier, int):
        tier = StorageTier(tier)
    return STORAGE_TIERS[tier]


# =============================================================================
# Bundle Types
# =============================================================================

class BundleType(Enum):
    """Types of bundles available"""
    SOVEREIGN = "sovereign"  # Full suite bundles
    MICRO = "micro"          # Niche-specific bundles
    FREE = "free"            # Free tier (join existing beacon)
    AI_GPU = "ai_gpu"        # Custom contract GPU hosting


# =============================================================================
# Sovereign Suite IDs
# =============================================================================

class SovereignSuiteID(Enum):
    """Sovereign Suite bundle identifiers"""
    STARTER = "starter"
    CREATOR = "creator"
    DEVELOPER = "developer"
    PROFESSIONAL = "professional"
    FAMILY = "family"
    SMALL_BUSINESS = "smallbusiness"
    ENTERPRISE = "enterprise"


# =============================================================================
# Micro Bundle IDs
# =============================================================================

class MicroBundleID(Enum):
    """Micro Bundle identifiers"""
    PERSONAL_PRODUCTIVITY = "personal_productivity"
    MEETING_ROOM = "meeting_room"
    PRIVACY_PACK = "privacy_pack"
    WRITER_STUDIO = "writer_studio"
    ARTIST_STOREFRONT = "artist_storefront"
    PODCASTER = "podcaster"
    FREELANCER = "freelancer"
    MUSICIAN = "musician"
    FAMILY_HUB = "family_hub"
    PHOTOGRAPHER = "photographer"
    BOOKKEEPER = "bookkeeper"
    VIDEO_CREATOR = "video_creator"
    CONTRACTOR = "contractor"
    REALTOR = "realtor"
    EDUCATOR = "educator"
    THERAPIST = "therapist"
    LEGAL = "legal"
    # AI/Ops micro-bundles
    DEFCON_ONE = "defcon_one"
    REACTOR_AI = "reactor_ai"


# =============================================================================
# Pricing Structure
# =============================================================================

@dataclass
class BundlePricing:
    """Pricing for a bundle across all 3 storage tiers"""
    tier_1_monthly: str  # 50GB
    tier_2_monthly: str  # 200GB
    tier_3_monthly: str  # 500GB+

    def get_price(self, tier: StorageTier | int) -> str:
        if isinstance(tier, int):
            tier = StorageTier(tier)
        return {
            StorageTier.TIER_1: self.tier_1_monthly,
            StorageTier.TIER_2: self.tier_2_monthly,
            StorageTier.TIER_3: self.tier_3_monthly,
        }[tier]


# Sovereign Suite Pricing
SOVEREIGN_PRICING: dict[SovereignSuiteID, BundlePricing] = {
    SovereignSuiteID.STARTER: BundlePricing("$29.99", "$45.99", "$65.99"),
    SovereignSuiteID.CREATOR: BundlePricing("$55.99", "$79.99", "$119.99"),
    SovereignSuiteID.DEVELOPER: BundlePricing("$55.99", "$79.99", "$119.99"),
    SovereignSuiteID.PROFESSIONAL: BundlePricing("$99.99", "$149.99", "$199.99"),
    SovereignSuiteID.FAMILY: BundlePricing("$55.99", "$79.99", "$119.99"),
    SovereignSuiteID.SMALL_BUSINESS: BundlePricing("$129.99", "$179.99", "$249.99"),
    SovereignSuiteID.ENTERPRISE: BundlePricing("$249.99", "$349.99", "Custom"),
}

# Micro Bundle Pricing
MICRO_PRICING: dict[MicroBundleID, BundlePricing] = {
    # Light micro-bundles (4GB MEDIUM VPS, weighted avg ~$17/mo cost)
    MicroBundleID.PERSONAL_PRODUCTIVITY: BundlePricing("$29.99", "$45.99", "$65.99"),
    MicroBundleID.MEETING_ROOM: BundlePricing("$29.99", "$45.99", "$65.99"),
    MicroBundleID.PRIVACY_PACK: BundlePricing("$29.99", "$45.99", "$65.99"),
    MicroBundleID.WRITER_STUDIO: BundlePricing("$29.99", "$45.99", "$65.99"),
    MicroBundleID.PODCASTER: BundlePricing("$35.99", "$55.99", "$79.99"),
    MicroBundleID.FREELANCER: BundlePricing("$35.99", "$55.99", "$79.99"),
    MicroBundleID.CONTRACTOR: BundlePricing("$35.99", "$55.99", "$79.99"),
    MicroBundleID.MUSICIAN: BundlePricing("$35.99", "$55.99", "$79.99"),
    MicroBundleID.BOOKKEEPER: BundlePricing("$35.99", "$55.99", "$79.99"),
    # Medium micro-bundles (8GB HIGH VPS, weighted avg ~$33/mo cost)
    MicroBundleID.ARTIST_STOREFRONT: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.FAMILY_HUB: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.PHOTOGRAPHER: BundlePricing("$55.99", "$79.99", "$119.99"),
    MicroBundleID.VIDEO_CREATOR: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.REALTOR: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.EDUCATOR: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.THERAPIST: BundlePricing("$55.99", "$79.99", "$119.99"),
    MicroBundleID.LEGAL: BundlePricing("$55.99", "$79.99", "$119.99"),
    # AI/Ops micro-bundles (8GB+ HIGH VPS required for AI)
    MicroBundleID.DEFCON_ONE: BundlePricing("$45.99", "$65.99", "$95.99"),
    MicroBundleID.REACTOR_AI: BundlePricing("$55.99", "$79.99", "$119.99"),
}


def get_sovereign_price(suite_id: SovereignSuiteID | str, tier: StorageTier | int) -> str:
    """Get price for a sovereign suite at a specific storage tier"""
    if isinstance(suite_id, str):
        suite_id = SovereignSuiteID(suite_id)
    return SOVEREIGN_PRICING[suite_id].get_price(tier)


def get_micro_price(bundle_id: MicroBundleID | str, tier: StorageTier | int) -> str:
    """Get price for a micro bundle at a specific storage tier"""
    if isinstance(bundle_id, str):
        bundle_id = MicroBundleID(bundle_id)
    return MICRO_PRICING[bundle_id].get_price(tier)
