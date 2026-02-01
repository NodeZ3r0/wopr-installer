"""
WOPR Beacon Model
=================

A Beacon is the core unit of ownership in the WOPR ecosystem.

Each Beacon represents:
- A user-owned VPS server
- Running a Sovereign Suite bundle
- With specific modules installed
- Under full user control

Beacons are:
- Owned by a single user (Authentik identity)
- Associated with a domain (e.g., myname.wopr.systems)
- Running a specific bundle (personal, creator, developer, professional)
- Containing installed modules

Users may have multiple Beacons (e.g., personal + work).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel


class BeaconStatus(str, Enum):
    """Beacon lifecycle status."""
    PROVISIONING = "provisioning"  # Being set up
    ACTIVE = "active"  # Running normally
    SUSPENDED = "suspended"  # Billing issue
    MAINTENANCE = "maintenance"  # Scheduled downtime
    DECOMMISSIONED = "decommissioned"  # Shut down


class BeaconProvider(str, Enum):
    """VPS providers for WOPR-managed Beacons."""
    HETZNER = "hetzner"
    VULTR = "vultr"
    DIGITALOCEAN = "digitalocean"
    BYO = "byo"  # Bring Your Own


@dataclass
class BeaconResource:
    """Resource allocation for a Beacon."""
    vcpu: int
    ram_gb: int
    disk_gb: int
    bandwidth_tb: Optional[float] = None


@dataclass
class Beacon:
    """
    A user's Beacon (their sovereign server).

    This is the primary unit of ownership in WOPR.
    """
    # Identity
    id: str  # UUID
    owner_id: str  # Authentik user ID
    name: str  # User-friendly name (e.g., "My Personal Cloud")

    # Domain
    domain: str  # Full domain (e.g., "mybeacon.wopr.systems")
    subdomain: str  # Just the subdomain part

    # Bundle & Modules
    bundle: str  # Bundle ID (personal, creator, developer, professional)
    modules: List[str] = field(default_factory=list)  # Installed module IDs
    pending_modules: List[str] = field(default_factory=list)  # Being installed

    # Infrastructure
    provider: BeaconProvider = BeaconProvider.HETZNER
    region: str = "us-east"
    datacenter: str = ""
    resources: Optional[BeaconResource] = None

    # Status
    status: BeaconStatus = BeaconStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Billing
    stripe_subscription_id: Optional[str] = None
    billing_cycle: str = "monthly"  # monthly, yearly

    # Mesh network
    mesh_fingerprint: Optional[str] = None
    mesh_peers: List[str] = field(default_factory=list)  # Peer fingerprints

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_module(self, module_id: str) -> bool:
        """Check if a module is installed on this Beacon."""
        return module_id in self.modules

    def has_capability(self, capability: str, capability_map: Dict) -> bool:
        """Check if this Beacon has a specific capability."""
        mapping = capability_map.get(capability)
        if not mapping:
            return False

        # Check primary module
        if mapping.primary_module in self.modules:
            return True

        # Check fallbacks
        return any(m in self.modules for m in mapping.fallback_modules)


# ============================================
# PYDANTIC MODELS (FOR API)
# ============================================

class BeaconCreate(BaseModel):
    """Request to create a new Beacon."""
    name: str
    bundle: str
    subdomain: str
    provider: str = "hetzner"
    region: str = "us-east"


class BeaconUpdate(BaseModel):
    """Request to update a Beacon."""
    name: Optional[str] = None
    tags: Optional[List[str]] = None


class BeaconResponse(BaseModel):
    """Beacon info returned by API."""
    id: str
    name: str
    domain: str
    bundle: str
    status: str
    modules: List[str]
    provider: str
    region: str
    mesh_fingerprint: Optional[str] = None
    mesh_peers: List[str] = []
    created_at: str

    class Config:
        from_attributes = True


class BeaconCapability(BaseModel):
    """A capability available on a Beacon."""
    capability: str
    name: str
    description: str
    icon: str
    section: str
    available: bool
    path: str


class BeaconCapabilitiesResponse(BaseModel):
    """All capabilities for a Beacon."""
    beacon_id: str
    bundle: str
    capabilities: List[BeaconCapability]


# ============================================
# DATABASE SCHEMA (SQL)
# ============================================

BEACON_SCHEMA_SQL = """
-- Beacons table
CREATE TABLE IF NOT EXISTS beacons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id VARCHAR(255) NOT NULL,  -- Authentik user ID

    -- Identity
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL UNIQUE,
    subdomain VARCHAR(63) NOT NULL,

    -- Bundle & Modules
    bundle VARCHAR(50) NOT NULL,
    modules JSONB DEFAULT '[]'::jsonb,
    pending_modules JSONB DEFAULT '[]'::jsonb,

    -- Infrastructure
    provider VARCHAR(50) DEFAULT 'hetzner',
    region VARCHAR(50) DEFAULT 'us-east',
    datacenter VARCHAR(50),
    resources JSONB,

    -- Status
    status VARCHAR(50) DEFAULT 'provisioning',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Billing
    stripe_subscription_id VARCHAR(255),
    billing_cycle VARCHAR(20) DEFAULT 'monthly',

    -- Mesh network
    mesh_fingerprint VARCHAR(128),
    mesh_peers JSONB DEFAULT '[]'::jsonb,

    -- Metadata
    tags JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_bundle CHECK (bundle IN ('personal', 'creator', 'developer', 'professional')),
    CONSTRAINT valid_status CHECK (status IN ('provisioning', 'active', 'suspended', 'maintenance', 'decommissioned'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_beacons_owner ON beacons(owner_id);
CREATE INDEX IF NOT EXISTS idx_beacons_domain ON beacons(domain);
CREATE INDEX IF NOT EXISTS idx_beacons_status ON beacons(status);
CREATE INDEX IF NOT EXISTS idx_beacons_bundle ON beacons(bundle);

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_beacon_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER beacon_updated
    BEFORE UPDATE ON beacons
    FOR EACH ROW
    EXECUTE FUNCTION update_beacon_timestamp();
"""


# ============================================
# IN-MEMORY STORE (DEVELOPMENT)
# ============================================

class BeaconStore:
    """
    In-memory Beacon store for development.

    Replace with PostgreSQL in production.
    """

    def __init__(self):
        self._beacons: Dict[str, Beacon] = {}
        self._by_owner: Dict[str, List[str]] = {}  # owner_id -> beacon_ids

    def create(self, beacon: Beacon) -> Beacon:
        """Create a new Beacon."""
        self._beacons[beacon.id] = beacon

        if beacon.owner_id not in self._by_owner:
            self._by_owner[beacon.owner_id] = []
        self._by_owner[beacon.owner_id].append(beacon.id)

        return beacon

    def get(self, beacon_id: str) -> Optional[Beacon]:
        """Get a Beacon by ID."""
        return self._beacons.get(beacon_id)

    def get_by_owner(self, owner_id: str) -> List[Beacon]:
        """Get all Beacons owned by a user."""
        beacon_ids = self._by_owner.get(owner_id, [])
        return [self._beacons[bid] for bid in beacon_ids if bid in self._beacons]

    def get_by_domain(self, domain: str) -> Optional[Beacon]:
        """Get a Beacon by domain."""
        for beacon in self._beacons.values():
            if beacon.domain == domain:
                return beacon
        return None

    def update(self, beacon_id: str, **kwargs) -> Optional[Beacon]:
        """Update a Beacon."""
        beacon = self._beacons.get(beacon_id)
        if not beacon:
            return None

        for key, value in kwargs.items():
            if hasattr(beacon, key):
                setattr(beacon, key, value)

        beacon.updated_at = datetime.now()
        return beacon

    def delete(self, beacon_id: str) -> bool:
        """Delete a Beacon."""
        beacon = self._beacons.get(beacon_id)
        if not beacon:
            return False

        del self._beacons[beacon_id]

        if beacon.owner_id in self._by_owner:
            self._by_owner[beacon.owner_id] = [
                bid for bid in self._by_owner[beacon.owner_id]
                if bid != beacon_id
            ]

        return True

    def list_all(self) -> List[Beacon]:
        """List all Beacons (admin only)."""
        return list(self._beacons.values())


# Global store instance (replace with DI in production)
beacon_store = BeaconStore()
