# WOPR Stripe Product Catalog
# ============================
#
# Supports per-beacon Stripe mode (test/live) by loading prices from JSON files.
# Live prices: bundles/stripe_prices_live.json
# Test prices: bundles/stripe_prices_test.json

import json
import os
from pathlib import Path
from typing import Dict, Optional, List

# Stripe Product IDs (from live Stripe account)
STRIPE_PRODUCTS: Dict[str, str] = {}

# Bundle pricing in cents (for validation)
BUNDLE_PRICING: Dict[str, Dict[str, int]] = {
    "starter": {"t1": 1599, "t2": 2599, "t3": 3599},
    "creator": {"t1": 3599, "t2": 5599, "t3": 9599},
    "developer": {"t1": 3599, "t2": 5599, "t3": 9599},
    "professional": {"t1": 6599, "t2": 9599, "t3": 14999},
    "family": {"t1": 4599, "t2": 6599, "t3": 9599},
    "small_business": {"t1": 9599, "t2": 14999, "t3": 19999},
    "enterprise": {"t1": 19999, "t2": 29999, "t3": 0},
    "meeting_room": {"t1": 1599, "t2": 2599, "t3": 3599},
    "privacy_pack": {"t1": 1599, "t2": 2599, "t3": 3599},
    "writer_studio": {"t1": 1999, "t2": 2999, "t3": 4599},
    "artist_storefront": {"t1": 1999, "t2": 2999, "t3": 4599},
    "podcaster": {"t1": 2599, "t2": 3599, "t3": 5599},
    "freelancer": {"t1": 2599, "t2": 3599, "t3": 5599},
    "musician": {"t1": 2599, "t2": 3599, "t3": 5599},
    "family_hub": {"t1": 2999, "t2": 4599, "t3": 6599},
    "photographer": {"t1": 2999, "t2": 4599, "t3": 6599},
    "bookkeeper": {"t1": 2999, "t2": 4599, "t3": 6599},
    "video_creator": {"t1": 3599, "t2": 5599, "t3": 9599},
    "contractor": {"t1": 3599, "t2": 5599, "t3": 9599},
    "realtor": {"t1": 3599, "t2": 5599, "t3": 9599},
    "educator": {"t1": 3599, "t2": 5599, "t3": 9599},
    "therapist": {"t1": 4599, "t2": 6599, "t3": 12599},
    "legal": {"t1": 4599, "t2": 6599, "t3": 12599},
}

# Bundle metadata
BUNDLE_INFO: Dict[str, Dict[str, str]] = {
    "starter": {"name": "Starter Sovereign Suite", "type": "sovereign"},
    "creator": {"name": "Creator Sovereign Suite", "type": "sovereign"},
    "developer": {"name": "Developer Sovereign Suite", "type": "sovereign"},
    "professional": {"name": "Professional Sovereign Suite", "type": "sovereign"},
    "family": {"name": "Family Sovereign Suite", "type": "sovereign"},
    "small_business": {"name": "Small Business Sovereign Suite", "type": "sovereign"},
    "enterprise": {"name": "Enterprise Sovereign Suite", "type": "sovereign"},
    "meeting_room": {"name": "Meeting Room", "type": "micro"},
    "privacy_pack": {"name": "Privacy Pack", "type": "micro"},
    "writer_studio": {"name": "Writer's Studio", "type": "micro"},
    "artist_storefront": {"name": "Artist Storefront", "type": "micro"},
    "podcaster": {"name": "Podcaster Pack", "type": "micro"},
    "freelancer": {"name": "Freelancer Essentials", "type": "micro"},
    "musician": {"name": "Musician Bundle", "type": "micro"},
    "family_hub": {"name": "Family Hub", "type": "micro"},
    "photographer": {"name": "Photographer Pro", "type": "micro"},
    "bookkeeper": {"name": "Bookkeeper Bundle", "type": "micro"},
    "video_creator": {"name": "Video Creator", "type": "micro"},
    "contractor": {"name": "Contractor Pro", "type": "micro"},
    "realtor": {"name": "Real Estate Agent", "type": "micro"},
    "educator": {"name": "Educator Suite", "type": "micro"},
    "therapist": {"name": "Therapist/Coach", "type": "micro"},
    "legal": {"name": "Legal Lite", "type": "micro"},
}

TIER_INFO: Dict[str, Dict[str, str]] = {
    "t1": {"name": "Tier 1", "storage": "50GB"},
    "t2": {"name": "Tier 2", "storage": "200GB"},
    "t3": {"name": "Tier 3", "storage": "500GB+"},
}


def _load_prices_from_json(filename: str) -> Dict[str, str]:
    """Load price IDs from JSON file and normalize to catalog key format."""
    price_file = Path(__file__).parent / "bundles" / filename
    if not price_file.exists():
        return {}

    with open(price_file) as f:
        data = json.load(f)

    prices: Dict[str, str] = {}
    tier_map = {"tier_1": "t1", "tier_2": "t2", "tier_3": "t3"}
    bundle_renames = {"smallbusiness": "small_business"}

    for btype in ("sovereign", "micro"):
        for bid, bdata in data.get(btype, {}).items():
            catalog_bid = bundle_renames.get(bid, bid)
            for tkey, price_id in bdata.get("prices", {}).items():
                tier = tier_map.get(tkey, tkey)
                prices[f"{catalog_bid}_{tier}_monthly"] = price_id

    return prices


# Load both test and live prices at module init
STRIPE_PRICES_LIVE: Dict[str, str] = _load_prices_from_json("stripe_prices_live.json")
STRIPE_PRICES_TEST: Dict[str, str] = _load_prices_from_json("stripe_prices_test.json")

# Legacy: STRIPE_PRICES for backward compatibility
_default_mode = os.environ.get("STRIPE_DEFAULT_MODE", os.environ.get("STRIPE_PRICE_MODE", "test"))
STRIPE_PRICES: Dict[str, str] = STRIPE_PRICES_LIVE if _default_mode == "live" else STRIPE_PRICES_TEST


# Helper functions
def get_price_id(bundle_id: str, tier: str, period: str = "monthly", mode: str = None) -> Optional[str]:
    """
    Get Stripe price ID for a bundle/tier/period combination.

    Args:
        bundle_id: Bundle identifier (e.g., "starter", "developer")
        tier: Storage tier (t1, t2, t3)
        period: Billing period ("monthly" or "yearly")
        mode: Stripe mode ("test" or "live"). If None, uses default from env.

    Returns:
        Stripe price ID or None if not found
    """
    key = f"{bundle_id}_{tier}_{period}"

    if mode == "live":
        return STRIPE_PRICES_LIVE.get(key)
    elif mode == "test":
        return STRIPE_PRICES_TEST.get(key)
    else:
        return STRIPE_PRICES.get(key)


def get_product_id(bundle_id: str, tier: str) -> Optional[str]:
    """Get Stripe product ID for a bundle/tier combination."""
    key = f"{bundle_id}_{tier}"
    return STRIPE_PRODUCTS.get(key)


def get_price_cents(bundle_id: str, tier: str) -> int:
    """Get monthly price in cents for a bundle/tier."""
    bundle = BUNDLE_PRICING.get(bundle_id, {})
    return bundle.get(tier, 0)


def get_price_display(bundle_id: str, tier: str) -> str:
    """Get formatted price string (e.g., '$15.99')."""
    cents = get_price_cents(bundle_id, tier)
    if cents == 0:
        return "Custom"
    return f"${cents / 100:.2f}"


def get_bundle_info(bundle_id: str) -> Optional[Dict[str, str]]:
    """Get bundle metadata."""
    return BUNDLE_INFO.get(bundle_id)


def get_tier_info(tier: str) -> Optional[Dict[str, str]]:
    """Get tier metadata."""
    return TIER_INFO.get(tier)


def get_all_bundles() -> List[str]:
    """Get list of all bundle IDs."""
    return list(BUNDLE_PRICING.keys())


def get_sovereign_suites() -> List[str]:
    """Get list of Sovereign Suite bundle IDs."""
    return [b for b, info in BUNDLE_INFO.items() if info.get("type") == "sovereign"]


def get_micro_bundles() -> List[str]:
    """Get list of Micro-Bundle IDs."""
    return [b for b, info in BUNDLE_INFO.items() if info.get("type") == "micro"]


def is_valid_bundle(bundle_id: str) -> bool:
    """Check if bundle ID is valid."""
    return bundle_id in BUNDLE_PRICING


def is_valid_tier(tier: str) -> bool:
    """Check if tier is valid."""
    return tier in TIER_INFO
