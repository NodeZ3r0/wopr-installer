"""
WOPR Module Registry
====================

Complete catalog of all WOPR Sovereign Suite modules.

Each module is a service that can be deployed to a WOPR instance.
Modules are organized by:
- Category (productivity, security, developer, etc.)
- Tier (which resource tier required)
- Bundle inclusion (which bundles include this by default)

Updated: January 2026
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


class ModuleCategory(Enum):
    """Module categories for organization."""
    CORE = "core"                    # Required for all bundles
    PRODUCTIVITY = "productivity"    # Files, calendar, etc.
    SECURITY = "security"           # Passwords, 2FA, etc.
    COMMUNICATION = "communication"  # Chat, video, email
    DEVELOPER = "developer"         # Git, CI/CD, AI coding
    CREATOR = "creator"             # Blog, store, portfolio
    BUSINESS = "business"           # CRM, invoicing, project mgmt
    MEDIA = "media"                 # Photos, music, streaming
    ANALYTICS = "analytics"         # Metrics, dashboards


class ModuleTier(Enum):
    """Resource tier required for module."""
    MINIMAL = "minimal"    # Runs on anything
    LOW = "low"           # 2 vCPU, 4GB RAM
    MEDIUM = "medium"     # 4 vCPU, 8GB RAM
    HIGH = "high"         # 8 vCPU, 16GB RAM
    VERY_HIGH = "very_high"  # 16 vCPU, 32GB RAM


@dataclass
class Module:
    """
    A deployable WOPR module/application.

    Attributes:
        id: Unique module identifier
        name: Human-readable name
        description: What this module does
        category: Module category
        tier: Minimum resource tier required
        container_image: Docker/Podman image to deploy
        default_port: Internal port the service runs on
        dependencies: Other module IDs this depends on
        bundles: Which bundles include this by default
        trial_eligible: Can be added as free trial for lower tiers
        trial_days: How many days of free trial (if eligible)
        monthly_addon_price: Price if added to non-included bundle
        authentik_app_slug: Slug for Authentik application
        caddy_routes: Caddy route patterns for this module
        env_vars: Default environment variables
        volumes: Required persistent volumes
        ram_mb: Estimated RAM usage in MB
        cpu_shares: Relative CPU weight (1024 = 1 core equivalent)
    """
    id: str
    name: str
    description: str
    category: ModuleCategory
    tier: ModuleTier
    container_image: str
    default_port: int

    # Bundle & pricing
    bundles: List[str] = field(default_factory=list)
    trial_eligible: bool = False
    trial_days: int = 90  # 3 months default
    monthly_addon_price: float = 0.0

    # Dependencies
    dependencies: List[str] = field(default_factory=list)

    # Authentik integration
    authentik_app_slug: str = ""
    authentik_group: str = ""  # Required Authentik group for access

    # Caddy routing
    caddy_routes: List[str] = field(default_factory=list)
    subdomain: str = ""  # e.g., "files" -> files.domain.com

    # Container config
    env_vars: Dict[str, str] = field(default_factory=dict)
    volumes: List[str] = field(default_factory=list)
    ram_mb: int = 512
    cpu_shares: int = 512

    def is_included_in(self, bundle: str) -> bool:
        """Check if module is included in a bundle by default."""
        return bundle in self.bundles

    def can_trial(self, current_bundle: str) -> bool:
        """Check if module can be trialed from current bundle."""
        return self.trial_eligible and not self.is_included_in(current_bundle)


# ============================================
# COMPLETE MODULE CATALOG
# ============================================

MODULES: Dict[str, Module] = {}

def register_module(module: Module) -> Module:
    """Register a module in the global catalog."""
    MODULES[module.id] = module
    return module


# --------------------------------------------
# CORE MODULES (All bundles)
# --------------------------------------------

register_module(Module(
    id="authentik",
    name="Authentik",
    description="Single Sign-On and identity management for all WOPR apps",
    category=ModuleCategory.CORE,
    tier=ModuleTier.MINIMAL,
    container_image="ghcr.io/goauthentik/server:latest",
    default_port=9000,
    bundles=["personal", "creator", "developer", "professional"],
    authentik_app_slug="authentik",
    subdomain="auth",
    ram_mb=1024,
    cpu_shares=512,
))

register_module(Module(
    id="caddy",
    name="Caddy",
    description="Automatic HTTPS reverse proxy for all services",
    category=ModuleCategory.CORE,
    tier=ModuleTier.MINIMAL,
    container_image="caddy:latest",
    default_port=443,
    bundles=["personal", "creator", "developer", "professional"],
    ram_mb=128,
    cpu_shares=256,
))

register_module(Module(
    id="postgresql",
    name="PostgreSQL",
    description="Primary database for WOPR applications",
    category=ModuleCategory.CORE,
    tier=ModuleTier.MINIMAL,
    container_image="postgres:15-alpine",
    default_port=5432,
    bundles=["personal", "creator", "developer", "professional"],
    ram_mb=512,
    cpu_shares=512,
))

register_module(Module(
    id="redis",
    name="Redis",
    description="In-memory cache and message broker",
    category=ModuleCategory.CORE,
    tier=ModuleTier.MINIMAL,
    container_image="redis:7-alpine",
    default_port=6379,
    bundles=["personal", "creator", "developer", "professional"],
    ram_mb=256,
    cpu_shares=256,
))


# --------------------------------------------
# PRODUCTIVITY MODULES
# --------------------------------------------

register_module(Module(
    id="nextcloud",
    name="Nextcloud",
    description="File storage, calendar, contacts, and collaboration",
    category=ModuleCategory.PRODUCTIVITY,
    tier=ModuleTier.LOW,
    container_image="nextcloud:stable",
    default_port=80,
    bundles=["personal", "creator", "developer", "professional"],
    dependencies=["postgresql", "redis"],
    authentik_app_slug="nextcloud",
    authentik_group="nextcloud-users",
    subdomain="files",
    ram_mb=1024,
    cpu_shares=1024,
    caddy_routes=["files.{domain}"],
))

register_module(Module(
    id="collabora",
    name="Collabora Online",
    description="Online office suite (docs, sheets, presentations)",
    category=ModuleCategory.PRODUCTIVITY,
    tier=ModuleTier.MEDIUM,
    container_image="collabora/code:latest",
    default_port=9980,
    bundles=["professional"],
    dependencies=["nextcloud"],
    authentik_app_slug="collabora",
    subdomain="office",
    ram_mb=2048,
    cpu_shares=1024,
    monthly_addon_price=5.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="outline",
    name="Outline",
    description="Team wiki and knowledge base",
    category=ModuleCategory.PRODUCTIVITY,
    tier=ModuleTier.MEDIUM,
    container_image="outlinewiki/outline:latest",
    default_port=3000,
    bundles=["professional"],
    dependencies=["postgresql", "redis"],
    authentik_app_slug="outline",
    authentik_group="outline-users",
    subdomain="wiki",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))


# --------------------------------------------
# SECURITY MODULES
# --------------------------------------------

register_module(Module(
    id="vaultwarden",
    name="Vaultwarden",
    description="Self-hosted password manager (Bitwarden compatible)",
    category=ModuleCategory.SECURITY,
    tier=ModuleTier.MINIMAL,
    container_image="vaultwarden/server:latest",
    default_port=80,
    bundles=["personal", "creator", "developer", "professional"],
    authentik_app_slug="vaultwarden",
    authentik_group="vaultwarden-users",
    subdomain="vault",
    ram_mb=256,
    cpu_shares=256,
    caddy_routes=["vault.{domain}"],
))


# --------------------------------------------
# COMMUNICATION MODULES
# --------------------------------------------

register_module(Module(
    id="matrix",
    name="Matrix (Synapse)",
    description="Decentralized chat and messaging",
    category=ModuleCategory.COMMUNICATION,
    tier=ModuleTier.MEDIUM,
    container_image="matrixdotorg/synapse:latest",
    default_port=8008,
    bundles=["professional"],
    dependencies=["postgresql"],
    authentik_app_slug="matrix",
    authentik_group="matrix-users",
    subdomain="matrix",
    ram_mb=1024,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="element",
    name="Element",
    description="Modern chat client for Matrix",
    category=ModuleCategory.COMMUNICATION,
    tier=ModuleTier.MINIMAL,
    container_image="vectorim/element-web:latest",
    default_port=80,
    bundles=["professional"],
    dependencies=["matrix"],
    authentik_app_slug="element",
    subdomain="chat",
    ram_mb=128,
    cpu_shares=128,
))

register_module(Module(
    id="jitsi",
    name="Jitsi Meet",
    description="Video conferencing and screen sharing",
    category=ModuleCategory.COMMUNICATION,
    tier=ModuleTier.HIGH,
    container_image="jitsi/web:latest",
    default_port=443,
    bundles=["professional"],
    authentik_app_slug="jitsi",
    authentik_group="jitsi-users",
    subdomain="meet",
    ram_mb=2048,
    cpu_shares=2048,
    monthly_addon_price=9.99,
    trial_eligible=True,
    trial_days=14,  # Video is expensive, shorter trial
))


# --------------------------------------------
# DEVELOPER MODULES
# --------------------------------------------

register_module(Module(
    id="forgejo",
    name="Forgejo",
    description="Self-hosted Git repository and code collaboration",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.LOW,
    container_image="codeberg.org/forgejo/forgejo:latest",
    default_port=3000,
    bundles=["developer", "professional"],
    dependencies=["postgresql"],
    authentik_app_slug="forgejo",
    authentik_group="forgejo-users",
    subdomain="git",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="woodpecker",
    name="Woodpecker CI",
    description="Continuous Integration and Deployment pipelines",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.MEDIUM,
    container_image="woodpeckerci/woodpecker-server:latest",
    default_port=8000,
    bundles=["developer", "professional"],
    dependencies=["forgejo", "postgresql"],
    authentik_app_slug="woodpecker",
    authentik_group="woodpecker-users",
    subdomain="ci",
    ram_mb=512,
    cpu_shares=1024,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="ollama",
    name="Ollama",
    description="Local LLM runtime for AI features",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.MEDIUM,
    container_image="ollama/ollama:latest",
    default_port=11434,
    bundles=["developer", "professional"],
    authentik_app_slug="ollama",
    subdomain="llm",
    ram_mb=4096,  # LLMs need RAM
    cpu_shares=2048,
    monthly_addon_price=0.0,  # Free but requires resources
    trial_eligible=True,
    trial_days=90,
))

register_module(Module(
    id="reactor",
    name="Reactor AI",
    description="AI-powered code assistant with DEFCON ONE safety controls",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.MEDIUM,
    container_image="wopr/reactor:latest",
    default_port=8080,
    bundles=["developer", "professional"],
    dependencies=["ollama", "forgejo", "defcon_one"],
    authentik_app_slug="reactor",
    authentik_group="reactor-users",
    subdomain="reactor",
    ram_mb=2048,
    cpu_shares=1024,
    monthly_addon_price=9.99,
    trial_eligible=True,  # KEY: Allow trial for vibe coders!
    trial_days=90,  # 3 months to hook them
))

register_module(Module(
    id="defcon_one",
    name="DEFCON ONE",
    description="Protected actions gateway - AI doesn't get root, people do",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.LOW,
    container_image="wopr/defcon-one:latest",
    default_port=8081,
    bundles=["developer", "professional"],
    dependencies=["authentik", "postgresql"],
    authentik_app_slug="defcon-one",
    authentik_group="defcon-operators",
    subdomain="defcon",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,  # Part of Reactor trial
    trial_days=90,
))

register_module(Module(
    id="code_server",
    name="VS Code Server",
    description="Browser-based VS Code IDE",
    category=ModuleCategory.DEVELOPER,
    tier=ModuleTier.MEDIUM,
    container_image="codercom/code-server:latest",
    default_port=8080,
    bundles=["developer", "professional"],
    authentik_app_slug="code-server",
    authentik_group="code-server-users",
    subdomain="code",
    ram_mb=1024,
    cpu_shares=1024,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))


# --------------------------------------------
# CREATOR MODULES
# --------------------------------------------

register_module(Module(
    id="ghost",
    name="Ghost",
    description="Professional publishing platform and blog",
    category=ModuleCategory.CREATOR,
    tier=ModuleTier.LOW,
    container_image="ghost:latest",
    default_port=2368,
    bundles=["creator", "professional"],
    dependencies=["postgresql"],
    authentik_app_slug="ghost",
    authentik_group="ghost-users",
    subdomain="blog",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="saleor",
    name="Saleor",
    description="Headless e-commerce platform",
    category=ModuleCategory.CREATOR,
    tier=ModuleTier.MEDIUM,
    container_image="ghcr.io/saleor/saleor:latest",
    default_port=8000,
    bundles=["creator", "professional"],
    dependencies=["postgresql", "redis"],
    authentik_app_slug="saleor",
    authentik_group="saleor-users",
    subdomain="store",
    ram_mb=1024,
    cpu_shares=1024,
    monthly_addon_price=9.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="wordpress",
    name="WordPress",
    description="Classic website and blog platform",
    category=ModuleCategory.CREATOR,
    tier=ModuleTier.LOW,
    container_image="wordpress:latest",
    default_port=80,
    bundles=[],  # Optional add-on only
    dependencies=["postgresql"],
    authentik_app_slug="wordpress",
    subdomain="www",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=2.99,
    trial_eligible=True,
    trial_days=30,
))


# --------------------------------------------
# BUSINESS MODULES
# --------------------------------------------

register_module(Module(
    id="espocrm",
    name="EspoCRM",
    description="Customer relationship management",
    category=ModuleCategory.BUSINESS,
    tier=ModuleTier.LOW,
    container_image="espocrm/espocrm:latest",
    default_port=80,
    bundles=[],  # Optional add-on
    dependencies=["postgresql"],
    authentik_app_slug="espocrm",
    authentik_group="crm-users",
    subdomain="crm",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="kimai",
    name="Kimai",
    description="Time tracking for freelancers and teams",
    category=ModuleCategory.BUSINESS,
    tier=ModuleTier.LOW,
    container_image="kimai/kimai2:latest",
    default_port=8001,
    bundles=[],  # Optional add-on
    dependencies=["postgresql"],
    authentik_app_slug="kimai",
    authentik_group="kimai-users",
    subdomain="time",
    ram_mb=256,
    cpu_shares=256,
    monthly_addon_price=2.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="invoiceninja",
    name="Invoice Ninja",
    description="Invoicing and payment tracking",
    category=ModuleCategory.BUSINESS,
    tier=ModuleTier.LOW,
    container_image="invoiceninja/invoiceninja:latest",
    default_port=80,
    bundles=[],  # Optional add-on
    dependencies=["postgresql"],
    authentik_app_slug="invoiceninja",
    authentik_group="invoicing-users",
    subdomain="invoices",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))


# --------------------------------------------
# MEDIA MODULES
# --------------------------------------------

register_module(Module(
    id="immich",
    name="Immich",
    description="Self-hosted photo and video backup (Google Photos alternative)",
    category=ModuleCategory.MEDIA,
    tier=ModuleTier.MEDIUM,
    container_image="ghcr.io/immich-app/immich-server:latest",
    default_port=3001,
    bundles=[],  # Optional add-on
    dependencies=["postgresql", "redis"],
    authentik_app_slug="immich",
    authentik_group="immich-users",
    subdomain="photos",
    ram_mb=2048,
    cpu_shares=1024,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="jellyfin",
    name="Jellyfin",
    description="Media server for movies, TV, and music",
    category=ModuleCategory.MEDIA,
    tier=ModuleTier.MEDIUM,
    container_image="jellyfin/jellyfin:latest",
    default_port=8096,
    bundles=[],  # Optional add-on
    authentik_app_slug="jellyfin",
    authentik_group="jellyfin-users",
    subdomain="media",
    ram_mb=2048,
    cpu_shares=2048,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))


# --------------------------------------------
# ANALYTICS MODULES
# --------------------------------------------

register_module(Module(
    id="plausible",
    name="Plausible",
    description="Privacy-friendly website analytics",
    category=ModuleCategory.ANALYTICS,
    tier=ModuleTier.LOW,
    container_image="plausible/analytics:latest",
    default_port=8000,
    bundles=[],  # Optional add-on
    dependencies=["postgresql"],
    authentik_app_slug="plausible",
    authentik_group="plausible-users",
    subdomain="analytics",
    ram_mb=512,
    cpu_shares=512,
    monthly_addon_price=4.99,
    trial_eligible=True,
    trial_days=30,
))

register_module(Module(
    id="uptime_kuma",
    name="Uptime Kuma",
    description="Self-hosted uptime monitoring",
    category=ModuleCategory.ANALYTICS,
    tier=ModuleTier.MINIMAL,
    container_image="louislam/uptime-kuma:latest",
    default_port=3001,
    bundles=["developer", "professional"],
    authentik_app_slug="uptime-kuma",
    authentik_group="uptime-users",
    subdomain="status",
    ram_mb=256,
    cpu_shares=256,
))


# --------------------------------------------
# RSS/CONTENT MODULES
# --------------------------------------------

register_module(Module(
    id="freshrss",
    name="FreshRSS",
    description="RSS feed reader and aggregator",
    category=ModuleCategory.PRODUCTIVITY,
    tier=ModuleTier.MINIMAL,
    container_image="freshrss/freshrss:latest",
    default_port=80,
    bundles=["personal", "creator", "developer", "professional"],
    authentik_app_slug="freshrss",
    authentik_group="freshrss-users",
    subdomain="rss",
    ram_mb=256,
    cpu_shares=256,
))


# ============================================
# BUNDLE DEFINITIONS
# ============================================

@dataclass
class BundleModules:
    """Modules included in each bundle."""
    bundle_id: str
    name: str
    description: str
    base_modules: List[str]  # Always included
    optional_modules: List[str]  # Can be added
    trial_modules: List[str]  # Can be trialed free
    resource_tier: ModuleTier

    def get_total_ram_mb(self) -> int:
        """Calculate total RAM needed for base modules."""
        total = 0
        for mod_id in self.base_modules:
            if mod_id in MODULES:
                total += MODULES[mod_id].ram_mb
        return total


BUNDLES: Dict[str, BundleModules] = {
    "personal": BundleModules(
        bundle_id="personal",
        name="Personal Sovereign Suite",
        description="Privacy-focused personal cloud",
        base_modules=[
            "authentik", "caddy", "postgresql", "redis",
            "nextcloud", "vaultwarden", "freshrss"
        ],
        optional_modules=[
            "immich", "jellyfin", "wordpress", "plausible"
        ],
        trial_modules=[
            # Let personal users try developer tools!
            "ollama", "reactor", "defcon_one",
            "forgejo", "ghost", "code_server"
        ],
        resource_tier=ModuleTier.LOW,
    ),

    "creator": BundleModules(
        bundle_id="creator",
        name="Creator Sovereign Suite",
        description="Personal cloud + monetization tools",
        base_modules=[
            "authentik", "caddy", "postgresql", "redis",
            "nextcloud", "vaultwarden", "freshrss",
            "ghost", "saleor"
        ],
        optional_modules=[
            "wordpress", "immich", "plausible", "espocrm",
            "kimai", "invoiceninja"
        ],
        trial_modules=[
            # Let creators try developer tools!
            "ollama", "reactor", "defcon_one",
            "forgejo", "code_server"
        ],
        resource_tier=ModuleTier.MEDIUM,
    ),

    "developer": BundleModules(
        bundle_id="developer",
        name="Developer Sovereign Suite",
        description="Code ownership + AI assistance",
        base_modules=[
            "authentik", "caddy", "postgresql", "redis",
            "nextcloud", "vaultwarden", "freshrss",
            "forgejo", "woodpecker", "ollama",
            "reactor", "defcon_one", "code_server",
            "uptime_kuma"
        ],
        optional_modules=[
            "ghost", "wordpress", "immich", "plausible"
        ],
        trial_modules=[
            # Developer can trial creator/business tools
            "saleor", "espocrm", "kimai", "invoiceninja",
            "matrix", "element", "jitsi", "collabora", "outline"
        ],
        resource_tier=ModuleTier.MEDIUM,
    ),

    "professional": BundleModules(
        bundle_id="professional",
        name="Professional Sovereign Suite",
        description="Complete sovereign work environment",
        base_modules=[
            "authentik", "caddy", "postgresql", "redis",
            "nextcloud", "vaultwarden", "freshrss",
            "ghost", "saleor",
            "forgejo", "woodpecker", "ollama",
            "reactor", "defcon_one", "code_server",
            "matrix", "element", "jitsi",
            "collabora", "outline", "uptime_kuma"
        ],
        optional_modules=[
            "wordpress", "immich", "jellyfin", "plausible",
            "espocrm", "kimai", "invoiceninja"
        ],
        trial_modules=[],  # Professional has everything
        resource_tier=ModuleTier.HIGH,
    ),
}


# ============================================
# MODULE REGISTRY CLASS
# ============================================

class ModuleRegistry:
    """
    Central registry for module queries and management.
    """

    @staticmethod
    def get_module(module_id: str) -> Optional[Module]:
        """Get a module by ID."""
        return MODULES.get(module_id)

    @staticmethod
    def get_bundle(bundle_id: str) -> Optional[BundleModules]:
        """Get bundle definition."""
        return BUNDLES.get(bundle_id)

    @staticmethod
    def get_base_modules(bundle_id: str) -> List[Module]:
        """Get all base modules for a bundle."""
        bundle = BUNDLES.get(bundle_id)
        if not bundle:
            return []
        return [MODULES[m] for m in bundle.base_modules if m in MODULES]

    @staticmethod
    def get_trial_eligible_modules(bundle_id: str) -> List[Module]:
        """Get modules that can be trialed from this bundle."""
        bundle = BUNDLES.get(bundle_id)
        if not bundle:
            return []
        return [MODULES[m] for m in bundle.trial_modules if m in MODULES]

    @staticmethod
    def get_addon_modules(bundle_id: str) -> List[Module]:
        """Get paid add-on modules for a bundle."""
        bundle = BUNDLES.get(bundle_id)
        if not bundle:
            return []
        return [MODULES[m] for m in bundle.optional_modules if m in MODULES]

    @staticmethod
    def calculate_resources(module_ids: List[str]) -> Dict[str, int]:
        """Calculate total resources for a set of modules."""
        total_ram = 0
        total_cpu = 0

        for mod_id in module_ids:
            if mod_id in MODULES:
                total_ram += MODULES[mod_id].ram_mb
                total_cpu += MODULES[mod_id].cpu_shares

        return {
            "ram_mb": total_ram,
            "ram_gb": total_ram // 1024,
            "cpu_shares": total_cpu,
            "estimated_cores": total_cpu // 1024,
        }

    @staticmethod
    def check_dependencies(module_id: str, enabled_modules: Set[str]) -> List[str]:
        """Check if module dependencies are satisfied."""
        module = MODULES.get(module_id)
        if not module:
            return []

        missing = []
        for dep in module.dependencies:
            if dep not in enabled_modules:
                missing.append(dep)
        return missing

    @staticmethod
    def get_install_order(module_ids: List[str]) -> List[str]:
        """Get modules in dependency-resolved install order."""
        # Simple topological sort
        ordered = []
        remaining = set(module_ids)
        installed = set()

        while remaining:
            # Find modules with all deps satisfied
            ready = []
            for mod_id in remaining:
                module = MODULES.get(mod_id)
                if not module:
                    ready.append(mod_id)
                    continue

                deps_satisfied = all(
                    d in installed or d not in module_ids
                    for d in module.dependencies
                )
                if deps_satisfied:
                    ready.append(mod_id)

            if not ready:
                # Circular dependency or missing dep
                ordered.extend(remaining)
                break

            for mod_id in ready:
                ordered.append(mod_id)
                installed.add(mod_id)
                remaining.remove(mod_id)

        return ordered

    @staticmethod
    def format_module_list(bundle_id: str) -> str:
        """Format module list for display."""
        bundle = BUNDLES.get(bundle_id)
        if not bundle:
            return "Unknown bundle"

        lines = [
            f"=== {bundle.name} ===",
            "",
            "INCLUDED MODULES:",
        ]

        for mod_id in bundle.base_modules:
            mod = MODULES.get(mod_id)
            if mod:
                lines.append(f"  + {mod.name}: {mod.description}")

        if bundle.trial_modules:
            lines.append("")
            lines.append("FREE 90-DAY TRIAL AVAILABLE:")
            for mod_id in bundle.trial_modules:
                mod = MODULES.get(mod_id)
                if mod:
                    lines.append(f"  * {mod.name}: {mod.description}")

        if bundle.optional_modules:
            lines.append("")
            lines.append("PAID ADD-ONS:")
            for mod_id in bundle.optional_modules:
                mod = MODULES.get(mod_id)
                if mod:
                    price = f"${mod.monthly_addon_price}/mo" if mod.monthly_addon_price else "Free"
                    lines.append(f"  $ {mod.name} ({price}): {mod.description}")

        return "\n".join(lines)
