"""
WOPR Custom Domain Service
===========================

Manages custom domain (BYOD - Bring Your Own Domain) functionality.

Features:
- DNS verification (A record and wildcard)
- SSL certificate provisioning via Let's Encrypt
- Caddy configuration updates
- Domain status tracking

Usage:
    from control_plane.services.custom_domain import CustomDomainService

    service = CustomDomainService(
        db_pool=db_pool,
        caddy_api_url="http://localhost:2019",
    )

    # Add a custom domain
    result = await service.add_domain(
        beacon_id="beacon-123",
        domain="cloud.example.com",
        expected_ip="1.2.3.4",
    )

    # Verify DNS propagation
    verification = await service.verify_dns(
        domain="cloud.example.com",
        expected_ip="1.2.3.4",
    )

    # Activate domain (after DNS verification)
    await service.activate_domain(beacon_id="beacon-123")
"""

import asyncio
import logging
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)


class DomainStatus(str, Enum):
    """Status of a custom domain."""
    NONE = "none"
    PENDING = "pending"
    VERIFYING = "verifying"
    ACTIVE = "active"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class DNSVerificationResult:
    """Result of DNS verification check."""
    verified: bool
    domain: str
    expected_ip: str
    a_record_status: str  # "verified", "missing", "wrong_ip"
    a_record_ip: Optional[str]
    wildcard_status: str  # "verified", "missing", "wrong_ip"
    wildcard_ip: Optional[str]
    errors: List[str]
    checked_at: str


@dataclass
class CustomDomainConfig:
    """Configuration for a custom domain."""
    beacon_id: str
    domain: str
    status: DomainStatus
    expected_ip: str
    created_at: datetime
    verified_at: Optional[datetime] = None
    ssl_issued_at: Optional[datetime] = None
    ssl_expires_at: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CustomDomainService:
    """
    Service for managing custom domains on WOPR beacons.

    Handles the full lifecycle of custom domain setup:
    1. Domain registration (storing the domain)
    2. DNS verification
    3. SSL certificate provisioning
    4. Caddy configuration
    """

    def __init__(
        self,
        db_pool=None,
        caddy_api_url: str = "http://localhost:2019",
        acme_email: str = "ssl@wopr.systems",
    ):
        """
        Initialize the custom domain service.

        Args:
            db_pool: asyncpg connection pool (optional, uses in-memory if not provided)
            caddy_api_url: URL of Caddy's admin API
            acme_email: Email for Let's Encrypt certificate registration
        """
        self.db_pool = db_pool
        self.caddy_api_url = caddy_api_url
        self.acme_email = acme_email

        # In-memory storage fallback (when db_pool is None)
        self._domains: Dict[str, CustomDomainConfig] = {}

    async def add_domain(
        self,
        beacon_id: str,
        domain: str,
        expected_ip: str,
    ) -> Dict[str, Any]:
        """
        Add a custom domain to a beacon.

        Args:
            beacon_id: ID of the beacon
            domain: The custom domain (e.g., "cloud.example.com")
            expected_ip: IP address the domain should point to

        Returns:
            Dict with success status and domain config
        """
        domain = domain.lower().strip()

        # Validate domain format
        if not self._is_valid_domain(domain):
            return {
                "success": False,
                "error": "Invalid domain format",
            }

        # Check if domain is already in use
        existing = await self._get_domain_by_name(domain)
        if existing and existing.beacon_id != beacon_id:
            return {
                "success": False,
                "error": "Domain is already in use by another beacon",
            }

        # Create domain config
        config = CustomDomainConfig(
            beacon_id=beacon_id,
            domain=domain,
            status=DomainStatus.PENDING,
            expected_ip=expected_ip,
            created_at=datetime.now(),
        )

        # Store the domain
        await self._save_domain(config)

        logger.info(f"Custom domain added: {domain} for beacon {beacon_id}")

        return {
            "success": True,
            "domain": domain,
            "status": config.status.value,
            "expected_ip": expected_ip,
            "message": "Domain saved. Please configure DNS and verify.",
        }

    async def remove_domain(self, beacon_id: str) -> Dict[str, Any]:
        """
        Remove a custom domain from a beacon.

        Args:
            beacon_id: ID of the beacon

        Returns:
            Dict with success status
        """
        config = await self._get_domain_by_beacon(beacon_id)
        if not config:
            return {
                "success": True,
                "message": "No custom domain configured",
            }

        domain = config.domain

        # Remove from Caddy if active
        if config.status == DomainStatus.ACTIVE:
            await self._remove_caddy_route(domain)

        # Remove from storage
        await self._delete_domain(beacon_id)

        logger.info(f"Custom domain removed: {domain} from beacon {beacon_id}")

        return {
            "success": True,
            "domain": domain,
            "message": f"Domain {domain} removed",
        }

    async def verify_dns(
        self,
        domain: str,
        expected_ip: str,
    ) -> DNSVerificationResult:
        """
        Verify DNS propagation for a domain.

        Checks:
        1. A record for the root domain
        2. Wildcard A record (tested via random subdomain)

        Args:
            domain: The domain to verify
            expected_ip: Expected IP address

        Returns:
            DNSVerificationResult with detailed status
        """
        errors = []
        a_record_status = "missing"
        a_record_ip = None
        wildcard_status = "missing"
        wildcard_ip = None

        # Check A record for root domain
        try:
            a_record_ip = await self._resolve_dns(domain)
            if a_record_ip == expected_ip:
                a_record_status = "verified"
            else:
                a_record_status = "wrong_ip"
                errors.append(f"A record points to {a_record_ip}, expected {expected_ip}")
        except Exception as e:
            a_record_status = "missing"
            errors.append(f"No A record found for {domain}: {e}")

        # Check wildcard A record (test with a verification subdomain)
        test_subdomain = f"_wopr-dns-verify.{domain}"
        try:
            wildcard_ip = await self._resolve_dns(test_subdomain)
            if wildcard_ip == expected_ip:
                wildcard_status = "verified"
            else:
                wildcard_status = "wrong_ip"
                errors.append(f"Wildcard record points to {wildcard_ip}, expected {expected_ip}")
        except Exception as e:
            wildcard_status = "missing"
            errors.append(f"No wildcard A record found for *.{domain}: {e}")

        verified = (a_record_status == "verified" and wildcard_status == "verified")

        return DNSVerificationResult(
            verified=verified,
            domain=domain,
            expected_ip=expected_ip,
            a_record_status=a_record_status,
            a_record_ip=a_record_ip,
            wildcard_status=wildcard_status,
            wildcard_ip=wildcard_ip,
            errors=errors,
            checked_at=datetime.now().isoformat(),
        )

    async def verify_and_activate(self, beacon_id: str) -> Dict[str, Any]:
        """
        Verify DNS and activate a custom domain if verification passes.

        This is the main method to call after DNS has been configured.
        It will:
        1. Verify DNS propagation
        2. If verified, configure Caddy to handle the domain
        3. Let's Encrypt will automatically provision SSL

        Args:
            beacon_id: ID of the beacon

        Returns:
            Dict with verification result and activation status
        """
        config = await self._get_domain_by_beacon(beacon_id)
        if not config:
            return {
                "success": False,
                "error": "No custom domain configured",
            }

        # Update status to verifying
        config.status = DomainStatus.VERIFYING
        config.last_check_at = datetime.now()
        await self._save_domain(config)

        # Verify DNS
        result = await self.verify_dns(config.domain, config.expected_ip)

        if result.verified:
            # Configure Caddy for the domain
            caddy_success = await self._configure_caddy_route(
                domain=config.domain,
                upstream=f"http://{config.expected_ip}:80",
            )

            if caddy_success:
                config.status = DomainStatus.ACTIVE
                config.verified_at = datetime.now()
                config.error_message = None
                await self._save_domain(config)

                logger.info(f"Custom domain activated: {config.domain}")

                return {
                    "success": True,
                    "verified": True,
                    "activated": True,
                    "domain": config.domain,
                    "status": "active",
                    "message": "Domain verified and activated successfully!",
                }
            else:
                config.status = DomainStatus.FAILED
                config.error_message = "Failed to configure Caddy"
                await self._save_domain(config)

                return {
                    "success": False,
                    "verified": True,
                    "activated": False,
                    "error": "DNS verified but failed to configure web server",
                }
        else:
            config.status = DomainStatus.PENDING
            config.error_message = "; ".join(result.errors)
            await self._save_domain(config)

            return {
                "success": False,
                "verified": False,
                "domain": config.domain,
                "status": "pending",
                "a_record_status": result.a_record_status,
                "wildcard_status": result.wildcard_status,
                "errors": result.errors,
                "message": "DNS verification failed. Please check your DNS configuration.",
            }

    async def get_domain_status(self, beacon_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a beacon's custom domain.

        Args:
            beacon_id: ID of the beacon

        Returns:
            Dict with domain status or None if not configured
        """
        config = await self._get_domain_by_beacon(beacon_id)
        if not config:
            return None

        return {
            "domain": config.domain,
            "status": config.status.value,
            "expected_ip": config.expected_ip,
            "created_at": config.created_at.isoformat(),
            "verified_at": config.verified_at.isoformat() if config.verified_at else None,
            "ssl_issued_at": config.ssl_issued_at.isoformat() if config.ssl_issued_at else None,
            "ssl_expires_at": config.ssl_expires_at.isoformat() if config.ssl_expires_at else None,
            "last_check_at": config.last_check_at.isoformat() if config.last_check_at else None,
            "error_message": config.error_message,
        }

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if a domain name is valid."""
        import re
        pattern = r'^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$'
        return bool(re.match(pattern, domain.lower()))

    async def _resolve_dns(self, hostname: str) -> str:
        """
        Resolve a hostname to an IP address.

        Args:
            hostname: The hostname to resolve

        Returns:
            IP address string

        Raises:
            Exception if resolution fails
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, socket.gethostbyname, hostname)
        return result

    async def _get_domain_by_beacon(self, beacon_id: str) -> Optional[CustomDomainConfig]:
        """Get custom domain config by beacon ID."""
        if self.db_pool:
            # TODO: Implement database lookup
            pass

        return self._domains.get(beacon_id)

    async def _get_domain_by_name(self, domain: str) -> Optional[CustomDomainConfig]:
        """Get custom domain config by domain name."""
        if self.db_pool:
            # TODO: Implement database lookup
            pass

        for config in self._domains.values():
            if config.domain == domain:
                return config
        return None

    async def _save_domain(self, config: CustomDomainConfig) -> None:
        """Save custom domain config."""
        if self.db_pool:
            # TODO: Implement database save
            pass

        self._domains[config.beacon_id] = config

    async def _delete_domain(self, beacon_id: str) -> None:
        """Delete custom domain config."""
        if self.db_pool:
            # TODO: Implement database delete
            pass

        self._domains.pop(beacon_id, None)

    async def _configure_caddy_route(
        self,
        domain: str,
        upstream: str,
    ) -> bool:
        """
        Configure Caddy to handle a custom domain.

        Uses Caddy's admin API to add a route for the domain.
        SSL certificates are automatically provisioned by Caddy.

        Args:
            domain: The custom domain
            upstream: The upstream server URL

        Returns:
            True if configuration succeeded
        """
        try:
            # Caddy route configuration
            # This adds routes for both the root domain and wildcard
            route_config = {
                "@id": f"custom-domain-{domain.replace('.', '-')}",
                "match": [
                    {"host": [domain, f"*.{domain}"]},
                ],
                "handle": [
                    {
                        "handler": "reverse_proxy",
                        "upstreams": [{"dial": upstream.replace("http://", "").replace("https://", "")}],
                    }
                ],
                "terminal": True,
            }

            async with httpx.AsyncClient() as client:
                # Add the route via Caddy API
                response = await client.post(
                    f"{self.caddy_api_url}/config/apps/http/servers/srv0/routes",
                    json=route_config,
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    logger.info(f"Caddy route configured for {domain}")
                    return True
                else:
                    logger.error(f"Caddy API error: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Failed to configure Caddy for {domain}: {e}")
            return False

    async def _remove_caddy_route(self, domain: str) -> bool:
        """
        Remove a custom domain route from Caddy.

        Args:
            domain: The custom domain

        Returns:
            True if removal succeeded
        """
        try:
            route_id = f"custom-domain-{domain.replace('.', '-')}"

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.caddy_api_url}/id/{route_id}",
                    timeout=30.0,
                )

                if response.status_code in (200, 204):
                    logger.info(f"Caddy route removed for {domain}")
                    return True
                else:
                    logger.warning(f"Caddy route removal returned: {response.status_code}")
                    return True  # Route might not exist, which is fine

        except Exception as e:
            logger.error(f"Failed to remove Caddy route for {domain}: {e}")
            return False

    async def check_ssl_certificate(self, domain: str) -> Dict[str, Any]:
        """
        Check SSL certificate status for a domain.

        Args:
            domain: The domain to check

        Returns:
            Dict with certificate status
        """
        try:
            context = ssl.create_default_context()

            loop = asyncio.get_event_loop()

            def _check():
                with socket.create_connection((domain, 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()
                        return cert

            cert = await loop.run_in_executor(None, _check)

            if cert:
                not_after = cert.get("notAfter", "")
                # Parse the date (format: 'Sep 30 23:59:59 2023 GMT')
                from datetime import datetime
                expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")

                return {
                    "valid": True,
                    "domain": domain,
                    "issuer": dict(cert.get("issuer", [])),
                    "expires_at": expires.isoformat(),
                    "days_until_expiry": (expires - datetime.now()).days,
                }

        except Exception as e:
            return {
                "valid": False,
                "domain": domain,
                "error": str(e),
            }


# ============================================================================
# DNS Record Instructions Generator
# ============================================================================

def get_dns_instructions(domain: str, ip_address: str) -> Dict[str, Any]:
    """
    Generate DNS configuration instructions for a custom domain.

    Args:
        domain: The custom domain
        ip_address: The target IP address

    Returns:
        Dict with DNS records and instructions
    """
    # Determine if this is a subdomain or root domain
    parts = domain.split(".")
    is_subdomain = len(parts) > 2

    if is_subdomain:
        # For subdomains like "cloud.example.com"
        subdomain = parts[0]
        root_domain = ".".join(parts[1:])

        records = [
            {
                "type": "A",
                "name": subdomain,
                "value": ip_address,
                "ttl": 300,
                "purpose": f"Points {domain} to your server",
            },
            {
                "type": "A",
                "name": f"*.{subdomain}",
                "value": ip_address,
                "ttl": 300,
                "purpose": f"Wildcard for app subdomains (auth.{domain}, files.{domain}, etc.)",
            },
        ]
    else:
        # For root domains like "example.com"
        records = [
            {
                "type": "A",
                "name": "@",
                "value": ip_address,
                "ttl": 300,
                "purpose": f"Points {domain} to your server",
            },
            {
                "type": "A",
                "name": "*",
                "value": ip_address,
                "ttl": 300,
                "purpose": f"Wildcard for app subdomains (auth.{domain}, files.{domain}, etc.)",
            },
        ]

    return {
        "domain": domain,
        "ip_address": ip_address,
        "records": records,
        "notes": [
            "DNS changes typically propagate within 5-30 minutes, but can take up to 48 hours.",
            "The wildcard (*) record is required for WOPR apps to work on subdomains.",
            "If using Cloudflare, set records to 'DNS only' (gray cloud), not 'Proxied'.",
            "TTL of 300 seconds (5 minutes) is recommended for initial setup.",
        ],
    }
