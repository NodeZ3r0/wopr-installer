from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditConfig:
    service_name: str
    environment: str = "production"
    storage_backend: str = "sqlite"  # sqlite, postgres, json_file
    storage_url: Optional[str] = None  # DB URL or file path
    webhook_url: Optional[str] = None
    log_request_bodies: bool = False
    redact_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, service_name: str, prefix: str = "WOPR_AUDIT"):
        import os
        return cls(
            service_name=service_name,
            environment=os.getenv(f"{prefix}_ENVIRONMENT", "production"),
            storage_backend=os.getenv(f"{prefix}_STORAGE", "sqlite"),
            storage_url=os.getenv(f"{prefix}_STORAGE_URL"),
            webhook_url=os.getenv(f"{prefix}_WEBHOOK_URL"),
            log_request_bodies=os.getenv(f"{prefix}_LOG_BODIES", "false").lower() == "true",
        )
