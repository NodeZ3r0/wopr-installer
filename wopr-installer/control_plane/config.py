"""
WOPR Centralized Configuration
===============================

Single source of truth for all configuration values.
Reads from environment variables with sensible defaults.
"""

import os
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class StripeConfig:
    secret_key: str = ""
    webhook_secret: str = ""
    price_mode: str = "test"  # "test" or "live"


@dataclass
class CloudflareConfig:
    api_token: str = ""
    zone_id: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token and self.zone_id)


@dataclass
class SMTPConfig:
    host: str = "smtp.mailgun.org"
    port: int = 587
    user: str = ""
    password: str = ""
    from_email: str = "WOPR <noreply@wopr.systems>"
    reply_to: str = "support@wopr.systems"
    use_tls: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.user and self.password)


@dataclass
class DatabaseConfig:
    url: str = "postgresql://wopr:changeme@localhost:5432/wopr"
    min_pool_size: int = 2
    max_pool_size: int = 10


@dataclass
class AuthentikConfig:
    url: str = "https://auth.wopr.systems"
    api_token: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.api_token)


@dataclass
class ProviderTokens:
    hetzner: str = ""
    digitalocean: str = ""
    vultr: str = ""
    linode: str = ""
    ovh_application_key: str = ""
    ovh_application_secret: str = ""
    ovh_consumer_key: str = ""
    ovh_project_id: str = ""

    def available_providers(self) -> List[str]:
        providers = []
        if self.hetzner:
            providers.append("hetzner")
        if self.digitalocean:
            providers.append("digitalocean")
        if self.vultr:
            providers.append("vultr")
        if self.linode:
            providers.append("linode")
        if self.ovh_application_key:
            providers.append("ovh")
        return providers


@dataclass
class WOPRConfig:
    """Master configuration for WOPR control plane."""

    # Sub-configs
    stripe: StripeConfig = field(default_factory=StripeConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    authentik: AuthentikConfig = field(default_factory=AuthentikConfig)
    providers: ProviderTokens = field(default_factory=ProviderTokens)

    # Application settings
    wopr_domain: str = "wopr.systems"
    job_store_path: str = "/var/lib/wopr/jobs"
    document_output_dir: str = "/var/lib/wopr/documents"
    log_level: str = "INFO"
    log_format: str = "json"
    cors_origins: List[str] = field(
        default_factory=lambda: ["https://wopr.systems", "https://orc.wopr.systems"]
    )

    @classmethod
    def from_env(cls) -> "WOPRConfig":
        """Load configuration from environment variables."""
        return cls(
            stripe=StripeConfig(
                secret_key=os.environ.get("STRIPE_SECRET_KEY", ""),
                webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
                price_mode=os.environ.get("STRIPE_PRICE_MODE", "test"),
            ),
            cloudflare=CloudflareConfig(
                api_token=os.environ.get("CLOUDFLARE_API_TOKEN", ""),
                zone_id=os.environ.get("CLOUDFLARE_ZONE_ID", ""),
            ),
            smtp=SMTPConfig(
                host=os.environ.get("SMTP_HOST", "smtp.mailgun.org"),
                port=int(os.environ.get("SMTP_PORT", "587")),
                user=os.environ.get("SMTP_USER", ""),
                password=os.environ.get("SMTP_PASSWORD", ""),
                from_email=os.environ.get("FROM_EMAIL", "WOPR <noreply@wopr.systems>"),
                reply_to=os.environ.get("REPLY_TO_EMAIL", "support@wopr.systems"),
            ),
            database=DatabaseConfig(
                url=os.environ.get("DATABASE_URL", "postgresql://wopr:changeme@localhost:5432/wopr"),
            ),
            authentik=AuthentikConfig(
                url=os.environ.get("AUTHENTIK_URL", "https://auth.wopr.systems"),
                api_token=os.environ.get("AUTHENTIK_API_TOKEN", ""),
            ),
            providers=ProviderTokens(
                hetzner=os.environ.get("HETZNER_API_TOKEN", ""),
                digitalocean=os.environ.get("DIGITALOCEAN_API_TOKEN", ""),
                vultr=os.environ.get("VULTR_API_TOKEN", ""),
                linode=os.environ.get("LINODE_API_TOKEN", ""),
                ovh_application_key=os.environ.get("OVH_APPLICATION_KEY", ""),
                ovh_application_secret=os.environ.get("OVH_APPLICATION_SECRET", ""),
                ovh_consumer_key=os.environ.get("OVH_CONSUMER_KEY", ""),
                ovh_project_id=os.environ.get("OVH_PROJECT_ID", ""),
            ),
            wopr_domain=os.environ.get("WOPR_DOMAIN", "wopr.systems"),
            job_store_path=os.environ.get("JOB_STORE_PATH", "/var/lib/wopr/jobs"),
            document_output_dir=os.environ.get("DOCUMENT_OUTPUT_DIR", "/var/lib/wopr/documents"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            log_format=os.environ.get("LOG_FORMAT", "json"),
            cors_origins=os.environ.get(
                "CORS_ORIGINS", "https://wopr.systems,https://orc.wopr.systems"
            ).split(","),
        )
