"""
WOPR Intent Resolver
====================

Resolves user intents to dashboard destinations.

Flow:
1. User visits /go/drive
2. Resolver checks authentication
3. Resolver identifies user's Beacon(s)
4. Resolver checks if capability exists on Beacon
5. Resolver redirects to dashboard section OR shows explanation

Users NEVER see:
- Raw app URLs (nextcloud.beacon.wopr.systems)
- Infrastructure details
- Module names

Users ALWAYS land on:
- Dashboard with appropriate section visible
- OR explanation of what's missing
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

from .capabilities import (
    Capability,
    CAPABILITY_MAP,
    get_capability_for_intent,
    get_module_for_capability,
    get_dashboard_section,
)


class ResolverResult(str, Enum):
    """Possible outcomes of intent resolution."""
    REDIRECT_DASHBOARD = "redirect_dashboard"  # Happy path
    REDIRECT_LOGIN = "redirect_login"  # Not authenticated
    REDIRECT_ONBOARD = "redirect_onboard"  # No Beacon yet
    SHOW_UNAVAILABLE = "show_unavailable"  # Capability not on Beacon
    SHOW_ERROR = "show_error"  # Something went wrong


@dataclass
class Intent:
    """
    Represents a user's intent.

    Created from /go/{intent} URLs.
    """
    raw: str  # Original intent string from URL
    capability: Optional[Capability]  # Resolved capability
    valid: bool  # Whether intent maps to a known capability

    @classmethod
    def from_path(cls, path: str) -> "Intent":
        """Parse intent from URL path component."""
        raw = path.strip("/").lower()
        capability = get_capability_for_intent(raw)
        return cls(
            raw=raw,
            capability=capability,
            valid=capability is not None,
        )


@dataclass
class ResolvedIntent:
    """
    Result of resolving an intent for a specific user.
    """
    intent: Intent
    result: ResolverResult
    redirect_url: Optional[str] = None
    dashboard_section: Optional[str] = None
    module_id: Optional[str] = None
    message: Optional[str] = None
    beacon_id: Optional[str] = None


@dataclass
class Beacon:
    """
    Represents a user's Beacon (their server).

    In production, this comes from the database.
    """
    id: str
    owner_id: str  # Authentik user ID
    domain: str  # e.g., "mybeacon.wopr.systems"
    bundle: str  # e.g., "personal", "developer"
    modules: List[str]  # Installed module IDs
    active: bool = True


class IntentResolver:
    """
    Resolves user intents to dashboard destinations.

    This is the core routing logic for the WOPR Beacon system.
    """

    def __init__(self, dashboard_base_url: str = "/dashboard"):
        self.dashboard_base = dashboard_base_url

    def resolve(
        self,
        intent: Intent,
        user: Optional[Dict[str, Any]] = None,
        beacons: Optional[List[Beacon]] = None,
    ) -> ResolvedIntent:
        """
        Resolve an intent for a user.

        Args:
            intent: The parsed intent
            user: User identity from Authentik (None if not authenticated)
            beacons: User's Beacon(s) (None if not authenticated)

        Returns:
            ResolvedIntent with redirect or explanation
        """
        # Step 1: Check authentication
        if user is None:
            return ResolvedIntent(
                intent=intent,
                result=ResolverResult.REDIRECT_LOGIN,
                redirect_url="/auth/login",
                message="Please sign in to continue",
            )

        # Step 2: Check if intent is valid
        if not intent.valid:
            return ResolvedIntent(
                intent=intent,
                result=ResolverResult.SHOW_ERROR,
                message=f"Unknown destination: {intent.raw}",
            )

        # Step 3: Check if user has a Beacon
        if not beacons or len(beacons) == 0:
            return ResolvedIntent(
                intent=intent,
                result=ResolverResult.REDIRECT_ONBOARD,
                redirect_url="/onboard",
                message="You don't have a Beacon yet. Let's set one up.",
            )

        # Step 4: Find a Beacon with the requested capability
        # For now, use first active Beacon (multi-Beacon support later)
        beacon = next((b for b in beacons if b.active), None)
        if not beacon:
            return ResolvedIntent(
                intent=intent,
                result=ResolverResult.SHOW_ERROR,
                message="No active Beacon found",
            )

        # Step 5: Check if capability exists on Beacon
        module_id = get_module_for_capability(
            intent.capability,
            beacon.modules,
        )

        if module_id is None:
            # Capability not available - show explanation
            mapping = CAPABILITY_MAP.get(intent.capability)
            return ResolvedIntent(
                intent=intent,
                result=ResolverResult.SHOW_UNAVAILABLE,
                beacon_id=beacon.id,
                dashboard_section=get_dashboard_section(intent.capability),
                message=self._unavailable_message(intent.capability, mapping),
            )

        # Step 6: Success! Redirect to dashboard section
        section = get_dashboard_section(intent.capability)
        redirect_url = f"{self.dashboard_base}/beacon/{beacon.id}/{section}"

        return ResolvedIntent(
            intent=intent,
            result=ResolverResult.REDIRECT_DASHBOARD,
            redirect_url=redirect_url,
            dashboard_section=section,
            module_id=module_id,
            beacon_id=beacon.id,
        )

    def _unavailable_message(
        self,
        capability: Capability,
        mapping: Any,
    ) -> str:
        """Generate a calm explanation for unavailable capability."""
        name = mapping.display_name if mapping else capability.value.title()
        return (
            f"{name} isn't enabled on your Beacon yet. "
            "This is your server, running on your infrastructure. "
            "You can enable this capability from your dashboard."
        )


# Singleton resolver instance
_resolver = IntentResolver()


def resolve_intent(
    path: str,
    user: Optional[Dict[str, Any]] = None,
    beacons: Optional[List[Beacon]] = None,
) -> ResolvedIntent:
    """
    Convenience function to resolve an intent.

    Args:
        path: The intent path (e.g., "drive", "photos")
        user: User identity from Authentik
        beacons: User's Beacon(s)

    Returns:
        ResolvedIntent with redirect or explanation
    """
    intent = Intent.from_path(path)
    return _resolver.resolve(intent, user, beacons)


def get_available_intents() -> List[Dict[str, Any]]:
    """
    Get all available intents for documentation/UI.

    Returns list of intent info without exposing module details.
    """
    intents = []
    for capability, mapping in CAPABILITY_MAP.items():
        intents.append({
            "path": f"/go/{capability.value}",
            "name": mapping.display_name,
            "description": mapping.description,
            "icon": mapping.icon,
            "section": mapping.dashboard_section,
        })
    return intents


# Registry of all valid intents (for validation)
INTENT_REGISTRY = {cap.value for cap in Capability}
