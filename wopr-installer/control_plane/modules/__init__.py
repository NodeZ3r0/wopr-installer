"""
WOPR Module Registry
====================

Central registry for all WOPR Sovereign Suite modules/apps.

Each module represents a deployable application that can be:
- Included in a bundle (base)
- Added as an optional paid add-on
- Added as a free trial add-on

Module lifecycle:
1. User selects bundle -> base modules enabled
2. User can add optional modules (paid or trial)
3. Trial modules expire after trial period
4. Authentik gates access based on entitlements
"""

from .registry import (
    ModuleRegistry,
    Module,
    ModuleCategory,
    ModuleTier,
    BundleModules,
    MODULES,
)

from .trials import (
    TrialManager,
    TrialStatus,
    TrialConfig,
)

__all__ = [
    "ModuleRegistry",
    "Module",
    "ModuleCategory",
    "ModuleTier",
    "BundleModules",
    "MODULES",
    "TrialManager",
    "TrialStatus",
    "TrialConfig",
]
