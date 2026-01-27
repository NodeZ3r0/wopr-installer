"""
Authentik Provisioning Service

Automatically provisions SSO applications in user's Authentik instance
when modules are installed via the one-click installer.
"""

import secrets
import string
import httpx
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ProviderType(Enum):
    OAUTH2 = "oauth2"
    PROXY = "proxy"
    SAML = "saml"
    LDAP = "ldap"


@dataclass
class AuthentikConfig:
    """User's Authentik instance configuration from onboarding"""
    base_url: str  # e.g., https://auth.userdomain.com
    api_token: str
    default_flow_slug: str = "default-provider-authorization-implicit-consent"
    certificate_id: Optional[str] = None


@dataclass
class UserProfile:
    """User profile data collected during onboarding"""
    username: str
    email: str
    handle: str  # e.g., @username
    display_name: str
    domain: str  # User's base domain
    organization: Optional[str] = None


@dataclass
class ProvisionedApp:
    """Result of provisioning an app in Authentik"""
    app_slug: str
    app_name: str
    provider_id: int
    application_id: int
    client_id: str
    client_secret: Optional[str]  # None for proxy providers
    provider_type: ProviderType
    external_host: str  # The URL users access


def generate_client_secret(length: int = 64) -> str:
    """Generate a cryptographically secure client secret"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_client_id(app_slug: str) -> str:
    """Generate a client ID based on app slug + random suffix"""
    suffix = secrets.token_hex(8)
    return f"{app_slug}-{suffix}"


class AuthentikProvisioner:
    """
    Provisions SSO applications in a user's Authentik instance.

    Usage:
        config = AuthentikConfig(
            base_url="https://auth.example.com",
            api_token="ak-xxxx"
        )
        user = UserProfile(
            username="john",
            email="john@example.com",
            ...
        )
        provisioner = AuthentikProvisioner(config, user)

        # Provision an OIDC app
        result = await provisioner.provision_oauth2_app(
            app_slug="nextcloud",
            app_name="Nextcloud",
            subdomain="cloud",
            redirect_uris=["https://cloud.example.com/apps/oidc/callback"]
        )
    """

    def __init__(self, config: AuthentikConfig, user: UserProfile):
        self.config = config
        self.user = user
        self.client = httpx.AsyncClient(
            base_url=f"{config.base_url}/api/v3",
            headers={
                "Authorization": f"Bearer {config.api_token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # =========================================================================
    # Core API Methods
    # =========================================================================

    async def _get_authorization_flow(self) -> dict:
        """Get the default authorization flow"""
        resp = await self.client.get(
            f"/flows/instances/{self.config.default_flow_slug}/"
        )
        resp.raise_for_status()
        return resp.json()

    async def _get_or_create_property_mappings(self, provider_type: ProviderType) -> list[str]:
        """Get default property mappings for provider type"""
        if provider_type == ProviderType.OAUTH2:
            # Get all OAuth2 scope mappings
            resp = await self.client.get(
                "/propertymappings/scope/",
                params={"managed__isnull": False}
            )
            resp.raise_for_status()
            data = resp.json()
            # Return IDs of default OIDC scopes
            default_scopes = ["openid", "email", "profile"]
            return [
                m["pk"] for m in data.get("results", [])
                if any(scope in m.get("scope_name", "") for scope in default_scopes)
            ]
        return []

    async def _create_provider(
        self,
        name: str,
        provider_type: ProviderType,
        **kwargs
    ) -> dict:
        """Create a provider in Authentik"""

        if provider_type == ProviderType.OAUTH2:
            endpoint = "/providers/oauth2/"
            flow = await self._get_authorization_flow()
            property_mappings = await self._get_or_create_property_mappings(provider_type)

            payload = {
                "name": name,
                "authorization_flow": flow["pk"],
                "client_type": "confidential",
                "client_id": kwargs.get("client_id", generate_client_id(name.lower())),
                "client_secret": kwargs.get("client_secret", generate_client_secret()),
                "redirect_uris": kwargs.get("redirect_uris", []),
                "property_mappings": property_mappings,
                "access_token_validity": "hours=1",
                "refresh_token_validity": "days=30",
                "include_claims_in_id_token": True,
                "issuer_mode": "per_provider",
                "sub_mode": "user_email",
            }

        elif provider_type == ProviderType.PROXY:
            endpoint = "/providers/proxy/"
            flow = await self._get_authorization_flow()

            payload = {
                "name": name,
                "authorization_flow": flow["pk"],
                "external_host": kwargs.get("external_host"),
                "internal_host": kwargs.get("internal_host"),
                "mode": "forward_single",  # Forward auth single app mode
                "access_token_validity": "hours=24",
                "intercept_header_auth": True,
                "basic_auth_enabled": False,
            }

            # Add certificate if available (for secure cookies)
            if self.config.certificate_id:
                payload["certificate"] = self.config.certificate_id
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

        resp = await self.client.post(endpoint, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _create_application(
        self,
        name: str,
        slug: str,
        provider_id: int,
        **kwargs
    ) -> dict:
        """Create an application in Authentik"""
        payload = {
            "name": name,
            "slug": slug,
            "provider": provider_id,
            "meta_launch_url": kwargs.get("launch_url", ""),
            "meta_description": kwargs.get("description", ""),
            "policy_engine_mode": "any",
            "open_in_new_tab": True,
        }

        # Add icon if provided
        if kwargs.get("icon"):
            payload["meta_icon"] = kwargs["icon"]

        resp = await self.client.post("/core/applications/", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _create_group(self, name: str, users: list[str] = None) -> dict:
        """Create a group for app access control"""
        payload = {
            "name": name,
            "is_superuser": False,
        }
        if users:
            payload["users"] = users

        resp = await self.client.post("/core/groups/", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _create_policy_binding(
        self,
        app_id: int,
        group_id: str,
        order: int = 0
    ) -> dict:
        """Bind a group to an application for access control"""
        payload = {
            "target": app_id,
            "group": group_id,
            "order": order,
            "enabled": True,
            "negate": False,
            "timeout": 30,
        }
        resp = await self.client.post("/policies/bindings/", json=payload)
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # High-Level Provisioning Methods
    # =========================================================================

    async def provision_oauth2_app(
        self,
        app_slug: str,
        app_name: str,
        subdomain: str,
        redirect_uris: list[str] = None,
        description: str = "",
        icon: str = None,
        create_group: bool = True,
    ) -> ProvisionedApp:
        """
        Provision an OAuth2/OIDC application.

        Args:
            app_slug: Unique identifier (e.g., "nextcloud")
            app_name: Display name (e.g., "Nextcloud")
            subdomain: Subdomain to use (e.g., "cloud" -> cloud.userdomain.com)
            redirect_uris: OAuth redirect URIs (auto-generated if not provided)
            description: App description
            icon: URL to app icon
            create_group: Whether to create an access control group

        Returns:
            ProvisionedApp with credentials to inject into the module
        """
        external_host = f"https://{subdomain}.{self.user.domain}"

        # Generate redirect URIs if not provided
        if not redirect_uris:
            redirect_uris = [
                f"{external_host}/oauth/callback",
                f"{external_host}/auth/callback",
                f"{external_host}/api/auth/callback/authentik",
                f"{external_host}/login/oauth2/code/authentik",
                f"{external_host}/apps/oidc/callback",  # Nextcloud specific
                f"{external_host}/auth/oidc/callback",
            ]

        # Generate credentials
        client_id = generate_client_id(app_slug)
        client_secret = generate_client_secret()

        # Create provider
        provider = await self._create_provider(
            name=f"{app_name} Provider",
            provider_type=ProviderType.OAUTH2,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=redirect_uris,
        )

        # Create application
        application = await self._create_application(
            name=app_name,
            slug=app_slug,
            provider_id=provider["pk"],
            launch_url=external_host,
            description=description,
            icon=icon,
        )

        # Create access group if requested
        if create_group:
            group = await self._create_group(f"{app_name} Users")
            await self._create_policy_binding(application["pk"], group["pk"])

        return ProvisionedApp(
            app_slug=app_slug,
            app_name=app_name,
            provider_id=provider["pk"],
            application_id=application["pk"],
            client_id=client_id,
            client_secret=client_secret,
            provider_type=ProviderType.OAUTH2,
            external_host=external_host,
        )

    async def provision_proxy_app(
        self,
        app_slug: str,
        app_name: str,
        subdomain: str,
        internal_port: int,
        internal_host: str = None,
        description: str = "",
        icon: str = None,
        create_group: bool = True,
    ) -> ProvisionedApp:
        """
        Provision a Proxy authentication application.

        Used for apps that don't support OIDC natively - Authentik handles
        auth via forward auth and passes headers to the backend.

        Args:
            app_slug: Unique identifier (e.g., "portainer")
            app_name: Display name (e.g., "Portainer")
            subdomain: Subdomain to use
            internal_port: The port the app runs on internally
            internal_host: Internal hostname (defaults to app_slug container name)
            description: App description
            icon: URL to app icon
            create_group: Whether to create an access control group

        Returns:
            ProvisionedApp (client_secret will be None for proxy apps)
        """
        external_host = f"https://{subdomain}.{self.user.domain}"

        if not internal_host:
            internal_host = f"http://{app_slug}:{internal_port}"

        # Create provider
        provider = await self._create_provider(
            name=f"{app_name} Proxy Provider",
            provider_type=ProviderType.PROXY,
            external_host=external_host,
            internal_host=internal_host,
        )

        # Create application
        application = await self._create_application(
            name=app_name,
            slug=app_slug,
            provider_id=provider["pk"],
            launch_url=external_host,
            description=description,
            icon=icon,
        )

        # Create access group if requested
        if create_group:
            group = await self._create_group(f"{app_name} Users")
            await self._create_policy_binding(application["pk"], group["pk"])

        return ProvisionedApp(
            app_slug=app_slug,
            app_name=app_name,
            provider_id=provider["pk"],
            application_id=application["pk"],
            client_id=f"{app_slug}-proxy",
            client_secret=None,  # Proxy apps don't use client secrets
            provider_type=ProviderType.PROXY,
            external_host=external_host,
        )

    async def provision_from_module(
        self,
        module: "Module",  # From registry
    ) -> ProvisionedApp:
        """
        Provision an app from a module definition.

        Automatically determines whether to use OIDC or Proxy based on
        the module's sso_type field.
        """
        from ..modules.registry import SSOType

        subdomain = module.subdomain or module.id

        if module.sso_type == SSOType.OIDC:
            return await self.provision_oauth2_app(
                app_slug=module.id,
                app_name=module.name,
                subdomain=subdomain,
                description=module.description,
            )
        elif module.sso_type in (SSOType.PROXY, SSOType.NONE):
            # Even apps with "NONE" get proxy auth for security
            return await self.provision_proxy_app(
                app_slug=module.id,
                app_name=module.name,
                subdomain=subdomain,
                internal_port=module.default_port,
                description=module.description,
            )
        else:
            # SAML, LDAP, OAuth2 - fall back to proxy for now
            return await self.provision_proxy_app(
                app_slug=module.id,
                app_name=module.name,
                subdomain=subdomain,
                internal_port=module.default_port,
                description=module.description,
            )

    # =========================================================================
    # Cleanup Methods
    # =========================================================================

    async def deprovision_app(self, app_slug: str) -> bool:
        """
        Remove an application and its provider from Authentik.

        Returns True if successfully removed, False if not found.
        """
        # Get application
        resp = await self.client.get(f"/core/applications/{app_slug}/")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        app = resp.json()

        provider_id = app.get("provider")

        # Delete application first
        resp = await self.client.delete(f"/core/applications/{app_slug}/")
        resp.raise_for_status()

        # Delete provider if exists
        if provider_id:
            # Try OAuth2 first, then Proxy
            for endpoint in ["/providers/oauth2/", "/providers/proxy/"]:
                resp = await self.client.delete(f"{endpoint}{provider_id}/")
                if resp.status_code != 404:
                    break

        return True


# =============================================================================
# Environment Variable Generator
# =============================================================================

def generate_env_vars(
    provisioned_app: ProvisionedApp,
    authentik_config: AuthentikConfig,
    user: UserProfile,
) -> dict[str, str]:
    """
    Generate environment variables to inject into a module's docker-compose.

    These variables enable the app to authenticate with Authentik.
    """
    env = {
        # Core OIDC/OAuth2 settings
        "AUTHENTIK_HOST": authentik_config.base_url,
        "OIDC_ISSUER": f"{authentik_config.base_url}/application/o/{provisioned_app.app_slug}/",
        "OIDC_CLIENT_ID": provisioned_app.client_id,
        "OIDC_DISCOVERY_URL": f"{authentik_config.base_url}/application/o/{provisioned_app.app_slug}/.well-known/openid-configuration",

        # User info
        "ADMIN_USER": user.username,
        "ADMIN_EMAIL": user.email,
        "ADMIN_HANDLE": user.handle,
        "ADMIN_DISPLAY_NAME": user.display_name,
        "USER_DOMAIN": user.domain,

        # App URLs
        "APP_URL": provisioned_app.external_host,
        "APP_DOMAIN": provisioned_app.external_host.replace("https://", ""),
    }

    # Add client secret for OIDC apps
    if provisioned_app.client_secret:
        env["OIDC_CLIENT_SECRET"] = provisioned_app.client_secret

    # Add organization if available
    if user.organization:
        env["ORGANIZATION"] = user.organization

    return env


def generate_caddy_forward_auth_snippet(
    authentik_host: str,
    app_slug: str,
) -> str:
    """
    Generate Caddy forward_auth configuration snippet.

    Used for apps that need proxy authentication through Authentik.
    """
    return f"""
    forward_auth authentik-server:9000 {{
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
        trusted_proxies private_ranges
    }}
"""
