"""
WOPR VPS Provider Abstraction Layer
====================================

Multi-vendor provisioning to prevent lock-in and enable true distribution.

Supported Providers:
- Hetzner (hcloud-python)
- Vultr (libcloud)
- DigitalOcean (libcloud)
- Linode/Akamai (libcloud)
- OVHcloud (libcloud)
- Contabo (custom)
- BYO VPS (SSH-based)
"""

from .base import (
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Region,
    Instance,
    InstanceStatus,
    ProvisionConfig,
    ProviderError,
)
from .registry import ProviderRegistry

__all__ = [
    "WOPRProviderInterface",
    "ResourceTier",
    "Plan",
    "Region",
    "Instance",
    "InstanceStatus",
    "ProvisionConfig",
    "ProviderError",
    "ProviderRegistry",
]
