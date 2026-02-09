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
        # Cloudflare Registrar
        "CloudflareRegistrar": ".cloudflare_registrar",
        "DomainAvailability": ".cloudflare_registrar",
        "DomainPricing": ".cloudflare_registrar",
        "DomainRegistrationRequest": ".cloudflare_registrar",
        "RegisteredDomain": ".cloudflare_registrar",
        "DomainStatus": ".cloudflare_registrar",
        "check_domain_availability": ".cloudflare_registrar",
        "search_domains": ".cloudflare_registrar",
        "get_tld_pricing": ".cloudflare_registrar",
        # Namecheap Registrar
        "NamecheapRegistrar": ".namecheap_registrar",
        "NamecheapDomainAvailability": ".namecheap_registrar",
        "NamecheapDomainPricing": ".namecheap_registrar",
        "NamecheapRegistrationRequest": ".namecheap_registrar",
        "NamecheapRegisteredDomain": ".namecheap_registrar",
        "NamecheapDomainStatus": ".namecheap_registrar",
        "check_namecheap_availability": ".namecheap_registrar",
        "search_namecheap_domains": ".namecheap_registrar",
        "get_namecheap_tld_pricing": ".namecheap_registrar",
        # Unified Domain Registrar
        "DomainRegistrar": ".domain_registrar",
        "RegistrarName": ".domain_registrar",
        "DomainAvailabilityStatus": ".domain_registrar",
        "RegistrarPricing": ".domain_registrar",
        "DomainSearchResult": ".domain_registrar",
        "MultiRegistrarSearchResponse": ".domain_registrar",
        "DomainRegistrationRequest": ".domain_registrar",
        "RegisteredDomainResponse": ".domain_registrar",
        "search_domains_multi_registrar": ".domain_registrar",
        "register_domain_multi_registrar": ".domain_registrar",
        "get_all_tld_pricing_comparison": ".domain_registrar",
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
    "CloudflareRegistrar",
    "DomainAvailability",
    "DomainPricing",
    "DomainRegistrationRequest",
    "RegisteredDomain",
    "DomainStatus",
    "check_domain_availability",
    "search_domains",
    "get_tld_pricing",
    # Namecheap Registrar
    "NamecheapRegistrar",
    "NamecheapDomainAvailability",
    "NamecheapDomainPricing",
    "NamecheapRegistrationRequest",
    "NamecheapRegisteredDomain",
    "NamecheapDomainStatus",
    "check_namecheap_availability",
    "search_namecheap_domains",
    "get_namecheap_tld_pricing",
    # Unified Domain Registrar
    "DomainRegistrar",
    "RegistrarName",
    "DomainAvailabilityStatus",
    "RegistrarPricing",
    "DomainSearchResult",
    "MultiRegistrarSearchResponse",
    "DomainRegistrationRequest",
    "RegisteredDomainResponse",
    "search_domains_multi_registrar",
    "register_domain_multi_registrar",
    "get_all_tld_pricing_comparison",
    "FirewallService",
    "BeaconMonitor",
]
