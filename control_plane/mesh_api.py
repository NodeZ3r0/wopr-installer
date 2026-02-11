"""
WOPR Mesh Network API
=====================

Control plane endpoints for managing the distributed peer-to-peer
mesh network between WOPR beacons.

This API runs on the orchestrator (orc.wopr.systems) and provides:
- Mesh invite generation for a customer's beacons
- Peer status aggregation across a customer's fleet
- Mesh topology visualization data

IMPORTANT: The orchestrator does NOT participate in the mesh itself.
It only facilitates initial introductions between beacons owned by
the same customer. Once beacons are peered, they communicate directly
with zero central dependency.

The mesh is:
- Peer-to-peer: beacons talk directly to each other
- No single point of failure: losing the orchestrator doesn't break existing peers
- Invite-based: beacons peer via cryptographic invite tokens
- Authenticated: each beacon has an Ed25519 identity

Updated: February 2026
"""

import json
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException, Request
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# ============================================
# PYDANTIC MODELS
# ============================================

if FASTAPI_AVAILABLE:

    class MeshPeerInfo(BaseModel):
        """Info about a peer in the mesh."""
        beacon_id: str
        domain: str
        fingerprint: str
        peered_at: Optional[str] = None
        status: str = "unknown"

    class MeshStatusResponse(BaseModel):
        """Mesh status for a single beacon."""
        beacon_id: str
        domain: str
        fingerprint: Optional[str] = None
        mesh_url: Optional[str] = None
        peer_count: int = 0
        peers: List[MeshPeerInfo] = []
        healthy: bool = False

    class MeshTopologyResponse(BaseModel):
        """Mesh topology across a customer's beacons."""
        customer_id: str
        beacons: List[MeshStatusResponse]
        total_peers: int = 0
        fully_meshed: bool = False

    class MeshInviteRequest(BaseModel):
        """Request to generate a mesh invite from one beacon."""
        source_beacon_id: str

    class MeshInviteResponse(BaseModel):
        """Generated mesh invite token."""
        invite_token: str
        source_domain: str
        source_fingerprint: str
        expires_in: str = "24 hours"

    class MeshPeerRequest(BaseModel):
        """Request to peer two beacons."""
        source_beacon_id: str
        target_beacon_id: str

    class MeshPeerResponse(BaseModel):
        """Result of a peering request."""
        status: str
        source_domain: str
        target_domain: str
        message: str


# ============================================
# MESH MANAGER
# ============================================

class MeshManager:
    """
    Manages mesh operations across a customer's beacon fleet.

    The MeshManager on the orchestrator is a facilitator, not a participant.
    It helps beacons find each other and exchange invites, but once peered,
    beacons communicate directly with no orchestrator involvement.
    """

    def __init__(self, beacon_store=None, db_pool=None):
        self.beacon_store = beacon_store
        self.db_pool = db_pool
        self._http_client = httpx.AsyncClient(timeout=15.0, verify=True)

    async def get_beacon_mesh_status(self, beacon_domain: str) -> Dict[str, Any]:
        """Query a beacon's mesh agent for its current status."""
        mesh_url = f"https://mesh.{beacon_domain}/api/v1/mesh/ping"
        try:
            response = await self._http_client.get(mesh_url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug(f"Cannot reach mesh agent on {beacon_domain}: {e}")
        return {"status": "unreachable", "peer_count": 0}

    async def get_beacon_peers(self, beacon_domain: str) -> List[Dict]:
        """Get the peer list from a beacon's mesh agent."""
        mesh_url = f"https://mesh.{beacon_domain}/api/v1/mesh/peers"
        try:
            response = await self._http_client.get(mesh_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("peers", [])
        except Exception as e:
            logger.debug(f"Cannot get peers from {beacon_domain}: {e}")
        return []

    async def generate_invite(self, beacon_domain: str) -> Optional[str]:
        """
        Ask a beacon to generate a mesh invite token.

        The orchestrator calls the beacon's mesh API to create an invite.
        The invite token is returned and can be given to another beacon.
        """
        # We need to call the beacon's mesh agent to generate an invite
        # Since the mesh agent runs bash, we use SSH or the beacon's API
        # For now, we call the mesh API on the beacon
        mesh_url = f"https://mesh.{beacon_domain}/api/v1/mesh/create-invite"
        try:
            response = await self._http_client.post(mesh_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("invite_token")
        except Exception as e:
            logger.error(f"Failed to generate invite from {beacon_domain}: {e}")
        return None

    async def get_customer_topology(
        self, customer_id: str, beacons: List[Any]
    ) -> Dict[str, Any]:
        """
        Build mesh topology for a customer's beacons.

        Queries each beacon's mesh agent and builds a complete
        picture of the mesh network.
        """
        topology = {
            "customer_id": customer_id,
            "beacons": [],
            "total_peers": 0,
            "fully_meshed": False,
        }

        beacon_count = len(beacons)
        all_peer_counts = []

        for beacon in beacons:
            domain = beacon.domain if hasattr(beacon, "domain") else beacon.get("domain", "")
            beacon_id = beacon.id if hasattr(beacon, "id") else beacon.get("id", "")

            status = await self.get_beacon_mesh_status(domain)
            peers = await self.get_beacon_peers(domain)

            beacon_status = {
                "beacon_id": beacon_id,
                "domain": domain,
                "fingerprint": status.get("fingerprint", ""),
                "mesh_url": f"https://mesh.{domain}",
                "peer_count": len(peers),
                "peers": peers,
                "healthy": status.get("status") == "ok",
            }
            topology["beacons"].append(beacon_status)
            all_peer_counts.append(len(peers))

        topology["total_peers"] = sum(all_peer_counts)

        # Fully meshed = every beacon is peered with every other beacon
        if beacon_count > 1:
            expected_peers = beacon_count - 1
            topology["fully_meshed"] = all(c >= expected_peers for c in all_peer_counts)

        return topology

    async def auto_mesh_customer_beacons(
        self, customer_id: str, new_beacon_domain: str, existing_beacons: List[Any]
    ) -> List[str]:
        """
        Automatically peer a new beacon with all existing beacons
        for the same customer.

        This is called during provisioning. Each existing beacon
        generates an invite, and the invites are embedded in the
        new beacon's bootstrap.json so it auto-accepts them on first boot.

        Returns list of invite tokens for the new beacon.
        """
        invite_tokens = []

        for beacon in existing_beacons:
            domain = beacon.domain if hasattr(beacon, "domain") else beacon.get("domain", "")
            if domain == new_beacon_domain:
                continue

            # Ask each existing beacon to generate an invite
            invite = await self.generate_invite(domain)
            if invite:
                invite_tokens.append(invite)
                logger.info(
                    f"Generated mesh invite from {domain} for new beacon {new_beacon_domain}"
                )
            else:
                logger.warning(
                    f"Could not generate mesh invite from {domain}"
                )

        return invite_tokens


# ============================================
# API ROUTER
# ============================================

def create_mesh_router(mesh_manager: MeshManager, beacon_store=None) -> "APIRouter":
    """Create FastAPI router for mesh endpoints."""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI not available")

    router = APIRouter(prefix="/api/v1/mesh", tags=["mesh"])

    @router.get("/topology/{customer_id}")
    async def get_mesh_topology(customer_id: str):
        """Get mesh topology for a customer's beacons."""
        if not beacon_store:
            raise HTTPException(500, "Beacon store not configured")

        beacons = beacon_store.get_by_owner(customer_id)
        if not beacons:
            raise HTTPException(404, "No beacons found for customer")

        topology = await mesh_manager.get_customer_topology(customer_id, beacons)
        return topology

    @router.get("/status/{beacon_id}")
    async def get_beacon_mesh_status(beacon_id: str):
        """Get mesh status for a specific beacon."""
        if not beacon_store:
            raise HTTPException(500, "Beacon store not configured")

        beacon = beacon_store.get(beacon_id)
        if not beacon:
            raise HTTPException(404, "Beacon not found")

        status = await mesh_manager.get_beacon_mesh_status(beacon.domain)
        peers = await mesh_manager.get_beacon_peers(beacon.domain)

        return {
            "beacon_id": beacon_id,
            "domain": beacon.domain,
            "fingerprint": status.get("fingerprint", ""),
            "mesh_url": f"https://mesh.{beacon.domain}",
            "peer_count": len(peers),
            "peers": peers,
            "healthy": status.get("status") == "ok",
        }

    @router.post("/invite")
    async def create_mesh_invite(request: MeshInviteRequest):
        """Generate a mesh invite from a specific beacon."""
        if not beacon_store:
            raise HTTPException(500, "Beacon store not configured")

        beacon = beacon_store.get(request.source_beacon_id)
        if not beacon:
            raise HTTPException(404, "Source beacon not found")

        invite = await mesh_manager.generate_invite(beacon.domain)
        if not invite:
            raise HTTPException(502, "Failed to generate invite from beacon")

        status = await mesh_manager.get_beacon_mesh_status(beacon.domain)

        return MeshInviteResponse(
            invite_token=invite,
            source_domain=beacon.domain,
            source_fingerprint=status.get("fingerprint", ""),
        )

    @router.post("/peer")
    async def peer_beacons(request: MeshPeerRequest):
        """Peer two beacons owned by the same customer."""
        if not beacon_store:
            raise HTTPException(500, "Beacon store not configured")

        source = beacon_store.get(request.source_beacon_id)
        target = beacon_store.get(request.target_beacon_id)

        if not source or not target:
            raise HTTPException(404, "One or both beacons not found")

        # Verify same owner
        if source.owner_id != target.owner_id:
            raise HTTPException(403, "Beacons must belong to the same owner")

        # Generate invite from source
        invite = await mesh_manager.generate_invite(source.domain)
        if not invite:
            raise HTTPException(502, f"Failed to generate invite from {source.domain}")

        # Send invite to target beacon for acceptance
        accept_url = f"https://mesh.{target.domain}/api/v1/mesh/accept-invite"
        try:
            response = await mesh_manager._http_client.post(
                accept_url,
                json={"invite_token": invite}
            )
            if response.status_code == 200:
                return MeshPeerResponse(
                    status="peered",
                    source_domain=source.domain,
                    target_domain=target.domain,
                    message=f"Beacons peered successfully",
                )
            else:
                raise HTTPException(
                    502,
                    f"Target beacon rejected invite: {response.status_code}"
                )
        except httpx.RequestError as e:
            raise HTTPException(
                502,
                f"Cannot reach target beacon mesh agent: {e}"
            )

    return router
