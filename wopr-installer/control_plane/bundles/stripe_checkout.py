"""
Stripe Checkout Session Management

Creates Stripe Checkout Sessions for bundle subscriptions.
Maps bundle/tier selections to correct Stripe Price IDs.
"""

import json
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import stripe

from .tiers import BundleType, StorageTier, SovereignSuiteID, MicroBundleID


@dataclass
class StripePriceMapping:
    """Loaded Stripe price mappings"""
    mode: str  # "test" or "live"
    sovereign: dict[str, dict]
    micro: dict[str, dict]

    def get_price_id(
        self,
        bundle_type: BundleType,
        bundle_id: str,
        storage_tier: StorageTier,
    ) -> Optional[str]:
        """Get Stripe Price ID for a bundle/tier combination"""
        tier_key = f"tier_{storage_tier.value}"

        if bundle_type == BundleType.SOVEREIGN:
            bundle_data = self.sovereign.get(bundle_id)
        elif bundle_type == BundleType.MICRO:
            bundle_data = self.micro.get(bundle_id)
        else:
            return None

        if not bundle_data:
            return None

        return bundle_data.get("prices", {}).get(tier_key)

    def get_product_id(
        self,
        bundle_type: BundleType,
        bundle_id: str,
    ) -> Optional[str]:
        """Get Stripe Product ID for a bundle"""
        if bundle_type == BundleType.SOVEREIGN:
            bundle_data = self.sovereign.get(bundle_id)
        elif bundle_type == BundleType.MICRO:
            bundle_data = self.micro.get(bundle_id)
        else:
            return None

        if not bundle_data:
            return None

        return bundle_data.get("product_id")


def load_price_mapping(use_test_mode: bool = False) -> StripePriceMapping:
    """Load Stripe price mappings from JSON file"""
    bundles_dir = Path(__file__).parent

    if use_test_mode:
        price_file = bundles_dir / "stripe_prices_test.json"
    else:
        price_file = bundles_dir / "stripe_prices_live.json"

    if not price_file.exists():
        raise FileNotFoundError(f"Stripe price mapping not found: {price_file}")

    with open(price_file) as f:
        data = json.load(f)

    return StripePriceMapping(
        mode=data.get("mode", "live" if not use_test_mode else "test"),
        sovereign=data.get("sovereign", {}),
        micro=data.get("micro", {}),
    )


class StripeCheckout:
    """
    Handles Stripe Checkout Session creation for WOPR bundles.

    Usage:
        checkout = StripeCheckout(
            api_key="sk_live_...",
            success_url="https://wopr.systems/checkout/success",
            cancel_url="https://wopr.systems/join",
            use_test_mode=False,
        )

        session_url = checkout.create_session(
            bundle_type=BundleType.SOVEREIGN,
            bundle_id="starter",
            storage_tier=StorageTier.TIER_1,
            customer_email="user@example.com",
            metadata={"domain": "example.com", "username": "johndoe"},
        )

        # Redirect user to session_url
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        success_url: str = "https://wopr.systems/checkout/success",
        cancel_url: str = "https://wopr.systems/join",
        use_test_mode: bool = False,
        webhook_secret: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY")
        self.success_url = success_url
        self.cancel_url = cancel_url
        self.use_test_mode = use_test_mode
        self.webhook_secret = webhook_secret or os.environ.get("STRIPE_WEBHOOK_SECRET")

        if not self.api_key:
            raise ValueError("Stripe API key required. Set STRIPE_SECRET_KEY env var or pass api_key.")

        stripe.api_key = self.api_key
        self.price_mapping = load_price_mapping(use_test_mode)

    def create_session(
        self,
        bundle_type: BundleType,
        bundle_id: str,
        storage_tier: StorageTier,
        customer_email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Create a Stripe Checkout Session and return the URL.

        Args:
            bundle_type: SOVEREIGN or MICRO
            bundle_id: e.g., "starter", "meeting_room"
            storage_tier: TIER_1, TIER_2, or TIER_3
            customer_email: Pre-fill customer email
            metadata: Additional metadata (domain, username, etc.)

        Returns:
            Checkout session URL to redirect user to
        """
        # Get the correct price ID
        price_id = self.price_mapping.get_price_id(bundle_type, bundle_id, storage_tier)

        if not price_id:
            raise ValueError(
                f"No price found for {bundle_type.value}-{bundle_id} tier {storage_tier.value}"
            )

        # Build checkout bundle string for webhook (e.g., "sovereign-starter")
        checkout_bundle = f"{bundle_type.value}-{bundle_id}"

        # Merge metadata
        session_metadata = {
            "bundle": checkout_bundle,
            "bundle_type": bundle_type.value,
            "bundle_id": bundle_id,
            "tier": str(storage_tier.value),
        }
        if metadata:
            session_metadata.update(metadata)

        # Build success URL with session ID placeholder
        success_url_with_session = f"{self.success_url}?session_id={{CHECKOUT_SESSION_ID}}"

        # Create checkout session
        session_params = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1,
            }],
            "success_url": success_url_with_session,
            "cancel_url": self.cancel_url,
            "metadata": session_metadata,
            "subscription_data": {
                "metadata": session_metadata,
            },
            "allow_promotion_codes": True,
        }

        if customer_email:
            session_params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        return session.url

    def create_session_from_checkout_string(
        self,
        checkout_bundle: str,  # e.g., "sovereign-starter" or "micro-meeting_room"
        storage_tier: int,      # 1, 2, or 3
        customer_email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Create checkout session from checkout string format.

        This is the format used by the join page form.
        """
        # Parse checkout bundle
        parts = checkout_bundle.split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid checkout bundle format: {checkout_bundle}")

        bundle_type_str, bundle_id = parts

        try:
            bundle_type = BundleType(bundle_type_str)
        except ValueError:
            raise ValueError(f"Invalid bundle type: {bundle_type_str}")

        try:
            tier = StorageTier(storage_tier)
        except ValueError:
            raise ValueError(f"Invalid storage tier: {storage_tier}")

        return self.create_session(
            bundle_type=bundle_type,
            bundle_id=bundle_id,
            storage_tier=tier,
            customer_email=customer_email,
            metadata=metadata,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature and return event.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header value

        Returns:
            Verified Stripe event dict

        Raises:
            ValueError: If signature verification fails
        """
        if not self.webhook_secret:
            raise ValueError("Webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Invalid webhook signature: {e}")


def create_checkout_api(app, checkout: StripeCheckout):
    """
    Create FastAPI routes for Stripe checkout.

    Endpoints:
    - POST /api/checkout/create - Create checkout session
    - GET /api/checkout/prices - Get available prices
    """
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    from typing import Optional

    router = APIRouter(tags=["checkout"])

    class CreateCheckoutRequest(BaseModel):
        bundle: str  # e.g., "sovereign-starter" or "micro-meeting_room"
        tier: int    # Storage tier: 1, 2, or 3
        email: Optional[str] = None
        domain: Optional[str] = None
        username: Optional[str] = None
        display_name: Optional[str] = None

    class CheckoutResponse(BaseModel):
        checkout_url: str
        session_id: Optional[str] = None

    @router.post("/api/checkout/create", response_model=CheckoutResponse)
    async def create_checkout(request: CreateCheckoutRequest):
        """Create a Stripe Checkout Session for a bundle subscription"""
        try:
            metadata = {}
            if request.domain:
                metadata["domain"] = request.domain
            if request.username:
                metadata["username"] = request.username
            if request.display_name:
                metadata["display_name"] = request.display_name

            checkout_url = checkout.create_session_from_checkout_string(
                checkout_bundle=request.bundle,
                storage_tier=request.tier,
                customer_email=request.email,
                metadata=metadata if metadata else None,
            )

            return CheckoutResponse(checkout_url=checkout_url)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Checkout error: {str(e)}")

    @router.get("/api/checkout/prices")
    async def get_prices():
        """Get all available bundle prices"""
        mapping = checkout.price_mapping

        return {
            "mode": mapping.mode,
            "sovereign": {
                bundle_id: {
                    "name": data.get("name"),
                    "product_id": data.get("product_id"),
                    "prices": data.get("prices"),
                }
                for bundle_id, data in mapping.sovereign.items()
            },
            "micro": {
                bundle_id: {
                    "name": data.get("name"),
                    "product_id": data.get("product_id"),
                    "prices": data.get("prices"),
                }
                for bundle_id, data in mapping.micro.items()
            },
        }

    @router.get("/api/checkout/price/{bundle}/{tier}")
    async def get_price(bundle: str, tier: int):
        """Get price ID for a specific bundle/tier"""
        try:
            parts = bundle.split("-", 1)
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid bundle format")

            bundle_type = BundleType(parts[0])
            bundle_id = parts[1]
            storage_tier = StorageTier(tier)

            price_id = checkout.price_mapping.get_price_id(
                bundle_type, bundle_id, storage_tier
            )

            if not price_id:
                raise HTTPException(status_code=404, detail="Price not found")

            return {
                "bundle": bundle,
                "tier": tier,
                "price_id": price_id,
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    app.include_router(router)
    return router
