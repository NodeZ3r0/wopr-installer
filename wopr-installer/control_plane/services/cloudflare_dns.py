"""
WOPR Cloudflare DNS Service
============================

Manages DNS records for WOPR beacons via the Cloudflare API.

Handles:
- A record creation for beacon subdomains
- Wildcard A records for app subdomains (*.beacon.wopr.systems)
- Record deletion on cancellation/cleanup
- Record listing for a zone

Uses the official cloudflare Python SDK.
Requires: pip install cloudflare
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

try:
    import cloudflare as cf
    CLOUDFLARE_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AVAILABLE = False
    logger.warning("cloudflare package not installed. Run: pip install cloudflare")


class CloudflareDNS:
    """
    Cloudflare DNS management for WOPR beacon subdomains.

    Creates and manages DNS records within a single zone (e.g., wopr.systems).
    """

    def __init__(self, api_token: str, zone_id: str):
        """
        Initialize with Cloudflare API token and zone ID.

        Args:
            api_token: Cloudflare API token with DNS edit permissions
            zone_id: Cloudflare zone ID for the target domain
        """
        if not CLOUDFLARE_AVAILABLE:
            raise ImportError("cloudflare package not installed")

        self.zone_id = zone_id
        self.client = cf.Cloudflare(api_token=api_token)

    async def create_a_record(
        self,
        name: str,
        ip: str,
        proxied: bool = False,
        ttl: int = 300,
    ) -> str:
        """
        Create an A record.

        Args:
            name: Full DNS name (e.g., "my-beacon.wopr.systems")
            ip: IPv4 address to point to
            proxied: Whether to proxy through Cloudflare (False for direct)
            ttl: TTL in seconds (ignored if proxied=True)

        Returns:
            Record ID string
        """
        import asyncio

        def _create():
            result = self.client.dns.records.create(
                zone_id=self.zone_id,
                type="A",
                name=name,
                content=ip,
                proxied=proxied,
                ttl=1 if proxied else ttl,
            )
            return result.id

        record_id = await asyncio.to_thread(_create)
        logger.info(f"Created A record: {name} -> {ip} (id={record_id})")
        return record_id

    async def create_cname_record(
        self,
        name: str,
        target: str,
        proxied: bool = False,
        ttl: int = 300,
    ) -> str:
        """
        Create a CNAME record.

        Args:
            name: Full DNS name
            target: CNAME target
            proxied: Whether to proxy through Cloudflare
            ttl: TTL in seconds

        Returns:
            Record ID string
        """
        import asyncio

        def _create():
            result = self.client.dns.records.create(
                zone_id=self.zone_id,
                type="CNAME",
                name=name,
                content=target,
                proxied=proxied,
                ttl=1 if proxied else ttl,
            )
            return result.id

        record_id = await asyncio.to_thread(_create)
        logger.info(f"Created CNAME record: {name} -> {target} (id={record_id})")
        return record_id

    async def delete_record(self, record_id: str) -> bool:
        """
        Delete a DNS record by ID.

        Args:
            record_id: Cloudflare record ID

        Returns:
            True if deleted successfully
        """
        import asyncio

        def _delete():
            self.client.dns.records.delete(
                dns_record_id=record_id,
                zone_id=self.zone_id,
            )

        try:
            await asyncio.to_thread(_delete)
            logger.info(f"Deleted DNS record: {record_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete DNS record {record_id}: {e}")
            return False

    async def list_records(
        self,
        name: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List DNS records, optionally filtered.

        Args:
            name: Filter by record name
            record_type: Filter by type (A, CNAME, etc.)

        Returns:
            List of record dicts
        """
        import asyncio

        def _list():
            params = {"zone_id": self.zone_id}
            if name:
                params["name"] = name
            if record_type:
                params["type"] = record_type

            results = self.client.dns.records.list(**params)
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "name": r.name,
                    "content": r.content,
                    "proxied": r.proxied,
                    "ttl": r.ttl,
                }
                for r in results
            ]

        return await asyncio.to_thread(_list)

    async def update_record(
        self,
        record_id: str,
        ip: Optional[str] = None,
        proxied: Optional[bool] = None,
    ) -> bool:
        """
        Update an existing DNS record.

        Args:
            record_id: Record ID to update
            ip: New IP address (for A records)
            proxied: New proxied setting

        Returns:
            True if updated
        """
        import asyncio

        def _update():
            params = {}
            if ip is not None:
                params["content"] = ip
            if proxied is not None:
                params["proxied"] = proxied

            self.client.dns.records.edit(
                dns_record_id=record_id,
                zone_id=self.zone_id,
                **params,
            )

        try:
            await asyncio.to_thread(_update)
            logger.info(f"Updated DNS record: {record_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update DNS record {record_id}: {e}")
            return False

    async def delete_beacon_records(self, record_ids: Dict[str, str]) -> int:
        """
        Delete all DNS records for a beacon (A + wildcard).

        Args:
            record_ids: Dict of label -> record_id (from ProvisioningJob.dns_record_ids)

        Returns:
            Number of records successfully deleted
        """
        deleted = 0
        for label, record_id in record_ids.items():
            if await self.delete_record(record_id):
                deleted += 1
        return deleted
