"""
WOPR Intent Resolver API
========================

FastAPI routes for intent-based navigation.

Endpoints:
- GET /go/{intent} - Resolve intent and redirect
- GET /api/v1/intents - List available intents
- GET /api/v1/intents/{intent} - Get intent info

These endpoints are the ONLY way users navigate to capabilities.
Direct app URLs are never exposed.
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from .intents import (
    Intent,
    ResolvedIntent,
    ResolverResult,
    Beacon,
    resolve_intent,
    get_available_intents,
    INTENT_REGISTRY,
)
from .capabilities import (
    Capability,
    CAPABILITY_MAP,
    get_capability_display,
)
from ..models.beacon import beacon_store


# ============================================
# PYDANTIC MODELS
# ============================================

class IntentInfo(BaseModel):
    """Public info about an intent."""
    path: str
    name: str
    description: str
    icon: str
    section: str


class ResolvedIntentResponse(BaseModel):
    """Response for intent resolution (API mode)."""
    success: bool
    intent: str
    result: str
    redirect_url: Optional[str] = None
    section: Optional[str] = None
    message: Optional[str] = None
    beacon_id: Optional[str] = None


class UnavailableResponse(BaseModel):
    """Response when capability is unavailable."""
    available: bool
    capability: str
    name: str
    description: str
    message: str
    beacon_id: Optional[str] = None
    ask_joshua_url: str = "/joshua"


# ============================================
# ROUTER
# ============================================

router = APIRouter()


# ============================================
# DEPENDENCIES
# ============================================

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extract user identity from Authentik headers.
    Returns None if not authenticated (instead of raising).
    """
    user_id = request.headers.get("X-Authentik-UID")
    if not user_id:
        return None

    return {
        "user_id": user_id,
        "username": request.headers.get("X-Authentik-Username", ""),
        "email": request.headers.get("X-Authentik-Email", ""),
        "groups": request.headers.get("X-Authentik-Groups", "").split(","),
    }


async def get_user_beacons(user: Optional[Dict[str, Any]]) -> List[Beacon]:
    """
    Get Beacon(s) owned by or accessible to a user.

    Uses the beacon store (in-memory for dev, PostgreSQL in production).
    Falls back to mock data if no beacons exist yet.
    """
    if not user:
        return []

    # Get beacons from store
    stored_beacons = beacon_store.get_by_owner(user["user_id"])

    if stored_beacons:
        # Convert stored beacons to resolver Beacon type
        return [
            Beacon(
                id=b.id,
                owner_id=b.owner_id,
                domain=b.domain,
                bundle=b.bundle,
                modules=b.modules,
                active=b.status.value == "active" if hasattr(b.status, 'value') else b.status == "active",
            )
            for b in stored_beacons
        ]

    # Fallback: Mock beacon for development when no beacons exist
    # This allows testing without provisioning
    return [
        Beacon(
            id="dev-beacon-001",
            owner_id=user["user_id"],
            domain="dev.wopr.systems",
            bundle="developer",
            modules=[
                # Core
                "authentik", "caddy", "postgresql", "redis",
                # Personal
                "nextcloud", "vaultwarden", "freshrss",
                # Developer
                "forgejo", "woodpecker", "code_server",
                "uptime_kuma", "reactor",
            ],
            active=True,
        )
    ]


# ============================================
# INTENT RESOLUTION ENDPOINTS
# ============================================

@router.get("/go/{intent:path}")
async def resolve_go_intent(
    intent: str,
    request: Request,
    user: Optional[Dict] = Depends(get_current_user_optional),
):
    """
    Resolve an intent and redirect to the appropriate destination.

    This is the primary navigation endpoint. Users click links like:
    - /go/drive
    - /go/photos
    - /go/shop

    And are redirected to the appropriate dashboard section.
    """
    # Get user's beacons
    beacons = await get_user_beacons(user)

    # Resolve the intent
    resolved = resolve_intent(intent, user, beacons)

    # Handle each result type
    if resolved.result == ResolverResult.REDIRECT_LOGIN:
        # Redirect to login, preserving original intent
        login_url = f"/auth/login?next=/go/{intent}"
        return RedirectResponse(url=login_url, status_code=302)

    elif resolved.result == ResolverResult.REDIRECT_ONBOARD:
        # User has no Beacon - redirect to onboarding
        return RedirectResponse(url="/onboard", status_code=302)

    elif resolved.result == ResolverResult.REDIRECT_DASHBOARD:
        # Success! Redirect to dashboard section
        return RedirectResponse(url=resolved.redirect_url, status_code=302)

    elif resolved.result == ResolverResult.SHOW_UNAVAILABLE:
        # Capability not on Beacon - show explanation page
        return RedirectResponse(
            url=f"/dashboard/unavailable?capability={intent}&beacon={resolved.beacon_id}",
            status_code=302,
        )

    elif resolved.result == ResolverResult.SHOW_ERROR:
        # Unknown intent
        raise HTTPException(
            status_code=404,
            detail=f"Unknown destination: {intent}",
        )

    # Fallback
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/api/v1/intents", response_model=List[IntentInfo])
async def list_intents():
    """
    List all available intents.

    Returns public info about each intent without exposing
    underlying module details.
    """
    return get_available_intents()


@router.get("/api/v1/intents/{intent}")
async def get_intent_info(intent: str):
    """
    Get info about a specific intent.
    """
    if intent not in INTENT_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown intent: {intent}",
        )

    try:
        capability = Capability(intent)
        display = get_capability_display(capability)
        return {
            "intent": intent,
            "path": f"/go/{intent}",
            **display,
        }
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown intent: {intent}",
        )


@router.get("/api/v1/resolve/{intent}")
async def resolve_intent_api(
    intent: str,
    request: Request,
    user: Optional[Dict] = Depends(get_current_user_optional),
):
    """
    Resolve an intent and return the result as JSON.

    Unlike /go/{intent}, this doesn't redirect - it returns
    the resolution result for the frontend to handle.
    """
    beacons = await get_user_beacons(user)
    resolved = resolve_intent(intent, user, beacons)

    return ResolvedIntentResponse(
        success=resolved.result == ResolverResult.REDIRECT_DASHBOARD,
        intent=intent,
        result=resolved.result.value,
        redirect_url=resolved.redirect_url,
        section=resolved.dashboard_section,
        message=resolved.message,
        beacon_id=resolved.beacon_id,
    )


@router.get("/api/v1/beacon/{beacon_id}/capabilities")
async def get_beacon_capabilities(
    beacon_id: str,
    request: Request,
    user: Optional[Dict] = Depends(get_current_user_optional),
):
    """
    Get capabilities available on a specific Beacon.

    Returns what the user CAN do, not what modules exist.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    beacons = await get_user_beacons(user)
    beacon = next((b for b in beacons if b.id == beacon_id), None)

    if not beacon:
        raise HTTPException(status_code=404, detail="Beacon not found")

    # Map modules to capabilities
    capabilities = []
    for capability, mapping in CAPABILITY_MAP.items():
        # Check if any providing module is installed
        has_capability = (
            mapping.primary_module in beacon.modules or
            any(m in beacon.modules for m in mapping.fallback_modules)
        )

        capabilities.append({
            "capability": capability.value,
            "name": mapping.display_name,
            "description": mapping.description,
            "icon": mapping.icon,
            "section": mapping.dashboard_section,
            "available": has_capability,
            "path": f"/go/{capability.value}",
        })

    return {
        "beacon_id": beacon_id,
        "bundle": beacon.bundle,
        "capabilities": capabilities,
    }
