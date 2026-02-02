"""Support Gateway configuration loaded from environment."""

import os
from dataclasses import dataclass, field


@dataclass
class SupportGatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8443
    database_url: str = ""
    log_level: str = "INFO"
    breakglass_max_minutes: int = 30
    breakglass_default_minutes: int = 15
    ssh_ca_url: str = "http://127.0.0.1:9444"
    nebula_network: str = "10.0.0.0/8"
    cors_origins: list[str] = field(
        default_factory=lambda: ["https://support-gateway.wopr.systems"]
    )

    @classmethod
    def from_env(cls) -> "SupportGatewayConfig":
        origins = os.environ.get("CORS_ORIGINS", "https://support-gateway.wopr.systems")
        return cls(
            host=os.environ.get("SUPPORT_GW_HOST", "127.0.0.1"),
            port=int(os.environ.get("SUPPORT_GW_PORT", "8443")),
            database_url=os.environ.get("DATABASE_URL", ""),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            breakglass_max_minutes=int(
                os.environ.get("BREAKGLASS_MAX_MINUTES", "30")
            ),
            breakglass_default_minutes=int(
                os.environ.get("BREAKGLASS_DEFAULT_MINUTES", "15")
            ),
            ssh_ca_url=os.environ.get("SSH_CA_URL", "http://127.0.0.1:9444"),
            nebula_network=os.environ.get("NEBULA_NETWORK", "10.0.0.0/8"),
            cors_origins=[o.strip() for o in origins.split(",")],
        )
