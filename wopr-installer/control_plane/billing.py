"""
WOPR Billing Integration
========================

Stripe integration for WOPR Sovereign Suite subscriptions.

Flow:
1. User selects bundle and provider/region
2. Create Stripe Checkout Session with metadata
3. Redirect user to Stripe payment page
4. Webhook receives payment confirmation
5. Trigger provisioning with payment metadata
6. Send welcome email with setup instructions

Trial Flow (for add-on modules):
1. User on Personal/Creator wants to try Reactor AI
2. Start free trial (90 days, no payment required)
3. Stripe creates trial subscription
4. Authentik grants trial group access
5. Modules installed on instance
6. At day 75: reminder email
7. At day 90: convert to paid or disable

Documentation:
- Stripe Checkout: https://docs.stripe.com/payments/checkout
- Stripe Webhooks: https://docs.stripe.com/webhooks
- Stripe Trials: https://docs.stripe.com/billing/subscriptions/trials

Updated: January 2026
"""

import os
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False


class SubscriptionTier(Enum):
    """WOPR subscription tiers matching bundles."""
    PERSONAL = "personal"
    CREATOR = "creator"
    DEVELOPER = "developer"
    PROFESSIONAL = "professional"


@dataclass
class PricingPlan:
    """Pricing plan for a bundle."""
    tier: SubscriptionTier
    name: str
    description: str
    price_monthly_usd: float
    stripe_price_id: str  # Set in Stripe Dashboard
    features: list = field(default_factory=list)


# ============================================
# PRICING PLANS (Configure in Stripe Dashboard)
# ============================================

# Note: These Stripe Price IDs need to be created in your Stripe account
# and the IDs updated here. These are placeholders.

PRICING_PLANS = {
    SubscriptionTier.PERSONAL: PricingPlan(
        tier=SubscriptionTier.PERSONAL,
        name="Personal Sovereign Suite",
        description="Private cloud for individuals and families",
        price_monthly_usd=9.99,
        stripe_price_id="price_personal_monthly",  # Replace with actual Stripe Price ID
        features=[
            "Nextcloud (files, calendar, contacts)",
            "Vaultwarden (password manager)",
            "Automated daily backups",
            "SSL certificates included",
            "Basic monitoring",
        ]
    ),
    SubscriptionTier.CREATOR: PricingPlan(
        tier=SubscriptionTier.CREATOR,
        name="Creator Sovereign Suite",
        description="Personal cloud + monetization tools",
        price_monthly_usd=19.99,
        stripe_price_id="price_creator_monthly",  # Replace with actual Stripe Price ID
        features=[
            "Everything in Personal",
            "Saleor storefront",
            "Ghost blog",
            "Portfolio website",
        ]
    ),
    SubscriptionTier.DEVELOPER: PricingPlan(
        tier=SubscriptionTier.DEVELOPER,
        name="Developer Sovereign Suite",
        description="Code ownership + AI assistance",
        price_monthly_usd=29.99,
        stripe_price_id="price_developer_monthly",  # Replace with actual Stripe Price ID
        features=[
            "Everything in Personal",
            "Forgejo (self-hosted Git)",
            "Woodpecker CI/CD",
            "Reactor AI (CPU mode)",
            "DEFCON ONE controls",
        ]
    ),
    SubscriptionTier.PROFESSIONAL: PricingPlan(
        tier=SubscriptionTier.PROFESSIONAL,
        name="Professional Sovereign Suite",
        description="All-in-one sovereign work environment",
        price_monthly_usd=49.99,
        stripe_price_id="price_professional_monthly",  # Replace with actual Stripe Price ID
        features=[
            "Everything in Creator + Developer",
            "Matrix/Element chat",
            "Jitsi video conferencing",
            "Collabora Online office",
            "Outline wiki/docs",
        ]
    ),
}


@dataclass
class CheckoutMetadata:
    """Metadata attached to Stripe checkout session."""
    bundle: str
    provider_id: str
    region: str
    datacenter_id: str
    custom_domain: Optional[str] = None
    customer_email: str = ""
    referral_code: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        """Convert to Stripe-compatible metadata dict (all strings)."""
        return {
            "wopr_bundle": self.bundle,
            "wopr_provider": self.provider_id,
            "wopr_region": self.region,
            "wopr_datacenter": self.datacenter_id,
            "wopr_custom_domain": self.custom_domain or "",
            "wopr_referral": self.referral_code or "",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "CheckoutMetadata":
        """Create from Stripe metadata dict."""
        return cls(
            bundle=data.get("wopr_bundle", ""),
            provider_id=data.get("wopr_provider", ""),
            region=data.get("wopr_region", ""),
            datacenter_id=data.get("wopr_datacenter", ""),
            custom_domain=data.get("wopr_custom_domain") or None,
            referral_code=data.get("wopr_referral") or None,
        )


class WOPRBilling:
    """
    Stripe billing integration for WOPR.

    Handles:
    - Creating checkout sessions
    - Processing webhooks
    - Managing subscriptions
    """

    def __init__(
        self,
        stripe_secret_key: str,
        stripe_webhook_secret: str,
        success_url: str,
        cancel_url: str,
    ):
        """
        Initialize billing.

        Args:
            stripe_secret_key: Stripe secret API key
            stripe_webhook_secret: Webhook signing secret
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment cancelled
        """
        if not STRIPE_AVAILABLE:
            raise ImportError("stripe package not installed. Run: pip install stripe")

        stripe.api_key = stripe_secret_key
        self.webhook_secret = stripe_webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url

    def create_checkout_session(
        self,
        email: str,
        bundle: str,
        provider_id: str,
        region: str,
        datacenter_id: str,
        custom_domain: Optional[str] = None,
        referral_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for a WOPR subscription.

        Args:
            email: Customer email
            bundle: WOPR bundle name
            provider_id: VPS provider ID
            region: Geographic region
            datacenter_id: Specific datacenter
            custom_domain: Optional custom domain
            referral_code: Optional referral code

        Returns:
            Dict with session_id and checkout_url
        """
        # Get pricing plan
        tier = SubscriptionTier(bundle)
        plan = PRICING_PLANS.get(tier)
        if not plan:
            raise ValueError(f"Unknown bundle: {bundle}")

        # Build metadata
        metadata = CheckoutMetadata(
            bundle=bundle,
            provider_id=provider_id,
            region=region,
            datacenter_id=datacenter_id,
            custom_domain=custom_domain,
            customer_email=email,
            referral_code=referral_code,
        )

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[
                {
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }
            ],
            success_url=f"{self.success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=self.cancel_url,
            metadata=metadata.to_dict(),
            subscription_data={
                "metadata": metadata.to_dict(),
            },
            # Collect billing address for tax purposes
            billing_address_collection="required",
            # Allow promotion codes
            allow_promotion_codes=True,
        )

        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "bundle": bundle,
            "price_monthly": plan.price_monthly_usd,
        }

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> stripe.Event:
        """
        Verify webhook signature and return event.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            Verified Stripe Event

        Raises:
            ValueError: If signature verification fails
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret,
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Invalid webhook signature: {e}")

    def handle_checkout_completed(
        self,
        session: stripe.checkout.Session,
    ) -> Dict[str, Any]:
        """
        Handle checkout.session.completed event.

        This is called when payment succeeds and subscription is created.

        Args:
            session: Stripe Checkout Session object

        Returns:
            Dict with provisioning details
        """
        # Extract metadata
        metadata = CheckoutMetadata.from_dict(session.metadata or {})

        # Get customer info
        customer_id = session.customer
        subscription_id = session.subscription
        customer_email = session.customer_details.email if session.customer_details else ""

        return {
            "event": "checkout_completed",
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "customer_email": customer_email,
            "bundle": metadata.bundle,
            "provider_id": metadata.provider_id,
            "region": metadata.region,
            "datacenter_id": metadata.datacenter_id,
            "custom_domain": metadata.custom_domain,
            "ready_to_provision": True,
        }

    def handle_subscription_updated(
        self,
        subscription: stripe.Subscription,
    ) -> Dict[str, Any]:
        """Handle subscription updates (upgrades, downgrades)."""
        return {
            "event": "subscription_updated",
            "subscription_id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
        }

    def handle_subscription_deleted(
        self,
        subscription: stripe.Subscription,
    ) -> Dict[str, Any]:
        """Handle subscription cancellation."""
        return {
            "event": "subscription_deleted",
            "subscription_id": subscription.id,
            "cancel_at": subscription.canceled_at,
            # Trigger cleanup workflow
            "action": "schedule_instance_deletion",
        }

    def handle_payment_failed(
        self,
        invoice: stripe.Invoice,
    ) -> Dict[str, Any]:
        """Handle failed payment."""
        return {
            "event": "payment_failed",
            "invoice_id": invoice.id,
            "subscription_id": invoice.subscription,
            "customer_id": invoice.customer,
            "amount_due": invoice.amount_due,
            # Trigger notification
            "action": "notify_payment_failed",
        }

    def process_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Process incoming Stripe webhook.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            Dict with event handling result
        """
        event = self.verify_webhook_signature(payload, signature)

        handlers = {
            "checkout.session.completed": lambda e: self.handle_checkout_completed(e.data.object),
            "customer.subscription.updated": lambda e: self.handle_subscription_updated(e.data.object),
            "customer.subscription.deleted": lambda e: self.handle_subscription_deleted(e.data.object),
            "customer.subscription.trial_will_end": lambda e: self.handle_trial_will_end(e.data.object),
            "invoice.payment_failed": lambda e: self.handle_payment_failed(e.data.object),
        }

        handler = handlers.get(event.type)
        if handler:
            result = handler(event)
            result["event_id"] = event.id
            result["event_type"] = event.type
            return result

        return {
            "event_id": event.id,
            "event_type": event.type,
            "handled": False,
        }

    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Get subscription details."""
        return stripe.Subscription.retrieve(subscription_id)

    def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> stripe.Subscription:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period

        Returns:
            Updated subscription
        """
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=at_period_end,
        )

    # ============================================
    # TRIAL MANAGEMENT
    # ============================================

    def create_trial_subscription(
        self,
        customer_id: str,
        trial_price_id: str,
        trial_days: int,
        metadata: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Create a trial subscription for add-on modules.

        This creates a subscription with a trial period that:
        - Doesn't require payment method upfront
        - Converts to paid after trial ends
        - Can be cancelled anytime during trial

        Args:
            customer_id: Stripe customer ID
            trial_price_id: Price ID for the trial (post-trial billing)
            trial_days: Number of trial days (typically 90)
            metadata: WOPR metadata (trial_id, modules, etc.)

        Returns:
            Dict with subscription details
        """
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": trial_price_id}],
            trial_period_days=trial_days,
            # Allow trial without payment method
            payment_behavior="default_incomplete",
            payment_settings={
                "save_default_payment_method": "on_subscription",
            },
            metadata=metadata,
            expand=["latest_invoice"],
        )

        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "trial_start": subscription.trial_start,
            "trial_end": subscription.trial_end,
            "current_period_end": subscription.current_period_end,
        }

    def get_customer_trials(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all trial subscriptions for a customer.

        Returns:
            List of trial subscription details
        """
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="trialing",
        )

        trials = []
        for sub in subscriptions.data:
            # Check if it's a WOPR trial
            if sub.metadata.get("wopr_trial_id"):
                trials.append({
                    "subscription_id": sub.id,
                    "trial_id": sub.metadata.get("wopr_trial_id"),
                    "trial_name": sub.metadata.get("wopr_trial_name"),
                    "modules": sub.metadata.get("wopr_modules", "").split(","),
                    "trial_end": sub.trial_end,
                    "days_remaining": max(0, (sub.trial_end - int(datetime.now().timestamp())) // 86400),
                })

        return trials

    def convert_trial_to_paid(
        self,
        subscription_id: str,
    ) -> Dict[str, Any]:
        """
        Convert a trial subscription to paid immediately.

        Called when user upgrades their bundle to include trial features.

        Args:
            subscription_id: Trial subscription ID

        Returns:
            Updated subscription details
        """
        subscription = stripe.Subscription.modify(
            subscription_id,
            trial_end="now",  # End trial immediately
            proration_behavior="always_invoice",
        )

        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "converted": True,
        }

    def cancel_trial(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a trial subscription.

        Args:
            subscription_id: Trial subscription ID

        Returns:
            Cancellation confirmation
        """
        subscription = stripe.Subscription.delete(subscription_id)

        return {
            "subscription_id": subscription.id,
            "status": "canceled",
            "message": "Trial cancelled. Your data has been preserved.",
        }

    def handle_trial_will_end(
        self,
        subscription: stripe.Subscription,
    ) -> Dict[str, Any]:
        """
        Handle 'customer.subscription.trial_will_end' webhook.

        Stripe sends this 3 days before trial ends.

        Args:
            subscription: Stripe Subscription object

        Returns:
            Dict with notification details
        """
        metadata = subscription.metadata or {}

        return {
            "event": "trial_will_end",
            "subscription_id": subscription.id,
            "trial_id": metadata.get("wopr_trial_id"),
            "trial_name": metadata.get("wopr_trial_name"),
            "modules": metadata.get("wopr_modules", "").split(","),
            "trial_end": subscription.trial_end,
            "customer_id": subscription.customer,
            "action": "send_upgrade_reminder",
        }


# ============================================
# TRIAL PRICE CONFIGURATION
# ============================================

# These need to be created in Stripe Dashboard
# Each trial price should be set up as:
# - Recurring monthly price
# - Trial period configured in Stripe (or we override via API)

TRIAL_PRICES = {
    "reactor_ai_trial": {
        "price_id": "price_reactor_trial",
        "post_trial_price": 9.99,
        "description": "Reactor AI + DEFCON ONE (90-day trial)",
    },
    "developer_tools_trial": {
        "price_id": "price_devtools_trial",
        "post_trial_price": 14.99,
        "description": "Forgejo + Woodpecker + VS Code (30-day trial)",
    },
    "creator_tools_trial": {
        "price_id": "price_creator_trial",
        "post_trial_price": 9.99,
        "description": "Ghost + Saleor (30-day trial)",
    },
    "collaboration_trial": {
        "price_id": "price_collab_trial",
        "post_trial_price": 14.99,
        "description": "Matrix + Jitsi + Collabora (14-day trial)",
    },
}


# ============================================
# WEBHOOK HANDLER (Flask/FastAPI Example)
# ============================================

def create_webhook_handler(billing: WOPRBilling, provisioner):
    """
    Create a webhook handler function.

    This returns a function that can be used as a route handler
    in Flask, FastAPI, or other frameworks.

    Args:
        billing: WOPRBilling instance
        provisioner: WOPRProvisioner instance for triggering deployments

    Returns:
        Handler function
    """
    async def handle_stripe_webhook(request):
        """
        Webhook endpoint for Stripe events.

        POST /webhooks/stripe
        """
        payload = await request.body()
        signature = request.headers.get("Stripe-Signature")

        try:
            result = billing.process_webhook(payload, signature)

            # Trigger provisioning if payment completed
            if result.get("ready_to_provision"):
                # This would be async in production
                provision_result = provisioner.provision_for_bundle(
                    bundle=result["bundle"],
                    domain=f"{result['customer_id']}.wopr.systems",
                    customer_id=result["customer_id"],
                    provider_id=result["provider_id"],
                )

                result["provision_result"] = {
                    "success": provision_result.success,
                    "instance_ip": provision_result.instance.ip_address if provision_result.instance else None,
                }

            return {"status": "ok", "result": result}

        except ValueError as e:
            return {"status": "error", "message": str(e)}, 400

    return handle_stripe_webhook
