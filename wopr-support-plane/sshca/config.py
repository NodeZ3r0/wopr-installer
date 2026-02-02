"""SSH Certificate Authority configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class SSHCAConfig:
    host: str = "127.0.0.1"
    port: int = 9444
    ca_private_key_path: str = "/etc/wopr-sshca/ca_key"
    ca_public_key_path: str = "/etc/wopr-sshca/ca_key.pub"

    # Certificate validity per tier (seconds)
    cert_validity_diag: int = 300         # 5 minutes
    cert_validity_remediate: int = 600    # 10 minutes
    cert_validity_breakglass: int = 1800  # 30 minutes max

    # Principals allowed per tier
    allowed_principals_diag: list[str] = field(
        default_factory=lambda: ["wopr-diag"]
    )
    allowed_principals_remediate: list[str] = field(
        default_factory=lambda: ["wopr-diag", "wopr-remediate"]
    )
    allowed_principals_breakglass: list[str] = field(
        default_factory=lambda: ["wopr-diag", "wopr-remediate", "wopr-breakglass", "root"]
    )

    # Force commands per tier (None = unrestricted)
    force_command_diag: str = "/usr/local/bin/wopr-diag-shell"
    force_command_remediate: str = "/usr/local/bin/wopr-remediate-shell"
    force_command_breakglass: str | None = None  # Full access

    # Database for breakglass session validation
    database_url: str = ""

    @classmethod
    def from_env(cls) -> "SSHCAConfig":
        return cls(
            host=os.environ.get("SSHCA_HOST", "127.0.0.1"),
            port=int(os.environ.get("SSHCA_PORT", "9444")),
            ca_private_key_path=os.environ.get(
                "SSHCA_CA_KEY", "/etc/wopr-sshca/ca_key"
            ),
            ca_public_key_path=os.environ.get(
                "SSHCA_CA_PUB", "/etc/wopr-sshca/ca_key.pub"
            ),
            cert_validity_diag=int(os.environ.get("SSHCA_VALIDITY_DIAG", "300")),
            cert_validity_remediate=int(
                os.environ.get("SSHCA_VALIDITY_REMEDIATE", "600")
            ),
            cert_validity_breakglass=int(
                os.environ.get("SSHCA_VALIDITY_BREAKGLASS", "1800")
            ),
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql://wopr:changeme@localhost:5432/wopr_support",
            ),
        )
