"""
WOPR Provider Registry
======================

Central registry for managing available VPS providers.
Enables dynamic provider selection and multi-vendor deployments.
"""

from typing import Dict, List, Optional, Type
from .base import (
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Region,
    ProviderError,
)


class ProviderRegistry:
    """
    Registry of available VPS providers.

    Manages provider registration, instantiation, and selection
    to support multi-vendor deployments without lock-in.
    """

    _providers: Dict[str, Type[WOPRProviderInterface]] = {}
    _instances: Dict[str, WOPRProviderInterface] = {}

    @classmethod
    def register(cls, provider_class: Type[WOPRProviderInterface]) -> None:
        """
        Register a provider adapter class.

        Args:
            provider_class: Provider class implementing WOPRProviderInterface
        """
        provider_id = provider_class.PROVIDER_ID
        cls._providers[provider_id] = provider_class

    @classmethod
    def get_provider_class(cls, provider_id: str) -> Optional[Type[WOPRProviderInterface]]:
        """
        Get a registered provider class by ID.

        Args:
            provider_id: Provider identifier (e.g., 'hetzner', 'vultr')

        Returns:
            Provider class or None if not found
        """
        return cls._providers.get(provider_id)

    @classmethod
    def list_providers(cls) -> List[Dict[str, str]]:
        """
        List all registered providers.

        Returns:
            List of provider metadata dicts
        """
        return [
            {
                "id": provider_class.PROVIDER_ID,
                "name": provider_class.PROVIDER_NAME,
                "website": provider_class.PROVIDER_WEBSITE,
            }
            for provider_class in cls._providers.values()
        ]

    @classmethod
    def instantiate(
        cls,
        provider_id: str,
        api_token: str,
        **kwargs
    ) -> WOPRProviderInterface:
        """
        Create an instance of a provider adapter.

        Args:
            provider_id: Provider identifier
            api_token: API token for authentication
            **kwargs: Provider-specific configuration

        Returns:
            Configured provider instance

        Raises:
            ProviderError: If provider not found or instantiation fails
        """
        provider_class = cls.get_provider_class(provider_id)
        if not provider_class:
            raise ProviderError(
                provider_id,
                f"Provider not found: {provider_id}. "
                f"Available: {list(cls._providers.keys())}"
            )

        instance = provider_class(api_token, **kwargs)
        cls._instances[provider_id] = instance
        return instance

    @classmethod
    def get_instance(cls, provider_id: str) -> Optional[WOPRProviderInterface]:
        """
        Get an existing provider instance.

        Args:
            provider_id: Provider identifier

        Returns:
            Provider instance or None if not instantiated
        """
        return cls._instances.get(provider_id)

    @classmethod
    def compare_plans(
        cls,
        tier: ResourceTier,
        provider_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Compare plans across providers for a given tier.

        Args:
            tier: Resource tier to compare
            provider_ids: Optional list of providers to compare (all if None)

        Returns:
            List of plan comparisons sorted by price
        """
        if provider_ids is None:
            provider_ids = list(cls._instances.keys())

        comparisons = []
        for provider_id in provider_ids:
            instance = cls._instances.get(provider_id)
            if not instance:
                continue

            plans = instance.list_plans(tier=tier)
            for plan in plans:
                comparisons.append({
                    "provider": provider_id,
                    "plan": plan,
                    "price_monthly": plan.price_monthly_usd,
                    "cpu": plan.cpu,
                    "ram_gb": plan.ram_gb,
                    "disk_gb": plan.disk_gb,
                })

        # Sort by price
        return sorted(comparisons, key=lambda x: x["price_monthly"])

    @classmethod
    def get_cheapest_option(
        cls,
        tier: ResourceTier,
        preferred_regions: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Get the cheapest provider/plan combination for a tier.

        Args:
            tier: Resource tier required
            preferred_regions: Optional list of preferred region codes

        Returns:
            Dict with provider, plan, and region info, or None
        """
        comparisons = cls.compare_plans(tier)
        if not comparisons:
            return None

        # If region preference specified, try to find match
        if preferred_regions:
            for comparison in comparisons:
                plan = comparison["plan"]
                for region in preferred_regions:
                    if region in plan.available_regions:
                        return {
                            **comparison,
                            "region": region,
                        }

        # Fall back to cheapest overall
        return comparisons[0] if comparisons else None

    @classmethod
    def suggest_distribution(
        cls,
        count: int,
        tier: ResourceTier
    ) -> List[Dict]:
        """
        Suggest how to distribute nodes across providers.

        For true mesh distribution, we want nodes on different providers.

        Args:
            count: Number of nodes to provision
            tier: Resource tier for each node

        Returns:
            List of suggested provider/plan combinations
        """
        comparisons = cls.compare_plans(tier)
        if not comparisons:
            return []

        # Get unique providers sorted by price
        seen_providers = set()
        unique_by_provider = []
        for comp in comparisons:
            if comp["provider"] not in seen_providers:
                seen_providers.add(comp["provider"])
                unique_by_provider.append(comp)

        suggestions = []
        provider_count = len(unique_by_provider)

        for i in range(count):
            # Round-robin across providers
            provider_index = i % provider_count
            suggestions.append(unique_by_provider[provider_index])

        return suggestions


def register_provider(provider_class: Type[WOPRProviderInterface]):
    """
    Decorator to register a provider class.

    Usage:
        @register_provider
        class HetznerProvider(WOPRProviderInterface):
            ...
    """
    ProviderRegistry.register(provider_class)
    return provider_class
