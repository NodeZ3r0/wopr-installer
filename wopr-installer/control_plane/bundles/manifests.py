"""
WOPR Bundle Manifests

Defines which modules are included in each bundle:
- 7 Sovereign Suites (complete solutions)
- 16 Micro-Bundles (niche-specific packages)

Each bundle has the same modules regardless of storage tier.
Storage tier only affects resource limits (storage, RAM, users).
"""

from dataclasses import dataclass, field
from typing import Optional

from .tiers import (
    BundleType,
    SovereignSuiteID,
    MicroBundleID,
    StorageTier,
    SOVEREIGN_PRICING,
    MICRO_PRICING,
)


# =============================================================================
# Core Infrastructure (All Paid Bundles)
# =============================================================================

CORE_INFRASTRUCTURE = [
    "authentik",   # SSO - always required
    "caddy",       # Reverse proxy - always required
    "postgresql",  # Database - always required
    "redis",       # Cache - always required
]


# =============================================================================
# Bundle Manifest Definition
# =============================================================================

@dataclass
class BundleManifest:
    """Complete manifest for a bundle"""
    bundle_type: BundleType
    bundle_id: str  # SovereignSuiteID or MicroBundleID value
    name: str
    tagline: str
    modules: list[str]  # App modules included
    core_modules: list[str] = field(default_factory=lambda: CORE_INFRASTRUCTURE.copy())

    def get_all_modules(self) -> list[str]:
        """Get all modules (core + bundle-specific)"""
        return self.core_modules + self.modules


# =============================================================================
# SOVEREIGN SUITES (7)
# =============================================================================

SOVEREIGN_STARTER = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.STARTER.value,
    name="Starter",
    tagline="Drive, calendar, notes, tasks, passwords - the essentials to ditch Big Tech",
    modules=[
        "nextcloud",      # Drive + Calendar + Contacts
        "collabora",      # Office docs in Nextcloud
        "outline",        # Notes/wiki
        "vikunja",        # Tasks/kanban
        "vaultwarden",    # Password manager
        "uptime-kuma",    # Status monitoring
    ],
)

SOVEREIGN_CREATOR = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.CREATOR.value,
    name="Creator",
    tagline="Blog, portfolio, online store, newsletter - monetize your work",
    modules=[
        # From Starter
        "nextcloud",
        "collabora",
        "vaultwarden",
        # Creator-specific
        "ghost",          # Blog/newsletter
        "saleor",         # E-commerce storefront
        "immich",         # Photo portfolio/gallery
        "plausible",      # Analytics
        "listmonk",       # Email marketing
        "linkwarden",     # Bookmark/research archive
    ],
)

SOVEREIGN_DEVELOPER = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.DEVELOPER.value,
    name="Developer",
    tagline="Git hosting, CI/CD, code editor, Reactor AI coding assistant",
    modules=[
        # From Starter
        "nextcloud",
        "collabora",
        "vaultwarden",
        # Developer-specific
        "forgejo",        # Git hosting
        "woodpecker",     # CI/CD pipelines
        "code-server",    # VS Code in browser
        "reactor",        # Reactor AI coding assistant
        "portainer",      # Docker management
        "openwebui",      # Chat UI for LLMs
        "nocodb",         # Database spreadsheet
        "n8n",            # Workflow automation
        # ollama available as $14.99/mo addon (requires T2+ VPS for 8GB+ RAM)
    ],
)

SOVEREIGN_PROFESSIONAL = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.PROFESSIONAL.value,
    name="Professional",
    tagline="Creator + Developer combined + DEFCON ONE security gateway",
    modules=[
        # Core productivity
        "nextcloud",
        "collabora",
        "vaultwarden",
        "outline",
        # Creator modules
        "ghost",
        "saleor",
        "immich",
        "plausible",
        "listmonk",
        "linkwarden",
        # Developer modules
        "forgejo",
        "woodpecker",
        "code-server",
        "reactor",
        "portainer",
        "openwebui",
        "nocodb",
        "n8n",
        # Security
        "defcon-one",     # DEFCON ONE security gateway
        "crowdsec",       # Threat intelligence
        "netbird",        # Zero-trust VPN
        # ollama available as $14.99/mo addon (requires T2+ VPS for 8GB+ RAM)
    ],
)

SOVEREIGN_FAMILY = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.FAMILY.value,
    name="Family",
    tagline="6 user accounts, shared photos, shared passwords, family calendar",
    modules=[
        "nextcloud",      # Shared drive + family calendar
        "collabora",      # Office docs
        "immich",         # Shared family photos
        "vaultwarden",    # Shared passwords
        "jellyfin",       # Family media server
        "ntfy",           # Family notifications
        "uptime-kuma",    # Status monitoring
        "adguard",        # Family-safe DNS
    ],
)

SOVEREIGN_SMALL_BUSINESS = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.SMALL_BUSINESS.value,
    name="Small Business",
    tagline="CRM, team chat, office suite, DEFCON ONE + Reactor AI",
    modules=[
        # Productivity
        "nextcloud",
        "collabora",
        "outline",
        "vaultwarden",
        # Communication
        "mattermost",     # Team chat
        "jitsi",          # Video conferencing
        "ntfy",           # Push notifications
        # Business
        "espocrm",        # CRM
        "invoiceninja",   # Invoicing
        "kimai",          # Time tracking
        "calcom",         # Scheduling
        # AI & Security
        "reactor",        # AI coding assistant
        "openwebui",
        "defcon-one",
        # ollama available as $14.99/mo addon
        "crowdsec",
        "netbird",
        # DevOps
        "portainer",
        "grafana",
        "prometheus",
        "uptime-kuma",
    ],
)

SOVEREIGN_ENTERPRISE = BundleManifest(
    bundle_type=BundleType.SOVEREIGN,
    bundle_id=SovereignSuiteID.ENTERPRISE.value,
    name="Enterprise",
    tagline="Unlimited users, custom integrations, dedicated support, full AI suite",
    modules=[
        # Full productivity suite
        "nextcloud",
        "collabora",
        "outline",
        "bookstack",
        "paperless-ngx",
        "vaultwarden",
        "affine",
        "hedgedoc",
        "stirling-pdf",
        # Communication
        "mattermost",
        "matrix-synapse",
        "element",
        "jitsi",
        "mailcow",
        "listmonk",
        "ntfy",
        # Business
        "espocrm",
        "invoiceninja",
        "kimai",
        "calcom",
        "docuseal",
        "chatwoot",
        # Developer
        "forgejo",
        "woodpecker",
        "code-server",
        "portainer",
        "docker-registry",
        "nocodb",
        "n8n",
        "plane",
        # Full AI suite
        "reactor",
        "defcon-one",
        "openwebui",
        "langfuse",
        # ollama available as $14.99/mo addon
        # Security
        "crowdsec",
        "netbird",
        "passbolt",
        # Analytics
        "grafana",
        "prometheus",
        "plausible",
        "uptime-kuma",
        # Media
        "immich",
        "jellyfin",
    ],
)


# =============================================================================
# MICRO BUNDLES (17)
# =============================================================================

MICRO_PERSONAL_PRODUCTIVITY = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.PERSONAL_PRODUCTIVITY.value,
    name="Personal Productivity",
    tagline="Everything Google does, minus Google - de-Google your life",
    modules=[
        "nextcloud",      # Files + Calendar + Contacts + Notes + Tasks
        "collabora",      # Office docs
        "linkwarden",     # Bookmarks
        "wallabag",       # Read later
        "freshrss",       # RSS reader
    ],
)

MICRO_MEETING_ROOM = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.MEETING_ROOM.value,
    name="Meeting Room",
    tagline="Video calls, scheduling, collaborative notes - replace Zoom",
    modules=[
        "jitsi",          # Video conferencing
        "calcom",         # Scheduling
        "hedgedoc",       # Collaborative notes
        "ntfy",           # Meeting reminders
    ],
)

MICRO_PRIVACY_PACK = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.PRIVACY_PACK.value,
    name="Privacy Pack",
    tagline="Encrypted storage, password manager, private VPN - total privacy",
    modules=[
        "nextcloud",      # Encrypted storage
        "vaultwarden",    # Password manager
        "netbird",        # Zero-trust VPN
        "adguard",        # DNS privacy
    ],
)

MICRO_WRITER_STUDIO = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.WRITER_STUDIO.value,
    name="Writer's Studio",
    tagline="Blog, newsletter, research archive, bookmarks - replace Substack",
    modules=[
        "ghost",          # Blog + newsletter
        "linkwarden",     # Bookmarks/research
        "outline",        # Notes/drafts
        "plausible",      # Reader analytics
        "freshrss",       # RSS research feeds
    ],
)

MICRO_ARTIST_STOREFRONT = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.ARTIST_STOREFRONT.value,
    name="Artist Storefront",
    tagline="Online store, portfolio, photo galleries - replace Etsy",
    modules=[
        "saleor",         # E-commerce store
        "immich",         # Photo galleries
        "ghost",          # Portfolio/blog
        "plausible",      # Visitor analytics
    ],
)

MICRO_PODCASTER = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.PODCASTER.value,
    name="Podcaster Pack",
    tagline="Podcast hosting, show notes blog, listener analytics - own your feed",
    modules=[
        "castopod",       # Podcast hosting + RSS
        "ghost",          # Show notes blog
        "plausible",      # Listener analytics
        "nextcloud",      # Episode storage
        "listmonk",       # Listener newsletter
    ],
)

MICRO_FREELANCER = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.FREELANCER.value,
    name="Freelancer Essentials",
    tagline="Invoicing, scheduling, client contacts - run your business",
    modules=[
        "invoiceninja",   # Invoicing
        "calcom",         # Scheduling
        "espocrm",        # Client contacts
        "nextcloud",      # File sharing
        "vaultwarden",    # Credentials
    ],
)

MICRO_MUSICIAN = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.MUSICIAN.value,
    name="Musician Bundle",
    tagline="Music streaming, artist website, merch store - own your music",
    modules=[
        "funkwhale",      # Music streaming platform
        "ghost",          # Artist website/blog
        "saleor",         # Merch store
        "plausible",      # Fan analytics
        "listmonk",       # Fan newsletter
    ],
)

MICRO_FAMILY_HUB = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.FAMILY_HUB.value,
    name="Family Hub",
    tagline="Shared drive, photos, passwords for 6 family members",
    modules=[
        "nextcloud",      # Shared drive + calendar
        "immich",         # Family photos
        "vaultwarden",    # Shared passwords
        "jellyfin",       # Family media
    ],
)

MICRO_PHOTOGRAPHER = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.PHOTOGRAPHER.value,
    name="Photographer Pro",
    tagline="Photo library, client galleries, portfolio, print sales",
    modules=[
        "immich",         # Photo library + AI tagging
        "photoprism",     # Client gallery proofs
        "ghost",          # Portfolio website
        "saleor",         # Print sales
        "nextcloud",      # RAW file storage
    ],
)

MICRO_BOOKKEEPER = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.BOOKKEEPER.value,
    name="Bookkeeper Bundle",
    tagline="Document scanner, client portal, secure messaging",
    modules=[
        "paperless-ngx",  # Document scanner/OCR
        "nextcloud",      # Client file portal
        "mattermost",     # Secure client messaging
        "vaultwarden",    # Credential sharing
        "stirling-pdf",   # PDF tools
    ],
)

MICRO_VIDEO_CREATOR = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.VIDEO_CREATOR.value,
    name="Video Creator",
    tagline="Video hosting, community blog, paid memberships - replace YouTube",
    modules=[
        "peertube",       # Video hosting
        "ghost",          # Community blog + memberships
        "plausible",      # Viewer analytics
        "listmonk",       # Subscriber newsletter
        "nextcloud",      # Project file storage
    ],
)

MICRO_CONTRACTOR = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.CONTRACTOR.value,
    name="Contractor Pro",
    tagline="Digital contracts, project management, time tracking",
    modules=[
        "docuseal",       # Digital contracts/e-sign
        "plane",          # Project management
        "kimai",          # Time tracking
        "invoiceninja",   # Invoicing
        "nextcloud",      # Document sharing
    ],
)

MICRO_REALTOR = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.REALTOR.value,
    name="Real Estate Agent",
    tagline="Lead CRM, listing photos, digital contracts",
    modules=[
        "espocrm",        # Lead/client CRM
        "immich",         # Listing photos
        "docuseal",       # Digital contracts
        "calcom",         # Showing scheduler
        "ghost",          # Listing blog
    ],
)

MICRO_EDUCATOR = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.EDUCATOR.value,
    name="Educator Suite",
    tagline="Virtual classroom, whiteboard, file sharing for students",
    modules=[
        "jitsi",          # Virtual classroom
        "hedgedoc",       # Collaborative notes/whiteboard
        "nextcloud",      # File sharing
        "bookstack",      # Course wiki
        "outline",        # Lesson plans
    ],
)

MICRO_THERAPIST = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.THERAPIST.value,
    name="Therapist/Coach",
    tagline="Secure video sessions, encrypted notes, client portal - HIPAA-ready",
    modules=[
        "jitsi",          # Secure video sessions
        "nextcloud",      # Encrypted client files
        "standardnotes",  # Encrypted session notes
        "calcom",         # Appointment scheduling
        "vaultwarden",    # Secure credentials
    ],
)

MICRO_LEGAL = BundleManifest(
    bundle_type=BundleType.MICRO,
    bundle_id=MicroBundleID.LEGAL.value,
    name="Legal Lite",
    tagline="Document management, e-signatures, secure client portal",
    modules=[
        "paperless-ngx",  # Document management
        "docuseal",       # E-signatures
        "nextcloud",      # Secure client portal
        "mattermost",     # Secure messaging
        "vaultwarden",    # Credential vault
        "stirling-pdf",   # PDF tools
    ],
)


# =============================================================================
# Bundle Registries
# =============================================================================

SOVEREIGN_BUNDLES: dict[SovereignSuiteID, BundleManifest] = {
    SovereignSuiteID.STARTER: SOVEREIGN_STARTER,
    SovereignSuiteID.CREATOR: SOVEREIGN_CREATOR,
    SovereignSuiteID.DEVELOPER: SOVEREIGN_DEVELOPER,
    SovereignSuiteID.PROFESSIONAL: SOVEREIGN_PROFESSIONAL,
    SovereignSuiteID.FAMILY: SOVEREIGN_FAMILY,
    SovereignSuiteID.SMALL_BUSINESS: SOVEREIGN_SMALL_BUSINESS,
    SovereignSuiteID.ENTERPRISE: SOVEREIGN_ENTERPRISE,
}

MICRO_BUNDLES: dict[MicroBundleID, BundleManifest] = {
    MicroBundleID.PERSONAL_PRODUCTIVITY: MICRO_PERSONAL_PRODUCTIVITY,
    MicroBundleID.MEETING_ROOM: MICRO_MEETING_ROOM,
    MicroBundleID.PRIVACY_PACK: MICRO_PRIVACY_PACK,
    MicroBundleID.WRITER_STUDIO: MICRO_WRITER_STUDIO,
    MicroBundleID.ARTIST_STOREFRONT: MICRO_ARTIST_STOREFRONT,
    MicroBundleID.PODCASTER: MICRO_PODCASTER,
    MicroBundleID.FREELANCER: MICRO_FREELANCER,
    MicroBundleID.MUSICIAN: MICRO_MUSICIAN,
    MicroBundleID.FAMILY_HUB: MICRO_FAMILY_HUB,
    MicroBundleID.PHOTOGRAPHER: MICRO_PHOTOGRAPHER,
    MicroBundleID.BOOKKEEPER: MICRO_BOOKKEEPER,
    MicroBundleID.VIDEO_CREATOR: MICRO_VIDEO_CREATOR,
    MicroBundleID.CONTRACTOR: MICRO_CONTRACTOR,
    MicroBundleID.REALTOR: MICRO_REALTOR,
    MicroBundleID.EDUCATOR: MICRO_EDUCATOR,
    MicroBundleID.THERAPIST: MICRO_THERAPIST,
    MicroBundleID.LEGAL: MICRO_LEGAL,
}


# =============================================================================
# Lookup Functions
# =============================================================================

def get_sovereign_bundle(suite_id: SovereignSuiteID | str) -> BundleManifest:
    """Get sovereign suite manifest by ID"""
    if isinstance(suite_id, str):
        suite_id = SovereignSuiteID(suite_id)
    return SOVEREIGN_BUNDLES[suite_id]


def get_micro_bundle(bundle_id: MicroBundleID | str) -> BundleManifest:
    """Get micro bundle manifest by ID"""
    if isinstance(bundle_id, str):
        bundle_id = MicroBundleID(bundle_id)
    return MICRO_BUNDLES[bundle_id]


def get_bundle(bundle_type: BundleType | str, bundle_id: str) -> BundleManifest:
    """Get any bundle by type and ID"""
    if isinstance(bundle_type, str):
        bundle_type = BundleType(bundle_type)

    if bundle_type == BundleType.SOVEREIGN:
        return get_sovereign_bundle(bundle_id)
    elif bundle_type == BundleType.MICRO:
        return get_micro_bundle(bundle_id)
    else:
        raise ValueError(f"Unknown bundle type: {bundle_type}")


def get_modules_for_bundle(bundle_type: BundleType | str, bundle_id: str) -> list[str]:
    """Get all modules for a bundle (core + bundle-specific)"""
    bundle = get_bundle(bundle_type, bundle_id)
    return bundle.get_all_modules()


def parse_checkout_bundle(checkout_bundle: str) -> tuple[BundleType, str]:
    """
    Parse bundle string from checkout URL.
    Format: 'sovereign-starter' or 'micro-meeting_room'
    Returns: (BundleType, bundle_id)
    """
    if checkout_bundle.startswith("sovereign-"):
        return BundleType.SOVEREIGN, checkout_bundle.replace("sovereign-", "")
    elif checkout_bundle.startswith("micro-"):
        return BundleType.MICRO, checkout_bundle.replace("micro-", "")
    else:
        raise ValueError(f"Invalid bundle format: {checkout_bundle}")
