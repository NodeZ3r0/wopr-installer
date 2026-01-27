"""
Module Deployment Orchestrator

Handles the complete one-click installation flow:
1. Pull module configuration from GitHub
2. Provision SSO in user's Authentik
3. Generate and inject credentials
4. Deploy the container stack
5. Configure DNS/reverse proxy
"""

import os
import asyncio
import tempfile
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from .authentik_provisioner import (
    AuthentikProvisioner,
    AuthentikConfig,
    UserProfile,
    ProvisionedApp,
    generate_env_vars,
)
from .app_sso_configs import (
    get_app_sso_config,
    generate_app_specific_env,
)
from ..modules.registry import Module, ModuleRegistry, SSOType


@dataclass
class DeploymentConfig:
    """Configuration for module deployment"""
    install_base_path: str = "/opt/wopr/modules"
    github_org: str = "NodeZ3r0"
    compose_project_prefix: str = "wopr"
    network_name: str = "wopr-network"
    caddy_config_path: str = "/opt/wopr/caddy/sites"


@dataclass
class DeploymentResult:
    """Result of a module deployment"""
    success: bool
    module_id: str
    app_url: str
    provisioned_app: Optional[ProvisionedApp]
    error: Optional[str] = None
    deployed_at: datetime = None

    def __post_init__(self):
        if self.deployed_at is None:
            self.deployed_at = datetime.utcnow()


class ModuleDeployer:
    """
    Orchestrates the complete deployment of a WOPR module.

    Usage:
        deployer = ModuleDeployer(
            authentik_config=authentik_config,
            user_profile=user_profile,
        )

        result = await deployer.deploy_module("nextcloud")
    """

    def __init__(
        self,
        authentik_config: AuthentikConfig,
        user_profile: UserProfile,
        deployment_config: DeploymentConfig = None,
    ):
        self.authentik_config = authentik_config
        self.user_profile = user_profile
        self.config = deployment_config or DeploymentConfig()
        self.registry = ModuleRegistry()

    async def deploy_module(
        self,
        module_id: str,
        custom_env: dict[str, str] = None,
    ) -> DeploymentResult:
        """
        Deploy a module with full SSO integration.

        Args:
            module_id: The module identifier (e.g., "nextcloud")
            custom_env: Additional environment variables to inject

        Returns:
            DeploymentResult with deployment status and details
        """
        try:
            # 1. Get module definition
            module = self.registry.get_module(module_id)
            if not module:
                return DeploymentResult(
                    success=False,
                    module_id=module_id,
                    app_url="",
                    provisioned_app=None,
                    error=f"Module '{module_id}' not found in registry",
                )

            # 2. Clone module repo
            module_path = await self._clone_module_repo(module)

            # 3. Provision SSO in Authentik
            async with AuthentikProvisioner(
                self.authentik_config,
                self.user_profile
            ) as provisioner:
                provisioned_app = await provisioner.provision_from_module(module)

            # 4. Generate environment variables
            base_env = generate_env_vars(
                provisioned_app,
                self.authentik_config,
                self.user_profile,
            )

            # Apply app-specific SSO configurations
            oidc_discovery_url = f"{self.authentik_config.base_url}/application/o/{module_id}/.well-known/openid-configuration"
            env_vars = generate_app_specific_env(
                app_id=module_id,
                base_env=base_env,
                app_url=provisioned_app.external_host,
                authentik_url=self.authentik_config.base_url,
                app_slug=module_id,
                oidc_discovery_url=oidc_discovery_url,
            )

            # Add any custom env vars
            if custom_env:
                env_vars.update(custom_env)

            # Add module-specific secrets
            env_vars.update(self._generate_module_secrets(module))

            # 4b. Run post-deploy commands if any
            app_config = get_app_sso_config(module_id)
            post_deploy_cmds = app_config.post_deploy_commands if app_config else []

            # 5. Write .env file
            await self._write_env_file(module_path, env_vars)

            # 6. Update Caddy config for reverse proxy
            await self._configure_caddy(module, provisioned_app)

            # 7. Deploy with Docker Compose
            await self._deploy_compose(module_path, module)

            # 8. Reload Caddy to pick up new config
            await self._reload_caddy()

            # 9. Run post-deploy commands (e.g., enable OIDC plugins)
            if post_deploy_cmds:
                await self._run_post_deploy_commands(post_deploy_cmds)

            # 10. Update onboarding state with deployed module
            await self._update_deployed_modules(module_id)

            return DeploymentResult(
                success=True,
                module_id=module_id,
                app_url=provisioned_app.external_host,
                provisioned_app=provisioned_app,
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                module_id=module_id,
                app_url="",
                provisioned_app=None,
                error=str(e),
            )

    async def _clone_module_repo(self, module: Module) -> Path:
        """Clone the module repository from GitHub"""
        repo_name = f"wopr-{module.id}"
        repo_url = f"https://github.com/{self.config.github_org}/{repo_name}.git"
        install_path = Path(self.config.install_base_path) / module.id

        # Remove existing installation if present
        if install_path.exists():
            shutil.rmtree(install_path)

        # Clone the repo
        install_path.parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", repo_url, str(install_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to clone {repo_url}: {stderr.decode()}")

        return install_path

    def _generate_module_secrets(self, module: Module) -> dict[str, str]:
        """Generate module-specific secrets (DB passwords, etc.)"""
        import secrets
        import string

        def gen_password(length=32):
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        env = {
            # Database credentials
            "DB_PASSWORD": gen_password(),
            "DB_USER": module.id.replace("-", "_"),
            "DB_NAME": module.id.replace("-", "_"),

            # Redis password
            "REDIS_PASSWORD": gen_password(),

            # Generic secret key for apps that need it
            "SECRET_KEY": gen_password(64),
            "APP_SECRET": gen_password(64),

            # JWT signing key
            "JWT_SECRET": gen_password(64),
        }

        return env

    async def _write_env_file(self, module_path: Path, env_vars: dict[str, str]):
        """Write the .env file for the module"""
        env_file = module_path / ".env"

        lines = [
            "# Auto-generated by WOPR Installer",
            f"# Generated at: {datetime.utcnow().isoformat()}",
            "",
        ]

        for key, value in sorted(env_vars.items()):
            # Escape special characters in values
            escaped_value = value.replace('"', '\\"')
            lines.append(f'{key}="{escaped_value}"')

        env_file.write_text("\n".join(lines))

    async def _configure_caddy(self, module: Module, app: ProvisionedApp):
        """Generate and write Caddy reverse proxy configuration"""
        caddy_dir = Path(self.config.caddy_config_path)
        caddy_dir.mkdir(parents=True, exist_ok=True)

        subdomain = module.subdomain or module.id
        domain = f"{subdomain}.{self.user_profile.domain}"

        if module.sso_type == SSOType.OIDC:
            # OIDC apps handle auth themselves, just reverse proxy
            config = f"""{domain} {{
    reverse_proxy {module.id}:{module.default_port}

    tls {{
        dns cloudflare {{env.CF_API_TOKEN}}
    }}

    header {{
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
    }}

    log {{
        output file /var/log/caddy/{module.id}.log
        format json
    }}
}}
"""
        else:
            # Proxy auth - use Authentik forward auth
            config = f"""{domain} {{
    forward_auth authentik-server:9000 {{
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
        trusted_proxies private_ranges
    }}

    reverse_proxy {module.id}:{module.default_port}

    tls {{
        dns cloudflare {{env.CF_API_TOKEN}}
    }}

    header {{
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
    }}

    log {{
        output file /var/log/caddy/{module.id}.log
        format json
    }}
}}
"""

        config_file = caddy_dir / f"{module.id}.caddy"
        config_file.write_text(config)

    async def _deploy_compose(self, module_path: Path, module: Module):
        """Deploy the module using Docker Compose"""
        project_name = f"{self.config.compose_project_prefix}-{module.id}"

        proc = await asyncio.create_subprocess_exec(
            "docker", "compose",
            "-p", project_name,
            "-f", str(module_path / "docker-compose.yml"),
            "up", "-d", "--pull", "always",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(module_path),
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Docker Compose failed: {stderr.decode()}")

    async def _reload_caddy(self):
        """Reload Caddy to pick up new site configuration"""
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "caddy",
            "caddy", "reload",
            "--config", "/etc/caddy/Caddyfile",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        # Don't fail if reload fails - might be first deployment

    async def _run_post_deploy_commands(self, commands: list[str]):
        """Run post-deployment commands (e.g., enabling plugins)"""
        for cmd in commands:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                # Log but don't fail - post-deploy commands are best-effort
                print(f"Post-deploy command failed: {cmd}")
                print(f"Error: {stderr.decode()}")

    async def _update_deployed_modules(self, module_id: str):
        """Update the onboarding state with newly deployed module"""
        try:
            from .onboarding import OnboardingState
            state = OnboardingState.load()
            if state and module_id not in state.deployed_modules:
                state.deployed_modules.append(module_id)
                state.save()
        except Exception:
            pass  # Non-critical, don't fail deployment

    async def undeploy_module(self, module_id: str) -> bool:
        """
        Remove a deployed module.

        - Stops and removes containers
        - Removes Caddy config
        - Deprovisions from Authentik
        - Removes module files
        """
        try:
            module = self.registry.get_module(module_id)
            module_path = Path(self.config.install_base_path) / module_id

            # Stop containers
            if module_path.exists():
                project_name = f"{self.config.compose_project_prefix}-{module_id}"
                proc = await asyncio.create_subprocess_exec(
                    "docker", "compose",
                    "-p", project_name,
                    "-f", str(module_path / "docker-compose.yml"),
                    "down", "-v",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

            # Remove Caddy config
            caddy_file = Path(self.config.caddy_config_path) / f"{module_id}.caddy"
            if caddy_file.exists():
                caddy_file.unlink()
            await self._reload_caddy()

            # Deprovision from Authentik
            async with AuthentikProvisioner(
                self.authentik_config,
                self.user_profile
            ) as provisioner:
                await provisioner.deprovision_app(module_id)

            # Remove files
            if module_path.exists():
                shutil.rmtree(module_path)

            return True

        except Exception as e:
            print(f"Error undeploying {module_id}: {e}")
            return False


# =============================================================================
# Batch Deployment
# =============================================================================

async def deploy_multiple_modules(
    module_ids: list[str],
    authentik_config: AuthentikConfig,
    user_profile: UserProfile,
    deployment_config: DeploymentConfig = None,
    max_concurrent: int = 3,
) -> list[DeploymentResult]:
    """
    Deploy multiple modules concurrently.

    Args:
        module_ids: List of module IDs to deploy
        authentik_config: Authentik configuration
        user_profile: User profile from onboarding
        deployment_config: Optional deployment configuration
        max_concurrent: Maximum concurrent deployments

    Returns:
        List of DeploymentResults
    """
    deployer = ModuleDeployer(
        authentik_config,
        user_profile,
        deployment_config,
    )

    semaphore = asyncio.Semaphore(max_concurrent)

    async def deploy_with_limit(module_id: str) -> DeploymentResult:
        async with semaphore:
            return await deployer.deploy_module(module_id)

    tasks = [deploy_with_limit(mid) for mid in module_ids]
    return await asyncio.gather(*tasks)


# =============================================================================
# CLI Interface
# =============================================================================

async def main():
    """CLI for testing module deployment"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Deploy WOPR modules")
    parser.add_argument("action", choices=["deploy", "undeploy", "list"])
    parser.add_argument("--module", "-m", help="Module ID to deploy/undeploy")
    parser.add_argument("--config", "-c", help="Path to config JSON file")
    args = parser.parse_args()

    if args.action == "list":
        registry = ModuleRegistry()
        for module in registry.get_all_modules():
            print(f"{module.id}: {module.name} ({module.sso_type.value})")
        return

    if not args.config:
        print("Error: --config required for deploy/undeploy")
        return

    with open(args.config) as f:
        config = json.load(f)

    authentik_config = AuthentikConfig(
        base_url=config["authentik"]["base_url"],
        api_token=config["authentik"]["api_token"],
    )

    user_profile = UserProfile(
        username=config["user"]["username"],
        email=config["user"]["email"],
        handle=config["user"]["handle"],
        display_name=config["user"]["display_name"],
        domain=config["user"]["domain"],
    )

    deployer = ModuleDeployer(authentik_config, user_profile)

    if args.action == "deploy":
        result = await deployer.deploy_module(args.module)
        if result.success:
            print(f"✓ Deployed {args.module} at {result.app_url}")
        else:
            print(f"✗ Failed: {result.error}")

    elif args.action == "undeploy":
        success = await deployer.undeploy_module(args.module)
        if success:
            print(f"✓ Undeployed {args.module}")
        else:
            print(f"✗ Failed to undeploy {args.module}")


if __name__ == "__main__":
    asyncio.run(main())
