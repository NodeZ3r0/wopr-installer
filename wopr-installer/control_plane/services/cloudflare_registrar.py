"""
WOPR Cloudflare Registrar Service
===================================

Manages domain registration and purchase via the Cloudflare Registrar API.

Handles:
- Domain availability checking
- Domain pricing lookup for supported TLDs
- Domain registration through Cloudflare (requires user's Cloudflare account)
- Auto-configuration of DNS after purchase

Uses the official cloudflare Python SDK.
Requires: pip install cloudflare
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import cloudflare as cf
    CLOUDFLARE_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AVAILABLE = False
    logger.warning("cloudflare package not installed. Run: pip install cloudflare")


class DomainStatus(Enum):
    """Domain availability status."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREMIUM = "premium"
    UNKNOWN = "unknown"


@dataclass
class DomainAvailability:
    """Domain availability check result."""
    domain: str
    available: bool
    status: DomainStatus
    premium: bool = False
    premium_price: Optional[float] = None
    message: Optional[str] = None


@dataclass
class DomainPricing:
    """Domain pricing information."""
    tld: str
    registration_price: float
    renewal_price: float
    transfer_price: Optional[float] = None
    currency: str = "USD"
    icann_fee: float = 0.18  # Standard ICANN fee


@dataclass
class RegisteredDomain:
    """Registered domain information."""
    domain: str
    registrar: str = "cloudflare"
    status: str = "active"
    expires_at: Optional[str] = None
    auto_renew: bool = True
    locked: bool = True
    nameservers: List[str] = None

    def __post_init__(self):
        if self.nameservers is None:
            self.nameservers = []


@dataclass
class DomainRegistrationRequest:
    """Request to register a new domain."""
    domain: str
    years: int = 1
    auto_renew: bool = True
    privacy: bool = True
    # Registrant contact info
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    address1: str = ""
    address2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "US"
    organization: Optional[str] = None


class CloudflareRegistrar:
    """
    Cloudflare Registrar integration for domain registration.

    Provides domain availability checking, pricing lookup, and domain
    purchase capabilities through the Cloudflare Registrar API.
    """

    # Cloudflare-supported TLDs with approximate at-cost pricing
    # These are Cloudflare's wholesale prices (no markup)
    SUPPORTED_TLDS: Dict[str, DomainPricing] = {
        "com": DomainPricing("com", 9.77, 9.77, 9.77),
        "net": DomainPricing("net", 10.77, 10.77, 10.77),
        "org": DomainPricing("org", 10.11, 10.11, 10.11),
        "io": DomainPricing("io", 44.99, 44.99, 44.99),
        "co": DomainPricing("co", 11.99, 11.99, 11.99),
        "dev": DomainPricing("dev", 12.00, 12.00, 12.00),
        "app": DomainPricing("app", 14.00, 14.00, 14.00),
        "ai": DomainPricing("ai", 90.00, 90.00, 90.00),
        "me": DomainPricing("me", 7.00, 7.00, 7.00),
        "xyz": DomainPricing("xyz", 10.00, 10.00, 10.00),
        "info": DomainPricing("info", 8.00, 8.00, 8.00),
        "biz": DomainPricing("biz", 8.00, 8.00, 8.00),
        "tech": DomainPricing("tech", 12.00, 12.00, 12.00),
        "online": DomainPricing("online", 10.00, 10.00, 10.00),
        "cloud": DomainPricing("cloud", 12.00, 12.00, 12.00),
        "sh": DomainPricing("sh", 45.00, 45.00, 45.00),
        "systems": DomainPricing("systems", 20.00, 20.00, 20.00),
    }

    def __init__(self, api_token: str, account_id: str):
        """
        Initialize with Cloudflare API token and account ID.

        Args:
            api_token: Cloudflare API token with Registrar permissions
            account_id: Cloudflare account ID for domain registration
        """
        if not CLOUDFLARE_AVAILABLE:
            raise ImportError("cloudflare package not installed")

        self.account_id = account_id
        self.client = cf.Cloudflare(api_token=api_token)

    async def check_availability(self, domain: str) -> DomainAvailability:
        """
        Check if a domain is available for registration.

        Args:
            domain: Full domain name (e.g., "example.com")

        Returns:
            DomainAvailability with availability status
        """
        import asyncio

        def _check():
            try:
                # Use the registrar domains endpoint to check availability
                result = self.client.registrar.domains.get(
                    domain_name=domain,
                    account_id=self.account_id,
                )
                # If we get a result, domain is already registered (possibly by us)
                return DomainAvailability(
                    domain=domain,
                    available=False,
                    status=DomainStatus.UNAVAILABLE,
                    message="Domain is already registered"
                )
            except cf.NotFoundError:
                # Domain not found in our account - could be available
                # Need to use whois/availability check
                return self._check_domain_whois(domain)
            except cf.APIError as e:
                if "not available" in str(e).lower():
                    return DomainAvailability(
                        domain=domain,
                        available=False,
                        status=DomainStatus.UNAVAILABLE,
                        message=str(e)
                    )
                raise

        return await asyncio.to_thread(_check)

    def _check_domain_whois(self, domain: str) -> DomainAvailability:
        """
        Check domain availability via WHOIS-like lookup.

        This is a simplified check - in production, you'd use Cloudflare's
        actual availability check endpoint or a WHOIS service.
        """
        try:
            # Try to get domain info - if it fails with specific error, it's available
            # Cloudflare's API will indicate availability in the error message
            import socket
            # Simple DNS check as a proxy for availability
            try:
                socket.gethostbyname(domain)
                # If DNS resolves, domain is likely taken
                return DomainAvailability(
                    domain=domain,
                    available=False,
                    status=DomainStatus.UNAVAILABLE,
                    message="Domain has active DNS records"
                )
            except socket.gaierror:
                # DNS doesn't resolve - domain might be available
                # This is not definitive - proper WHOIS check needed
                return DomainAvailability(
                    domain=domain,
                    available=True,
                    status=DomainStatus.AVAILABLE,
                    message="Domain appears available (DNS check)"
                )
        except Exception as e:
            logger.warning(f"WHOIS check failed for {domain}: {e}")
            return DomainAvailability(
                domain=domain,
                available=False,
                status=DomainStatus.UNKNOWN,
                message=f"Unable to determine availability: {e}"
            )

    async def check_availability_bulk(
        self, domain_base: str, tlds: Optional[List[str]] = None
    ) -> List[DomainAvailability]:
        """
        Check availability across multiple TLDs.

        Args:
            domain_base: Domain name without TLD (e.g., "mycompany")
            tlds: List of TLDs to check (defaults to popular TLDs)

        Returns:
            List of DomainAvailability for each TLD
        """
        import asyncio

        if tlds is None:
            tlds = ["com", "net", "org", "io", "co", "dev", "app"]

        # Filter to supported TLDs
        tlds = [tld for tld in tlds if tld in self.SUPPORTED_TLDS]

        tasks = [
            self.check_availability(f"{domain_base}.{tld}")
            for tld in tlds
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_pricing(self, tld: str) -> Optional[DomainPricing]:
        """
        Get pricing for a specific TLD.

        Args:
            tld: Top-level domain (e.g., "com", "io")

        Returns:
            DomainPricing or None if TLD not supported
        """
        return self.SUPPORTED_TLDS.get(tld.lower().lstrip("."))

    def get_all_pricing(self) -> Dict[str, DomainPricing]:
        """
        Get pricing for all supported TLDs.

        Returns:
            Dict mapping TLD to DomainPricing
        """
        return self.SUPPORTED_TLDS.copy()

    def get_supported_tlds(self) -> List[str]:
        """
        Get list of supported TLDs for registration.

        Returns:
            List of TLD strings
        """
        return list(self.SUPPORTED_TLDS.keys())

    async def register_domain(
        self, request: DomainRegistrationRequest
    ) -> RegisteredDomain:
        """
        Register a new domain through Cloudflare Registrar.

        Args:
            request: DomainRegistrationRequest with domain and contact info

        Returns:
            RegisteredDomain on success

        Raises:
            ValueError: If domain is unavailable or TLD not supported
            cloudflare.APIError: On API failure
        """
        import asyncio

        # Validate TLD is supported
        tld = request.domain.split(".")[-1].lower()
        if tld not in self.SUPPORTED_TLDS:
            raise ValueError(f"TLD .{tld} is not supported by Cloudflare Registrar")

        # Check availability first
        availability = await self.check_availability(request.domain)
        if not availability.available:
            raise ValueError(
                f"Domain {request.domain} is not available: {availability.message}"
            )

        def _register():
            try:
                # Cloudflare Registrar domain registration
                # Note: Actual API call structure may vary - consult Cloudflare docs
                result = self.client.registrar.domains.create(
                    account_id=self.account_id,
                    name=request.domain,
                    auto_renew=request.auto_renew,
                    locked=True,
                    privacy=request.privacy,
                    # Contact information
                    registrant={
                        "first_name": request.first_name,
                        "last_name": request.last_name,
                        "email": request.email,
                        "phone": request.phone,
                        "address": request.address1,
                        "address2": request.address2 or None,
                        "city": request.city,
                        "state": request.state,
                        "zip": request.postal_code,
                        "country": request.country,
                        "organization": request.organization,
                    },
                )

                return RegisteredDomain(
                    domain=request.domain,
                    registrar="cloudflare",
                    status="active",
                    expires_at=getattr(result, "expires_at", None),
                    auto_renew=request.auto_renew,
                    locked=True,
                    nameservers=getattr(result, "name_servers", []),
                )
            except cf.APIError as e:
                logger.error(f"Domain registration failed: {e}")
                raise

        registered = await asyncio.to_thread(_register)
        logger.info(f"Registered domain: {request.domain}")
        return registered

    async def list_domains(self) -> List[RegisteredDomain]:
        """
        List all domains registered in this Cloudflare account.

        Returns:
            List of RegisteredDomain objects
        """
        import asyncio

        def _list():
            try:
                results = self.client.registrar.domains.list(
                    account_id=self.account_id,
                )
                return [
                    RegisteredDomain(
                        domain=d.name,
                        registrar="cloudflare",
                        status=getattr(d, "status", "active"),
                        expires_at=getattr(d, "expires_at", None),
                        auto_renew=getattr(d, "auto_renew", True),
                        locked=getattr(d, "locked", True),
                        nameservers=getattr(d, "name_servers", []),
                    )
                    for d in results
                ]
            except cf.APIError as e:
                logger.error(f"Failed to list domains: {e}")
                raise

        return await asyncio.to_thread(_list)

    async def get_domain(self, domain: str) -> Optional[RegisteredDomain]:
        """
        Get details for a specific registered domain.

        Args:
            domain: Domain name to look up

        Returns:
            RegisteredDomain or None if not found
        """
        import asyncio

        def _get():
            try:
                result = self.client.registrar.domains.get(
                    domain_name=domain,
                    account_id=self.account_id,
                )
                return RegisteredDomain(
                    domain=result.name,
                    registrar="cloudflare",
                    status=getattr(result, "status", "active"),
                    expires_at=getattr(result, "expires_at", None),
                    auto_renew=getattr(result, "auto_renew", True),
                    locked=getattr(result, "locked", True),
                    nameservers=getattr(result, "name_servers", []),
                )
            except cf.NotFoundError:
                return None
            except cf.APIError as e:
                logger.error(f"Failed to get domain {domain}: {e}")
                raise

        return await asyncio.to_thread(_get)

    async def update_domain_settings(
        self,
        domain: str,
        auto_renew: Optional[bool] = None,
        locked: Optional[bool] = None,
    ) -> bool:
        """
        Update domain settings.

        Args:
            domain: Domain name to update
            auto_renew: Enable/disable auto-renewal
            locked: Enable/disable transfer lock

        Returns:
            True if updated successfully
        """
        import asyncio

        def _update():
            try:
                params = {}
                if auto_renew is not None:
                    params["auto_renew"] = auto_renew
                if locked is not None:
                    params["locked"] = locked

                if not params:
                    return True

                self.client.registrar.domains.update(
                    domain_name=domain,
                    account_id=self.account_id,
                    **params,
                )
                return True
            except cf.APIError as e:
                logger.error(f"Failed to update domain {domain}: {e}")
                return False

        result = await asyncio.to_thread(_update)
        if result:
            logger.info(f"Updated domain settings: {domain}")
        return result

    async def configure_dns_for_wopr(
        self,
        domain: str,
        beacon_ip: str,
        dns_service: "CloudflareDNS",
    ) -> Dict[str, str]:
        """
        Auto-configure DNS for a newly registered domain for WOPR use.

        Creates the standard WOPR DNS records:
        - A record for root domain
        - Wildcard A record for subdomains

        Args:
            domain: The registered domain
            beacon_ip: IP address of the WOPR beacon
            dns_service: CloudflareDNS instance for the zone

        Returns:
            Dict mapping record names to record IDs
        """
        record_ids = {}

        # Create A record for root domain
        try:
            root_id = await dns_service.create_a_record(
                name=domain,
                ip=beacon_ip,
                proxied=False,
                ttl=300,
            )
            record_ids[domain] = root_id
            logger.info(f"Created A record: {domain} -> {beacon_ip}")
        except Exception as e:
            logger.error(f"Failed to create root A record for {domain}: {e}")
            raise

        # Create wildcard A record for all subdomains
        try:
            wildcard = f"*.{domain}"
            wildcard_id = await dns_service.create_a_record(
                name=wildcard,
                ip=beacon_ip,
                proxied=False,
                ttl=300,
            )
            record_ids[wildcard] = wildcard_id
            logger.info(f"Created wildcard A record: {wildcard} -> {beacon_ip}")
        except Exception as e:
            logger.error(f"Failed to create wildcard A record for {domain}: {e}")
            raise

        return record_ids

    async def get_zone_for_domain(self, domain: str) -> Optional[str]:
        """
        Get the Cloudflare zone ID for a registered domain.

        After registration, Cloudflare creates a zone for the domain.
        This returns that zone ID for DNS management.

        Args:
            domain: The registered domain

        Returns:
            Zone ID string or None if not found
        """
        import asyncio

        def _get_zone():
            try:
                zones = self.client.zones.list(name=domain)
                for zone in zones:
                    if zone.name == domain:
                        return zone.id
                return None
            except cf.APIError as e:
                logger.error(f"Failed to get zone for {domain}: {e}")
                return None

        return await asyncio.to_thread(_get_zone)


# Convenience functions for API endpoints

async def check_domain_availability(
    api_token: str,
    account_id: str,
    domain: str,
) -> Dict[str, Any]:
    """
    Check if a domain is available for registration.

    Returns dict with availability info suitable for API response.
    """
    registrar = CloudflareRegistrar(api_token, account_id)
    result = await registrar.check_availability(domain)

    pricing = registrar.get_pricing(domain.split(".")[-1])

    return {
        "domain": result.domain,
        "available": result.available,
        "status": result.status.value,
        "premium": result.premium,
        "premium_price": result.premium_price,
        "message": result.message,
        "pricing": {
            "registration": pricing.registration_price if pricing else None,
            "renewal": pricing.renewal_price if pricing else None,
            "currency": pricing.currency if pricing else "USD",
        } if pricing else None,
    }


async def search_domains(
    api_token: str,
    account_id: str,
    query: str,
    tlds: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search for available domains across multiple TLDs.

    Returns list of availability results suitable for API response.
    """
    registrar = CloudflareRegistrar(api_token, account_id)

    # Clean up query - remove any TLD if present
    domain_base = query.split(".")[0].lower()

    results = await registrar.check_availability_bulk(domain_base, tlds)

    output = []
    for result in results:
        if isinstance(result, Exception):
            continue
        pricing = registrar.get_pricing(result.domain.split(".")[-1])
        output.append({
            "domain": result.domain,
            "available": result.available,
            "status": result.status.value,
            "price": pricing.registration_price if pricing else None,
            "renewal": pricing.renewal_price if pricing else None,
        })

    # Sort: available first, then by price
    output.sort(key=lambda x: (not x["available"], x["price"] or 999))

    return output


def get_tld_pricing() -> List[Dict[str, Any]]:
    """
    Get pricing for all supported TLDs.

    Returns list of pricing info suitable for API response.
    """
    return [
        {
            "tld": f".{pricing.tld}",
            "registration": pricing.registration_price,
            "renewal": pricing.renewal_price,
            "transfer": pricing.transfer_price,
            "currency": pricing.currency,
        }
        for pricing in CloudflareRegistrar.SUPPORTED_TLDS.values()
    ]
