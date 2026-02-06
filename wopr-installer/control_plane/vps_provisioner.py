"""
WOPR VPS Provisioner
====================

Bridges Stripe payments to VPS creation via Hetzner API.

This is the "glue" that:
1. Receives checkout data from Stripe webhook
2. Creates a job in the job store
3. Generates cloud-init with bootstrap.json
4. Provisions a Hetzner VPS
5. VPS runs installer which calls back to update status

Updated: February 2026
"""

import os
import json
import secrets
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from .job_store import get_job_store
from .bundles.manifests import (
    parse_checkout_bundle,
    get_modules_for_bundle,
    CORE_INFRASTRUCTURE,
)
from .bundles.tiers import StorageTier, get_storage_tier

logger = logging.getLogger(__name__)


# Tier to Hetzner plan mapping
# NOTE: Hetzner renamed plans in 2025 (cx22 -> cx23, cpx21 -> cpx22, etc.)
# The provider_health.py service monitors for future changes
TIER_TO_HETZNER_PLAN = {
    "t1": "cpx22",   # 2 vCPU, 4GB RAM - good for light bundles
    "t2": "cpx32",   # 4 vCPU, 8GB RAM - good for most bundles
    "t3": "cpx42",   # 8 vCPU, 16GB RAM - for heavy bundles
}

# Bundle to minimum tier (some bundles need more resources)
BUNDLE_MIN_TIER = {
    # Heavy bundles need at least t2
    "professional": "t2",
    "small_business": "t2",
    "enterprise": "t3",
    "photographer": "t2",
    "video_creator": "t2",
    # AI bundles need t2 for Ollama
    "developer": "t2",
    "reactor_ai": "t2",
}


@dataclass
class VPSProvisionRequest:
    """Request to provision a VPS for a WOPR beacon."""
    job_id: str
    beacon_name: str
    bundle: str  # e.g., "starter", "developer", "meeting_room"
    tier: str  # t1, t2, t3
    customer_email: str
    customer_name: str
    provider: str = "hetzner"
    region: str = "fsn1"  # Falkenstein, Germany (good EU default)
    datacenter: str = ""
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class VPSProvisioner:
    """
    Handles VPS provisioning via Hetzner API.

    Usage:
        provisioner = VPSProvisioner(
            hetzner_token="...",
            orchestrator_url="https://api.wopr.systems",
            ssh_key_name="wopr-deploy",
        )

        result = await provisioner.provision(VPSProvisionRequest(...))
    """

    def __init__(
        self,
        hetzner_token: str,
        orchestrator_url: str,
        ssh_key_name: str = "wopr-deploy",
        default_region: str = "fsn1",
    ):
        self.hetzner_token = hetzner_token
        self.orchestrator_url = orchestrator_url
        self.ssh_key_name = ssh_key_name
        self.default_region = default_region

        # Lazy import Hetzner provider
        self._provider = None

    def _get_provider(self):
        """Get or create Hetzner provider instance."""
        if self._provider is None:
            from .providers.hetzner import HetznerProvider
            self._provider = HetznerProvider(api_token=self.hetzner_token)
        return self._provider

    def _get_plan_for_tier(self, bundle: str, tier: str) -> str:
        """Get Hetzner plan ID based on bundle and tier."""
        # Check if bundle requires a minimum tier
        min_tier = BUNDLE_MIN_TIER.get(bundle, "t1")
        tier_order = ["t1", "t2", "t3"]

        # Use the higher of requested tier or minimum tier
        if tier_order.index(tier) < tier_order.index(min_tier):
            tier = min_tier
            logger.info(f"Bundle {bundle} requires minimum tier {tier}")

        return TIER_TO_HETZNER_PLAN.get(tier, "cpx21")

    def _generate_cloud_init(self, request: VPSProvisionRequest) -> str:
        """Generate cloud-init user data for WOPR bootstrap."""
        # Parse bundle to get modules
        try:
            bundle_type, bundle_id = parse_checkout_bundle(request.bundle)
            app_modules = get_modules_for_bundle(bundle_type, bundle_id)
            # Remove core modules (they're separate)
            app_modules = [m for m in app_modules if m not in CORE_INFRASTRUCTURE]
        except ValueError:
            # Fallback: treat bundle as sovereign suite ID directly
            from .bundles.tiers import BundleType
            app_modules = get_modules_for_bundle(BundleType.SOVEREIGN, request.bundle)
            app_modules = [m for m in app_modules if m not in CORE_INFRASTRUCTURE]

        # Get storage tier info
        try:
            tier_num = int(request.tier.replace("t", ""))
            storage_tier = get_storage_tier(StorageTier(tier_num))
        except:
            storage_tier = get_storage_tier(StorageTier.TIER_1)

        # Build bootstrap.json content
        bootstrap = {
            "job_id": request.job_id,
            "beacon_name": request.beacon_name,
            "bundle": request.bundle,
            "domain": f"{request.beacon_name}.wopr.systems",
            "storage_tier": request.tier,
            "customer_id": request.stripe_customer_id or "",
            "customer_email": request.customer_email,
            "customer_name": request.customer_name,
            "orchestrator_url": self.orchestrator_url,
            "provisioned_at": datetime.now().isoformat(),
            "core_modules": CORE_INFRASTRUCTURE,
            "app_modules": app_modules,
            "storage_gb": storage_tier.storage_gb,
            "ram_mb": storage_tier.ram_mb,
            "max_users": storage_tier.max_users,
        }

        bootstrap_json = json.dumps(bootstrap, indent=2)

        # Cloud-init script
        return f"""#cloud-config
package_update: true
package_upgrade: true

packages:
  - curl
  - wget
  - git
  - jq
  - uuid-runtime

write_files:
  - path: /etc/wopr/bootstrap.json
    permissions: '0600'
    content: |
{self._indent_json(bootstrap_json, 6)}

runcmd:
  # Report VPS ready
  - |
    curl -sf -X POST "{self.orchestrator_url}/api/v1/provision/{request.job_id}/status" \
      -H "Content-Type: application/json" \
      -d '{{"status": "provisioning_vps", "message": "VPS created, starting installation..."}}' || true

  # Clone installer
  - mkdir -p /opt/wopr
  - git clone https://vault.wopr.systems/WOPRSystems/wopr-installer.git /opt/wopr 2>/dev/null || git clone http://159.203.138.7:3001/wopr/wopr-installer.git /opt/wopr

  # Run installer
  - cd /opt/wopr && bash scripts/wopr_install.sh --non-interactive --confirm-all
"""

    def _indent_json(self, json_str: str, spaces: int) -> str:
        """Indent JSON string for YAML embedding."""
        indent = " " * spaces
        return "\n".join(indent + line for line in json_str.split("\n"))

    async def provision(self, request: VPSProvisionRequest) -> Dict[str, Any]:
        """
        Provision a VPS for a WOPR beacon.

        Args:
            request: Provisioning request with all required data

        Returns:
            Dict with instance details
        """
        job_store = get_job_store()

        try:
            # Update job status
            job_store.set_state(
                request.job_id,
                "provisioning_vps",
                "Creating VPS instance..."
            )

            # Get Hetzner provider
            provider = self._get_provider()

            # Determine plan and region
            plan_id = self._get_plan_for_tier(request.bundle, request.tier)
            region = request.region or self.default_region

            # Generate cloud-init
            user_data = self._generate_cloud_init(request)

            # Generate instance name
            short_id = secrets.token_hex(4)
            instance_name = f"wopr-{request.beacon_name}-{short_id}"

            # Provision the VPS
            from .providers.base import ProvisionConfig
            config = ProvisionConfig(
                name=instance_name,
                region=region,
                plan_id=plan_id,
                image="ubuntu-24.04",
                ssh_keys=[self.ssh_key_name],
                user_data=user_data,
                wopr_bundle=request.bundle,
                wopr_customer_id=request.stripe_customer_id,
                wopr_customer_email=request.customer_email,
                wopr_customer_name=request.customer_name,
                metadata={
                    "wopr_job_id": request.job_id,
                    "wopr_beacon_name": request.beacon_name,
                },
                tags=[
                    f"wopr-job:{request.job_id}",
                    f"wopr-beacon:{request.beacon_name}",
                    f"wopr-bundle:{request.bundle}",
                ],
            )

            instance = provider.provision(config)

            # Update job with instance info
            job_store.update_job(
                request.job_id,
                state="waiting_for_vps",
                message=f"VPS created at {instance.ip_address}, waiting for boot...",
                instance_ip=instance.ip_address or "",
                instance_id=instance.id,
                provider=request.provider,
            )

            logger.info(
                f"VPS provisioned: {instance_name} at {instance.ip_address} "
                f"for job {request.job_id}"
            )

            return {
                "success": True,
                "job_id": request.job_id,
                "instance_id": instance.id,
                "instance_name": instance_name,
                "ip_address": instance.ip_address,
                "provider": request.provider,
                "region": region,
                "plan": plan_id,
            }

        except Exception as e:
            logger.error(f"VPS provisioning failed for job {request.job_id}: {e}")
            job_store.fail_job(request.job_id, str(e))
            return {
                "success": False,
                "job_id": request.job_id,
                "error": str(e),
            }


async def handle_stripe_checkout_completed(
    session_data: Dict[str, Any],
    provisioner: VPSProvisioner,
) -> Dict[str, Any]:
    """
    Handle Stripe checkout.session.completed webhook.

    This is the entry point from the Stripe webhook that kicks off
    the entire provisioning flow.

    Args:
        session_data: Stripe checkout session object
        provisioner: VPSProvisioner instance

    Returns:
        Dict with job_id and provisioning status
    """
    # Extract metadata from checkout session
    metadata = session_data.get("metadata", {})

    # Get customer info
    customer_email = session_data.get("customer_email", "")
    customer_details = session_data.get("customer_details", {})
    customer_name = customer_details.get("name", metadata.get("wopr_customer_name", ""))

    # Get bundle info from metadata
    bundle = metadata.get("wopr_bundle", "starter")
    tier = metadata.get("wopr_tier", "t1")
    beacon_name = metadata.get("wopr_beacon_name", "")
    provider = metadata.get("wopr_provider", "hetzner")
    region = metadata.get("wopr_region", "fsn1")
    datacenter = metadata.get("wopr_datacenter", "")

    # Generate job ID
    job_id = secrets.token_urlsafe(16)

    # Create job in store immediately
    job_store = get_job_store()
    job_store.create_job(
        job_id=job_id,
        beacon_name=beacon_name,
        bundle=bundle,
        tier=tier,
        customer_email=customer_email,
        customer_name=customer_name,
        provider=provider,
    )

    # Send provisioning started email
    try:
        from .email_service import EmailService
        from .stripe_catalog import get_bundle_info

        email_svc = EmailService()
        bundle_info = get_bundle_info(bundle) or {}
        provisioning_url = f"https://provision.wopr.systems/{job_id}"

        email_svc.send_provisioning_started(
            to_email=customer_email,
            name=customer_name or customer_email.split("@")[0],
            beacon_name=beacon_name,
            bundle_name=bundle_info.get("name", bundle),
            job_id=job_id,
            provisioning_url=provisioning_url,
        )
        logger.info(f"Sent provisioning email to {customer_email} for job {job_id}")
    except Exception as e:
        logger.warning(f"Failed to send provisioning email: {e}")

    # Create provisioning request
    request = VPSProvisionRequest(
        job_id=job_id,
        beacon_name=beacon_name,
        bundle=bundle,
        tier=tier,
        customer_email=customer_email,
        customer_name=customer_name,
        provider=provider,
        region=region,
        datacenter=datacenter,
        stripe_customer_id=session_data.get("customer"),
        stripe_subscription_id=session_data.get("subscription"),
    )

    # Start VPS provisioning (async)
    result = await provisioner.provision(request)

    return {
        "job_id": job_id,
        "provisioning_url": f"https://provision.wopr.systems/{job_id}",
        "beacon_name": beacon_name,
        "bundle": bundle,
        "tier": tier,
        "vps_created": result.get("success", False),
        "instance_ip": result.get("ip_address"),
        "error": result.get("error"),
    }
