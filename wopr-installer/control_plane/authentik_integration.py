"""
WOPR Authentik Integration
==========================

Integration with Authentik for:
- Single Sign-On (SSO) across all WOPR apps
- Feature gating via group membership
- Trial access management
- DEFCON ONE role mapping

This implements the "WOPR One Key To Rule Them All" model where
Authentik handles authentication and WOPR/DEFCON handle authorization.

Group Naming Convention:
- {app}-users: Permanent access to app (e.g., reactor-users)
- {app}-trial: Trial access to app (e.g., reactor-trial)
- defcon-{role}: DEFCON ONE roles (operators, contributors, observers)
- wopr-{bundle}: Bundle membership (personal, creator, developer, professional)

Updated: January 2026
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class DEFCONRole(Enum):
    """DEFCON ONE authorization roles."""
    SUPER_AUTHORITY = "SUPER_AUTHORITY"  # nodez3r0 only
    OPERATOR = "OPERATOR"                # Can approve production changes
    CONTRIBUTOR = "CONTRIBUTOR"          # Can submit proposals
    OBSERVER = "OBSERVER"                # Read-only access


@dataclass
class AuthentikUser:
    """User identity from Authentik."""
    user_id: str
    username: str
    email: str
    groups: List[str]
    is_active: bool
    is_superuser: bool


@dataclass
class AuthentikGroup:
    """Authentik group definition."""
    pk: str
    name: str
    is_superuser: bool
    parent: Optional[str]
    users: List[str]


# ============================================
# WOPR GROUP DEFINITIONS
# ============================================

# These groups should be created in Authentik during WOPR setup

WOPR_GROUPS = {
    # Bundle groups (every user is in exactly one)
    "wopr-personal": {
        "name": "WOPR Personal Users",
        "description": "Personal Sovereign Suite subscribers",
    },
    "wopr-creator": {
        "name": "WOPR Creator Users",
        "description": "Creator Sovereign Suite subscribers",
    },
    "wopr-developer": {
        "name": "WOPR Developer Users",
        "description": "Developer Sovereign Suite subscribers",
    },
    "wopr-professional": {
        "name": "WOPR Professional Users",
        "description": "Professional Sovereign Suite subscribers",
    },

    # App access groups (permanent)
    "nextcloud-users": {"name": "Nextcloud Users", "description": "Access to Nextcloud"},
    "vaultwarden-users": {"name": "Vaultwarden Users", "description": "Access to password manager"},
    "forgejo-users": {"name": "Forgejo Users", "description": "Access to Git repositories"},
    "woodpecker-users": {"name": "Woodpecker CI Users", "description": "Access to CI/CD"},
    "reactor-users": {"name": "Reactor AI Users", "description": "Access to AI coding assistant"},
    "ghost-users": {"name": "Ghost Users", "description": "Access to blog platform"},
    "saleor-users": {"name": "Saleor Users", "description": "Access to e-commerce"},
    "matrix-users": {"name": "Matrix/Element Users", "description": "Access to chat"},
    "jitsi-users": {"name": "Jitsi Users", "description": "Access to video calls"},
    "collabora-users": {"name": "Collabora Users", "description": "Access to online office"},
    "outline-users": {"name": "Outline Users", "description": "Access to wiki"},

    # Trial access groups (temporary)
    "reactor-trial": {"name": "Reactor AI Trial", "description": "90-day trial access"},
    "forgejo-trial": {"name": "Forgejo Trial", "description": "30-day trial access"},
    "woodpecker-trial": {"name": "Woodpecker CI Trial", "description": "30-day trial access"},
    "ghost-trial": {"name": "Ghost Trial", "description": "30-day trial access"},
    "saleor-trial": {"name": "Saleor Trial", "description": "30-day trial access"},
    "matrix-trial": {"name": "Matrix Trial", "description": "14-day trial access"},
    "jitsi-trial": {"name": "Jitsi Trial", "description": "14-day trial access"},
    "collabora-trial": {"name": "Collabora Trial", "description": "14-day trial access"},
    "defcon-trial": {"name": "DEFCON ONE Trial", "description": "90-day trial access"},
    "ollama-users": {"name": "Ollama Users", "description": "Access to local LLM"},

    # DEFCON ONE roles
    "defcon-operators": {
        "name": "DEFCON ONE Operators",
        "description": "Can approve production deployments",
    },
    "defcon-contributors": {
        "name": "DEFCON ONE Contributors",
        "description": "Can submit deployment proposals",
    },
    "defcon-observers": {
        "name": "DEFCON ONE Observers",
        "description": "Read-only access to DEFCON",
    },
}

# Bundle -> Groups mapping
# Updated for new Sovereign Suites and Micro-Bundles
BUNDLE_GROUPS = {
    # ==========================================
    # SOVEREIGN SUITES
    # ==========================================
    "starter": [
        "wopr-starter",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
    ],
    "creator": [
        "wopr-creator",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "ghost-users",
        "saleor-users",
        "immich-users",
        "listmonk-users",
    ],
    "developer": [
        "wopr-developer",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "forgejo-users",
        "woodpecker-users",
        "code-server-users",
        "reactor-users",
        "ollama-users",
        "uptime-kuma-users",
        "defcon-contributors",
    ],
    "professional": [
        "wopr-professional",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "ghost-users",
        "saleor-users",
        "immich-users",
        "listmonk-users",
        "forgejo-users",
        "woodpecker-users",
        "code-server-users",
        "reactor-users",
        "ollama-users",
        "matrix-users",
        "jitsi-users",
        "collabora-users",
        "outline-users",
        "uptime-kuma-users",
        "grafana-users",
        "defcon-operators",
    ],
    "family": [
        "wopr-family",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "immich-users",
        "jellyfin-users",
        "navidrome-users",
    ],
    "small_business": [
        "wopr-small-business",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "ghost-users",
        "saleor-users",
        "immich-users",
        "listmonk-users",
        "forgejo-users",
        "woodpecker-users",
        "reactor-users",
        "ollama-users",
        "matrix-users",
        "jitsi-users",
        "collabora-users",
        "outline-users",
        "invoiceninja-users",
        "calcom-users",
        "docuseal-users",
        "paperless-users",
        "uptime-kuma-users",
        "grafana-users",
        "defcon-operators",
    ],
    "enterprise": [
        "wopr-enterprise",
        # Enterprise gets all app groups
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
        "ghost-users",
        "saleor-users",
        "immich-users",
        "listmonk-users",
        "forgejo-users",
        "woodpecker-users",
        "code-server-users",
        "reactor-users",
        "ollama-users",
        "matrix-users",
        "jitsi-users",
        "collabora-users",
        "outline-users",
        "jellyfin-users",
        "navidrome-users",
        "audiobookshelf-users",
        "peertube-users",
        "invoiceninja-users",
        "calcom-users",
        "docuseal-users",
        "paperless-users",
        "uptime-kuma-users",
        "grafana-users",
        "defcon-operators",
    ],

    # ==========================================
    # MICRO-BUNDLES
    # ==========================================
    "meeting_room": [
        "wopr-meeting-room",
        "jitsi-users",
        "calcom-users",
        "outline-users",
    ],
    "privacy_pack": [
        "wopr-privacy-pack",
        "nextcloud-users",
        "vaultwarden-users",
    ],
    "writer_studio": [
        "wopr-writer-studio",
        "ghost-users",
        "listmonk-users",
        "linkwarden-users",
        "freshrss-users",
    ],
    "artist_storefront": [
        "wopr-artist-storefront",
        "saleor-users",
        "immich-users",
        "ghost-users",
    ],
    "podcaster": [
        "wopr-podcaster",
        "audiobookshelf-users",
        "ghost-users",
        "listmonk-users",
    ],
    "freelancer": [
        "wopr-freelancer",
        "invoiceninja-users",
        "calcom-users",
        "nextcloud-users",
        "vaultwarden-users",
    ],
    "musician": [
        "wopr-musician",
        "navidrome-users",
        "ghost-users",
        "saleor-users",
    ],
    "family_hub": [
        "wopr-family-hub",
        "nextcloud-users",
        "vaultwarden-users",
        "immich-users",
    ],
    "photographer": [
        "wopr-photographer",
        "immich-users",
        "saleor-users",
        "ghost-users",
    ],
    "bookkeeper": [
        "wopr-bookkeeper",
        "paperless-users",
        "nextcloud-users",
        "vaultwarden-users",
    ],
    "video_creator": [
        "wopr-video-creator",
        "peertube-users",
        "ghost-users",
        "saleor-users",
    ],
    "contractor": [
        "wopr-contractor",
        "docuseal-users",
        "vikunja-users",
        "invoiceninja-users",
        "calcom-users",
    ],
    "realtor": [
        "wopr-realtor",
        "immich-users",
        "calcom-users",
        "docuseal-users",
        "nextcloud-users",
    ],
    "educator": [
        "wopr-educator",
        "jitsi-users",
        "collabora-users",
        "outline-users",
        "nextcloud-users",
    ],
    "therapist": [
        "wopr-therapist",
        "jitsi-users",
        "calcom-users",
        "nextcloud-users",
        "vaultwarden-users",
    ],
    "legal": [
        "wopr-legal",
        "paperless-users",
        "docuseal-users",
        "vaultwarden-users",
        "nextcloud-users",
    ],

    # Legacy alias for backward compatibility
    "personal": [
        "wopr-starter",
        "nextcloud-users",
        "vaultwarden-users",
        "freshrss-users",
        "linkwarden-users",
        "vikunja-users",
    ],
}


class AuthentikClient:
    """
    Client for Authentik API.

    Handles user and group management for WOPR feature gating.
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
    ):
        """
        Initialize Authentik client.

        Args:
            base_url: Authentik instance URL (e.g., https://auth.wopr.systems)
            api_token: Authentik API token
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make API request to Authentik."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx not installed. Run: pip install httpx")

        url = f"{self.base_url}/api/v3/{endpoint}"

        with httpx.Client() as client:
            response = client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

    # =========================================
    # USER MANAGEMENT
    # =========================================

    def get_user(self, user_id: str) -> Optional[AuthentikUser]:
        """Get user by ID."""
        try:
            data = self._request("GET", f"core/users/{user_id}/")
            return AuthentikUser(
                user_id=str(data["pk"]),
                username=data["username"],
                email=data["email"],
                groups=[g["name"] for g in data.get("groups_obj", [])],
                is_active=data["is_active"],
                is_superuser=data["is_superuser"],
            )
        except Exception:
            return None

    def get_user_by_email(self, email: str) -> Optional[AuthentikUser]:
        """Get user by email address."""
        try:
            data = self._request("GET", f"core/users/?email={email}")
            if data.get("results"):
                user_data = data["results"][0]
                return AuthentikUser(
                    user_id=str(user_data["pk"]),
                    username=user_data["username"],
                    email=user_data["email"],
                    groups=[g["name"] for g in user_data.get("groups_obj", [])],
                    is_active=user_data["is_active"],
                    is_superuser=user_data["is_superuser"],
                )
        except Exception:
            pass
        return None

    def create_user(
        self,
        username: str,
        email: str,
        name: str,
    ) -> AuthentikUser:
        """
        Create a new Authentik user.

        Used during WOPR provisioning to create the admin user.
        """
        data = self._request("POST", "core/users/", {
            "username": username,
            "email": email,
            "name": name,
            "is_active": True,
        })

        return AuthentikUser(
            user_id=str(data["pk"]),
            username=data["username"],
            email=data["email"],
            groups=[],
            is_active=True,
            is_superuser=False,
        )

    # =========================================
    # GROUP MANAGEMENT
    # =========================================

    def get_group(self, group_name: str) -> Optional[AuthentikGroup]:
        """Get group by name."""
        try:
            data = self._request("GET", f"core/groups/?name={group_name}")
            if data.get("results"):
                group_data = data["results"][0]
                return AuthentikGroup(
                    pk=str(group_data["pk"]),
                    name=group_data["name"],
                    is_superuser=group_data.get("is_superuser", False),
                    parent=group_data.get("parent"),
                    users=[str(u) for u in group_data.get("users", [])],
                )
        except Exception:
            pass
        return None

    def create_group(self, name: str, is_superuser: bool = False) -> AuthentikGroup:
        """Create a new group."""
        data = self._request("POST", "core/groups/", {
            "name": name,
            "is_superuser": is_superuser,
        })

        return AuthentikGroup(
            pk=str(data["pk"]),
            name=data["name"],
            is_superuser=data.get("is_superuser", False),
            parent=None,
            users=[],
        )

    def add_user_to_group(self, user_id: str, group_name: str) -> bool:
        """Add user to a group."""
        group = self.get_group(group_name)
        if not group:
            return False

        try:
            self._request("POST", f"core/groups/{group.pk}/add_user/", {
                "pk": int(user_id),
            })
            return True
        except Exception:
            return False

    def remove_user_from_group(self, user_id: str, group_name: str) -> bool:
        """Remove user from a group."""
        group = self.get_group(group_name)
        if not group:
            return False

        try:
            self._request("POST", f"core/groups/{group.pk}/remove_user/", {
                "pk": int(user_id),
            })
            return True
        except Exception:
            return False

    def get_user_groups(self, user_id: str) -> List[str]:
        """Get all groups a user belongs to."""
        user = self.get_user(user_id)
        return user.groups if user else []

    # =========================================
    # BUNDLE MANAGEMENT
    # =========================================

    def setup_user_for_bundle(
        self,
        user_id: str,
        bundle: str,
    ) -> Dict[str, Any]:
        """
        Configure user groups based on their bundle.

        This is called during provisioning to grant access to
        all apps included in their bundle.

        Args:
            user_id: Authentik user ID
            bundle: WOPR bundle (personal, creator, developer, professional)

        Returns:
            Dict with groups added
        """
        groups_to_add = BUNDLE_GROUPS.get(bundle, [])

        added = []
        failed = []

        for group_name in groups_to_add:
            if self.add_user_to_group(user_id, group_name):
                added.append(group_name)
            else:
                failed.append(group_name)

        return {
            "bundle": bundle,
            "groups_added": added,
            "groups_failed": failed,
            "total_groups": len(groups_to_add),
        }

    def upgrade_bundle(
        self,
        user_id: str,
        old_bundle: str,
        new_bundle: str,
    ) -> Dict[str, Any]:
        """
        Upgrade user to a new bundle.

        Adds new groups and optionally removes old bundle group.
        """
        old_groups = set(BUNDLE_GROUPS.get(old_bundle, []))
        new_groups = set(BUNDLE_GROUPS.get(new_bundle, []))

        # Groups to add (in new but not old)
        to_add = new_groups - old_groups

        # Remove old bundle group
        old_bundle_group = f"wopr-{old_bundle}"
        if old_bundle_group in old_groups:
            self.remove_user_from_group(user_id, old_bundle_group)

        # Add new groups
        added = []
        for group_name in to_add:
            if self.add_user_to_group(user_id, group_name):
                added.append(group_name)

        return {
            "old_bundle": old_bundle,
            "new_bundle": new_bundle,
            "groups_added": added,
        }

    # =========================================
    # TRIAL MANAGEMENT
    # =========================================

    def grant_trial_access(
        self,
        user_id: str,
        trial_groups: List[str],
    ) -> Dict[str, Any]:
        """
        Grant trial access to user.

        Adds user to trial-specific groups (e.g., reactor-trial).

        Args:
            user_id: Authentik user ID
            trial_groups: List of trial group names

        Returns:
            Dict with results
        """
        added = []
        failed = []

        for group_name in trial_groups:
            if self.add_user_to_group(user_id, group_name):
                added.append(group_name)
            else:
                failed.append(group_name)

        return {
            "trial_groups_added": added,
            "trial_groups_failed": failed,
        }

    def revoke_trial_access(
        self,
        user_id: str,
        trial_groups: List[str],
    ) -> Dict[str, Any]:
        """
        Revoke trial access from user.

        Called when trial expires without conversion.
        """
        removed = []
        failed = []

        for group_name in trial_groups:
            if self.remove_user_from_group(user_id, group_name):
                removed.append(group_name)
            else:
                failed.append(group_name)

        return {
            "trial_groups_removed": removed,
            "trial_groups_failed": failed,
        }

    def convert_trial_to_permanent(
        self,
        user_id: str,
        trial_groups: List[str],
    ) -> Dict[str, Any]:
        """
        Convert trial access to permanent access.

        Moves user from trial groups (e.g., reactor-trial)
        to permanent groups (e.g., reactor-users).
        """
        converted = []

        for trial_group in trial_groups:
            # Remove -trial suffix and add -users
            permanent_group = trial_group.replace("-trial", "-users")

            # Remove from trial group
            self.remove_user_from_group(user_id, trial_group)

            # Add to permanent group
            if self.add_user_to_group(user_id, permanent_group):
                converted.append({
                    "from": trial_group,
                    "to": permanent_group,
                })

        return {"converted": converted}

    # =========================================
    # DEFCON ONE INTEGRATION
    # =========================================

    def get_defcon_role(self, user_id: str) -> DEFCONRole:
        """
        Determine user's DEFCON ONE role based on group membership.

        Role hierarchy:
        1. nodez3r0 -> SUPER_AUTHORITY
        2. defcon-operators -> OPERATOR
        3. defcon-contributors -> CONTRIBUTOR
        4. defcon-observers -> OBSERVER

        Raises PermissionError if no valid role.
        """
        groups = self.get_user_groups(user_id)

        if "nodez3r0" in groups:
            return DEFCONRole.SUPER_AUTHORITY
        if "defcon-operators" in groups:
            return DEFCONRole.OPERATOR
        if "defcon-contributors" in groups:
            return DEFCONRole.CONTRIBUTOR
        if "defcon-observers" in groups:
            return DEFCONRole.OBSERVER

        raise PermissionError("No valid DEFCON ONE role assigned")

    def can_approve_deployments(self, user_id: str) -> bool:
        """Check if user can approve production deployments."""
        try:
            role = self.get_defcon_role(user_id)
            return role in [DEFCONRole.SUPER_AUTHORITY, DEFCONRole.OPERATOR]
        except PermissionError:
            return False

    def can_submit_proposals(self, user_id: str) -> bool:
        """Check if user can submit deployment proposals."""
        try:
            role = self.get_defcon_role(user_id)
            return role in [
                DEFCONRole.SUPER_AUTHORITY,
                DEFCONRole.OPERATOR,
                DEFCONRole.CONTRIBUTOR,
            ]
        except PermissionError:
            return False

    # =========================================
    # INITIALIZATION
    # =========================================

    def initialize_wopr_groups(self) -> Dict[str, Any]:
        """
        Create all WOPR groups in Authentik.

        Called during initial WOPR setup.
        """
        created = []
        existing = []
        failed = []

        for group_name, group_info in WOPR_GROUPS.items():
            existing_group = self.get_group(group_name)

            if existing_group:
                existing.append(group_name)
            else:
                try:
                    self.create_group(group_name)
                    created.append(group_name)
                except Exception as e:
                    failed.append({"name": group_name, "error": str(e)})

        return {
            "created": created,
            "existing": existing,
            "failed": failed,
            "total": len(WOPR_GROUPS),
        }


# ============================================
# FEATURE GATING HELPERS
# ============================================

def check_feature_access(
    user_groups: List[str],
    required_groups: List[str],
    trial_groups: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Check if user has access to a feature.

    Access is granted if user is in:
    - Any of the required_groups (permanent access), OR
    - Any of the trial_groups (trial access)

    Args:
        user_groups: User's current group memberships
        required_groups: Groups that grant permanent access
        trial_groups: Groups that grant trial access (optional)

    Returns:
        Dict with access status and type
    """
    user_set = set(user_groups)
    required_set = set(required_groups)
    trial_set = set(trial_groups or [])

    # Check permanent access
    if user_set & required_set:
        return {
            "has_access": True,
            "access_type": "permanent",
            "matching_groups": list(user_set & required_set),
        }

    # Check trial access
    if trial_set and (user_set & trial_set):
        return {
            "has_access": True,
            "access_type": "trial",
            "matching_groups": list(user_set & trial_set),
        }

    return {
        "has_access": False,
        "access_type": None,
        "required_groups": required_groups,
        "trial_available": bool(trial_groups),
    }


# Feature -> Groups mapping for quick lookups
FEATURE_ACCESS = {
    "nextcloud": {
        "permanent": ["nextcloud-users"],
        "trial": [],
    },
    "vaultwarden": {
        "permanent": ["vaultwarden-users"],
        "trial": [],
    },
    "forgejo": {
        "permanent": ["forgejo-users"],
        "trial": ["forgejo-trial"],
    },
    "woodpecker": {
        "permanent": ["woodpecker-users"],
        "trial": ["woodpecker-trial"],
    },
    "reactor": {
        "permanent": ["reactor-users"],
        "trial": ["reactor-trial"],
    },
    "defcon_one": {
        "permanent": ["defcon-operators", "defcon-contributors"],
        "trial": ["defcon-trial"],
    },
    "ghost": {
        "permanent": ["ghost-users"],
        "trial": ["ghost-trial"],
    },
    "saleor": {
        "permanent": ["saleor-users"],
        "trial": ["saleor-trial"],
    },
    "matrix": {
        "permanent": ["matrix-users"],
        "trial": ["matrix-trial"],
    },
    "jitsi": {
        "permanent": ["jitsi-users"],
        "trial": ["jitsi-trial"],
    },
    "collabora": {
        "permanent": ["collabora-users"],
        "trial": ["collabora-trial"],
    },
}


def user_can_access_feature(user_groups: List[str], feature: str) -> Dict[str, Any]:
    """
    Check if user can access a specific WOPR feature.

    Args:
        user_groups: User's Authentik group memberships
        feature: Feature name (e.g., "reactor", "forgejo")

    Returns:
        Access check result
    """
    access_config = FEATURE_ACCESS.get(feature)
    if not access_config:
        return {"has_access": False, "error": f"Unknown feature: {feature}"}

    return check_feature_access(
        user_groups=user_groups,
        required_groups=access_config["permanent"],
        trial_groups=access_config.get("trial"),
    )
