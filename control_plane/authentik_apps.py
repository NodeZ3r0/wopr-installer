"""
WOPR Authentik App Registry
============================

Defines all WOPR applications and their Authentik configuration.

Each app has:
- OAuth2/OIDC provider settings
- Required group memberships for access
- Forward auth / proxy configuration
- Subdomain routing

This registry is used by:
1. Authentik setup scripts to create providers/applications
2. Bundle provisioning to determine app access
3. Dashboard to show available/locked apps

Updated: January 2026
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AuthMode(Enum):
    """Authentication mode for the app."""
    OAUTH2 = "oauth2"           # Full OAuth2/OIDC flow
    PROXY = "proxy"             # Forward auth via Authentik proxy
    HEADER = "header"           # Header-based auth (X-Authentik-*)
    NONE = "none"               # No auth (public)


class AppCategory(Enum):
    """App category for grouping in UI."""
    PRODUCTIVITY = "productivity"
    DEVELOPMENT = "development"
    COMMUNICATION = "communication"
    MEDIA = "media"
    COMMERCE = "commerce"
    SECURITY = "security"
    AI = "ai"
    SYSTEM = "system"


@dataclass
class AppConfig:
    """Configuration for a WOPR application."""
    id: str                         # Unique app identifier
    name: str                       # Display name
    description: str                # Short description
    subdomain: str                  # Subdomain (e.g., "files" -> files.beacon.wopr.systems)
    category: AppCategory           # Category for grouping
    auth_mode: AuthMode             # How to authenticate
    access_groups: List[str]        # Groups that grant permanent access
    trial_groups: List[str]         # Groups that grant trial access
    icon: str                       # Emoji or icon identifier
    oauth_redirect_uri: Optional[str] = None  # OAuth callback path
    proxy_skip_path_regex: Optional[str] = None  # Paths to skip auth
    internal_port: int = 80         # Internal container port
    requires_admin: bool = False    # Requires admin/superuser


# ============================================
# WOPR APPLICATION REGISTRY
# ============================================

WOPR_APPS: Dict[str, AppConfig] = {
    # ==========================================
    # PRODUCTIVITY APPS (Personal bundle base)
    # ==========================================
    "nextcloud": AppConfig(
        id="nextcloud",
        name="Nextcloud",
        description="Files, calendar, contacts, and more",
        subdomain="files",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["nextcloud-users"],
        trial_groups=[],
        icon="☁️",
        oauth_redirect_uri="/apps/sociallogin/custom_oidc/authentik",
        internal_port=80,
    ),
    "vaultwarden": AppConfig(
        id="vaultwarden",
        name="Vaultwarden",
        description="Password manager (Bitwarden compatible)",
        subdomain="vault",
        category=AppCategory.SECURITY,
        auth_mode=AuthMode.PROXY,
        access_groups=["vaultwarden-users"],
        trial_groups=[],
        icon="🔐",
        internal_port=80,
    ),
    "freshrss": AppConfig(
        id="freshrss",
        name="FreshRSS",
        description="RSS/Atom feed reader",
        subdomain="rss",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.HEADER,
        access_groups=["freshrss-users"],
        trial_groups=[],
        icon="📰",
        internal_port=80,
    ),
    "linkwarden": AppConfig(
        id="linkwarden",
        name="Linkwarden",
        description="Bookmark and link manager",
        subdomain="bookmarks",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["linkwarden-users"],
        trial_groups=[],
        icon="🔗",
        internal_port=3000,
    ),
    "tasks": AppConfig(
        id="vikunja",
        name="Vikunja",
        description="Task and project management",
        subdomain="tasks",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["vikunja-users"],
        trial_groups=[],
        icon="✅",
        internal_port=3456,
    ),

    # ==========================================
    # CREATOR APPS
    # ==========================================
    "ghost": AppConfig(
        id="ghost",
        name="Ghost",
        description="Professional publishing platform",
        subdomain="blog",
        category=AppCategory.COMMERCE,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["ghost-users"],
        trial_groups=["ghost-trial"],
        icon="👻",
        internal_port=2368,
    ),
    "saleor": AppConfig(
        id="saleor",
        name="Saleor",
        description="Headless e-commerce platform",
        subdomain="shop",
        category=AppCategory.COMMERCE,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["saleor-users"],
        trial_groups=["saleor-trial"],
        icon="🛒",
        internal_port=8000,
    ),
    "immich": AppConfig(
        id="immich",
        name="Immich",
        description="Photo and video backup",
        subdomain="photos",
        category=AppCategory.MEDIA,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["immich-users"],
        trial_groups=["immich-trial"],
        icon="📸",
        internal_port=3001,
    ),
    "listmonk": AppConfig(
        id="listmonk",
        name="Listmonk",
        description="Newsletter and mailing list manager",
        subdomain="newsletter",
        category=AppCategory.COMMERCE,
        auth_mode=AuthMode.PROXY,
        access_groups=["listmonk-users"],
        trial_groups=[],
        icon="📧",
        internal_port=9000,
    ),

    # ==========================================
    # DEVELOPER APPS
    # ==========================================
    "forgejo": AppConfig(
        id="forgejo",
        name="Forgejo",
        description="Git repository hosting",
        subdomain="git",
        category=AppCategory.DEVELOPMENT,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["forgejo-users"],
        trial_groups=["forgejo-trial"],
        icon="🦊",
        oauth_redirect_uri="/user/oauth2/authentik/callback",
        internal_port=3000,
    ),
    "woodpecker": AppConfig(
        id="woodpecker",
        name="Woodpecker CI",
        description="Continuous integration and deployment",
        subdomain="ci",
        category=AppCategory.DEVELOPMENT,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["woodpecker-users"],
        trial_groups=["woodpecker-trial"],
        icon="🪵",
        internal_port=8000,
    ),
    "code_server": AppConfig(
        id="code_server",
        name="VS Code Server",
        description="Browser-based VS Code editor",
        subdomain="code",
        category=AppCategory.DEVELOPMENT,
        auth_mode=AuthMode.PROXY,
        access_groups=["code-server-users"],
        trial_groups=[],
        icon="💻",
        internal_port=8080,
    ),
    "reactor": AppConfig(
        id="reactor",
        name="Reactor AI",
        description="AI-powered coding assistant",
        subdomain="reactor",
        category=AppCategory.AI,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["reactor-users"],
        trial_groups=["reactor-trial"],
        icon="⚛️",
        internal_port=8080,
    ),
    "ollama": AppConfig(
        id="ollama",
        name="Ollama",
        description="Local LLM inference",
        subdomain="llm",
        category=AppCategory.AI,
        auth_mode=AuthMode.PROXY,
        access_groups=["ollama-users"],
        trial_groups=["ollama-trial"],
        icon="🦙",
        internal_port=11434,
    ),

    # ==========================================
    # COMMUNICATION APPS
    # ==========================================
    "matrix": AppConfig(
        id="matrix",
        name="Matrix (Synapse)",
        description="Decentralized messaging server",
        subdomain="matrix",
        category=AppCategory.COMMUNICATION,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["matrix-users"],
        trial_groups=["matrix-trial"],
        icon="💬",
        internal_port=8008,
    ),
    "element": AppConfig(
        id="element",
        name="Element",
        description="Matrix web client",
        subdomain="chat",
        category=AppCategory.COMMUNICATION,
        auth_mode=AuthMode.NONE,  # Uses Matrix auth
        access_groups=["matrix-users"],
        trial_groups=["matrix-trial"],
        icon="💬",
        internal_port=80,
    ),
    "jitsi": AppConfig(
        id="jitsi",
        name="Jitsi Meet",
        description="Video conferencing",
        subdomain="meet",
        category=AppCategory.COMMUNICATION,
        auth_mode=AuthMode.PROXY,
        access_groups=["jitsi-users"],
        trial_groups=["jitsi-trial"],
        icon="📹",
        internal_port=80,
    ),
    "collabora": AppConfig(
        id="collabora",
        name="Collabora Online",
        description="Online office suite",
        subdomain="office",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.NONE,  # Integrated with Nextcloud
        access_groups=["collabora-users"],
        trial_groups=["collabora-trial"],
        icon="📄",
        internal_port=9980,
    ),
    "outline": AppConfig(
        id="outline",
        name="Outline",
        description="Team wiki and knowledge base",
        subdomain="wiki",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["outline-users"],
        trial_groups=["outline-trial"],
        icon="📝",
        internal_port=3000,
    ),

    # ==========================================
    # MEDIA APPS
    # ==========================================
    "jellyfin": AppConfig(
        id="jellyfin",
        name="Jellyfin",
        description="Media streaming server",
        subdomain="media",
        category=AppCategory.MEDIA,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["jellyfin-users"],
        trial_groups=["jellyfin-trial"],
        icon="🎬",
        internal_port=8096,
    ),
    "navidrome": AppConfig(
        id="navidrome",
        name="Navidrome",
        description="Music streaming server",
        subdomain="music",
        category=AppCategory.MEDIA,
        auth_mode=AuthMode.PROXY,
        access_groups=["navidrome-users"],
        trial_groups=[],
        icon="🎵",
        internal_port=4533,
    ),
    "audiobookshelf": AppConfig(
        id="audiobookshelf",
        name="Audiobookshelf",
        description="Audiobook and podcast server",
        subdomain="audiobooks",
        category=AppCategory.MEDIA,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["audiobookshelf-users"],
        trial_groups=[],
        icon="🎧",
        internal_port=80,
    ),
    "peertube": AppConfig(
        id="peertube",
        name="PeerTube",
        description="Federated video hosting",
        subdomain="video",
        category=AppCategory.MEDIA,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["peertube-users"],
        trial_groups=["peertube-trial"],
        icon="📺",
        internal_port=9000,
    ),

    # ==========================================
    # SECURITY & MONITORING
    # ==========================================
    "defcon_one": AppConfig(
        id="defcon_one",
        name="DEFCON ONE",
        description="Secure deployment gateway",
        subdomain="defcon",
        category=AppCategory.SECURITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["defcon-operators", "defcon-contributors", "defcon-observers"],
        trial_groups=["defcon-trial"],
        icon="🛡️",
        internal_port=8080,
    ),
    "uptime_kuma": AppConfig(
        id="uptime_kuma",
        name="Uptime Kuma",
        description="Uptime monitoring",
        subdomain="status",
        category=AppCategory.SYSTEM,
        auth_mode=AuthMode.PROXY,
        access_groups=["uptime-kuma-users"],
        trial_groups=[],
        icon="📊",
        internal_port=3001,
    ),
    "grafana": AppConfig(
        id="grafana",
        name="Grafana",
        description="Metrics and observability",
        subdomain="metrics",
        category=AppCategory.SYSTEM,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["grafana-users"],
        trial_groups=[],
        icon="📈",
        internal_port=3000,
    ),

    # ==========================================
    # BUSINESS APPS
    # ==========================================
    "invoice_ninja": AppConfig(
        id="invoice_ninja",
        name="Invoice Ninja",
        description="Invoicing and billing",
        subdomain="invoices",
        category=AppCategory.COMMERCE,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["invoiceninja-users"],
        trial_groups=[],
        icon="💰",
        internal_port=80,
    ),
    "cal_com": AppConfig(
        id="cal_com",
        name="Cal.com",
        description="Scheduling and appointments",
        subdomain="cal",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["calcom-users"],
        trial_groups=[],
        icon="📅",
        internal_port=3000,
    ),
    "docuseal": AppConfig(
        id="docuseal",
        name="DocuSeal",
        description="Document signing",
        subdomain="sign",
        category=AppCategory.COMMERCE,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["docuseal-users"],
        trial_groups=[],
        icon="✍️",
        internal_port=3000,
    ),
    "paperless": AppConfig(
        id="paperless",
        name="Paperless-ngx",
        description="Document management",
        subdomain="docs",
        category=AppCategory.PRODUCTIVITY,
        auth_mode=AuthMode.OAUTH2,
        access_groups=["paperless-users"],
        trial_groups=[],
        icon="📁",
        internal_port=8000,
    ),

    # ==========================================
    # SYSTEM APPS (Always available)
    # ==========================================
    "authentik": AppConfig(
        id="authentik",
        name="Authentik",
        description="Single sign-on and identity",
        subdomain="auth",
        category=AppCategory.SYSTEM,
        auth_mode=AuthMode.NONE,
        access_groups=[],
        trial_groups=[],
        icon="🔑",
        internal_port=9000,
        requires_admin=True,
    ),
    "dashboard": AppConfig(
        id="dashboard",
        name="WOPR Dashboard",
        description="Beacon control center",
        subdomain="dashboard",
        category=AppCategory.SYSTEM,
        auth_mode=AuthMode.PROXY,
        access_groups=[],  # All authenticated users
        trial_groups=[],
        icon="🏠",
        internal_port=3000,
    ),
}


# ============================================
# BUNDLE -> APP MAPPINGS
# ============================================

# Maps bundle IDs to the apps they include
BUNDLE_APPS: Dict[str, List[str]] = {
    # Sovereign Suites
    "starter": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "authentik", "dashboard",
    ],
    "creator": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "ghost", "saleor", "immich", "listmonk",
        "authentik", "dashboard",
    ],
    "developer": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "forgejo", "woodpecker", "code_server", "reactor", "ollama",
        "uptime_kuma",
        "authentik", "dashboard",
    ],
    "professional": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "ghost", "saleor", "immich", "listmonk",
        "forgejo", "woodpecker", "code_server", "reactor", "ollama",
        "matrix", "element", "jitsi", "collabora", "outline",
        "defcon_one", "uptime_kuma", "grafana",
        "authentik", "dashboard",
    ],
    "family": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "immich", "jellyfin", "navidrome",
        "authentik", "dashboard",
    ],
    "small_business": [
        "nextcloud", "vaultwarden", "freshrss", "linkwarden", "vikunja",
        "ghost", "saleor", "immich", "listmonk",
        "forgejo", "woodpecker", "reactor", "ollama",
        "matrix", "element", "jitsi", "collabora", "outline",
        "invoice_ninja", "cal_com", "docuseal", "paperless",
        "defcon_one", "uptime_kuma", "grafana",
        "authentik", "dashboard",
    ],
    "enterprise": [
        # Everything
        *WOPR_APPS.keys(),
    ],

    # Micro-Bundles
    "meeting_room": [
        "jitsi", "cal_com", "outline",
        "authentik", "dashboard",
    ],
    "privacy_pack": [
        "nextcloud", "vaultwarden",
        "authentik", "dashboard",
    ],
    "writer_studio": [
        "ghost", "listmonk", "linkwarden", "freshrss",
        "authentik", "dashboard",
    ],
    "artist_storefront": [
        "saleor", "immich", "ghost",
        "authentik", "dashboard",
    ],
    "podcaster": [
        "audiobookshelf", "ghost", "listmonk",
        "authentik", "dashboard",
    ],
    "freelancer": [
        "invoice_ninja", "cal_com", "nextcloud", "vaultwarden",
        "authentik", "dashboard",
    ],
    "musician": [
        "navidrome", "ghost", "saleor",
        "authentik", "dashboard",
    ],
    "family_hub": [
        "nextcloud", "vaultwarden", "immich",
        "authentik", "dashboard",
    ],
    "photographer": [
        "immich", "saleor", "ghost",
        "authentik", "dashboard",
    ],
    "bookkeeper": [
        "paperless", "nextcloud", "vaultwarden",
        "authentik", "dashboard",
    ],
    "video_creator": [
        "peertube", "ghost", "saleor",
        "authentik", "dashboard",
    ],
    "contractor": [
        "docuseal", "vikunja", "invoice_ninja", "cal_com",
        "authentik", "dashboard",
    ],
    "realtor": [
        "immich", "cal_com", "docuseal", "nextcloud",
        "authentik", "dashboard",
    ],
    "educator": [
        "jitsi", "collabora", "outline", "nextcloud",
        "authentik", "dashboard",
    ],
    "therapist": [
        "jitsi", "cal_com", "nextcloud", "vaultwarden",
        "authentik", "dashboard",
    ],
    "legal": [
        "paperless", "docuseal", "vaultwarden", "nextcloud",
        "authentik", "dashboard",
    ],
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_app(app_id: str) -> Optional[AppConfig]:
    """Get app configuration by ID."""
    return WOPR_APPS.get(app_id)


def get_apps_for_bundle(bundle_id: str) -> List[AppConfig]:
    """Get all apps included in a bundle."""
    app_ids = BUNDLE_APPS.get(bundle_id, [])
    return [WOPR_APPS[aid] for aid in app_ids if aid in WOPR_APPS]


def get_required_groups_for_bundle(bundle_id: str) -> List[str]:
    """Get all Authentik groups needed for a bundle's apps."""
    apps = get_apps_for_bundle(bundle_id)
    groups = set()

    for app in apps:
        groups.update(app.access_groups)

    return list(groups)


def get_apps_by_category(category: AppCategory) -> List[AppConfig]:
    """Get all apps in a category."""
    return [app for app in WOPR_APPS.values() if app.category == category]


def get_oauth_apps() -> List[AppConfig]:
    """Get all apps that use OAuth2/OIDC."""
    return [app for app in WOPR_APPS.values() if app.auth_mode == AuthMode.OAUTH2]


def get_proxy_apps() -> List[AppConfig]:
    """Get all apps that use forward auth proxy."""
    return [app for app in WOPR_APPS.values() if app.auth_mode == AuthMode.PROXY]


def user_has_app_access(user_groups: List[str], app_id: str) -> Dict[str, Any]:
    """
    Check if user has access to an app.

    Returns:
        Dict with has_access, access_type (permanent/trial), and matching_groups
    """
    app = get_app(app_id)
    if not app:
        return {"has_access": False, "error": f"Unknown app: {app_id}"}

    user_set = set(user_groups)
    access_set = set(app.access_groups)
    trial_set = set(app.trial_groups)

    # Check permanent access
    if user_set & access_set:
        return {
            "has_access": True,
            "access_type": "permanent",
            "matching_groups": list(user_set & access_set),
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
        "required_groups": app.access_groups,
        "trial_available": bool(app.trial_groups),
    }


def get_all_app_groups() -> List[str]:
    """Get a list of all unique access groups for all apps."""
    groups = set()
    for app in WOPR_APPS.values():
        groups.update(app.access_groups)
        groups.update(app.trial_groups)
    return sorted(groups)


def generate_traefik_labels(app: AppConfig, beacon_name: str) -> Dict[str, str]:
    """Generate Traefik labels for an app's routing."""
    domain = f"{app.subdomain}.{beacon_name}.wopr.systems"
    router_name = f"wopr-{app.id}"

    labels = {
        f"traefik.enable": "true",
        f"traefik.http.routers.{router_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.routers.{router_name}.entrypoints": "websecure",
        f"traefik.http.routers.{router_name}.tls": "true",
        f"traefik.http.routers.{router_name}.tls.certresolver": "letsencrypt",
        f"traefik.http.services.{router_name}.loadbalancer.server.port": str(app.internal_port),
    }

    # Add Authentik forward auth for proxy mode
    if app.auth_mode == AuthMode.PROXY:
        labels[f"traefik.http.routers.{router_name}.middlewares"] = "authentik@docker"

    return labels
