"""
WOPR Intent Resolvers
=====================

Intent-based navigation system for the Beacon Dashboard.

Users never see raw app URLs. They interact with intent endpoints:
- /go/drive → Nextcloud Files
- /go/photos → Nextcloud Photos / Immich
- /go/shop → Saleor storefront
- /go/dashboard → Beacon Dashboard

Resolvers:
1. Check Authentik authentication
2. Identify the user's Beacon(s)
3. Determine if the requested capability exists
4. Redirect to the appropriate dashboard section

This module implements the "Intent Resolver" pattern from the
Beacon Dashboard Implementation Primer.
"""

from .intents import (
    Intent,
    IntentResolver,
    INTENT_REGISTRY,
    resolve_intent,
    get_available_intents,
)

from .capabilities import (
    Capability,
    CAPABILITY_MAP,
    get_capability_for_intent,
    get_module_for_capability,
)

__all__ = [
    "Intent",
    "IntentResolver",
    "INTENT_REGISTRY",
    "resolve_intent",
    "get_available_intents",
    "Capability",
    "CAPABILITY_MAP",
    "get_capability_for_intent",
    "get_module_for_capability",
]
