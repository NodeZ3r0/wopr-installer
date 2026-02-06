"""
WOPR VPS Provider Abstraction Layer
====================================

Multi-vendor provisioning to prevent lock-in and enable true distribution.
Focused on privacy-respecting, independent providers.

Supported Providers (Fully Implemented):
- Hetzner (hcloud-python) - German, excellent value
- UpCloud (REST API) - Finnish, MaxIOPS storage
- Linode/Akamai (libcloud) - Predictable pricing
- OVHcloud (libcloud/OpenStack) - French, EU-focused
- DigitalOcean (libcloud) - Developer-friendly
- BYO VPS (SSH-based) - Bring your own server

Provider Stubs (Ready for Implementation):
- Scaleway (French, EU) - ARM64 support, green energy
- Contabo (German) - Budget-friendly, high specs
- Netcup (German) - No overselling, eco-friendly
- 1984 Hosting (Icelandic) - Privacy-first, Orwellian namesake
- Exoscale (Swiss) - Swiss privacy, no backdoors
- BuyVM/FranTech (Indie) - Privacy advocate, DDoS protection

DEPRECATED (Not Registered):
- Vultr - Problematic TOS (content ownership clause)

Note: Import provider modules to trigger @register_provider decorators.
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
    ProviderAuthError,
    ProviderResourceError,
)
from .registry import ProviderRegistry, register_provider

# Import providers to trigger registration via @register_provider decorator
# Fully implemented providers
from . import hetzner
from . import upcloud
from . import linode
from . import ovh
from . import digitalocean
from . import byo

# Stub providers (ready for implementation)
from . import scaleway
from . import contabo
from . import netcup
from . import hosting1984
from . import exoscale
from . import buyvm

# Note: vultr.py exists but is NOT imported - deprecated due to TOS concerns

__all__ = [
    # Base classes and types
    "WOPRProviderInterface",
    "ResourceTier",
    "Plan",
    "Region",
    "Instance",
    "InstanceStatus",
    "ProvisionConfig",
    "ProviderError",
    "ProviderAuthError",
    "ProviderResourceError",
    # Registry
    "ProviderRegistry",
    "register_provider",
]
