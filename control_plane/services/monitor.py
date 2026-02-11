"""
WOPR Beacon Health Monitor
============================

Background service that periodically checks beacon health
and tracks uptime.

Runs as a background task in the FastAPI application.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)


class BeaconMonitor:
    """
    Monitors health of deployed WOPR beacons.

    Polls each active beacon's health endpoint and records status.
    """

    def __init__(
        self,
        db_pool,
        wopr_domain: str = "wopr.systems",
        check_interval: int = 300,  # 5 minutes
        timeout: int = 10,
    ):
        self.db_pool = db_pool
        self.wopr_domain = wopr_domain
        self.check_interval = check_interval
        self.timeout = timeout
        self._running = False

    async def start(self):
        """Start the monitoring loop."""
        self._running = True
        logger.info("Beacon health monitor started")

        while self._running:
            try:
                await self._check_all_beacons()
            except Exception as e:
                logger.error(f"Monitor cycle failed: {e}")

            await asyncio.sleep(self.check_interval)

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("Beacon health monitor stopped")

    async def _check_all_beacons(self):
        """Check health of all active beacons."""
        if not self.db_pool:
            return

        rows = await self.db_pool.fetch(
            "SELECT id, subdomain, ip_address FROM beacons WHERE status = 'active'"
        )

        if not rows:
            return

        logger.debug(f"Checking {len(rows)} active beacon(s)")

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            tasks = [
                self._check_beacon(client, dict(row))
                for row in rows
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_beacon(self, client: httpx.AsyncClient, beacon: Dict[str, Any]):
        """Check a single beacon's health."""
        subdomain = beacon.get("subdomain", "")
        ip = beacon.get("ip_address", "")
        beacon_id = beacon["id"]

        # Try HTTPS first, then HTTP by IP
        urls = []
        if subdomain:
            urls.append(f"https://{subdomain}.{self.wopr_domain}/api/health")
        if ip:
            urls.append(f"http://{ip}:8080/api/health")

        healthy = False
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    healthy = True
                    break
            except Exception:
                continue

        # Record result
        try:
            await self.db_pool.execute(
                """
                UPDATE beacons
                SET last_health_check = NOW(),
                    last_health_status = $2
                WHERE id = $1
                """,
                beacon_id,
                "healthy" if healthy else "unhealthy",
            )

            if not healthy:
                logger.warning(f"Beacon {beacon_id} ({subdomain}) is unhealthy")

        except Exception as e:
            logger.error(f"Failed to record health for beacon {beacon_id}: {e}")

    async def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all beacon health statuses."""
        if not self.db_pool:
            return {"error": "No database connection"}

        total = await self.db_pool.fetchval(
            "SELECT COUNT(*) FROM beacons WHERE status = 'active'"
        )
        healthy = await self.db_pool.fetchval(
            "SELECT COUNT(*) FROM beacons WHERE status = 'active' AND last_health_status = 'healthy'"
        )
        unhealthy = await self.db_pool.fetchval(
            "SELECT COUNT(*) FROM beacons WHERE status = 'active' AND last_health_status = 'unhealthy'"
        )
        unchecked = await self.db_pool.fetchval(
            "SELECT COUNT(*) FROM beacons WHERE status = 'active' AND last_health_check IS NULL"
        )

        return {
            "total_active": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unchecked": unchecked,
            "monitor_running": self._running,
        }
