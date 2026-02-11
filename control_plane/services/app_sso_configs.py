"""
App-Specific SSO Configuration Templates

Each app has its own quirks for OIDC/SSO integration:
- Different callback URL patterns
- Different environment variable names
- Different claim mappings
- Special scopes required

This module provides app-specific overrides for the generic provisioner.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class AppSSOConfig:
    """SSO configuration for a specific application"""
    app_id: str

    # OAuth2/OIDC settings
    redirect_uri_patterns: list[str] = field(default_factory=list)
    required_scopes: list[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    token_endpoint_auth_method: str = "client_secret_post"  # or client_secret_basic

    # Environment variable mappings (app's env var name -> our standard name)
    env_mappings: dict[str, str] = field(default_factory=dict)

    # Additional static env vars needed
    extra_env: dict[str, str] = field(default_factory=dict)

    # Custom initialization commands (run after deployment)
    post_deploy_commands: list[str] = field(default_factory=list)

    # Special notes for manual steps (if any)
    notes: Optional[str] = None


# =============================================================================
# Productivity Apps
# =============================================================================

NEXTCLOUD_CONFIG = AppSSOConfig(
    app_id="nextcloud",
    redirect_uri_patterns=[
        "{app_url}/apps/oidc/callback",
        "{app_url}/apps/user_oidc/callback",
    ],
    required_scopes=["openid", "email", "profile", "groups"],
    env_mappings={
        "OIDC_LOGIN_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_LOGIN_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_LOGIN_PROVIDER_URL": "OIDC_ISSUER",
    },
    extra_env={
        "OIDC_LOGIN_AUTO_REDIRECT": "true",
        "OIDC_LOGIN_LOGOUT_URL": "{authentik_url}/application/o/{app_slug}/end-session/",
        "OIDC_LOGIN_BUTTON_TEXT": "Login with WOPR",
        "OIDC_LOGIN_HIDE_PASSWORD_FORM": "false",
        "OIDC_LOGIN_USE_ID_TOKEN": "true",
        "OIDC_LOGIN_ATTRIBUTES_ID": "sub",
        "OIDC_LOGIN_ATTRIBUTES_NAME": "name",
        "OIDC_LOGIN_ATTRIBUTES_MAIL": "email",
        "OIDC_LOGIN_ATTRIBUTES_GROUPS": "groups",
    },
    post_deploy_commands=[
        "docker exec nextcloud occ app:enable user_oidc",
        "docker exec nextcloud occ config:app:set user_oidc allow_multiple_user_backends --value=0",
    ],
)

OUTLINE_CONFIG = AppSSOConfig(
    app_id="outline",
    redirect_uri_patterns=[
        "{app_url}/auth/oidc.callback",
    ],
    required_scopes=["openid", "email", "profile"],
    env_mappings={
        "OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_AUTH_URI": "OIDC_AUTH_URL",
        "OIDC_TOKEN_URI": "OIDC_TOKEN_URL",
        "OIDC_USERINFO_URI": "OIDC_USERINFO_URL",
    },
    extra_env={
        "OIDC_DISPLAY_NAME": "WOPR SSO",
        "OIDC_SCOPES": "openid email profile",
        "OIDC_USERNAME_CLAIM": "preferred_username",
    },
)

BOOKSTACK_CONFIG = AppSSOConfig(
    app_id="bookstack",
    redirect_uri_patterns=[
        "{app_url}/oidc/callback",
    ],
    env_mappings={
        "OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "OIDC_NAME": "WOPR SSO",
        "OIDC_DISPLAY_NAME_CLAIMS": "name",
        "OIDC_ISSUER_DISCOVER": "true",
        "OIDC_USER_TO_GROUPS": "true",
        "OIDC_GROUPS_CLAIM": "groups",
        "OIDC_REMOVE_FROM_GROUPS": "true",
        "AUTH_AUTO_INITIATE": "true",
    },
)

PAPERLESS_CONFIG = AppSSOConfig(
    app_id="paperless-ngx",
    redirect_uri_patterns=[
        "{app_url}/accounts/oidc/authentik/login/callback/",
    ],
    env_mappings={
        "PAPERLESS_SOCIALACCOUNT_PROVIDERS": "OIDC_CONFIG_JSON",
    },
    extra_env={
        "PAPERLESS_ENABLE_HTTP_REMOTE_USER": "true",
        "PAPERLESS_HTTP_REMOTE_USER_HEADER_NAME": "HTTP_X_AUTHENTIK_USERNAME",
        "PAPERLESS_LOGOUT_REDIRECT_URL": "{authentik_url}/application/o/{app_slug}/end-session/",
    },
)

HEDGEDOC_CONFIG = AppSSOConfig(
    app_id="hedgedoc",
    redirect_uri_patterns=[
        "{app_url}/auth/oauth2/callback",
    ],
    env_mappings={
        "CMD_OAUTH2_CLIENT_ID": "OIDC_CLIENT_ID",
        "CMD_OAUTH2_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "CMD_OAUTH2_AUTHORIZATION_URL": "OIDC_AUTH_URL",
        "CMD_OAUTH2_TOKEN_URL": "OIDC_TOKEN_URL",
        "CMD_OAUTH2_USER_PROFILE_URL": "OIDC_USERINFO_URL",
    },
    extra_env={
        "CMD_OAUTH2_PROVIDERNAME": "WOPR",
        "CMD_OAUTH2_SCOPE": "openid email profile",
        "CMD_OAUTH2_USER_PROFILE_USERNAME_ATTR": "preferred_username",
        "CMD_OAUTH2_USER_PROFILE_DISPLAY_NAME_ATTR": "name",
        "CMD_OAUTH2_USER_PROFILE_EMAIL_ATTR": "email",
    },
)

AFFINE_CONFIG = AppSSOConfig(
    app_id="affine",
    redirect_uri_patterns=[
        "{app_url}/oauth/callback",
    ],
    env_mappings={
        "OAUTH_OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OAUTH_OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OAUTH_OIDC_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "OAUTH_OIDC_ENABLED": "true",
        "OAUTH_OIDC_SCOPE": "openid profile email",
    },
)

CALCOM_CONFIG = AppSSOConfig(
    app_id="calcom",
    redirect_uri_patterns=[
        "{app_url}/api/auth/callback/authentik",
    ],
    required_scopes=["openid", "email", "profile"],
    env_mappings={
        "OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "OIDC_ENABLED": "true",
    },
)

# =============================================================================
# Communication Apps
# =============================================================================

MATRIX_SYNAPSE_CONFIG = AppSSOConfig(
    app_id="matrix-synapse",
    redirect_uri_patterns=[
        "{app_url}/_synapse/client/oidc/callback",
    ],
    required_scopes=["openid", "email", "profile"],
    env_mappings={},  # Synapse uses YAML config
    extra_env={
        "SYNAPSE_OIDC_ENABLED": "true",
    },
    notes="Synapse requires YAML configuration for OIDC. See authentik/synapse-oidc.yaml template.",
)

MATTERMOST_CONFIG = AppSSOConfig(
    app_id="mattermost",
    redirect_uri_patterns=[
        "{app_url}/signup/gitlab/complete",
        "{app_url}/login/gitlab/complete",
    ],
    env_mappings={
        "MM_GITLABSETTINGS_ID": "OIDC_CLIENT_ID",
        "MM_GITLABSETTINGS_SECRET": "OIDC_CLIENT_SECRET",
        "MM_GITLABSETTINGS_AUTHENDPOINT": "OIDC_AUTH_URL",
        "MM_GITLABSETTINGS_TOKENENDPOINT": "OIDC_TOKEN_URL",
        "MM_GITLABSETTINGS_USERAPIENDPOINT": "OIDC_USERINFO_URL",
    },
    extra_env={
        "MM_GITLABSETTINGS_ENABLE": "true",
        "MM_GITLABSETTINGS_SCOPE": "openid email profile",
    },
    notes="Mattermost uses GitLab settings for generic OAuth2/OIDC",
)

JITSI_CONFIG = AppSSOConfig(
    app_id="jitsi",
    redirect_uri_patterns=[
        "{app_url}/",
    ],
    extra_env={
        "ENABLE_AUTH": "1",
        "AUTH_TYPE": "jwt",
        "ENABLE_GUESTS": "0",
    },
    notes="Jitsi uses JWT auth. Authentik proxy provider handles authentication.",
)

ELEMENT_CONFIG = AppSSOConfig(
    app_id="element",
    redirect_uri_patterns=[],  # Element is a client, redirects to Matrix server
    extra_env={},
    notes="Element uses Matrix homeserver OIDC. Configure via config.json to point to Synapse.",
)

# =============================================================================
# Developer Apps
# =============================================================================

FORGEJO_CONFIG = AppSSOConfig(
    app_id="forgejo",
    redirect_uri_patterns=[
        "{app_url}/user/oauth2/authentik/callback",
    ],
    required_scopes=["openid", "email", "profile", "groups"],
    env_mappings={
        "FORGEJO__oauth2_client__AUTHENTIK__CLIENT_ID": "OIDC_CLIENT_ID",
        "FORGEJO__oauth2_client__AUTHENTIK__CLIENT_SECRET": "OIDC_CLIENT_SECRET",
    },
    extra_env={
        "FORGEJO__oauth2_client__ENABLED": "true",
        "FORGEJO__oauth2_client__AUTHENTIK__PROVIDER": "openidConnect",
        "FORGEJO__oauth2_client__AUTHENTIK__ICON_URL": "https://goauthentik.io/img/icon.png",
        "FORGEJO__oauth2_client__AUTHENTIK__SCOPES": "openid email profile groups",
        "FORGEJO__oauth2_client__AUTHENTIK__AUTO_DISCOVER_URL": "{oidc_discovery_url}",
        "FORGEJO__oauth2_client__AUTHENTIK__GROUP_CLAIM_NAME": "groups",
        "FORGEJO__oauth2_client__AUTHENTIK__ADMIN_GROUP": "forgejo-admins",
    },
)

PORTAINER_CONFIG = AppSSOConfig(
    app_id="portainer",
    redirect_uri_patterns=[
        "{app_url}/",
    ],
    env_mappings={},
    extra_env={},
    notes="Portainer Business supports OAuth. Community edition uses proxy auth via Authentik.",
)

CODE_SERVER_CONFIG = AppSSOConfig(
    app_id="code-server",
    redirect_uri_patterns=[],  # Uses proxy auth
    extra_env={
        "PASSWORD": "",  # Disable password auth, use Authentik proxy
    },
    notes="Code-server uses Authentik proxy authentication. No native OIDC.",
)

N8N_CONFIG = AppSSOConfig(
    app_id="n8n",
    redirect_uri_patterns=[
        "{app_url}/rest/oauth2-credential/callback",
    ],
    env_mappings={},  # n8n uses settings UI
    extra_env={
        "N8N_USER_MANAGEMENT_DISABLED": "false",
    },
    notes="n8n OIDC is configured via UI. Community edition has limited SSO support.",
)

NOCODB_CONFIG = AppSSOConfig(
    app_id="nocodb",
    redirect_uri_patterns=[
        "{app_url}/api/v1/auth/callback/oidc",
    ],
    env_mappings={
        "NC_OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "NC_OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "NC_OIDC_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "NC_OIDC_ENABLED": "true",
        "NC_OIDC_NAME": "WOPR SSO",
    },
)

PLANE_CONFIG = AppSSOConfig(
    app_id="plane",
    redirect_uri_patterns=[
        "{app_url}/api/v1/auth/callback/oidc/",
    ],
    env_mappings={
        "OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_ISSUER_URL": "OIDC_ISSUER",
    },
    extra_env={
        "ENABLE_OIDC": "1",
        "OIDC_PROVIDER_NAME": "WOPR SSO",
    },
)

# =============================================================================
# Security Apps
# =============================================================================

VAULTWARDEN_CONFIG = AppSSOConfig(
    app_id="vaultwarden",
    redirect_uri_patterns=[
        "{app_url}/identity/connect/oidc-signin",
    ],
    required_scopes=["openid", "email", "profile", "groups"],
    env_mappings={
        "SSO_CLIENT_ID": "OIDC_CLIENT_ID",
        "SSO_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "SSO_AUTHORITY": "OIDC_ISSUER",
    },
    extra_env={
        "SSO_ENABLED": "true",
        "SSO_ONLY": "false",  # Allow password auth as backup
        "SSO_SIGNUPS_MATCH_EMAIL": "true",
        "SSO_ORGANIZATIONS_ENABLED": "true",
        "SSO_ORGANIZATIONS_ALL_COLLECTIONS": "true",
    },
)

NETBIRD_CONFIG = AppSSOConfig(
    app_id="netbird",
    redirect_uri_patterns=[
        "{app_url}/auth/callback",
        "{app_url}/silent-auth",
    ],
    required_scopes=["openid", "email", "profile", "offline_access"],
    env_mappings={
        "NETBIRD_AUTH_CLIENT_ID": "OIDC_CLIENT_ID",
        "NETBIRD_AUTH_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "NETBIRD_AUTH_AUTHORITY": "OIDC_ISSUER",
    },
    extra_env={
        "NETBIRD_AUTH_SUPPORTED_SCOPES": "openid email profile offline_access",
        "NETBIRD_AUTH_DEVICE_AUTH_PROVIDER": "none",
        "NETBIRD_AUTH_USE_ID_TOKEN": "true",
        "NETBIRD_AUTH_AUDIENCE": "{app_url}",
    },
)

# =============================================================================
# Business Apps
# =============================================================================

INVOICENINJA_CONFIG = AppSSOConfig(
    app_id="invoiceninja",
    redirect_uri_patterns=[
        "{app_url}/auth/oidc/callback",
    ],
    env_mappings={},  # Uses .env file directly
    extra_env={
        "OIDC_ENABLED": "true",
        "OIDC_NAME": "WOPR SSO",
        "OIDC_SCOPES": "openid email profile",
    },
)

ERPNEXT_CONFIG = AppSSOConfig(
    app_id="erpnext",
    redirect_uri_patterns=[
        "{app_url}/api/method/frappe.integrations.oauth2_logins.login_via_oauth2",
    ],
    env_mappings={},
    extra_env={},
    notes="ERPNext OAuth is configured via UI: Setup > Integrations > Social Login Key",
)

ODOO_CONFIG = AppSSOConfig(
    app_id="odoo",
    redirect_uri_patterns=[
        "{app_url}/auth_oauth/signin",
    ],
    env_mappings={},
    extra_env={},
    notes="Odoo requires auth_oauth module. Configure via Settings > General Settings > OAuth",
)

KIMAI_CONFIG = AppSSOConfig(
    app_id="kimai",
    redirect_uri_patterns=[
        "{app_url}/auth/check_oidc",
    ],
    env_mappings={},  # Kimai uses local.yaml config
    extra_env={
        "OIDC_ENABLED": "true",
    },
    notes="Kimai OIDC requires kimai.yaml configuration",
)

CHATWOOT_CONFIG = AppSSOConfig(
    app_id="chatwoot",
    redirect_uri_patterns=[
        "{app_url}/omniauth/openid_connect/callback",
    ],
    env_mappings={
        "OPENID_CONNECT_CLIENT_ID": "OIDC_CLIENT_ID",
        "OPENID_CONNECT_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OPENID_CONNECT_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "OPENID_CONNECT_ENABLED": "true",
        "OPENID_CONNECT_NAME": "WOPR SSO",
    },
)

# =============================================================================
# Media Apps
# =============================================================================

IMMICH_CONFIG = AppSSOConfig(
    app_id="immich",
    redirect_uri_patterns=[
        "{app_url}/auth/login",
        "{app_url}/user-settings",
        "app.immich:/",  # Mobile app
    ],
    required_scopes=["openid", "email", "profile"],
    env_mappings={
        "IMMICH_OAUTH_CLIENT_ID": "OIDC_CLIENT_ID",
        "IMMICH_OAUTH_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "IMMICH_OAUTH_ISSUER_URL": "OIDC_ISSUER",
    },
    extra_env={
        "IMMICH_OAUTH_ENABLED": "true",
        "IMMICH_OAUTH_AUTO_REGISTER": "true",
        "IMMICH_OAUTH_BUTTON_TEXT": "Login with WOPR",
        "IMMICH_OAUTH_AUTO_LAUNCH": "false",
        "IMMICH_OAUTH_MOBILE_OVERRIDE_ENABLED": "true",
    },
)

JELLYFIN_CONFIG = AppSSOConfig(
    app_id="jellyfin",
    redirect_uri_patterns=[
        "{app_url}/sso/OID/redirect/authentik",
    ],
    env_mappings={},
    extra_env={},
    notes="Jellyfin requires SSO plugin. Install via Plugins > Catalog > SSO Authentication",
)

AUDIOBOOKSHELF_CONFIG = AppSSOConfig(
    app_id="audiobookshelf",
    redirect_uri_patterns=[
        "{app_url}/auth/openid/callback",
        "{app_url}/auth/openid/mobile-redirect",
    ],
    env_mappings={},  # Config via UI
    extra_env={},
    notes="Audiobookshelf OIDC configured via Settings > Authentication",
)

NAVIDROME_CONFIG = AppSSOConfig(
    app_id="navidrome",
    redirect_uri_patterns=[],  # Uses proxy auth
    extra_env={
        "ND_REVERSEPROXYWHITELIST": "0.0.0.0/0",
        "ND_REVERSEPROXYUSERHEADER": "X-Authentik-Username",
    },
    notes="Navidrome uses reverse proxy authentication headers from Authentik",
)

PHOTOPRISM_CONFIG = AppSSOConfig(
    app_id="photoprism",
    redirect_uri_patterns=[
        "{app_url}/api/v1/oauth/callback",
    ],
    env_mappings={
        "PHOTOPRISM_OIDC_CLIENT": "OIDC_CLIENT_ID",
        "PHOTOPRISM_OIDC_SECRET": "OIDC_CLIENT_SECRET",
        "PHOTOPRISM_OIDC_URI": "OIDC_ISSUER",
    },
    extra_env={
        "PHOTOPRISM_OIDC_ENABLED": "true",
        "PHOTOPRISM_OIDC_PROVIDER": "WOPR",
        "PHOTOPRISM_OIDC_REGISTER": "true",
        "PHOTOPRISM_DISABLE_OIDC": "false",
    },
)

# =============================================================================
# Analytics Apps
# =============================================================================

GRAFANA_CONFIG = AppSSOConfig(
    app_id="grafana",
    redirect_uri_patterns=[
        "{app_url}/login/generic_oauth",
    ],
    required_scopes=["openid", "email", "profile", "groups"],
    env_mappings={
        "GF_AUTH_GENERIC_OAUTH_CLIENT_ID": "OIDC_CLIENT_ID",
        "GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "GF_AUTH_GENERIC_OAUTH_AUTH_URL": "OIDC_AUTH_URL",
        "GF_AUTH_GENERIC_OAUTH_TOKEN_URL": "OIDC_TOKEN_URL",
        "GF_AUTH_GENERIC_OAUTH_API_URL": "OIDC_USERINFO_URL",
    },
    extra_env={
        "GF_AUTH_GENERIC_OAUTH_ENABLED": "true",
        "GF_AUTH_GENERIC_OAUTH_NAME": "WOPR SSO",
        "GF_AUTH_GENERIC_OAUTH_SCOPES": "openid email profile groups",
        "GF_AUTH_GENERIC_OAUTH_EMAIL_ATTRIBUTE_PATH": "email",
        "GF_AUTH_GENERIC_OAUTH_LOGIN_ATTRIBUTE_PATH": "preferred_username",
        "GF_AUTH_GENERIC_OAUTH_NAME_ATTRIBUTE_PATH": "name",
        "GF_AUTH_GENERIC_OAUTH_GROUPS_ATTRIBUTE_PATH": "groups",
        "GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH": "contains(groups[*], 'grafana-admins') && 'Admin' || contains(groups[*], 'grafana-editors') && 'Editor' || 'Viewer'",
        "GF_AUTH_GENERIC_OAUTH_ALLOW_SIGN_UP": "true",
        "GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN": "false",
        "GF_AUTH_SIGNOUT_REDIRECT_URL": "{authentik_url}/application/o/{app_slug}/end-session/",
    },
)

UPTIME_KUMA_CONFIG = AppSSOConfig(
    app_id="uptime-kuma",
    redirect_uri_patterns=[
        "{app_url}/callback",
    ],
    env_mappings={},  # Config via UI
    extra_env={},
    notes="Uptime Kuma OIDC configured via Settings > Security",
)

PLAUSIBLE_CONFIG = AppSSOConfig(
    app_id="plausible",
    redirect_uri_patterns=[],  # Uses proxy auth
    extra_env={
        "DISABLE_REGISTRATION": "true",
    },
    notes="Plausible uses Authentik proxy authentication",
)

UMAMI_CONFIG = AppSSOConfig(
    app_id="umami",
    redirect_uri_patterns=[],  # Uses proxy auth
    extra_env={},
    notes="Umami uses Authentik proxy authentication",
)


# =============================================================================
# Creator Apps
# =============================================================================

GHOST_CONFIG = AppSSOConfig(
    app_id="ghost",
    redirect_uri_patterns=[],  # Uses staff SSO via magic links
    extra_env={},
    notes="Ghost uses magic link authentication. Staff SSO available in Ghost(Pro) only.",
)

MASTODON_CONFIG = AppSSOConfig(
    app_id="mastodon",
    redirect_uri_patterns=[
        "{app_url}/auth/auth/openid_connect/callback",
    ],
    env_mappings={
        "OIDC_CLIENT_ID": "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET": "OIDC_CLIENT_SECRET",
        "OIDC_ISSUER": "OIDC_ISSUER",
    },
    extra_env={
        "OIDC_ENABLED": "true",
        "OIDC_DISPLAY_NAME": "WOPR SSO",
        "OIDC_DISCOVERY": "true",
        "OIDC_SCOPE": "openid,profile,email",
        "OIDC_UID_FIELD": "preferred_username",
        "OIDC_REDIRECT_URI": "{app_url}/auth/auth/openid_connect/callback",
        "OIDC_SECURITY_ASSUME_EMAIL_IS_VERIFIED": "true",
    },
)

PEERTUBE_CONFIG = AppSSOConfig(
    app_id="peertube",
    redirect_uri_patterns=[
        "{app_url}/plugins/auth-openid-connect/router/code-cb",
    ],
    env_mappings={},  # Uses plugin config
    extra_env={},
    notes="PeerTube requires auth-openid-connect plugin. Configure via Admin > Plugins",
)


# =============================================================================
# Config Registry
# =============================================================================

APP_SSO_CONFIGS: dict[str, AppSSOConfig] = {
    # Productivity
    "nextcloud": NEXTCLOUD_CONFIG,
    "outline": OUTLINE_CONFIG,
    "bookstack": BOOKSTACK_CONFIG,
    "paperless-ngx": PAPERLESS_CONFIG,
    "hedgedoc": HEDGEDOC_CONFIG,
    "affine": AFFINE_CONFIG,
    "calcom": CALCOM_CONFIG,

    # Communication
    "matrix-synapse": MATRIX_SYNAPSE_CONFIG,
    "mattermost": MATTERMOST_CONFIG,
    "jitsi": JITSI_CONFIG,
    "element": ELEMENT_CONFIG,

    # Developer
    "forgejo": FORGEJO_CONFIG,
    "portainer": PORTAINER_CONFIG,
    "code-server": CODE_SERVER_CONFIG,
    "n8n": N8N_CONFIG,
    "nocodb": NOCODB_CONFIG,
    "plane": PLANE_CONFIG,

    # Security
    "vaultwarden": VAULTWARDEN_CONFIG,
    "netbird": NETBIRD_CONFIG,

    # Business
    "invoiceninja": INVOICENINJA_CONFIG,
    "erpnext": ERPNEXT_CONFIG,
    "odoo": ODOO_CONFIG,
    "kimai": KIMAI_CONFIG,
    "chatwoot": CHATWOOT_CONFIG,

    # Media
    "immich": IMMICH_CONFIG,
    "jellyfin": JELLYFIN_CONFIG,
    "audiobookshelf": AUDIOBOOKSHELF_CONFIG,
    "navidrome": NAVIDROME_CONFIG,
    "photoprism": PHOTOPRISM_CONFIG,

    # Analytics
    "grafana": GRAFANA_CONFIG,
    "uptime-kuma": UPTIME_KUMA_CONFIG,
    "plausible": PLAUSIBLE_CONFIG,
    "umami": UMAMI_CONFIG,

    # Creator
    "ghost": GHOST_CONFIG,
    "mastodon": MASTODON_CONFIG,
    "peertube": PEERTUBE_CONFIG,
}


def get_app_sso_config(app_id: str) -> Optional[AppSSOConfig]:
    """Get the SSO configuration for an app"""
    return APP_SSO_CONFIGS.get(app_id)


def resolve_env_template(
    template: str,
    app_url: str,
    authentik_url: str,
    app_slug: str,
    oidc_discovery_url: str,
) -> str:
    """Resolve template variables in environment values"""
    return template.format(
        app_url=app_url,
        authentik_url=authentik_url,
        app_slug=app_slug,
        oidc_discovery_url=oidc_discovery_url,
    )


def generate_app_specific_env(
    app_id: str,
    base_env: dict[str, str],
    app_url: str,
    authentik_url: str,
    app_slug: str,
    oidc_discovery_url: str,
) -> dict[str, str]:
    """
    Generate environment variables with app-specific overrides.

    Takes the base env vars from the provisioner and applies
    app-specific mappings and extras.
    """
    config = get_app_sso_config(app_id)
    if not config:
        return base_env

    result = {}

    # Apply env mappings (rename our standard vars to app-specific names)
    for app_var, our_var in config.env_mappings.items():
        if our_var in base_env:
            result[app_var] = base_env[our_var]

    # Add extra static env vars with template resolution
    for key, value in config.extra_env.items():
        result[key] = resolve_env_template(
            value, app_url, authentik_url, app_slug, oidc_discovery_url
        )

    # Keep any base vars not overridden
    for key, value in base_env.items():
        if key not in result and key not in config.env_mappings.values():
            result[key] = value

    return result
