"""
WOPR Trial Management System
============================

Manages free trial periods for add-on modules.

Key features:
- 90-day free trial for Reactor AI + DEFCON ONE for lower tiers
- Stripe-tracked trial subscriptions (no payment until trial ends)
- Authentik group membership for feature gating
- Automatic notifications before trial expiry
- Clean upgrade path to paid bundle

The Trial Flow:
1. User on Personal/Creator bundle wants to try Reactor AI
2. They click "Start Free Trial" in dashboard
3. Stripe creates trial subscription (90 days, $0)
4. Authentik adds user to reactor-trial group
5. Ollama + Reactor + DEFCON ONE get installed
6. At day 75: email "Your trial ends in 15 days"
7. At day 90: either upgrade or modules disabled

Updated: January 2026
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import json

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False


class TrialStatus(Enum):
    """Trial subscription status."""
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"  # <15 days left
    EXPIRED = "expired"
    CONVERTED = "converted"  # Upgraded to paid
    CANCELLED = "cancelled"


@dataclass
class TrialConfig:
    """Configuration for a trial offering."""
    trial_id: str
    name: str
    description: str
    modules: List[str]  # Module IDs included in trial
    duration_days: int = 90
    stripe_price_id: str = ""  # Price ID for post-trial billing
    upgrade_bundle: str = ""  # Recommended upgrade bundle
    authentik_groups: List[str] = field(default_factory=list)


# ============================================
# TRIAL OFFERINGS
# ============================================

TRIAL_OFFERINGS: Dict[str, TrialConfig] = {
    "reactor_ai_trial": TrialConfig(
        trial_id="reactor_ai_trial",
        name="Reactor AI Developer Trial",
        description="Try AI-powered coding with DEFCON ONE safety controls",
        modules=["ollama", "reactor", "defcon_one"],
        duration_days=90,
        stripe_price_id="price_reactor_trial",  # $0 for 90 days, then $9.99/mo
        upgrade_bundle="developer",
        authentik_groups=["reactor-trial", "defcon-trial", "ollama-users"],
    ),

    "developer_tools_trial": TrialConfig(
        trial_id="developer_tools_trial",
        name="Developer Tools Trial",
        description="Try Git hosting, CI/CD, and VS Code in browser",
        modules=["forgejo", "woodpecker", "code_server"],
        duration_days=30,
        stripe_price_id="price_devtools_trial",
        upgrade_bundle="developer",
        authentik_groups=["forgejo-trial", "woodpecker-trial", "code-server-trial"],
    ),

    "creator_tools_trial": TrialConfig(
        trial_id="creator_tools_trial",
        name="Creator Tools Trial",
        description="Try professional blogging and e-commerce",
        modules=["ghost", "saleor"],
        duration_days=30,
        stripe_price_id="price_creator_trial",
        upgrade_bundle="creator",
        authentik_groups=["ghost-trial", "saleor-trial"],
    ),

    "collaboration_trial": TrialConfig(
        trial_id="collaboration_trial",
        name="Team Collaboration Trial",
        description="Try Matrix chat, Jitsi video, and Collabora office",
        modules=["matrix", "element", "jitsi", "collabora"],
        duration_days=14,  # Expensive resources, shorter trial
        stripe_price_id="price_collab_trial",
        upgrade_bundle="professional",
        authentik_groups=["matrix-trial", "jitsi-trial", "collabora-trial"],
    ),
}


@dataclass
class ActiveTrial:
    """An active trial for a customer."""
    trial_id: str
    customer_id: str
    instance_id: str
    stripe_subscription_id: str
    started_at: datetime
    expires_at: datetime
    status: TrialStatus
    modules_installed: List[str]
    reminder_sent_15_days: bool = False
    reminder_sent_7_days: bool = False
    reminder_sent_1_day: bool = False

    def days_remaining(self) -> int:
        """Get days remaining in trial."""
        if self.status not in [TrialStatus.ACTIVE, TrialStatus.EXPIRING_SOON]:
            return 0
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    def is_expiring_soon(self) -> bool:
        """Check if trial is expiring within 15 days."""
        return 0 < self.days_remaining() <= 15

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "trial_id": self.trial_id,
            "customer_id": self.customer_id,
            "instance_id": self.instance_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status.value,
            "modules_installed": self.modules_installed,
            "reminder_sent_15_days": self.reminder_sent_15_days,
            "reminder_sent_7_days": self.reminder_sent_7_days,
            "reminder_sent_1_day": self.reminder_sent_1_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveTrial":
        """Deserialize from storage."""
        return cls(
            trial_id=data["trial_id"],
            customer_id=data["customer_id"],
            instance_id=data["instance_id"],
            stripe_subscription_id=data["stripe_subscription_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            status=TrialStatus(data["status"]),
            modules_installed=data["modules_installed"],
            reminder_sent_15_days=data.get("reminder_sent_15_days", False),
            reminder_sent_7_days=data.get("reminder_sent_7_days", False),
            reminder_sent_1_day=data.get("reminder_sent_1_day", False),
        )


class TrialManager:
    """
    Manages trial subscriptions across Stripe, Authentik, and module deployment.

    This is the central coordinator for the trial system.
    """

    def __init__(
        self,
        stripe_secret_key: str,
        authentik_api_url: str,
        authentik_api_token: str,
    ):
        """
        Initialize trial manager.

        Args:
            stripe_secret_key: Stripe API key
            authentik_api_url: Authentik API base URL
            authentik_api_token: Authentik API token
        """
        if STRIPE_AVAILABLE:
            stripe.api_key = stripe_secret_key

        self.authentik_api_url = authentik_api_url
        self.authentik_api_token = authentik_api_token
        self._trials: Dict[str, ActiveTrial] = {}

    def get_available_trials(self, bundle_id: str) -> List[TrialConfig]:
        """
        Get trials available for a bundle.

        Users can only trial modules not in their bundle.
        """
        from .registry import BUNDLES

        bundle = BUNDLES.get(bundle_id)
        if not bundle:
            return []

        available = []
        for trial_id, trial in TRIAL_OFFERINGS.items():
            # Check if any trial module is not in user's bundle
            has_new_modules = any(
                m not in bundle.base_modules
                for m in trial.modules
            )
            if has_new_modules:
                available.append(trial)

        return available

    def start_trial(
        self,
        trial_id: str,
        customer_id: str,
        instance_id: str,
        customer_email: str,
    ) -> Dict[str, Any]:
        """
        Start a free trial for a customer.

        This:
        1. Creates a Stripe subscription with trial period
        2. Adds user to Authentik trial groups
        3. Triggers module installation
        4. Records trial in database

        Args:
            trial_id: Which trial offering
            customer_id: Stripe customer ID
            instance_id: WOPR instance ID
            customer_email: Customer email

        Returns:
            Trial details including expiry date
        """
        trial_config = TRIAL_OFFERINGS.get(trial_id)
        if not trial_config:
            raise ValueError(f"Unknown trial: {trial_id}")

        # Check if already has this trial
        existing = self._get_customer_trial(customer_id, trial_id)
        if existing and existing.status == TrialStatus.ACTIVE:
            raise ValueError(f"Trial already active: {trial_id}")

        # Create Stripe subscription with trial
        subscription = self._create_stripe_trial_subscription(
            customer_id=customer_id,
            trial_config=trial_config,
        )

        # Calculate dates
        started_at = datetime.now()
        expires_at = started_at + timedelta(days=trial_config.duration_days)

        # Create trial record
        active_trial = ActiveTrial(
            trial_id=trial_id,
            customer_id=customer_id,
            instance_id=instance_id,
            stripe_subscription_id=subscription["id"] if subscription else "",
            started_at=started_at,
            expires_at=expires_at,
            status=TrialStatus.ACTIVE,
            modules_installed=trial_config.modules,
        )

        # Store trial
        trial_key = f"{customer_id}:{trial_id}"
        self._trials[trial_key] = active_trial

        # Add to Authentik groups
        self._add_to_authentik_groups(
            customer_id=customer_id,
            groups=trial_config.authentik_groups,
        )

        return {
            "success": True,
            "trial_id": trial_id,
            "started_at": started_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "duration_days": trial_config.duration_days,
            "modules": trial_config.modules,
            "stripe_subscription_id": active_trial.stripe_subscription_id,
            "message": f"Your {trial_config.name} has started! "
                      f"You have {trial_config.duration_days} days to explore.",
        }

    def _create_stripe_trial_subscription(
        self,
        customer_id: str,
        trial_config: TrialConfig,
    ) -> Optional[Dict]:
        """
        Create Stripe subscription with trial period.

        The subscription is created with:
        - trial_period_days set to duration
        - No payment method required during trial
        - Automatic conversion to paid after trial

        Returns:
            Stripe subscription object or None if Stripe unavailable
        """
        if not STRIPE_AVAILABLE:
            return None

        # Create subscription with trial
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": trial_config.stripe_price_id}],
            trial_period_days=trial_config.duration_days,
            # Don't require payment method during trial
            payment_behavior="default_incomplete",
            # Metadata for tracking
            metadata={
                "wopr_trial_id": trial_config.trial_id,
                "wopr_trial_name": trial_config.name,
                "wopr_modules": ",".join(trial_config.modules),
            },
            # Expand for full details
            expand=["latest_invoice.payment_intent"],
        )

        return {
            "id": subscription.id,
            "status": subscription.status,
            "trial_end": subscription.trial_end,
            "current_period_end": subscription.current_period_end,
        }

    def _add_to_authentik_groups(
        self,
        customer_id: str,
        groups: List[str],
    ) -> bool:
        """
        Add user to Authentik groups for feature access.

        This grants the user access to trial features through
        Authentik's group-based authorization.
        """
        # TODO: Implement Authentik API calls
        # POST /api/v3/core/groups/{group_pk}/add_user/
        # with user ID

        # For now, log the intent
        print(f"[Authentik] Adding {customer_id} to groups: {groups}")
        return True

    def _remove_from_authentik_groups(
        self,
        customer_id: str,
        groups: List[str],
    ) -> bool:
        """Remove user from Authentik trial groups."""
        # TODO: Implement Authentik API calls
        # POST /api/v3/core/groups/{group_pk}/remove_user/

        print(f"[Authentik] Removing {customer_id} from groups: {groups}")
        return True

    def check_trial_status(
        self,
        customer_id: str,
        trial_id: str,
    ) -> Dict[str, Any]:
        """
        Check the status of a customer's trial.

        Returns current status, days remaining, and upgrade options.
        """
        trial = self._get_customer_trial(customer_id, trial_id)
        if not trial:
            return {
                "status": TrialStatus.NOT_STARTED.value,
                "can_start": True,
            }

        trial_config = TRIAL_OFFERINGS.get(trial_id)

        # Update status if expiring soon
        if trial.status == TrialStatus.ACTIVE and trial.is_expiring_soon():
            trial.status = TrialStatus.EXPIRING_SOON

        # Check if expired
        if trial.status in [TrialStatus.ACTIVE, TrialStatus.EXPIRING_SOON]:
            if datetime.now() >= trial.expires_at:
                trial.status = TrialStatus.EXPIRED
                self._handle_trial_expiry(trial)

        return {
            "status": trial.status.value,
            "trial_id": trial_id,
            "started_at": trial.started_at.isoformat(),
            "expires_at": trial.expires_at.isoformat(),
            "days_remaining": trial.days_remaining(),
            "modules": trial.modules_installed,
            "upgrade_bundle": trial_config.upgrade_bundle if trial_config else None,
            "upgrade_message": self._get_upgrade_message(trial),
        }

    def _get_customer_trial(
        self,
        customer_id: str,
        trial_id: str,
    ) -> Optional[ActiveTrial]:
        """Get a customer's trial by ID."""
        trial_key = f"{customer_id}:{trial_id}"
        return self._trials.get(trial_key)

    def _handle_trial_expiry(self, trial: ActiveTrial) -> None:
        """
        Handle trial expiration.

        This:
        1. Removes user from trial Authentik groups
        2. Disables trial modules (but doesn't delete data)
        3. Sends final upgrade email
        """
        trial_config = TRIAL_OFFERINGS.get(trial.trial_id)
        if trial_config:
            # Remove from trial groups
            self._remove_from_authentik_groups(
                customer_id=trial.customer_id,
                groups=trial_config.authentik_groups,
            )

        # Note: We don't delete the modules or their data
        # User can upgrade and resume, or modules stay dormant

    def _get_upgrade_message(self, trial: ActiveTrial) -> str:
        """Get contextual upgrade message based on trial status."""
        days = trial.days_remaining()
        trial_config = TRIAL_OFFERINGS.get(trial.trial_id)
        bundle = trial_config.upgrade_bundle if trial_config else "developer"

        if trial.status == TrialStatus.EXPIRED:
            return (
                f"Your trial has ended. Upgrade to the {bundle.title()} bundle "
                f"to continue using {trial_config.name if trial_config else 'these features'}."
            )
        elif days <= 7:
            return (
                f"Only {days} days left! Upgrade now to keep your "
                f"{trial_config.name if trial_config else 'trial features'} running."
            )
        elif days <= 15:
            return (
                f"Your trial ends in {days} days. "
                f"Ready to upgrade to {bundle.title()}?"
            )
        else:
            return (
                f"Enjoying your trial? {days} days remaining. "
                f"Upgrade anytime to unlock even more features."
            )

    def convert_trial_to_paid(
        self,
        customer_id: str,
        trial_id: str,
        new_bundle: str,
    ) -> Dict[str, Any]:
        """
        Convert a trial to a paid subscription.

        This happens when user upgrades their bundle.
        The trial subscription becomes a regular subscription.
        """
        trial = self._get_customer_trial(customer_id, trial_id)
        if not trial:
            raise ValueError("No active trial found")

        trial_config = TRIAL_OFFERINGS.get(trial_id)

        # Update Stripe subscription to remove trial
        if STRIPE_AVAILABLE and trial.stripe_subscription_id:
            stripe.Subscription.modify(
                trial.stripe_subscription_id,
                trial_end="now",  # End trial immediately
                proration_behavior="always_invoice",
            )

        # Move user from trial groups to permanent groups
        if trial_config:
            self._remove_from_authentik_groups(
                customer_id=customer_id,
                groups=trial_config.authentik_groups,
            )
            # Add to permanent groups (remove -trial suffix)
            permanent_groups = [
                g.replace("-trial", "-users")
                for g in trial_config.authentik_groups
            ]
            self._add_to_authentik_groups(
                customer_id=customer_id,
                groups=permanent_groups,
            )

        # Update trial status
        trial.status = TrialStatus.CONVERTED

        return {
            "success": True,
            "message": f"Welcome to {new_bundle.title()}! Your trial features are now permanent.",
            "new_bundle": new_bundle,
            "modules_unlocked": trial.modules_installed,
        }

    def cancel_trial(
        self,
        customer_id: str,
        trial_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel a trial early.

        User can cancel anytime. Modules get disabled but data preserved.
        """
        trial = self._get_customer_trial(customer_id, trial_id)
        if not trial:
            raise ValueError("No active trial found")

        # Cancel Stripe subscription
        if STRIPE_AVAILABLE and trial.stripe_subscription_id:
            stripe.Subscription.delete(trial.stripe_subscription_id)

        # Remove from Authentik groups
        trial_config = TRIAL_OFFERINGS.get(trial_id)
        if trial_config:
            self._remove_from_authentik_groups(
                customer_id=customer_id,
                groups=trial_config.authentik_groups,
            )

        trial.status = TrialStatus.CANCELLED

        return {
            "success": True,
            "message": "Trial cancelled. Your data has been preserved if you decide to upgrade later.",
        }

    def process_trial_reminders(self) -> List[Dict[str, Any]]:
        """
        Process all trials and send reminder notifications.

        Should be run daily via cron.

        Returns list of reminders sent.
        """
        reminders = []

        for trial_key, trial in self._trials.items():
            if trial.status not in [TrialStatus.ACTIVE, TrialStatus.EXPIRING_SOON]:
                continue

            days = trial.days_remaining()

            # 15-day reminder
            if days <= 15 and not trial.reminder_sent_15_days:
                reminders.append(self._send_trial_reminder(trial, 15))
                trial.reminder_sent_15_days = True

            # 7-day reminder
            elif days <= 7 and not trial.reminder_sent_7_days:
                reminders.append(self._send_trial_reminder(trial, 7))
                trial.reminder_sent_7_days = True

            # 1-day reminder
            elif days <= 1 and not trial.reminder_sent_1_day:
                reminders.append(self._send_trial_reminder(trial, 1))
                trial.reminder_sent_1_day = True

        return reminders

    def _send_trial_reminder(
        self,
        trial: ActiveTrial,
        days_remaining: int,
    ) -> Dict[str, Any]:
        """Send trial expiry reminder email."""
        trial_config = TRIAL_OFFERINGS.get(trial.trial_id)

        # TODO: Integrate with email service
        return {
            "type": "trial_reminder",
            "customer_id": trial.customer_id,
            "trial_id": trial.trial_id,
            "days_remaining": days_remaining,
            "upgrade_bundle": trial_config.upgrade_bundle if trial_config else None,
        }


# ============================================
# STRIPE WEBHOOK HANDLERS FOR TRIALS
# ============================================

def handle_trial_will_end(subscription: Dict) -> Dict[str, Any]:
    """
    Handle Stripe 'customer.subscription.trial_will_end' webhook.

    Sent 3 days before trial ends.
    """
    metadata = subscription.get("metadata", {})
    trial_id = metadata.get("wopr_trial_id")

    return {
        "event": "trial_will_end",
        "subscription_id": subscription["id"],
        "trial_id": trial_id,
        "trial_end": subscription.get("trial_end"),
        "action": "send_upgrade_reminder",
    }


def handle_subscription_updated(subscription: Dict) -> Dict[str, Any]:
    """
    Handle subscription status changes.

    If trial ends and becomes active (paid), convert the trial.
    If cancelled or unpaid, disable features.
    """
    status = subscription.get("status")
    metadata = subscription.get("metadata", {})
    trial_id = metadata.get("wopr_trial_id")

    if status == "active" and not subscription.get("trial_end"):
        # Trial converted to paid
        return {
            "event": "trial_converted",
            "trial_id": trial_id,
            "action": "upgrade_to_permanent",
        }
    elif status in ["canceled", "unpaid"]:
        return {
            "event": "trial_ended",
            "trial_id": trial_id,
            "action": "disable_trial_features",
        }

    return {"event": "subscription_updated", "status": status}
