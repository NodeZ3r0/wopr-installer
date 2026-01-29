"""
WOPR Control Plane Services

Core services for the WOPR installer:
- authentik_provisioner: Provisions SSO apps in Authentik
- module_deployer: Deploys modules with full SSO integration
- app_sso_configs: App-specific SSO configuration templates
- onboarding: User onboarding and configuration management
- cloudflare_dns: DNS record management via Cloudflare
- firewall: Per-provider firewall rule creation
- monitor: Beacon health monitoring

Imports are lazy to avoid broken import chains when individual
modules have unresolved dependencies.
"""


def __getattr__(name):
    """Lazy import to avoid circular/broken import chains."""
    _import_map = {
        # Authentik Provisioner
        "AuthentikProvisioner": ".authentik_provisioner",
        "AuthentikConfig": ".authentik_provisioner",
        "UserProfile": ".authentik_provisioner",
        "ProvisionedApp": ".authentik_provisioner",
        "ProviderType": ".authentik_provisioner",
        "generate_env_vars": ".authentik_provisioner",
        "generate_client_secret": ".authentik_provisioner",
        # Module Deployer
        "ModuleDeployer": ".module_deployer",
        "DeploymentConfig": ".module_deployer",
        "DeploymentResult": ".module_deployer",
        "deploy_multiple_modules": ".module_deployer",
        # App SSO Configs
        "AppSSOConfig": ".app_sso_configs",
        "get_app_sso_config": ".app_sso_configs",
        "generate_app_specific_env": ".app_sso_configs",
        "APP_SSO_CONFIGS": ".app_sso_configs",
        # Onboarding
        "OnboardingState": ".onboarding",
        "OnboardingWizard": ".onboarding",
        "UserOnboarding": ".onboarding",
        "AuthentikOnboarding": ".onboarding",
        "InfrastructureConfig": ".onboarding",
        # Cloudflare DNS
        "CloudflareDNS": ".cloudflare_dns",
        # Firewall
        "FirewallService": ".firewall",
        # Monitor
        "BeaconMonitor": ".monitor",
    }

    if name in _import_map:
        import importlib
        module = importlib.import_module(_import_map[name], package=__name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuthentikProvisioner",
    "AuthentikConfig",
    "UserProfile",
    "ProvisionedApp",
    "ProviderType",
    "generate_env_vars",
    "generate_client_secret",
    "ModuleDeployer",
    "DeploymentConfig",
    "DeploymentResult",
    "deploy_multiple_modules",
    "AppSSOConfig",
    "get_app_sso_config",
    "generate_app_specific_env",
    "APP_SSO_CONFIGS",
    "OnboardingState",
    "OnboardingWizard",
    "UserOnboarding",
    "AuthentikOnboarding",
    "InfrastructureConfig",
    "CloudflareDNS",
    "FirewallService",
    "BeaconMonitor",
]
