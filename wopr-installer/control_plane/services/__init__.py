"""
WOPR Control Plane Services

Core services for the WOPR installer:
- authentik_provisioner: Provisions SSO apps in Authentik
- module_deployer: Deploys modules with full SSO integration
- app_sso_configs: App-specific SSO configuration templates
- onboarding: User onboarding and configuration management
"""

from .authentik_provisioner import (
    AuthentikProvisioner,
    AuthentikConfig,
    UserProfile,
    ProvisionedApp,
    ProviderType,
    generate_env_vars,
    generate_client_secret,
)

from .module_deployer import (
    ModuleDeployer,
    DeploymentConfig,
    DeploymentResult,
    deploy_multiple_modules,
)

from .app_sso_configs import (
    AppSSOConfig,
    get_app_sso_config,
    generate_app_specific_env,
    APP_SSO_CONFIGS,
)

from .onboarding import (
    OnboardingState,
    OnboardingWizard,
    UserOnboarding,
    AuthentikOnboarding,
    InfrastructureConfig,
)

__all__ = [
    # Authentik Provisioner
    "AuthentikProvisioner",
    "AuthentikConfig",
    "UserProfile",
    "ProvisionedApp",
    "ProviderType",
    "generate_env_vars",
    "generate_client_secret",

    # Module Deployer
    "ModuleDeployer",
    "DeploymentConfig",
    "DeploymentResult",
    "deploy_multiple_modules",

    # App SSO Configs
    "AppSSOConfig",
    "get_app_sso_config",
    "generate_app_specific_env",
    "APP_SSO_CONFIGS",

    # Onboarding
    "OnboardingState",
    "OnboardingWizard",
    "UserOnboarding",
    "AuthentikOnboarding",
    "InfrastructureConfig",
]
