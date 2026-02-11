"""
WOPR Module Registry - 77 Modules across 9 Categories
Updated: January 2026
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


class ModuleCategory(Enum):
    CORE = "core"
    PRODUCTIVITY = "productivity"
    SECURITY = "security"
    COMMUNICATION = "communication"
    DEVELOPER = "developer"
    CREATOR = "creator"
    BUSINESS = "business"
    MEDIA = "media"
    ANALYTICS = "analytics"


class ModuleTier(Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SSOType(Enum):
    OIDC = "oidc"
    SAML = "saml"
    LDAP = "ldap"
    PROXY = "proxy"
    OAUTH2 = "oauth2"
    NONE = "none"


@dataclass
class Module:
    id: str
    name: str
    description: str
    category: ModuleCategory
    tier: ModuleTier
    container_image: str
    default_port: int
    sso_type: SSOType = SSOType.PROXY
    authentik_app_slug: str = ""
    authentik_group: str = ""
    bundles: List[str] = field(default_factory=list)
    trial_eligible: bool = False
    trial_days: int = 90
    monthly_addon_price: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    subdomain: str = ""
    ram_mb: int = 512
    cpu_shares: int = 512
    replaces: str = ""
    repo_url: str = ""

    def is_included_in(self, bundle: str) -> bool:
        return bundle in self.bundles


MODULES: Dict[str, Module] = {}

def register_module(module: Module) -> Module:
    MODULES[module.id] = module
    return module


class ModuleRegistry:
    """Registry wrapper providing lookup methods for deployed modules."""

    def get_module(self, module_id: str) -> Optional[Module]:
        return MODULES.get(module_id)

    def get_all_modules(self) -> List[Module]:
        return list(MODULES.values())

    def get_modules_for_bundle(self, bundle: str) -> List[Module]:
        return [m for m in MODULES.values() if m.is_included_in(bundle)]

    def get_modules_by_category(self, category: ModuleCategory) -> List[Module]:
        return [m for m in MODULES.values() if m.category == category]

# CORE (4)
register_module(Module(id="authentik", name="Authentik", description="SSO and identity management", category=ModuleCategory.CORE, tier=ModuleTier.LOW, container_image="ghcr.io/goauthentik/server:2025.8", default_port=9000, sso_type=SSOType.NONE, bundles=["starter","creator","developer","professional","family","small_business","enterprise"], subdomain="auth", ram_mb=1024, replaces="Okta, Auth0"))
register_module(Module(id="caddy", name="Caddy", description="Automatic HTTPS reverse proxy", category=ModuleCategory.CORE, tier=ModuleTier.MINIMAL, container_image="caddy:2-alpine", default_port=443, sso_type=SSOType.NONE, bundles=["starter","creator","developer","professional","family","small_business","enterprise"], ram_mb=128, replaces="Nginx, Apache"))
register_module(Module(id="postgresql", name="PostgreSQL", description="Primary database", category=ModuleCategory.CORE, tier=ModuleTier.LOW, container_image="postgres:16-alpine", default_port=5432, sso_type=SSOType.NONE, bundles=["starter","creator","developer","professional","family","small_business","enterprise"], ram_mb=512, replaces="AWS RDS"))
register_module(Module(id="redis", name="Redis", description="Cache and message broker", category=ModuleCategory.CORE, tier=ModuleTier.MINIMAL, container_image="redis:7-alpine", default_port=6379, sso_type=SSOType.NONE, bundles=["starter","creator","developer","professional","family","small_business","enterprise"], ram_mb=256, replaces="AWS ElastiCache"))

# PRODUCTIVITY (13)
register_module(Module(id="nextcloud", name="Nextcloud", description="Files, calendar, contacts", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="nextcloud:29-apache", default_port=80, sso_type=SSOType.OIDC, bundles=["starter","creator","developer","professional","family","small_business"], dependencies=["postgresql","redis"], authentik_app_slug="nextcloud", subdomain="files", ram_mb=1024, replaces="Google Drive, Dropbox"))
register_module(Module(id="collabora", name="Collabora Online", description="Online office suite", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.MEDIUM, container_image="collabora/code:24.04", default_port=9980, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["nextcloud"], subdomain="office", ram_mb=2048, monthly_addon_price=5.99, trial_eligible=True, replaces="Google Docs, Microsoft 365"))
register_module(Module(id="outline", name="Outline", description="Team wiki and knowledge base", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="outlinewiki/outline:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["postgresql","redis"], subdomain="wiki", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Notion, Confluence"))
register_module(Module(id="paperless_ngx", name="Paperless-ngx", description="Document management with OCR", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.MEDIUM, container_image="ghcr.io/paperless-ngx/paperless-ngx:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["postgresql","redis"], subdomain="docs", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Evernote, Adobe Scan"))
register_module(Module(id="bookstack", name="BookStack", description="Wiki and documentation", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="lscr.io/linuxserver/bookstack:latest", default_port=6875, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business"], dependencies=["postgresql"], subdomain="books", ram_mb=512, monthly_addon_price=2.99, trial_eligible=True, replaces="GitBook"))
register_module(Module(id="affine", name="AFFiNE", description="Notion alternative knowledge base", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.MEDIUM, container_image="ghcr.io/toeverything/affine-graphql:stable", default_port=3010, sso_type=SSOType.OIDC, bundles=["professional","enterprise"], dependencies=["postgresql","redis"], subdomain="notes", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Notion, Coda"))
register_module(Module(id="linkwarden", name="Linkwarden", description="Bookmark manager with archival", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="ghcr.io/linkwarden/linkwarden:latest", default_port=3000, sso_type=SSOType.PROXY, bundles=["starter","creator","developer","professional"], dependencies=["postgresql"], subdomain="links", ram_mb=512, replaces="Pocket, Raindrop"))
register_module(Module(id="standardnotes", name="Standard Notes", description="Encrypted notes", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="standardnotes/server:latest", default_port=3000, sso_type=SSOType.PROXY, bundles=["starter","professional","family"], dependencies=["postgresql","redis"], subdomain="notes", ram_mb=512, replaces="Apple Notes, Evernote"))
register_module(Module(id="calcom", name="Cal.com", description="Appointment scheduling", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="calcom/cal.com:v6.1.11", default_port=3000, sso_type=SSOType.OIDC, bundles=["creator","professional","small_business"], dependencies=["postgresql"], subdomain="cal", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Calendly"))
register_module(Module(id="hedgedoc", name="HedgeDoc", description="Collaborative markdown", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="quay.io/hedgedoc/hedgedoc:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["postgresql"], subdomain="pad", ram_mb=512, replaces="HackMD"))
register_module(Module(id="stirling_pdf", name="Stirling PDF", description="PDF tools suite", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="frooodle/s-pdf:latest", default_port=8080, sso_type=SSOType.PROXY, bundles=["starter","creator","professional","small_business"], subdomain="pdf", ram_mb=512, replaces="Adobe Acrobat"))
register_module(Module(id="docuseal", name="DocuSeal", description="Document signing", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.LOW, container_image="docuseal/docuseal:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["postgresql"], subdomain="sign", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="DocuSign"))
register_module(Module(id="freshrss", name="FreshRSS", description="RSS feed reader", category=ModuleCategory.PRODUCTIVITY, tier=ModuleTier.MINIMAL, container_image="freshrss/freshrss:latest", default_port=80, sso_type=SSOType.PROXY, bundles=["starter","creator","developer","professional"], subdomain="rss", ram_mb=256, replaces="Feedly"))

# SECURITY (7)
register_module(Module(id="vaultwarden", name="Vaultwarden", description="Password manager (Bitwarden)", category=ModuleCategory.SECURITY, tier=ModuleTier.MINIMAL, container_image="vaultwarden/server:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["starter","creator","developer","professional","family","small_business"], subdomain="vault", ram_mb=256, replaces="Bitwarden, 1Password, LastPass"))
register_module(Module(id="netbird", name="NetBird", description="WireGuard mesh VPN", category=ModuleCategory.SECURITY, tier=ModuleTier.LOW, container_image="netbirdio/netbird:latest", default_port=443, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business","enterprise"], dependencies=["postgresql"], subdomain="vpn", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Tailscale, NordVPN"))
register_module(Module(id="crowdsec", name="CrowdSec", description="Collaborative IDS", category=ModuleCategory.SECURITY, tier=ModuleTier.LOW, container_image="crowdsecurity/crowdsec:latest", default_port=8080, sso_type=SSOType.PROXY, bundles=["developer","professional","small_business","enterprise"], subdomain="security", ram_mb=512, replaces="Fail2ban"))
register_module(Module(id="wg_easy", name="WireGuard Easy", description="Simple WireGuard VPN", category=ModuleCategory.SECURITY, tier=ModuleTier.MINIMAL, container_image="ghcr.io/wg-easy/wg-easy:latest", default_port=51821, sso_type=SSOType.PROXY, bundles=["starter","family"], subdomain="wg", ram_mb=128, replaces="NordVPN, ExpressVPN"))
register_module(Module(id="adguard", name="AdGuard Home", description="Ad and tracker blocking", category=ModuleCategory.SECURITY, tier=ModuleTier.MINIMAL, container_image="adguard/adguardhome:latest", default_port=3000, sso_type=SSOType.PROXY, bundles=["starter","family","small_business"], subdomain="dns", ram_mb=256, replaces="Pi-hole, NextDNS"))
register_module(Module(id="passbolt", name="Passbolt", description="Team password manager", category=ModuleCategory.SECURITY, tier=ModuleTier.LOW, container_image="passbolt/passbolt:latest", default_port=443, sso_type=SSOType.OIDC, bundles=["small_business","enterprise"], dependencies=["postgresql"], subdomain="passwords", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="1Password Teams"))
register_module(Module(id="support-plane", name="WOPR Support Plane", description="Zero-trust remote support with SSH CA and audit logging", category=ModuleCategory.SECURITY, tier=ModuleTier.LOW, container_image="wopr/support-gateway:latest", default_port=8443, sso_type=SSOType.PROXY, authentik_app_slug="support-gateway", authentik_group="wopr-support-diag", bundles=["professional","small_business","enterprise"], dependencies=["authentik","caddy","postgresql"], subdomain="support-gateway", ram_mb=512, replaces="Custom SSH access, VPN-only support"))

# COMMUNICATION (8)
register_module(Module(id="matrix", name="Matrix (Synapse)", description="Decentralized chat server", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.MEDIUM, container_image="matrixdotorg/synapse:latest", default_port=8008, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["postgresql"], subdomain="matrix", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Slack, Teams"))
register_module(Module(id="element", name="Element", description="Matrix chat client", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.MINIMAL, container_image="vectorim/element-web:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["matrix"], subdomain="chat", ram_mb=128, replaces="Slack app"))
register_module(Module(id="jitsi", name="Jitsi Meet", description="Video conferencing", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.HIGH, container_image="jitsi/web:stable", default_port=443, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], subdomain="meet", ram_mb=2048, monthly_addon_price=9.99, trial_eligible=True, trial_days=14, replaces="Zoom, Google Meet"))
register_module(Module(id="mattermost", name="Mattermost", description="Slack alternative", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.MEDIUM, container_image="mattermost/mattermost-team-edition:latest", default_port=8065, sso_type=SSOType.OIDC, bundles=["small_business","enterprise"], dependencies=["postgresql"], subdomain="team", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Slack, Teams"))
register_module(Module(id="mailcow", name="Mailcow", description="Complete email server", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.HIGH, container_image="mailcow/mailcow-dockerized:latest", default_port=443, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], subdomain="mail", ram_mb=4096, monthly_addon_price=9.99, trial_eligible=True, replaces="Gmail, Outlook"))
register_module(Module(id="listmonk", name="Listmonk", description="Newsletter manager", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.LOW, container_image="listmonk/listmonk:latest", default_port=9000, sso_type=SSOType.PROXY, bundles=["creator","professional","small_business"], dependencies=["postgresql"], subdomain="newsletter", ram_mb=256, monthly_addon_price=2.99, trial_eligible=True, replaces="Mailchimp"))
register_module(Module(id="ntfy", name="ntfy", description="Push notifications", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.MINIMAL, container_image="binwiederhier/ntfy:latest", default_port=80, sso_type=SSOType.PROXY, bundles=["developer","professional"], subdomain="notify", ram_mb=128, replaces="Pushover"))
register_module(Module(id="mumble", name="Mumble", description="Voice chat", category=ModuleCategory.COMMUNICATION, tier=ModuleTier.LOW, container_image="mumblevoip/mumble-server:latest", default_port=64738, sso_type=SSOType.PROXY, bundles=["family"], subdomain="voice", ram_mb=256, replaces="Discord voice"))

# DEVELOPER (14)
register_module(Module(id="forgejo", name="Forgejo", description="Git repository hosting", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="codeberg.org/forgejo/forgejo:8", default_port=3000, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business"], dependencies=["postgresql"], subdomain="git", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="GitHub, GitLab"))
register_module(Module(id="woodpecker", name="Woodpecker CI", description="CI/CD pipelines", category=ModuleCategory.DEVELOPER, tier=ModuleTier.MEDIUM, container_image="woodpeckerci/woodpecker-server:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business"], dependencies=["forgejo","postgresql"], subdomain="ci", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="GitHub Actions, CircleCI"))
register_module(Module(id="ollama", name="Ollama", description="Local LLM runtime", category=ModuleCategory.DEVELOPER, tier=ModuleTier.HIGH, container_image="ollama/ollama:latest", default_port=11434, sso_type=SSOType.PROXY, bundles=["developer","professional"], subdomain="llm", ram_mb=8192, trial_eligible=True, replaces="OpenAI API, Claude API"))
register_module(Module(id="reactor", name="Reactor AI", description="AI code assistant with DEFCON ONE", category=ModuleCategory.DEVELOPER, tier=ModuleTier.MEDIUM, container_image="wopr/reactor:latest", default_port=8080, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["ollama","forgejo","defcon_one"], subdomain="reactor", ram_mb=2048, monthly_addon_price=9.99, trial_eligible=True, replaces="GitHub Copilot, Cursor"))
register_module(Module(id="defcon_one", name="DEFCON ONE", description="Protected actions gateway", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="wopr/defcon-one:latest", default_port=8081, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["authentik","postgresql"], subdomain="defcon", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Custom approval workflows"))
register_module(Module(id="code_server", name="VS Code Server", description="Browser-based VS Code", category=ModuleCategory.DEVELOPER, tier=ModuleTier.MEDIUM, container_image="codercom/code-server:latest", default_port=8080, sso_type=SSOType.OIDC, bundles=["developer","professional"], subdomain="code", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="VS Code, Codespaces"))
register_module(Module(id="portainer", name="Portainer", description="Docker management UI", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="portainer/portainer-ce:latest", default_port=9000, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business"], subdomain="docker", ram_mb=256, replaces="Docker Desktop"))
register_module(Module(id="registry", name="Docker Registry", description="Private container registry", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="registry:2", default_port=5000, sso_type=SSOType.PROXY, bundles=["developer","professional","small_business"], subdomain="registry", ram_mb=256, replaces="Docker Hub, GHCR"))
register_module(Module(id="langfuse", name="Langfuse", description="LLM observability", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="langfuse/langfuse:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["postgresql"], subdomain="llm-ops", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="LangSmith"))
register_module(Module(id="openwebui", name="Open WebUI", description="ChatGPT-style LLM UI", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="ghcr.io/open-webui/open-webui:main", default_port=8080, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["ollama"], subdomain="ai", ram_mb=512, replaces="ChatGPT, Claude.ai"))
register_module(Module(id="n8n", name="n8n", description="Workflow automation", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="n8nio/n8n:latest", default_port=5678, sso_type=SSOType.OIDC, bundles=["creator","developer","professional","small_business"], dependencies=["postgresql"], subdomain="automation", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Zapier, Make"))
register_module(Module(id="nocodb", name="NocoDB", description="Airtable alternative", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="nocodb/nocodb:latest", default_port=8080, sso_type=SSOType.OIDC, bundles=["creator","developer","professional","small_business"], dependencies=["postgresql"], subdomain="tables", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Airtable"))
register_module(Module(id="plane", name="Plane", description="Project management", category=ModuleCategory.DEVELOPER, tier=ModuleTier.LOW, container_image="makeplane/plane-frontend:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["developer","professional","small_business"], dependencies=["postgresql","redis"], subdomain="projects", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Jira, Linear"))
register_module(Module(id="gitea_runner", name="Gitea Act Runner", description="CI/CD runner", category=ModuleCategory.DEVELOPER, tier=ModuleTier.MEDIUM, container_image="gitea/act_runner:latest", default_port=0, sso_type=SSOType.NONE, bundles=["developer","professional"], dependencies=["forgejo"], ram_mb=1024, replaces="GitHub Actions runners"))

# CREATOR (10)
register_module(Module(id="ghost", name="Ghost", description="Professional blog platform", category=ModuleCategory.CREATOR, tier=ModuleTier.LOW, container_image="ghost:5-alpine", default_port=2368, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql"], subdomain="blog", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Medium, Substack"))
register_module(Module(id="saleor", name="Saleor", description="E-commerce platform", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="ghcr.io/saleor/saleor:latest", default_port=8000, sso_type=SSOType.PROXY, bundles=["creator","professional","small_business"], dependencies=["postgresql","redis"], subdomain="store", ram_mb=1024, monthly_addon_price=9.99, trial_eligible=True, replaces="Shopify"))
register_module(Module(id="peertube", name="PeerTube", description="Video hosting platform", category=ModuleCategory.CREATOR, tier=ModuleTier.HIGH, container_image="chocobozzz/peertube:production-bookworm", default_port=9000, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql","redis"], subdomain="video", ram_mb=2048, monthly_addon_price=9.99, trial_eligible=True, replaces="YouTube, Vimeo"))
register_module(Module(id="pixelfed", name="Pixelfed", description="Photo sharing (Instagram)", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="pixelfed/pixelfed:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql","redis"], subdomain="photos", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Instagram"))
register_module(Module(id="writefreely", name="WriteFreely", description="Minimalist blogging", category=ModuleCategory.CREATOR, tier=ModuleTier.MINIMAL, container_image="writeas/writefreely:latest", default_port=8080, sso_type=SSOType.OIDC, bundles=["creator"], dependencies=["postgresql"], subdomain="write", ram_mb=256, replaces="Medium"))
register_module(Module(id="funkwhale", name="Funkwhale", description="Music streaming/hosting", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="funkwhale/all-in-one:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["creator"], dependencies=["postgresql","redis"], subdomain="music", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Bandcamp, SoundCloud"))
register_module(Module(id="castopod", name="Castopod", description="Podcast hosting", category=ModuleCategory.CREATOR, tier=ModuleTier.LOW, container_image="castopod/castopod:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql"], subdomain="podcast", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Anchor, Spotify"))
register_module(Module(id="mastodon", name="Mastodon", description="Decentralized social", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="tootsuite/mastodon:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql","redis"], subdomain="social", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Twitter/X"))
register_module(Module(id="gotosocial", name="GoToSocial", description="Lightweight ActivityPub", category=ModuleCategory.CREATOR, tier=ModuleTier.MINIMAL, container_image="superseriousbusiness/gotosocial:latest", default_port=8080, sso_type=SSOType.OIDC, bundles=["creator"], dependencies=["postgresql"], subdomain="fedi", ram_mb=256, replaces="Twitter/X"))
register_module(Module(id="lemmy", name="Lemmy", description="Reddit alternative", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="dessalines/lemmy:latest", default_port=8536, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql"], subdomain="community", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Reddit"))

# BUSINESS (10)
register_module(Module(id="espocrm", name="EspoCRM", description="CRM system", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="espocrm/espocrm:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["small_business","enterprise"], dependencies=["postgresql"], subdomain="crm", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Salesforce"))
register_module(Module(id="kimai", name="Kimai", description="Time tracking", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="kimai/kimai2:latest", default_port=8001, sso_type=SSOType.OIDC, bundles=["creator","professional","small_business"], dependencies=["postgresql"], subdomain="time", ram_mb=256, monthly_addon_price=2.99, trial_eligible=True, replaces="Toggl, Harvest"))
register_module(Module(id="invoiceninja", name="Invoice Ninja", description="Invoicing", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="invoiceninja/invoiceninja:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["creator","professional","small_business"], dependencies=["postgresql"], subdomain="invoices", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="FreshBooks"))
register_module(Module(id="erpnext", name="ERPNext", description="Full ERP suite", category=ModuleCategory.BUSINESS, tier=ModuleTier.HIGH, container_image="frappe/erpnext:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["enterprise"], dependencies=["postgresql","redis"], subdomain="erp", ram_mb=4096, monthly_addon_price=19.99, trial_eligible=True, replaces="SAP, NetSuite"))
register_module(Module(id="dolibarr", name="Dolibarr", description="ERP/CRM for SMBs", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="dolibarr/dolibarr:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["small_business"], dependencies=["postgresql"], subdomain="business", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="QuickBooks"))
register_module(Module(id="odoo", name="Odoo Community", description="Business suite", category=ModuleCategory.BUSINESS, tier=ModuleTier.HIGH, container_image="odoo:17", default_port=8069, sso_type=SSOType.OIDC, bundles=["enterprise"], dependencies=["postgresql"], subdomain="odoo", ram_mb=2048, monthly_addon_price=14.99, trial_eligible=True, replaces="Zoho One"))
register_module(Module(id="twenty", name="Twenty", description="Modern CRM", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="twentycrm/twenty:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["professional","small_business"], dependencies=["postgresql"], subdomain="sales", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="HubSpot"))
register_module(Module(id="akaunting", name="Akaunting", description="Accounting", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="akaunting/akaunting:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["creator","small_business"], dependencies=["postgresql"], subdomain="accounting", ram_mb=512, monthly_addon_price=2.99, trial_eligible=True, replaces="QuickBooks, Xero"))
register_module(Module(id="documenso", name="Documenso", description="Document signing", category=ModuleCategory.BUSINESS, tier=ModuleTier.LOW, container_image="documenso/documenso:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["professional","small_business"], dependencies=["postgresql"], subdomain="esign", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="DocuSign"))
register_module(Module(id="chatwoot", name="Chatwoot", description="Customer support", category=ModuleCategory.BUSINESS, tier=ModuleTier.MEDIUM, container_image="chatwoot/chatwoot:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["professional","small_business","enterprise"], dependencies=["postgresql","redis"], subdomain="support", ram_mb=1024, monthly_addon_price=4.99, trial_eligible=True, replaces="Intercom, Zendesk"))

# MEDIA (8)
register_module(Module(id="immich", name="Immich", description="Photo/video backup", category=ModuleCategory.MEDIA, tier=ModuleTier.MEDIUM, container_image="ghcr.io/immich-app/immich-server:latest", default_port=3001, sso_type=SSOType.OIDC, bundles=["family","professional"], dependencies=["postgresql","redis"], subdomain="photos", ram_mb=2048, monthly_addon_price=4.99, trial_eligible=True, replaces="Google Photos"))
register_module(Module(id="jellyfin", name="Jellyfin", description="Media server", category=ModuleCategory.MEDIA, tier=ModuleTier.MEDIUM, container_image="jellyfin/jellyfin:latest", default_port=8096, sso_type=SSOType.OIDC, bundles=["family"], subdomain="media", ram_mb=2048, monthly_addon_price=4.99, trial_eligible=True, replaces="Plex, Netflix"))
register_module(Module(id="audiobookshelf", name="Audiobookshelf", description="Audiobook server", category=ModuleCategory.MEDIA, tier=ModuleTier.LOW, container_image="ghcr.io/advplyr/audiobookshelf:latest", default_port=80, sso_type=SSOType.OIDC, bundles=["family"], subdomain="audiobooks", ram_mb=512, monthly_addon_price=2.99, trial_eligible=True, replaces="Audible"))
register_module(Module(id="navidrome", name="Navidrome", description="Music streaming", category=ModuleCategory.MEDIA, tier=ModuleTier.LOW, container_image="deluan/navidrome:latest", default_port=4533, sso_type=SSOType.PROXY, bundles=["family"], subdomain="stream", ram_mb=256, replaces="Spotify"))
register_module(Module(id="stash", name="Stash", description="Media organizer", category=ModuleCategory.MEDIA, tier=ModuleTier.MEDIUM, container_image="stashapp/stash:latest", default_port=9999, sso_type=SSOType.PROXY, bundles=[], subdomain="stash", ram_mb=1024, monthly_addon_price=2.99, trial_eligible=True, replaces="Custom media org"))
register_module(Module(id="photoprism", name="PhotoPrism", description="AI photo management", category=ModuleCategory.MEDIA, tier=ModuleTier.HIGH, container_image="photoprism/photoprism:latest", default_port=2342, sso_type=SSOType.OIDC, bundles=["professional"], subdomain="gallery", ram_mb=4096, monthly_addon_price=4.99, trial_eligible=True, replaces="Google Photos AI"))
register_module(Module(id="kavita", name="Kavita", description="Ebook/comic library", category=ModuleCategory.MEDIA, tier=ModuleTier.LOW, container_image="kizaing/kavita:latest", default_port=5000, sso_type=SSOType.PROXY, bundles=["family"], subdomain="library", ram_mb=512, replaces="Kindle"))
register_module(Module(id="calibre_web", name="Calibre-Web", description="Ebook library", category=ModuleCategory.MEDIA, tier=ModuleTier.LOW, container_image="lscr.io/linuxserver/calibre-web:latest", default_port=8083, sso_type=SSOType.OIDC, bundles=["family"], subdomain="ebooks", ram_mb=512, replaces="Kindle, Kobo"))

# ANALYTICS (8)
register_module(Module(id="plausible", name="Plausible", description="Privacy analytics", category=ModuleCategory.ANALYTICS, tier=ModuleTier.LOW, container_image="plausible/analytics:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql"], subdomain="analytics", ram_mb=512, monthly_addon_price=4.99, trial_eligible=True, replaces="Google Analytics"))
register_module(Module(id="uptime_kuma", name="Uptime Kuma", description="Uptime monitoring", category=ModuleCategory.ANALYTICS, tier=ModuleTier.MINIMAL, container_image="louislam/uptime-kuma:latest", default_port=3001, sso_type=SSOType.PROXY, bundles=["developer","professional","small_business"], subdomain="status", ram_mb=256, replaces="Pingdom, UptimeRobot"))
register_module(Module(id="grafana", name="Grafana", description="Metrics dashboards", category=ModuleCategory.ANALYTICS, tier=ModuleTier.LOW, container_image="grafana/grafana:latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["developer","professional","enterprise"], dependencies=["postgresql"], subdomain="grafana", ram_mb=512, replaces="Datadog"))
register_module(Module(id="prometheus", name="Prometheus", description="Metrics collection", category=ModuleCategory.ANALYTICS, tier=ModuleTier.LOW, container_image="prom/prometheus:latest", default_port=9090, sso_type=SSOType.PROXY, bundles=["developer","professional","enterprise"], subdomain="metrics", ram_mb=512, replaces="Datadog"))
register_module(Module(id="netdata", name="Netdata", description="Real-time monitoring", category=ModuleCategory.ANALYTICS, tier=ModuleTier.LOW, container_image="netdata/netdata:latest", default_port=19999, sso_type=SSOType.PROXY, bundles=["developer","professional"], subdomain="monitor", ram_mb=512, replaces="New Relic"))
register_module(Module(id="umami", name="Umami", description="Simple analytics", category=ModuleCategory.ANALYTICS, tier=ModuleTier.LOW, container_image="ghcr.io/umami-software/umami:postgresql-latest", default_port=3000, sso_type=SSOType.OIDC, bundles=["creator","professional"], dependencies=["postgresql"], subdomain="stats", ram_mb=256, replaces="Google Analytics"))
register_module(Module(id="healthchecks", name="Healthchecks", description="Cron job monitoring", category=ModuleCategory.ANALYTICS, tier=ModuleTier.MINIMAL, container_image="healthchecks/healthchecks:latest", default_port=8000, sso_type=SSOType.OIDC, bundles=["developer","professional"], dependencies=["postgresql"], subdomain="health", ram_mb=256, replaces="Cronitor"))
register_module(Module(id="gatus", name="Gatus", description="Service health dashboard", category=ModuleCategory.ANALYTICS, tier=ModuleTier.MINIMAL, container_image="twinproduction/gatus:latest", default_port=8080, sso_type=SSOType.PROXY, bundles=["developer","professional","small_business"], subdomain="health-status", ram_mb=128, replaces="StatusPage"))
register_module(Module(id="social_poster", name="Social Poster", description="AI-powered multi-platform social media auto-poster", category=ModuleCategory.CREATOR, tier=ModuleTier.MEDIUM, container_image="wopr/social-poster:latest", default_port=8585, sso_type=SSOType.PROXY, bundles=["creator","professional","small_business"], dependencies=["postgresql","redis","ollama"], subdomain="social-poster", ram_mb=1024, monthly_addon_price=9.99, trial_eligible=True, replaces="Buffer, Hootsuite, Later"))

def get_module_count():
    counts = {cat.value: len([m for m in MODULES.values() if m.category == cat]) for cat in ModuleCategory}
    counts["total"] = len(MODULES)
    return counts

if __name__ == "__main__":
    print(f"WOPR Module Registry: {get_module_count()}")


# ── Bundle registry (merged from bundles.manifests) ─────────────────────────
def _build_bundles():
    """Build a combined BUNDLES dict with string keys from sovereign + micro manifests."""
    try:
        from ..bundles.manifests import SOVEREIGN_BUNDLES, MICRO_BUNDLES, BundleManifest
        # Add compatibility properties if needed
        if not hasattr(BundleManifest, 'base_modules'):
            BundleManifest.base_modules = property(lambda self: self.modules)
        if not hasattr(BundleManifest, 'description'):
            BundleManifest.description = property(lambda self: self.tagline)
        if not hasattr(BundleManifest, 'trial_modules'):
            BundleManifest.trial_modules = property(lambda self: [
                m_id for m_id in self.modules
                if m_id in MODULES and MODULES[m_id].trial_eligible
            ])
        combined = {}
        for k, v in SOVEREIGN_BUNDLES.items():
            combined[k.value if hasattr(k, 'value') else str(k)] = v
        for k, v in MICRO_BUNDLES.items():
            combined[k.value if hasattr(k, 'value') else str(k)] = v
        return combined
    except ImportError:
        return {}

BUNDLES = _build_bundles()

class BundleModules:
    """Convenience class for querying modules within bundles."""
    @staticmethod
    def get_bundle_modules(bundle_id: str) -> List[str]:
        bundle = BUNDLES.get(bundle_id)
        return bundle.modules if bundle else []

    @staticmethod
    def get_all_bundle_ids() -> List[str]:
        return list(BUNDLES.keys())
