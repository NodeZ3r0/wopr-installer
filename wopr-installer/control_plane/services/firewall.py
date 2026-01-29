"""
WOPR Firewall Service
=====================

Creates provider-specific firewall rules for WOPR beacons.

Standard ports opened:
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS)
- 8443 (Authentik)

All other inbound traffic is denied.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Standard WOPR firewall rules
WOPR_FIREWALL_RULES = [
    {"port": "22", "protocol": "tcp", "description": "SSH"},
    {"port": "80", "protocol": "tcp", "description": "HTTP"},
    {"port": "443", "protocol": "tcp", "description": "HTTPS"},
    {"port": "8443", "protocol": "tcp", "description": "Authentik"},
]


class FirewallService:
    """
    Creates and manages firewall rules across providers.

    Each provider has a different firewall API, so this service
    dispatches to the correct implementation.
    """

    async def create_firewall(
        self,
        provider_id: str,
        provider_instance: Any,
        instance_id: str,
        job_id: str,
    ) -> Optional[str]:
        """
        Create a firewall and attach it to an instance.

        Args:
            provider_id: Provider identifier (hetzner, digitalocean, etc.)
            provider_instance: The provider adapter object
            instance_id: Provider instance/server ID
            job_id: WOPR job ID for naming

        Returns:
            Firewall ID if created, None on failure
        """
        try:
            handler = getattr(self, f"_create_{provider_id}_firewall", None)
            if handler:
                return await handler(provider_instance, instance_id, job_id)
            else:
                logger.warning(f"No firewall handler for provider: {provider_id}")
                return None
        except Exception as e:
            logger.error(f"Failed to create firewall for {provider_id}: {e}")
            return None

    async def _create_hetzner_firewall(
        self, provider: Any, instance_id: str, job_id: str
    ) -> Optional[str]:
        """Create Hetzner firewall via hcloud API."""
        import asyncio

        def _create():
            try:
                from hcloud.firewalls import (
                    FirewallRule,
                )

                rules = []
                for rule in WOPR_FIREWALL_RULES:
                    rules.append(
                        FirewallRule(
                            direction="in",
                            protocol=rule["protocol"],
                            port=rule["port"],
                            source_ips=["0.0.0.0/0", "::/0"],
                            description=rule["description"],
                        )
                    )

                fw_name = f"wopr-{job_id[:8]}"
                response = provider.client.firewalls.create(
                    name=fw_name,
                    rules=rules,
                )
                firewall = response.firewall

                # Apply to server
                server = provider.client.servers.get_by_id(int(instance_id))
                if server:
                    from hcloud.firewalls import FirewallResource
                    firewall.apply_to_resources(
                        [FirewallResource(type="server", server=server)]
                    )

                return str(firewall.id)
            except Exception as e:
                logger.error(f"Hetzner firewall creation failed: {e}")
                return None

        return await asyncio.to_thread(_create)

    async def _create_digitalocean_firewall(
        self, provider: Any, instance_id: str, job_id: str
    ) -> Optional[str]:
        """
        Create DigitalOcean firewall.

        Note: DigitalOcean firewalls via libcloud are limited.
        For full firewall support, the DO API v2 should be used directly.
        """
        logger.info(
            f"DigitalOcean firewall: Using cloud-init iptables rules for instance {instance_id}. "
            "Native DO firewall requires direct API integration."
        )
        return None

    async def _create_vultr_firewall(
        self, provider: Any, instance_id: str, job_id: str
    ) -> Optional[str]:
        """
        Create Vultr firewall group.

        Note: Vultr firewall groups via libcloud are limited.
        For full firewall support, the Vultr API v2 should be used directly.
        """
        logger.info(
            f"Vultr firewall: Using cloud-init iptables rules for instance {instance_id}. "
            "Native Vultr firewall requires direct API integration."
        )
        return None

    async def _create_linode_firewall(
        self, provider: Any, instance_id: str, job_id: str
    ) -> Optional[str]:
        """
        Create Linode Cloud Firewall.

        Note: Linode firewalls via libcloud are limited.
        For full firewall support, the Linode API v4 should be used directly.
        """
        logger.info(
            f"Linode firewall: Using cloud-init iptables rules for instance {instance_id}. "
            "Native Linode firewall requires direct API integration."
        )
        return None

    async def _create_ovh_firewall(
        self, provider: Any, instance_id: str, job_id: str
    ) -> Optional[str]:
        """
        Create OVH security group (OpenStack).

        Note: OVH uses OpenStack security groups.
        """
        logger.info(
            f"OVH firewall: Using cloud-init iptables rules for instance {instance_id}. "
            "Native OVH security groups require OpenStack API integration."
        )
        return None


def generate_iptables_cloud_init() -> str:
    """
    Generate cloud-init snippet for iptables-based firewall.

    This is the universal fallback that works on all providers,
    applied via cloud-init user data.
    """
    rules = []
    for rule in WOPR_FIREWALL_RULES:
        rules.append(
            f"iptables -A INPUT -p {rule['protocol']} --dport {rule['port']} "
            f"-j ACCEPT  # {rule['description']}"
        )

    return "\n".join([
        "# WOPR Firewall Rules (iptables)",
        "iptables -F INPUT",
        "iptables -A INPUT -i lo -j ACCEPT",
        "iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
        "iptables -A INPUT -p icmp -j ACCEPT",
        *rules,
        "iptables -A INPUT -j DROP",
        "",
        "# Persist rules",
        "iptables-save > /etc/iptables/rules.v4 2>/dev/null || true",
        "",
        "# IPv6 rules",
        "ip6tables -F INPUT",
        "ip6tables -A INPUT -i lo -j ACCEPT",
        "ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
        "ip6tables -A INPUT -p icmpv6 -j ACCEPT",
    ] + [
        f"ip6tables -A INPUT -p {rule['protocol']} --dport {rule['port']} "
        f"-j ACCEPT  # {rule['description']}"
        for rule in WOPR_FIREWALL_RULES
    ] + [
        "ip6tables -A INPUT -j DROP",
        "ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true",
    ])
