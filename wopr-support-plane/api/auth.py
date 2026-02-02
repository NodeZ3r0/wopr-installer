"""Authentication middleware for Authentik forward-auth headers from Caddy."""

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request

TIER_DIAG = "diag"
TIER_REMEDIATE = "remediate"
TIER_BREAKGLASS = "breakglass"

GROUP_DIAG = "wopr-support-diag"
GROUP_REMEDIATE = "wopr-support-remediate"
GROUP_BREAKGLASS = "wopr-support-breakglass"

# Ordered highest to lowest privilege
TIER_HIERARCHY = [TIER_BREAKGLASS, TIER_REMEDIATE, TIER_DIAG]


@dataclass
class SupportUser:
    uid: str
    username: str
    email: str
    groups: list[str]

    @property
    def access_tier(self) -> str:
        """Return the highest access tier the user holds."""
        if GROUP_BREAKGLASS in self.groups:
            return TIER_BREAKGLASS
        if GROUP_REMEDIATE in self.groups:
            return TIER_REMEDIATE
        if GROUP_DIAG in self.groups:
            return TIER_DIAG
        return ""

    def has_tier(self, minimum_tier: str) -> bool:
        """Check if user meets the minimum tier requirement."""
        user_rank = (
            TIER_HIERARCHY.index(self.access_tier)
            if self.access_tier in TIER_HIERARCHY
            else len(TIER_HIERARCHY)
        )
        required_rank = (
            TIER_HIERARCHY.index(minimum_tier)
            if minimum_tier in TIER_HIERARCHY
            else -1
        )
        return user_rank <= required_rank


async def get_current_user(request: Request) -> SupportUser:
    """Extract and validate Authentik headers injected by Caddy."""
    uid = request.headers.get("X-Authentik-UID", "")
    username = request.headers.get("X-Authentik-Username", "")
    email = request.headers.get("X-Authentik-Email", "")
    groups_raw = request.headers.get("X-Authentik-Groups", "")

    if not uid:
        raise HTTPException(status_code=401, detail="Missing authentication headers")

    groups = [g.strip() for g in groups_raw.split(",") if g.strip()]

    user = SupportUser(uid=uid, username=username, email=email, groups=groups)

    if not user.access_tier:
        raise HTTPException(
            status_code=403,
            detail="No support-plane access tier assigned",
        )

    return user


def require_tier(minimum_tier: str) -> Callable:
    """Dependency factory that enforces a minimum access tier."""

    async def _check(user: SupportUser = Depends(get_current_user)) -> SupportUser:
        if not user.has_tier(minimum_tier):
            raise HTTPException(
                status_code=403,
                detail=f"Requires {minimum_tier} tier or higher",
            )
        return user

    return _check
