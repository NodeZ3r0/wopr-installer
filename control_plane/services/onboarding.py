"""
WOPR Onboarding Service

Captures and stores user configuration during initial setup:
- User profile (username, email, handle, etc.)
- Authentik credentials
- Domain configuration
- Infrastructure preferences

This data is used by the module deployer to provision apps with SSO.
"""

import os
import json
import secrets
import string
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime

from .authentik_provisioner import AuthentikConfig, UserProfile


@dataclass
class InfrastructureConfig:
    """Infrastructure configuration collected during onboarding"""
    domain: str  # Primary domain (e.g., example.com)
    cloudflare_api_token: Optional[str] = None
    cloudflare_zone_id: Optional[str] = None

    # Server settings
    server_ip: Optional[str] = None
    ssh_port: int = 22

    # Docker settings
    docker_network: str = "wopr-network"
    compose_project_prefix: str = "wopr"

    # Storage paths
    data_path: str = "/opt/wopr/data"
    config_path: str = "/opt/wopr/config"
    backup_path: str = "/opt/wopr/backups"


@dataclass
class AuthentikOnboarding:
    """Authentik configuration collected during setup"""
    base_url: str  # https://auth.domain.com
    api_token: str
    admin_password: str  # Initial admin password
    secret_key: str  # Authentik secret key

    # Bootstrap token for first-time setup
    bootstrap_token: Optional[str] = None

    # Default flows
    authorization_flow: str = "default-provider-authorization-implicit-consent"
    authentication_flow: str = "default-authentication-flow"

    def to_authentik_config(self) -> AuthentikConfig:
        return AuthentikConfig(
            base_url=self.base_url,
            api_token=self.api_token,
            default_flow_slug=self.authorization_flow,
        )


@dataclass
class UserOnboarding:
    """User profile information collected during onboarding"""
    username: str
    email: str
    handle: str  # @username format
    display_name: str
    password_hash: Optional[str] = None  # Hashed, never stored plain

    # Optional organization info
    organization: Optional[str] = None
    organization_domain: Optional[str] = None

    # Preferences
    timezone: str = "UTC"
    locale: str = "en-US"

    def to_user_profile(self, domain: str) -> UserProfile:
        return UserProfile(
            username=self.username,
            email=self.email,
            handle=self.handle,
            display_name=self.display_name,
            domain=domain,
            organization=self.organization,
        )


@dataclass
class OnboardingState:
    """Complete onboarding state persisted to disk"""
    user: UserOnboarding
    authentik: AuthentikOnboarding
    infrastructure: InfrastructureConfig

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0.0"

    # Deployment tracking
    deployed_modules: list[str] = field(default_factory=list)

    def save(self, path: Path = None):
        """Save onboarding state to disk"""
        if path is None:
            path = Path("/opt/wopr/config/onboarding.json")
        path.parent.mkdir(parents=True, exist_ok=True)

        self.updated_at = datetime.utcnow().isoformat()
        data = asdict(self)

        # Don't persist sensitive fields
        if "password_hash" in data.get("user", {}):
            del data["user"]["password_hash"]

        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path = None) -> Optional["OnboardingState"]:
        """Load onboarding state from disk"""
        if path is None:
            path = Path("/opt/wopr/config/onboarding.json")

        if not path.exists():
            return None

        data = json.loads(path.read_text())

        return cls(
            user=UserOnboarding(**data["user"]),
            authentik=AuthentikOnboarding(**data["authentik"]),
            infrastructure=InfrastructureConfig(**data["infrastructure"]),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", "1.0.0"),
            deployed_modules=data.get("deployed_modules", []),
        )


# =============================================================================
# Onboarding Flow
# =============================================================================

class OnboardingWizard:
    """
    Interactive onboarding wizard that collects user configuration.

    This is called by the web UI during initial WOPR setup.
    """

    def __init__(self):
        self.state: Optional[OnboardingState] = None

    def generate_secrets(self) -> dict[str, str]:
        """Generate all required secrets for the installation"""
        def gen_secret(length=64):
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        return {
            "authentik_secret_key": gen_secret(64),
            "authentik_bootstrap_token": gen_secret(32),
            "postgres_password": gen_secret(32),
            "redis_password": gen_secret(32),
            "jwt_secret": gen_secret(64),
        }

    async def validate_domain(self, domain: str) -> dict:
        """Validate domain configuration"""
        import httpx

        results = {
            "domain": domain,
            "dns_configured": False,
            "ssl_available": False,
            "errors": [],
        }

        # Check if domain resolves
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.head(f"https://{domain}", timeout=10)
                results["ssl_available"] = True
                results["dns_configured"] = True
        except httpx.ConnectError:
            results["errors"].append(f"Cannot connect to {domain}")
        except Exception as e:
            results["errors"].append(str(e))

        return results

    async def validate_authentik(self, config: AuthentikOnboarding) -> dict:
        """Validate Authentik connection"""
        import httpx

        results = {
            "connected": False,
            "api_token_valid": False,
            "version": None,
            "errors": [],
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config.base_url}/api/v3/admin/version/",
                    headers={"Authorization": f"Bearer {config.api_token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results["connected"] = True
                    results["api_token_valid"] = True
                    results["version"] = data.get("version_current")
                elif resp.status_code == 401:
                    results["errors"].append("Invalid API token")
                else:
                    results["errors"].append(f"API returned {resp.status_code}")
        except Exception as e:
            results["errors"].append(str(e))

        return results

    def create_state(
        self,
        user_data: dict,
        authentik_data: dict,
        infra_data: dict,
    ) -> OnboardingState:
        """Create onboarding state from wizard data"""
        secrets = self.generate_secrets()

        # Build user profile
        user = UserOnboarding(
            username=user_data["username"],
            email=user_data["email"],
            handle=user_data.get("handle", f"@{user_data['username']}"),
            display_name=user_data.get("display_name", user_data["username"]),
            organization=user_data.get("organization"),
            timezone=user_data.get("timezone", "UTC"),
        )

        # Build Authentik config
        domain = infra_data["domain"]
        authentik = AuthentikOnboarding(
            base_url=authentik_data.get("base_url", f"https://auth.{domain}"),
            api_token=authentik_data.get("api_token", ""),
            admin_password=authentik_data.get("admin_password", secrets["authentik_bootstrap_token"][:16]),
            secret_key=secrets["authentik_secret_key"],
            bootstrap_token=secrets["authentik_bootstrap_token"],
        )

        # Build infrastructure config
        infrastructure = InfrastructureConfig(
            domain=domain,
            cloudflare_api_token=infra_data.get("cloudflare_api_token"),
            cloudflare_zone_id=infra_data.get("cloudflare_zone_id"),
            server_ip=infra_data.get("server_ip"),
            data_path=infra_data.get("data_path", "/opt/wopr/data"),
        )

        self.state = OnboardingState(
            user=user,
            authentik=authentik,
            infrastructure=infrastructure,
        )

        return self.state

    def get_deployer_configs(self) -> tuple[AuthentikConfig, UserProfile]:
        """Get configs needed for module deployer"""
        if not self.state:
            raise ValueError("Onboarding not complete")

        return (
            self.state.authentik.to_authentik_config(),
            self.state.user.to_user_profile(self.state.infrastructure.domain),
        )


# =============================================================================
# API Endpoints for Web UI
# =============================================================================

def create_onboarding_api(app):
    """
    Create FastAPI routes for onboarding.

    Call this to add onboarding endpoints to your FastAPI app:
        create_onboarding_api(app)
    """
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
    wizard = OnboardingWizard()

    class UserData(BaseModel):
        username: str
        email: str
        handle: Optional[str] = None
        display_name: Optional[str] = None
        organization: Optional[str] = None
        timezone: str = "UTC"

    class AuthentikData(BaseModel):
        base_url: Optional[str] = None
        api_token: Optional[str] = None
        admin_password: Optional[str] = None

    class InfraData(BaseModel):
        domain: str
        cloudflare_api_token: Optional[str] = None
        cloudflare_zone_id: Optional[str] = None
        server_ip: Optional[str] = None

    class OnboardingRequest(BaseModel):
        user: UserData
        authentik: AuthentikData
        infrastructure: InfraData

    @router.get("/status")
    async def get_status():
        """Check if onboarding is complete"""
        state = OnboardingState.load()
        return {
            "completed": state is not None,
            "domain": state.infrastructure.domain if state else None,
            "user": state.user.username if state else None,
        }

    @router.post("/validate/domain")
    async def validate_domain(domain: str):
        """Validate domain configuration"""
        return await wizard.validate_domain(domain)

    @router.post("/validate/authentik")
    async def validate_authentik(data: AuthentikData):
        """Validate Authentik connection"""
        config = AuthentikOnboarding(
            base_url=data.base_url or "",
            api_token=data.api_token or "",
            admin_password="",
            secret_key="",
        )
        return await wizard.validate_authentik(config)

    @router.post("/complete")
    async def complete_onboarding(data: OnboardingRequest):
        """Complete onboarding and save configuration"""
        try:
            state = wizard.create_state(
                user_data=data.user.model_dump(),
                authentik_data=data.authentik.model_dump(),
                infra_data=data.infrastructure.model_dump(),
            )
            state.save()
            return {"success": True, "message": "Onboarding complete"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/config")
    async def get_config():
        """Get current configuration (for display only)"""
        state = OnboardingState.load()
        if not state:
            raise HTTPException(status_code=404, detail="Onboarding not complete")

        return {
            "user": {
                "username": state.user.username,
                "email": state.user.email,
                "handle": state.user.handle,
                "display_name": state.user.display_name,
            },
            "domain": state.infrastructure.domain,
            "authentik_url": state.authentik.base_url,
            "deployed_modules": state.deployed_modules,
        }

    app.include_router(router)
    return router
