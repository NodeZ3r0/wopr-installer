"""
WOPR Unified Domain Registrar Service
======================================

Provides a unified interface for domain registration across multiple registrars.

Supports:
- Cloudflare Registrar (at-cost pricing)
- Namecheap Registrar (competitive pricing)

Features:
- Search best prices across all configured registrars
- Route registration to the appropriate registrar
- Auto-configure DNS after purchase
- Unified Pydantic models for consistent API responses
"""

import logging
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Unified API Responses
# =============================================================================


class RegistrarName(str, Enum):
    """Supported registrars."""
    CLOUDFLARE = "cloudflare"
    NAMECHEAP = "namecheap"


class DomainAvailabilityStatus(str, Enum):
    """Domain availability status."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREMIUM = "premium"
    UNKNOWN = "unknown"


class RegistrarPricing(BaseModel):
    """Pricing information from a single registrar."""
    registrar: RegistrarName
    registration_price: Optional[float] = None
    renewal_price: Optional[float] = None
    transfer_price: Optional[float] = None
    currency: str = "USD"
    icann_fee: float = 0.18
    is_premium: bool = False
    premium_price: Optional[float] = None

    @property
    def total_first_year(self) -> Optional[float]:
        """Total cost for first year including ICANN fee."""
        if self.is_premium and self.premium_price:
            return self.premium_price + self.icann_fee
        if self.registration_price:
            return self.registration_price + self.icann_fee
        return None


class DomainSearchResult(BaseModel):
    """Unified domain search result with pricing from all registrars."""
    domain: str
    available: bool
    status: DomainAvailabilityStatus
    prices: List[RegistrarPricing] = Field(default_factory=list)
    best_price: Optional[RegistrarPricing] = None
    message: Optional[str] = None

    def calculate_best_price(self) -> None:
        """Set best_price to the lowest-priced available registrar."""
        available_prices = [
            p for p in self.prices
            if p.registration_price is not None
        ]
        if available_prices:
            self.best_price = min(
                available_prices,
                key=lambda p: p.total_first_year or float('inf')
            )


class MultiRegistrarSearchResponse(BaseModel):
    """Response containing search results across multiple TLDs and registrars."""
    query: str
    results: List[DomainSearchResult]
    registrars_queried: List[RegistrarName]


class DomainRegistrationRequest(BaseModel):
    """Unified domain registration request."""
    domain: str
    registrar: RegistrarName
    years: int = 1
    auto_renew: bool = True
    privacy: bool = True
    # Contact information
    first_name: str
    last_name: str
    email: str
    phone: str
    address1: str
    address2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "US"
    organization: Optional[str] = None


class RegisteredDomainResponse(BaseModel):
    """Unified response for a registered domain."""
    domain: str
    registrar: RegistrarName
    status: str = "active"
    expires_at: Optional[str] = None
    auto_renew: bool = True
    locked: bool = True
    nameservers: List[str] = Field(default_factory=list)
    dns_configured: bool = False
    dns_records: Dict[str, str] = Field(default_factory=dict)


# =============================================================================
# Unified Domain Registrar Service
# =============================================================================


class DomainRegistrar:
    """
    Unified domain registrar that queries multiple registrar APIs.

    Aggregates pricing from Cloudflare and Namecheap to find the best prices,
    and routes registration requests to the appropriate registrar.
    """

    def __init__(
        self,
        # Cloudflare credentials
        cloudflare_api_token: Optional[str] = None,
        cloudflare_account_id: Optional[str] = None,
        # Namecheap credentials
        namecheap_api_user: Optional[str] = None,
        namecheap_api_key: Optional[str] = None,
        namecheap_username: Optional[str] = None,
        namecheap_client_ip: Optional[str] = None,
        namecheap_sandbox: bool = False,
        # DNS configuration
        dns_zone_id: Optional[str] = None,
    ):
        """
        Initialize with credentials for each registrar.

        Only registrars with complete credentials will be enabled.
        """
        self._cloudflare = None
        self._namecheap = None
        self._dns_service = None
        self._dns_zone_id = dns_zone_id

        # Initialize Cloudflare if credentials provided
        if cloudflare_api_token and cloudflare_account_id:
            try:
                from .cloudflare_registrar import CloudflareRegistrar
                self._cloudflare = CloudflareRegistrar(
                    api_token=cloudflare_api_token,
                    account_id=cloudflare_account_id,
                )
                logger.info("Cloudflare registrar initialized")
            except ImportError as e:
                logger.warning(f"Cloudflare registrar unavailable: {e}")

            # Also initialize DNS service for auto-configuration
            if dns_zone_id:
                try:
                    from .cloudflare_dns import CloudflareDNS
                    self._dns_service = CloudflareDNS(
                        api_token=cloudflare_api_token,
                        zone_id=dns_zone_id,
                    )
                    logger.info("Cloudflare DNS service initialized")
                except ImportError as e:
                    logger.warning(f"Cloudflare DNS service unavailable: {e}")

        # Initialize Namecheap if credentials provided
        if all([namecheap_api_user, namecheap_api_key, namecheap_username, namecheap_client_ip]):
            try:
                from .namecheap_registrar import NamecheapRegistrar
                self._namecheap = NamecheapRegistrar(
                    api_user=namecheap_api_user,
                    api_key=namecheap_api_key,
                    username=namecheap_username,
                    client_ip=namecheap_client_ip,
                    sandbox=namecheap_sandbox,
                )
                logger.info("Namecheap registrar initialized")
            except ImportError as e:
                logger.warning(f"Namecheap registrar unavailable: {e}")

    @property
    def available_registrars(self) -> List[RegistrarName]:
        """List of configured and available registrars."""
        registrars = []
        if self._cloudflare:
            registrars.append(RegistrarName.CLOUDFLARE)
        if self._namecheap:
            registrars.append(RegistrarName.NAMECHEAP)
        return registrars

    @property
    def cloudflare_configured(self) -> bool:
        """Check if Cloudflare is configured."""
        return self._cloudflare is not None

    @property
    def namecheap_configured(self) -> bool:
        """Check if Namecheap is configured."""
        return self._namecheap is not None

    def get_supported_tlds(self) -> List[str]:
        """Get union of supported TLDs from all registrars."""
        tlds = set()
        if self._cloudflare:
            tlds.update(self._cloudflare.get_supported_tlds())
        if self._namecheap:
            tlds.update(self._namecheap.get_supported_tlds())
        return sorted(list(tlds))

    async def search_best_price(
        self,
        domain: str,
        tlds: Optional[List[str]] = None,
    ) -> MultiRegistrarSearchResponse:
        """
        Search for domain availability and get prices from all registrars.

        Args:
            domain: Domain name (with or without TLD)
            tlds: Optional list of TLDs to check (if domain has no TLD)

        Returns:
            MultiRegistrarSearchResponse with results sorted by price
        """
        # Parse domain
        parts = domain.lower().strip().split(".")
        if len(parts) >= 2 and parts[-1] in self.get_supported_tlds():
            # Full domain provided
            domain_base = ".".join(parts[:-1])
            search_tlds = [parts[-1]]
        else:
            # Just the name, search across TLDs
            domain_base = parts[0]
            search_tlds = tlds or ["com", "net", "org", "io", "co", "dev", "app"]

        # Gather results from all registrars in parallel
        tasks = []

        if self._cloudflare:
            tasks.append(self._search_cloudflare(domain_base, search_tlds))

        if self._namecheap:
            tasks.append(self._search_namecheap(domain_base, search_tlds))

        # Execute all searches in parallel
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results by domain
        domain_results: Dict[str, DomainSearchResult] = {}

        for registrar_results in all_results:
            if isinstance(registrar_results, Exception):
                logger.error(f"Registrar search failed: {registrar_results}")
                continue

            for domain_name, availability, pricing in registrar_results:
                if domain_name not in domain_results:
                    domain_results[domain_name] = DomainSearchResult(
                        domain=domain_name,
                        available=availability,
                        status=(
                            DomainAvailabilityStatus.AVAILABLE if availability
                            else DomainAvailabilityStatus.UNAVAILABLE
                        ),
                        prices=[],
                    )

                # Update availability (available if any registrar says available)
                if availability:
                    domain_results[domain_name].available = True
                    domain_results[domain_name].status = DomainAvailabilityStatus.AVAILABLE

                # Add pricing
                if pricing:
                    domain_results[domain_name].prices.append(pricing)

        # Calculate best price for each domain
        results = list(domain_results.values())
        for result in results:
            result.calculate_best_price()

        # Sort by: available first, then by best price
        results.sort(key=lambda r: (
            not r.available,
            r.best_price.total_first_year if r.best_price else float('inf')
        ))

        return MultiRegistrarSearchResponse(
            query=domain_base,
            results=results,
            registrars_queried=self.available_registrars,
        )

    async def _search_cloudflare(
        self,
        domain_base: str,
        tlds: List[str],
    ) -> List[tuple]:
        """Search Cloudflare for domain availability."""
        results = []

        try:
            # Filter to Cloudflare-supported TLDs
            cf_tlds = [t for t in tlds if t in self._cloudflare.SUPPORTED_TLDS]

            for tld in cf_tlds:
                domain = f"{domain_base}.{tld}"
                try:
                    availability = await self._cloudflare.check_availability(domain)
                    pricing_info = self._cloudflare.get_pricing(tld)

                    pricing = RegistrarPricing(
                        registrar=RegistrarName.CLOUDFLARE,
                        registration_price=pricing_info.registration_price if pricing_info else None,
                        renewal_price=pricing_info.renewal_price if pricing_info else None,
                        transfer_price=pricing_info.transfer_price if pricing_info else None,
                        is_premium=availability.premium,
                        premium_price=availability.premium_price,
                    )

                    results.append((domain, availability.available, pricing))

                except Exception as e:
                    logger.warning(f"Cloudflare check failed for {domain}: {e}")
                    results.append((domain, False, None))

        except Exception as e:
            logger.error(f"Cloudflare search failed: {e}")

        return results

    async def _search_namecheap(
        self,
        domain_base: str,
        tlds: List[str],
    ) -> List[tuple]:
        """Search Namecheap for domain availability."""
        results = []

        try:
            # Namecheap supports bulk checking
            availability_results = await self._namecheap.check_availability_bulk(
                domain_base, tlds
            )

            for availability in availability_results:
                tld = availability.domain.split(".")[-1]
                pricing_info = self._namecheap.get_estimated_pricing(tld)

                pricing = RegistrarPricing(
                    registrar=RegistrarName.NAMECHEAP,
                    registration_price=pricing_info.registration_price if pricing_info else None,
                    renewal_price=pricing_info.renewal_price if pricing_info else None,
                    transfer_price=pricing_info.transfer_price if pricing_info else None,
                    is_premium=availability.premium,
                    premium_price=availability.premium_price,
                )

                results.append((availability.domain, availability.available, pricing))

        except Exception as e:
            logger.error(f"Namecheap search failed: {e}")

        return results

    async def register_domain(
        self,
        request: DomainRegistrationRequest,
        beacon_ip: Optional[str] = None,
    ) -> RegisteredDomainResponse:
        """
        Register a domain through the specified registrar.

        Args:
            request: DomainRegistrationRequest with domain and registrar choice
            beacon_ip: Optional IP for auto DNS configuration

        Returns:
            RegisteredDomainResponse with registration details

        Raises:
            ValueError: If registrar not configured or domain unavailable
        """
        if request.registrar == RegistrarName.CLOUDFLARE:
            return await self._register_cloudflare(request, beacon_ip)
        elif request.registrar == RegistrarName.NAMECHEAP:
            return await self._register_namecheap(request, beacon_ip)
        else:
            raise ValueError(f"Unknown registrar: {request.registrar}")

    async def _register_cloudflare(
        self,
        request: DomainRegistrationRequest,
        beacon_ip: Optional[str] = None,
    ) -> RegisteredDomainResponse:
        """Register domain through Cloudflare."""
        if not self._cloudflare:
            raise ValueError("Cloudflare registrar not configured")

        from .cloudflare_registrar import DomainRegistrationRequest as CFRequest

        cf_request = CFRequest(
            domain=request.domain,
            years=request.years,
            auto_renew=request.auto_renew,
            privacy=request.privacy,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            address1=request.address1,
            address2=request.address2 or "",
            city=request.city,
            state=request.state,
            postal_code=request.postal_code,
            country=request.country,
            organization=request.organization,
        )

        registered = await self._cloudflare.register_domain(cf_request)

        response = RegisteredDomainResponse(
            domain=registered.domain,
            registrar=RegistrarName.CLOUDFLARE,
            status=registered.status,
            expires_at=registered.expires_at,
            auto_renew=registered.auto_renew,
            locked=registered.locked,
            nameservers=registered.nameservers,
        )

        # Auto-configure DNS if beacon IP provided and DNS service available
        if beacon_ip and self._dns_service:
            try:
                # Get zone for newly registered domain
                zone_id = await self._cloudflare.get_zone_for_domain(request.domain)
                if zone_id:
                    from .cloudflare_dns import CloudflareDNS
                    dns = CloudflareDNS(
                        api_token=self._cloudflare.client.api_token,
                        zone_id=zone_id,
                    )
                    record_ids = await self._cloudflare.configure_dns_for_wopr(
                        domain=request.domain,
                        beacon_ip=beacon_ip,
                        dns_service=dns,
                    )
                    response.dns_configured = True
                    response.dns_records = record_ids
            except Exception as e:
                logger.warning(f"DNS auto-configuration failed: {e}")

        return response

    async def _register_namecheap(
        self,
        request: DomainRegistrationRequest,
        beacon_ip: Optional[str] = None,
    ) -> RegisteredDomainResponse:
        """Register domain through Namecheap."""
        if not self._namecheap:
            raise ValueError("Namecheap registrar not configured")

        from .namecheap_registrar import NamecheapRegistrationRequest as NCRequest

        nc_request = NCRequest(
            domain=request.domain,
            years=request.years,
            auto_renew=request.auto_renew,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            address1=request.address1,
            address2=request.address2 or "",
            city=request.city,
            state=request.state,
            postal_code=request.postal_code,
            country=request.country,
            organization=request.organization,
            add_free_whois_guard=request.privacy,
        )

        registered = await self._namecheap.register_domain(nc_request)

        response = RegisteredDomainResponse(
            domain=registered.domain,
            registrar=RegistrarName.NAMECHEAP,
            status=registered.status,
            expires_at=registered.expires_at,
            auto_renew=registered.auto_renew,
            locked=registered.locked,
            nameservers=registered.nameservers,
        )

        # For Namecheap, DNS configuration requires setting nameservers
        # to point to Cloudflare (if using Cloudflare DNS) or using
        # Namecheap's BasicDNS
        if beacon_ip:
            try:
                # If we have a Cloudflare DNS zone, set up the domain there
                if self._dns_service and self._dns_zone_id:
                    # Create A records in the existing Cloudflare zone
                    # Note: This requires the domain to point to Cloudflare nameservers
                    logger.info(
                        f"Domain {request.domain} registered with Namecheap. "
                        f"Configure nameservers to use Cloudflare for DNS management."
                    )
            except Exception as e:
                logger.warning(f"DNS configuration note: {e}")

        return response

    async def get_all_pricing(self) -> Dict[str, Dict[str, RegistrarPricing]]:
        """
        Get pricing for all TLDs from all registrars.

        Returns:
            Dict mapping TLD to dict of registrar -> pricing
        """
        pricing: Dict[str, Dict[str, RegistrarPricing]] = {}

        if self._cloudflare:
            for tld, cf_pricing in self._cloudflare.get_all_pricing().items():
                if tld not in pricing:
                    pricing[tld] = {}
                pricing[tld]["cloudflare"] = RegistrarPricing(
                    registrar=RegistrarName.CLOUDFLARE,
                    registration_price=cf_pricing.registration_price,
                    renewal_price=cf_pricing.renewal_price,
                    transfer_price=cf_pricing.transfer_price,
                )

        if self._namecheap:
            for tld, nc_pricing in self._namecheap.get_all_estimated_pricing().items():
                if tld not in pricing:
                    pricing[tld] = {}
                pricing[tld]["namecheap"] = RegistrarPricing(
                    registrar=RegistrarName.NAMECHEAP,
                    registration_price=nc_pricing.registration_price,
                    renewal_price=nc_pricing.renewal_price,
                    transfer_price=nc_pricing.transfer_price,
                )

        return pricing


# =============================================================================
# Convenience Functions for API Endpoints
# =============================================================================


async def search_domains_multi_registrar(
    domain: str,
    tlds: Optional[List[str]] = None,
    # Cloudflare
    cloudflare_api_token: Optional[str] = None,
    cloudflare_account_id: Optional[str] = None,
    # Namecheap
    namecheap_api_user: Optional[str] = None,
    namecheap_api_key: Optional[str] = None,
    namecheap_username: Optional[str] = None,
    namecheap_client_ip: Optional[str] = None,
    namecheap_sandbox: bool = False,
) -> Dict[str, Any]:
    """
    Search for domain availability across multiple registrars.

    Returns API-friendly dict with results sorted by best price.
    """
    registrar = DomainRegistrar(
        cloudflare_api_token=cloudflare_api_token,
        cloudflare_account_id=cloudflare_account_id,
        namecheap_api_user=namecheap_api_user,
        namecheap_api_key=namecheap_api_key,
        namecheap_username=namecheap_username,
        namecheap_client_ip=namecheap_client_ip,
        namecheap_sandbox=namecheap_sandbox,
    )

    response = await registrar.search_best_price(domain, tlds)

    return {
        "query": response.query,
        "registrars_queried": [r.value for r in response.registrars_queried],
        "results": [
            {
                "domain": r.domain,
                "available": r.available,
                "status": r.status.value,
                "prices": [
                    {
                        "registrar": p.registrar.value,
                        "registration": p.registration_price,
                        "renewal": p.renewal_price,
                        "total_first_year": p.total_first_year,
                        "is_premium": p.is_premium,
                        "premium_price": p.premium_price,
                    }
                    for p in r.prices
                ],
                "best_price": {
                    "registrar": r.best_price.registrar.value,
                    "registration": r.best_price.registration_price,
                    "renewal": r.best_price.renewal_price,
                    "total_first_year": r.best_price.total_first_year,
                } if r.best_price else None,
            }
            for r in response.results
        ],
    }


async def register_domain_multi_registrar(
    domain: str,
    registrar: str,
    contact_info: Dict[str, Any],
    beacon_ip: Optional[str] = None,
    # Cloudflare
    cloudflare_api_token: Optional[str] = None,
    cloudflare_account_id: Optional[str] = None,
    dns_zone_id: Optional[str] = None,
    # Namecheap
    namecheap_api_user: Optional[str] = None,
    namecheap_api_key: Optional[str] = None,
    namecheap_username: Optional[str] = None,
    namecheap_client_ip: Optional[str] = None,
    namecheap_sandbox: bool = False,
) -> Dict[str, Any]:
    """
    Register a domain through the specified registrar.

    Returns API-friendly dict with registration details.
    """
    registrar_service = DomainRegistrar(
        cloudflare_api_token=cloudflare_api_token,
        cloudflare_account_id=cloudflare_account_id,
        namecheap_api_user=namecheap_api_user,
        namecheap_api_key=namecheap_api_key,
        namecheap_username=namecheap_username,
        namecheap_client_ip=namecheap_client_ip,
        namecheap_sandbox=namecheap_sandbox,
        dns_zone_id=dns_zone_id,
    )

    request = DomainRegistrationRequest(
        domain=domain,
        registrar=RegistrarName(registrar),
        first_name=contact_info.get("first_name", ""),
        last_name=contact_info.get("last_name", ""),
        email=contact_info.get("email", ""),
        phone=contact_info.get("phone", ""),
        address1=contact_info.get("address1", ""),
        address2=contact_info.get("address2"),
        city=contact_info.get("city", ""),
        state=contact_info.get("state", ""),
        postal_code=contact_info.get("postal_code", ""),
        country=contact_info.get("country", "US"),
        organization=contact_info.get("organization"),
        years=contact_info.get("years", 1),
        auto_renew=contact_info.get("auto_renew", True),
        privacy=contact_info.get("privacy", True),
    )

    response = await registrar_service.register_domain(request, beacon_ip)

    return {
        "domain": response.domain,
        "registrar": response.registrar.value,
        "status": response.status,
        "expires_at": response.expires_at,
        "auto_renew": response.auto_renew,
        "locked": response.locked,
        "nameservers": response.nameservers,
        "dns_configured": response.dns_configured,
        "dns_records": response.dns_records,
    }


def get_all_tld_pricing_comparison() -> List[Dict[str, Any]]:
    """
    Get pricing comparison for all TLDs across registrars.

    Returns list suitable for API response showing price comparison.
    """
    from .cloudflare_registrar import CloudflareRegistrar
    from .namecheap_registrar import NamecheapRegistrar

    # Get all TLDs from both registrars
    all_tlds = set(CloudflareRegistrar.SUPPORTED_TLDS.keys())
    all_tlds.update(NamecheapRegistrar.ESTIMATED_TLDS.keys())

    comparison = []
    for tld in sorted(all_tlds):
        entry = {
            "tld": f".{tld}",
            "cloudflare": None,
            "namecheap": None,
            "best_registrar": None,
            "best_price": None,
        }

        cf_pricing = CloudflareRegistrar.SUPPORTED_TLDS.get(tld)
        nc_pricing = NamecheapRegistrar.ESTIMATED_TLDS.get(tld)

        if cf_pricing:
            entry["cloudflare"] = {
                "registration": cf_pricing.registration_price,
                "renewal": cf_pricing.renewal_price,
            }

        if nc_pricing:
            entry["namecheap"] = {
                "registration": nc_pricing.registration_price,
                "renewal": nc_pricing.renewal_price,
            }

        # Determine best price
        if cf_pricing and nc_pricing:
            if cf_pricing.registration_price <= nc_pricing.registration_price:
                entry["best_registrar"] = "cloudflare"
                entry["best_price"] = cf_pricing.registration_price
            else:
                entry["best_registrar"] = "namecheap"
                entry["best_price"] = nc_pricing.registration_price
        elif cf_pricing:
            entry["best_registrar"] = "cloudflare"
            entry["best_price"] = cf_pricing.registration_price
        elif nc_pricing:
            entry["best_registrar"] = "namecheap"
            entry["best_price"] = nc_pricing.registration_price

        comparison.append(entry)

    # Sort by best price
    comparison.sort(key=lambda x: x["best_price"] or float('inf'))

    return comparison
