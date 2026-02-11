"""
WOPR Capability Mapping
=======================

Maps user intents to underlying module capabilities.

Users think in terms of what they want to DO:
- "I want to access my files" → /go/drive
- "I want to see my photos" → /go/photos
- "I want to manage my shop" → /go/shop

This module maps those intents to the actual modules that provide
the capability, without exposing module names to users.

The user NEVER sees:
- "Nextcloud"
- "Saleor"
- "Vaultwarden"

They see:
- "Drive"
- "Shop"
- "Vault"
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List


class Capability(str, Enum):
    """
    User-facing capabilities.

    These are what users understand - not technical module names.
    """
    # Storage
    DRIVE = "drive"
    PHOTOS = "photos"

    # Security
    VAULT = "vault"

    # Communication
    CHAT = "chat"
    VIDEO = "video"

    # Productivity
    DOCS = "docs"
    WIKI = "wiki"
    CALENDAR = "calendar"
    CONTACTS = "contacts"
    RSS = "rss"

    # Commerce
    SHOP = "shop"
    BLOG = "blog"

    # Developer
    CODE = "code"
    GIT = "git"
    CI = "ci"
    MONITORING = "monitoring"

    # AI
    AI = "ai"
    REACTOR = "reactor"

    # Media
    MEDIA = "media"

    # Admin
    DASHBOARD = "dashboard"
    SETTINGS = "settings"
    SSO = "sso"


@dataclass
class CapabilityMapping:
    """Maps a capability to the module(s) that provide it."""
    capability: Capability
    primary_module: str  # Module ID from registry
    fallback_modules: List[str]  # Alternative modules if primary unavailable
    dashboard_section: str  # Where in dashboard to land
    display_name: str  # User-facing name
    description: str  # User-facing description
    icon: str  # Icon identifier


# Canonical mapping of capabilities to modules
CAPABILITY_MAP: dict[Capability, CapabilityMapping] = {
    # Storage capabilities
    Capability.DRIVE: CapabilityMapping(
        capability=Capability.DRIVE,
        primary_module="nextcloud",
        fallback_modules=[],
        dashboard_section="storage",
        display_name="Drive",
        description="Your files, documents, and folders",
        icon="folder",
    ),
    Capability.PHOTOS: CapabilityMapping(
        capability=Capability.PHOTOS,
        primary_module="nextcloud",  # Nextcloud Photos/Memories
        fallback_modules=["immich"],
        dashboard_section="storage",
        display_name="Photos",
        description="Your photos and memories",
        icon="image",
    ),

    # Security capabilities
    Capability.VAULT: CapabilityMapping(
        capability=Capability.VAULT,
        primary_module="vaultwarden",
        fallback_modules=[],
        dashboard_section="security",
        display_name="Vault",
        description="Your passwords and secrets",
        icon="lock",
    ),

    # Communication capabilities
    Capability.CHAT: CapabilityMapping(
        capability=Capability.CHAT,
        primary_module="element",
        fallback_modules=["matrix"],
        dashboard_section="communication",
        display_name="Chat",
        description="Secure messaging",
        icon="message-circle",
    ),
    Capability.VIDEO: CapabilityMapping(
        capability=Capability.VIDEO,
        primary_module="jitsi",
        fallback_modules=[],
        dashboard_section="communication",
        display_name="Video",
        description="Video meetings",
        icon="video",
    ),

    # Productivity capabilities
    Capability.DOCS: CapabilityMapping(
        capability=Capability.DOCS,
        primary_module="collabora",
        fallback_modules=["outline"],
        dashboard_section="productivity",
        display_name="Docs",
        description="Documents and spreadsheets",
        icon="file-text",
    ),
    Capability.WIKI: CapabilityMapping(
        capability=Capability.WIKI,
        primary_module="outline",
        fallback_modules=[],
        dashboard_section="productivity",
        display_name="Wiki",
        description="Team knowledge base",
        icon="book-open",
    ),
    Capability.CALENDAR: CapabilityMapping(
        capability=Capability.CALENDAR,
        primary_module="nextcloud",  # Nextcloud Calendar
        fallback_modules=[],
        dashboard_section="productivity",
        display_name="Calendar",
        description="Your schedule",
        icon="calendar",
    ),
    Capability.CONTACTS: CapabilityMapping(
        capability=Capability.CONTACTS,
        primary_module="nextcloud",  # Nextcloud Contacts
        fallback_modules=[],
        dashboard_section="productivity",
        display_name="Contacts",
        description="Your address book",
        icon="users",
    ),
    Capability.RSS: CapabilityMapping(
        capability=Capability.RSS,
        primary_module="freshrss",
        fallback_modules=[],
        dashboard_section="productivity",
        display_name="News",
        description="RSS feeds and news",
        icon="rss",
    ),

    # Commerce capabilities
    Capability.SHOP: CapabilityMapping(
        capability=Capability.SHOP,
        primary_module="saleor",
        fallback_modules=[],
        dashboard_section="commerce",
        display_name="Shop",
        description="Your online store",
        icon="shopping-bag",
    ),
    Capability.BLOG: CapabilityMapping(
        capability=Capability.BLOG,
        primary_module="ghost",
        fallback_modules=["wordpress"],
        dashboard_section="commerce",
        display_name="Blog",
        description="Your blog or portfolio",
        icon="edit-3",
    ),

    # Developer capabilities
    Capability.CODE: CapabilityMapping(
        capability=Capability.CODE,
        primary_module="code_server",
        fallback_modules=[],
        dashboard_section="developer",
        display_name="Code",
        description="VS Code in your browser",
        icon="code",
    ),
    Capability.GIT: CapabilityMapping(
        capability=Capability.GIT,
        primary_module="forgejo",
        fallback_modules=[],
        dashboard_section="developer",
        display_name="Git",
        description="Your code repositories",
        icon="git-branch",
    ),
    Capability.CI: CapabilityMapping(
        capability=Capability.CI,
        primary_module="woodpecker",
        fallback_modules=[],
        dashboard_section="developer",
        display_name="CI/CD",
        description="Build automation",
        icon="play-circle",
    ),
    Capability.MONITORING: CapabilityMapping(
        capability=Capability.MONITORING,
        primary_module="uptime_kuma",
        fallback_modules=[],
        dashboard_section="developer",
        display_name="Monitoring",
        description="Uptime and status",
        icon="activity",
    ),

    # AI capabilities
    Capability.AI: CapabilityMapping(
        capability=Capability.AI,
        primary_module="ollama",
        fallback_modules=[],
        dashboard_section="ai",
        display_name="AI",
        description="Local AI models",
        icon="cpu",
    ),
    Capability.REACTOR: CapabilityMapping(
        capability=Capability.REACTOR,
        primary_module="reactor",
        fallback_modules=[],
        dashboard_section="ai",
        display_name="Reactor",
        description="AI coding assistant",
        icon="zap",
    ),

    # Media capabilities
    Capability.MEDIA: CapabilityMapping(
        capability=Capability.MEDIA,
        primary_module="jellyfin",
        fallback_modules=[],
        dashboard_section="media",
        display_name="Media",
        description="Movies, music, and more",
        icon="film",
    ),

    # Admin capabilities
    Capability.DASHBOARD: CapabilityMapping(
        capability=Capability.DASHBOARD,
        primary_module="dashboard",  # WOPR native
        fallback_modules=[],
        dashboard_section="admin",
        display_name="Dashboard",
        description="Your Beacon control center",
        icon="grid",
    ),
    Capability.SETTINGS: CapabilityMapping(
        capability=Capability.SETTINGS,
        primary_module="dashboard",
        fallback_modules=[],
        dashboard_section="admin",
        display_name="Settings",
        description="Beacon configuration",
        icon="settings",
    ),
    Capability.SSO: CapabilityMapping(
        capability=Capability.SSO,
        primary_module="authentik",
        fallback_modules=[],
        dashboard_section="admin",
        display_name="Identity",
        description="Account and security",
        icon="shield",
    ),
}


def get_capability_for_intent(intent: str) -> Optional[Capability]:
    """
    Map an intent string to a Capability enum.

    Intent strings come from /go/{intent} URLs.
    """
    try:
        return Capability(intent.lower())
    except ValueError:
        return None


def get_module_for_capability(
    capability: Capability,
    available_modules: List[str],
) -> Optional[str]:
    """
    Given a capability and the modules available on a Beacon,
    return the module that should handle it.

    Checks primary module first, then fallbacks.
    """
    mapping = CAPABILITY_MAP.get(capability)
    if not mapping:
        return None

    # Check primary module
    if mapping.primary_module in available_modules:
        return mapping.primary_module

    # Check fallbacks
    for fallback in mapping.fallback_modules:
        if fallback in available_modules:
            return fallback

    return None


def get_dashboard_section(capability: Capability) -> Optional[str]:
    """Get the dashboard section for a capability."""
    mapping = CAPABILITY_MAP.get(capability)
    return mapping.dashboard_section if mapping else None


def get_capability_display(capability: Capability) -> dict:
    """Get user-facing display info for a capability."""
    mapping = CAPABILITY_MAP.get(capability)
    if not mapping:
        return {}

    return {
        "name": mapping.display_name,
        "description": mapping.description,
        "icon": mapping.icon,
        "section": mapping.dashboard_section,
    }
