"""
WOPR Namecheap Registrar Service
=================================

Manages domain registration and purchase via the Namecheap API.

Handles:
- Domain availability checking
- Domain pricing lookup for supported TLDs
- Domain registration through Namecheap
- Domain listing

Uses Namecheap's XML API.
API Documentation: https://www.namecheap.com/support/api/intro/
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import urllib.parse

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx package not installed. Run: pip install httpx")


class NamecheapDomainStatus(Enum):
    """Domain availability status from Namecheap."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREMIUM = "premium"
    UNKNOWN = "unknown"


@dataclass
class NamecheapDomainAvailability:
    """Domain availability check result from Namecheap."""
    domain: str
    available: bool
    status: NamecheapDomainStatus
    premium: bool = False
    premium_price: Optional[float] = None
    message: Optional[str] = None


@dataclass
class NamecheapDomainPricing:
    """Domain pricing information from Namecheap."""
    tld: str
    registration_price: float
    renewal_price: float
    transfer_price: Optional[float] = None
    currency: str = "USD"
    icann_fee: float = 0.18


@dataclass
class NamecheapRegisteredDomain:
    """Registered domain information from Namecheap."""
    domain: str
    registrar: str = "namecheap"
    status: str = "active"
    expires_at: Optional[str] = None
    auto_renew: bool = True
    locked: bool = True
    nameservers: List[str] = None

    def __post_init__(self):
        if self.nameservers is None:
            self.nameservers = []


@dataclass
class NamecheapRegistrationRequest:
    """Request to register a new domain via Namecheap."""
    domain: str
    years: int = 1
    auto_renew: bool = True
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
    # Namecheap-specific
    add_free_whois_guard: bool = True


class NamecheapRegistrar:
    """
    Namecheap Registrar integration for domain registration.

    Provides domain availability checking, pricing lookup, and domain
    purchase capabilities through the Namecheap API.
    """

    # Namecheap API endpoints
    API_BASE_PRODUCTION = "https://api.namecheap.com/xml.response"
    API_BASE_SANDBOX = "https://api.sandbox.namecheap.com/xml.response"

    # Approximate Namecheap pricing for common TLDs
    # These are estimates - actual prices are fetched from API
    ESTIMATED_TLDS: Dict[str, NamecheapDomainPricing] = {
        "com": NamecheapDomainPricing("com", 10.98, 14.98, 10.98),
        "net": NamecheapDomainPricing("net", 12.98, 14.98, 12.98),
        "org": NamecheapDomainPricing("org", 12.98, 14.98, 12.98),
        "io": NamecheapDomainPricing("io", 32.98, 42.98, 32.98),
        "co": NamecheapDomainPricing("co", 11.98, 29.98, 11.98),
        "dev": NamecheapDomainPricing("dev", 14.98, 14.98, 14.98),
        "app": NamecheapDomainPricing("app", 16.98, 16.98, 16.98),
        "ai": NamecheapDomainPricing("ai", 74.98, 74.98, 74.98),
        "me": NamecheapDomainPricing("me", 5.98, 19.98, 5.98),
        "xyz": NamecheapDomainPricing("xyz", 1.98, 12.98, 1.98),
        "info": NamecheapDomainPricing("info", 4.98, 19.98, 4.98),
        "biz": NamecheapDomainPricing("biz", 12.98, 16.98, 12.98),
        "tech": NamecheapDomainPricing("tech", 6.98, 44.98, 6.98),
        "online": NamecheapDomainPricing("online", 3.98, 34.98, 3.98),
        "cloud": NamecheapDomainPricing("cloud", 9.98, 22.98, 9.98),
        "sh": NamecheapDomainPricing("sh", 39.98, 39.98, 39.98),
        "systems": NamecheapDomainPricing("systems", 22.98, 22.98, 22.98),
    }

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        sandbox: bool = False,
    ):
        """
        Initialize with Namecheap API credentials.

        Args:
            api_user: Namecheap API username
            api_key: Namecheap API key
            username: Namecheap account username (usually same as api_user)
            client_ip: Whitelisted client IP address
            sandbox: Use sandbox API for testing
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx package not installed")

        self.api_user = api_user
        self.api_key = api_key
        self.username = username
        self.client_ip = client_ip
        self.api_base = self.API_BASE_SANDBOX if sandbox else self.API_BASE_PRODUCTION
        self._pricing_cache: Dict[str, NamecheapDomainPricing] = {}

    def _build_request_params(self, command: str, **kwargs) -> Dict[str, str]:
        """Build the base request parameters for Namecheap API."""
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        params.update(kwargs)
        return params

    async def _make_request(self, command: str, **kwargs) -> ET.Element:
        """Make an API request to Namecheap and parse XML response."""
        import asyncio

        params = self._build_request_params(command, **kwargs)

        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_base, params=params, timeout=30.0)
            response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.text)

        # Check for API errors
        status = root.get("Status", "").lower()
        if status == "error":
            errors = root.find(".//Errors")
            if errors is not None:
                error_msgs = [e.text for e in errors.findall("Error")]
                raise Exception(f"Namecheap API Error: {'; '.join(error_msgs)}")
            raise Exception("Namecheap API returned an error")

        return root

    async def check_availability(self, domain: str) -> NamecheapDomainAvailability:
        """
        Check if a domain is available for registration.

        Args:
            domain: Full domain name (e.g., "example.com")

        Returns:
            NamecheapDomainAvailability with availability status
        """
        try:
            root = await self._make_request(
                "namecheap.domains.check",
                DomainList=domain,
            )

            # Parse domain check result
            result = root.find(".//DomainCheckResult")
            if result is None:
                return NamecheapDomainAvailability(
                    domain=domain,
                    available=False,
                    status=NamecheapDomainStatus.UNKNOWN,
                    message="No result returned from API",
                )

            available = result.get("Available", "").lower() == "true"
            is_premium = result.get("IsPremiumName", "").lower() == "true"
            premium_price = None

            if is_premium:
                try:
                    premium_price = float(result.get("PremiumRegistrationPrice", 0))
                except (ValueError, TypeError):
                    pass

            status = NamecheapDomainStatus.AVAILABLE if available else NamecheapDomainStatus.UNAVAILABLE
            if is_premium:
                status = NamecheapDomainStatus.PREMIUM

            return NamecheapDomainAvailability(
                domain=domain,
                available=available or is_premium,
                status=status,
                premium=is_premium,
                premium_price=premium_price,
                message="Premium domain" if is_premium else None,
            )

        except Exception as e:
            logger.error(f"Namecheap availability check failed for {domain}: {e}")
            return NamecheapDomainAvailability(
                domain=domain,
                available=False,
                status=NamecheapDomainStatus.UNKNOWN,
                message=str(e),
            )

    async def check_availability_bulk(
        self, domain_base: str, tlds: Optional[List[str]] = None
    ) -> List[NamecheapDomainAvailability]:
        """
        Check availability across multiple TLDs.

        Args:
            domain_base: Domain name without TLD (e.g., "mycompany")
            tlds: List of TLDs to check (defaults to popular TLDs)

        Returns:
            List of NamecheapDomainAvailability for each TLD
        """
        import asyncio

        if tlds is None:
            tlds = ["com", "net", "org", "io", "co", "dev", "app"]

        # Namecheap allows checking multiple domains in one call
        domains = [f"{domain_base}.{tld}" for tld in tlds]
        domain_list = ",".join(domains)

        try:
            root = await self._make_request(
                "namecheap.domains.check",
                DomainList=domain_list,
            )

            results = []
            for result in root.findall(".//DomainCheckResult"):
                domain = result.get("Domain", "")
                available = result.get("Available", "").lower() == "true"
                is_premium = result.get("IsPremiumName", "").lower() == "true"
                premium_price = None

                if is_premium:
                    try:
                        premium_price = float(result.get("PremiumRegistrationPrice", 0))
                    except (ValueError, TypeError):
                        pass

                status = NamecheapDomainStatus.AVAILABLE if available else NamecheapDomainStatus.UNAVAILABLE
                if is_premium:
                    status = NamecheapDomainStatus.PREMIUM

                results.append(NamecheapDomainAvailability(
                    domain=domain,
                    available=available or is_premium,
                    status=status,
                    premium=is_premium,
                    premium_price=premium_price,
                    message="Premium domain" if is_premium else None,
                ))

            return results

        except Exception as e:
            logger.error(f"Namecheap bulk availability check failed: {e}")
            # Return unknown status for all domains
            return [
                NamecheapDomainAvailability(
                    domain=f"{domain_base}.{tld}",
                    available=False,
                    status=NamecheapDomainStatus.UNKNOWN,
                    message=str(e),
                )
                for tld in tlds
            ]

    async def get_pricing(self, tld: str) -> Optional[NamecheapDomainPricing]:
        """
        Get pricing for a specific TLD from Namecheap API.

        Args:
            tld: Top-level domain (e.g., "com", "io")

        Returns:
            NamecheapDomainPricing or None if TLD not available
        """
        tld = tld.lower().lstrip(".")

        # Check cache first
        if tld in self._pricing_cache:
            return self._pricing_cache[tld]

        try:
            root = await self._make_request(
                "namecheap.users.getPricing",
                ProductType="DOMAIN",
                ProductCategory="REGISTER",
                ActionName="REGISTER",
            )

            # Find the TLD in the pricing response
            for product in root.findall(".//Product"):
                product_name = product.get("Name", "").lower()
                if product_name == tld:
                    price_element = product.find("Price")
                    if price_element is not None:
                        try:
                            reg_price = float(price_element.get("Price", 0))

                            # Try to get renewal price
                            renewal_price = reg_price  # Default to same

                            pricing = NamecheapDomainPricing(
                                tld=tld,
                                registration_price=reg_price,
                                renewal_price=renewal_price,
                                transfer_price=reg_price,
                            )
                            self._pricing_cache[tld] = pricing
                            return pricing
                        except (ValueError, TypeError):
                            pass

            # Fall back to estimated pricing
            return self.ESTIMATED_TLDS.get(tld)

        except Exception as e:
            logger.warning(f"Failed to get Namecheap pricing for {tld}: {e}")
            return self.ESTIMATED_TLDS.get(tld)

    def get_estimated_pricing(self, tld: str) -> Optional[NamecheapDomainPricing]:
        """
        Get estimated pricing for a TLD without API call.

        Args:
            tld: Top-level domain (e.g., "com", "io")

        Returns:
            NamecheapDomainPricing or None if TLD not supported
        """
        return self.ESTIMATED_TLDS.get(tld.lower().lstrip("."))

    def get_all_estimated_pricing(self) -> Dict[str, NamecheapDomainPricing]:
        """
        Get estimated pricing for all supported TLDs.

        Returns:
            Dict mapping TLD to NamecheapDomainPricing
        """
        return self.ESTIMATED_TLDS.copy()

    def get_supported_tlds(self) -> List[str]:
        """
        Get list of supported TLDs.

        Returns:
            List of TLD strings
        """
        return list(self.ESTIMATED_TLDS.keys())

    async def register_domain(
        self, request: NamecheapRegistrationRequest
    ) -> NamecheapRegisteredDomain:
        """
        Register a new domain through Namecheap.

        Args:
            request: NamecheapRegistrationRequest with domain and contact info

        Returns:
            NamecheapRegisteredDomain on success

        Raises:
            ValueError: If domain is unavailable
            Exception: On API failure
        """
        # Check availability first
        availability = await self.check_availability(request.domain)
        if not availability.available:
            raise ValueError(
                f"Domain {request.domain} is not available: {availability.message}"
            )

        # Split domain into SLD and TLD
        parts = request.domain.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid domain format: {request.domain}")
        sld, tld = parts

        # Build registration parameters
        params = {
            "DomainName": request.domain,
            "Years": str(request.years),
            # Registrant contact
            "RegistrantFirstName": request.first_name,
            "RegistrantLastName": request.last_name,
            "RegistrantAddress1": request.address1,
            "RegistrantCity": request.city,
            "RegistrantStateProvince": request.state,
            "RegistrantPostalCode": request.postal_code,
            "RegistrantCountry": request.country,
            "RegistrantPhone": request.phone,
            "RegistrantEmailAddress": request.email,
            # Tech contact (same as registrant)
            "TechFirstName": request.first_name,
            "TechLastName": request.last_name,
            "TechAddress1": request.address1,
            "TechCity": request.city,
            "TechStateProvince": request.state,
            "TechPostalCode": request.postal_code,
            "TechCountry": request.country,
            "TechPhone": request.phone,
            "TechEmailAddress": request.email,
            # Admin contact (same as registrant)
            "AdminFirstName": request.first_name,
            "AdminLastName": request.last_name,
            "AdminAddress1": request.address1,
            "AdminCity": request.city,
            "AdminStateProvince": request.state,
            "AdminPostalCode": request.postal_code,
            "AdminCountry": request.country,
            "AdminPhone": request.phone,
            "AdminEmailAddress": request.email,
            # Aux Billing contact (same as registrant)
            "AuxBillingFirstName": request.first_name,
            "AuxBillingLastName": request.last_name,
            "AuxBillingAddress1": request.address1,
            "AuxBillingCity": request.city,
            "AuxBillingStateProvince": request.state,
            "AuxBillingPostalCode": request.postal_code,
            "AuxBillingCountry": request.country,
            "AuxBillingPhone": request.phone,
            "AuxBillingEmailAddress": request.email,
        }

        # Add optional fields
        if request.address2:
            params["RegistrantAddress2"] = request.address2
            params["TechAddress2"] = request.address2
            params["AdminAddress2"] = request.address2
            params["AuxBillingAddress2"] = request.address2

        if request.organization:
            params["RegistrantOrganizationName"] = request.organization
            params["TechOrganizationName"] = request.organization
            params["AdminOrganizationName"] = request.organization
            params["AuxBillingOrganizationName"] = request.organization

        if request.add_free_whois_guard:
            params["AddFreeWhoisguard"] = "yes"
            params["WGEnabled"] = "yes"

        try:
            root = await self._make_request("namecheap.domains.create", **params)

            result = root.find(".//DomainCreateResult")
            if result is None:
                raise Exception("No registration result returned")

            registered = result.get("Registered", "").lower() == "true"
            if not registered:
                raise Exception("Domain registration failed")

            domain_id = result.get("DomainID", "")
            order_id = result.get("OrderID", "")

            logger.info(f"Registered domain via Namecheap: {request.domain} (ID: {domain_id})")

            return NamecheapRegisteredDomain(
                domain=request.domain,
                registrar="namecheap",
                status="active",
                auto_renew=request.auto_renew,
            )

        except Exception as e:
            logger.error(f"Namecheap domain registration failed: {e}")
            raise

    async def list_domains(self) -> List[NamecheapRegisteredDomain]:
        """
        List all domains in the Namecheap account.

        Returns:
            List of NamecheapRegisteredDomain objects
        """
        try:
            root = await self._make_request(
                "namecheap.domains.getList",
                PageSize="100",
            )

            domains = []
            for domain_elem in root.findall(".//Domain"):
                name = domain_elem.get("Name", "")
                expires = domain_elem.get("Expires", "")
                is_expired = domain_elem.get("IsExpired", "").lower() == "true"
                is_locked = domain_elem.get("IsLocked", "").lower() == "true"
                auto_renew = domain_elem.get("AutoRenew", "").lower() == "true"

                domains.append(NamecheapRegisteredDomain(
                    domain=name,
                    registrar="namecheap",
                    status="expired" if is_expired else "active",
                    expires_at=expires,
                    auto_renew=auto_renew,
                    locked=is_locked,
                ))

            return domains

        except Exception as e:
            logger.error(f"Failed to list Namecheap domains: {e}")
            raise

    async def get_domain(self, domain: str) -> Optional[NamecheapRegisteredDomain]:
        """
        Get details for a specific domain.

        Args:
            domain: Domain name to look up

        Returns:
            NamecheapRegisteredDomain or None if not found
        """
        try:
            # Split domain into SLD and TLD
            parts = domain.rsplit(".", 1)
            if len(parts) != 2:
                return None
            sld, tld = parts

            root = await self._make_request(
                "namecheap.domains.getInfo",
                DomainName=domain,
            )

            result = root.find(".//DomainGetInfoResult")
            if result is None:
                return None

            status = result.get("Status", "active")
            created = result.find(".//CreatedDate")
            expires = result.find(".//ExpiredDate")

            # Get nameservers
            nameservers = []
            ns_elem = result.find(".//Nameservers")
            if ns_elem is not None:
                for ns in ns_elem.text.split(",") if ns_elem.text else []:
                    nameservers.append(ns.strip())

            return NamecheapRegisteredDomain(
                domain=domain,
                registrar="namecheap",
                status=status.lower(),
                expires_at=expires.text if expires is not None else None,
                nameservers=nameservers,
            )

        except Exception as e:
            logger.warning(f"Failed to get Namecheap domain info for {domain}: {e}")
            return None

    async def set_nameservers(self, domain: str, nameservers: List[str]) -> bool:
        """
        Set custom nameservers for a domain.

        Args:
            domain: Domain name
            nameservers: List of nameserver hostnames

        Returns:
            True if successful
        """
        # Split domain into SLD and TLD
        parts = domain.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid domain format: {domain}")
        sld, tld = parts

        try:
            params = {
                "SLD": sld,
                "TLD": tld,
            }
            # Add nameservers
            for i, ns in enumerate(nameservers[:12], 1):  # Max 12 nameservers
                params[f"Nameserver{i}"] = ns

            root = await self._make_request(
                "namecheap.domains.dns.setCustom",
                **params,
            )

            result = root.find(".//DomainDNSSetCustomResult")
            if result is not None:
                updated = result.get("Updated", "").lower() == "true"
                if updated:
                    logger.info(f"Set nameservers for {domain}: {nameservers}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to set nameservers for {domain}: {e}")
            return False


# Convenience functions for API endpoints

async def check_namecheap_availability(
    api_user: str,
    api_key: str,
    username: str,
    client_ip: str,
    domain: str,
    sandbox: bool = False,
) -> Dict[str, Any]:
    """
    Check if a domain is available for registration via Namecheap.

    Returns dict with availability info suitable for API response.
    """
    registrar = NamecheapRegistrar(api_user, api_key, username, client_ip, sandbox)
    result = await registrar.check_availability(domain)

    pricing = registrar.get_estimated_pricing(domain.split(".")[-1])

    return {
        "domain": result.domain,
        "available": result.available,
        "status": result.status.value,
        "premium": result.premium,
        "premium_price": result.premium_price,
        "message": result.message,
        "registrar": "namecheap",
        "pricing": {
            "registration": pricing.registration_price if pricing else None,
            "renewal": pricing.renewal_price if pricing else None,
            "currency": pricing.currency if pricing else "USD",
        } if pricing else None,
    }


async def search_namecheap_domains(
    api_user: str,
    api_key: str,
    username: str,
    client_ip: str,
    query: str,
    tlds: Optional[List[str]] = None,
    sandbox: bool = False,
) -> List[Dict[str, Any]]:
    """
    Search for available domains across multiple TLDs via Namecheap.

    Returns list of availability results suitable for API response.
    """
    registrar = NamecheapRegistrar(api_user, api_key, username, client_ip, sandbox)

    # Clean up query - remove any TLD if present
    domain_base = query.split(".")[0].lower()

    results = await registrar.check_availability_bulk(domain_base, tlds)

    output = []
    for result in results:
        pricing = registrar.get_estimated_pricing(result.domain.split(".")[-1])
        output.append({
            "domain": result.domain,
            "available": result.available,
            "status": result.status.value,
            "price": pricing.registration_price if pricing else None,
            "renewal": pricing.renewal_price if pricing else None,
            "premium": result.premium,
            "premium_price": result.premium_price,
            "registrar": "namecheap",
        })

    # Sort: available first, then by price
    output.sort(key=lambda x: (not x["available"], x["price"] or 999))

    return output


def get_namecheap_tld_pricing() -> List[Dict[str, Any]]:
    """
    Get estimated pricing for all supported TLDs.

    Returns list of pricing info suitable for API response.
    """
    return [
        {
            "tld": f".{pricing.tld}",
            "registration": pricing.registration_price,
            "renewal": pricing.renewal_price,
            "transfer": pricing.transfer_price,
            "currency": pricing.currency,
            "registrar": "namecheap",
        }
        for pricing in NamecheapRegistrar.ESTIMATED_TLDS.values()
    ]
