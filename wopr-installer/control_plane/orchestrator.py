"""
WOPR Provisioning Orchestrator
==============================

Main orchestration engine for WOPR deployments.

Ties together:
- Stripe payment completion
- VPS provisioning
- DNS configuration (Cloudflare)
- WOPR deployment (cloud-init)
- PDF documentation generation
- Welcome email delivery

Flow:
1. Payment webhook received
2. Provision VPS with selected provider
3. Wait for VPS to be ready
4. Configure DNS (subdomain.wopr.systems)
5. Deploy WOPR via cloud-init
6. Generate documentation (PDF)
7. Send welcome email with credentials

Updated: January 2026
"""

import os
import json
import uuid
import time
import asyncio
import random
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ProvisioningState(Enum):
    """States in the provisioning workflow."""
    PENDING = "pending"
    PAYMENT_RECEIVED = "payment_received"
    PROVISIONING_VPS = "provisioning_vps"
    WAITING_FOR_VPS = "waiting_for_vps"
    CONFIGURING_DNS = "configuring_dns"
    DEPLOYING_WOPR = "deploying_wopr"
    GENERATING_DOCS = "generating_docs"
    SENDING_WELCOME = "sending_welcome"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProvisioningJob:
    """Tracks a provisioning job through its lifecycle."""
    job_id: str
    customer_id: str
    customer_email: str
    bundle: str
    provider_id: str
    region: str
    datacenter_id: str
    storage_tier: int = 1
    customer_name: Optional[str] = None
    custom_domain: Optional[str] = None

    # State tracking
    state: ProvisioningState = ProvisioningState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Provisioning results
    instance_id: Optional[str] = None
    instance_ip: Optional[str] = None
    wopr_subdomain: Optional[str] = None
    root_password: Optional[str] = None
    dns_record_ids: Dict[str, str] = field(default_factory=dict)

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0

    # Stripe IDs
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    # Beacon reference
    beacon_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "customer_email": self.customer_email,
            "customer_name": self.customer_name,
            "bundle": self.bundle,
            "storage_tier": self.storage_tier,
            "provider_id": self.provider_id,
            "region": self.region,
            "datacenter_id": self.datacenter_id,
            "custom_domain": self.custom_domain,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "instance_id": self.instance_id,
            "instance_ip": self.instance_ip,
            "wopr_subdomain": self.wopr_subdomain,
            "dns_record_ids": json.dumps(self.dns_record_ids),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "stripe_customer_id": self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "beacon_id": self.beacon_id,
        }


class WOPROrchestrator:
    """
    Main orchestration engine for WOPR provisioning.

    Coordinates the entire flow from payment to running instance.
    All methods are async for non-blocking operation.
    """

    # WOPR subdomain base
    WOPR_DOMAIN = "wopr.systems"

    def __init__(
        self,
        providers: Dict[str, Any],
        db_pool=None,
        cloudflare_dns=None,
        email_service=None,
        doc_generator=None,
        wopr_domain: str = "wopr.systems",
        job_store_path: str = "/var/lib/wopr/jobs",
    ):
        """
        Initialize the orchestrator.

        Args:
            providers: Dict of provider_id -> configured provider instance
            db_pool: asyncpg connection pool (optional, falls back to JSON files)
            cloudflare_dns: CloudflareDNS service (optional)
            email_service: EmailService instance (optional)
            doc_generator: WOPRDocumentGenerator instance (optional)
            wopr_domain: Base domain for WOPR subdomains
            job_store_path: Path to persist job state (JSON fallback)
        """
        self.providers = providers
        self.db_pool = db_pool
        self.cloudflare_dns = cloudflare_dns
        self.email_service = email_service
        self.doc_generator = doc_generator
        self.WOPR_DOMAIN = wopr_domain
        self.job_store_path = job_store_path

        # In-memory cache (DB is source of truth when available)
        self.jobs: Dict[str, ProvisioningJob] = {}

        # Weighted round-robin state
        self._rr_counter: int = 0

        os.makedirs(job_store_path, exist_ok=True)

    # =========================================
    # WEIGHTED ROUND-ROBIN PROVIDER SELECTION
    # =========================================

    async def select_provider(self, bundle: Optional[str] = None) -> str:
        """
        Select next provider using weighted round-robin.

        Weights from plan_registry.PROVIDER_WEIGHTS (out of 100):
          hetzner=40, digitalocean=20, linode=20, ovh=10, upcloud=10

        Only selects from providers that are actually initialized.
        Falls back to random choice if DB counter unavailable.
        """
        from control_plane.providers.plan_registry import PROVIDER_WEIGHTS

        # Filter to only available providers
        available = {
            pid: weight
            for pid, weight in PROVIDER_WEIGHTS.items()
            if pid in self.providers
        }

        if not available:
            # Last resort: pick any initialized provider
            if self.providers:
                return next(iter(self.providers))
            raise RuntimeError("No providers initialized")

        # Build weighted selection list (e.g., hetzner appears 40 times)
        weighted_pool = []
        for pid, weight in available.items():
            weighted_pool.extend([pid] * weight)

        # Get counter from DB or use in-memory
        counter = await self._get_rr_counter()
        selected = weighted_pool[counter % len(weighted_pool)]

        # Increment counter
        await self._increment_rr_counter()

        logger.info(
            f"Provider selected: {selected} (counter={counter}, "
            f"pool_size={len(weighted_pool)}, available={list(available.keys())})"
        )
        return selected

    async def _get_rr_counter(self) -> int:
        """Get current round-robin counter from DB or memory."""
        if self.db_pool:
            try:
                row = await self.db_pool.fetchrow(
                    "SELECT value FROM wopr_state WHERE key = 'rr_counter'"
                )
                if row:
                    return int(row["value"])
            except Exception:
                pass
        return self._rr_counter

    async def _increment_rr_counter(self) -> None:
        """Increment round-robin counter in DB and memory."""
        self._rr_counter += 1
        if self.db_pool:
            try:
                await self.db_pool.execute("""
                    INSERT INTO wopr_state (key, value)
                    VALUES ('rr_counter', $1::text)
                    ON CONFLICT (key)
                    DO UPDATE SET value = $1::text, updated_at = NOW()
                """, str(self._rr_counter))
            except Exception as e:
                logger.debug(f"Could not persist rr_counter to DB: {e}")

    def create_job(
        self,
        customer_id: str,
        customer_email: str,
        bundle: str,
        provider_id: str,
        region: str,
        datacenter_id: str,
        storage_tier: int = 1,
        customer_name: Optional[str] = None,
        custom_domain: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> ProvisioningJob:
        """Create a new provisioning job."""
        job_id = str(uuid.uuid4())

        job = ProvisioningJob(
            job_id=job_id,
            customer_id=customer_id,
            customer_email=customer_email,
            bundle=bundle,
            provider_id=provider_id,
            region=region,
            datacenter_id=datacenter_id,
            storage_tier=storage_tier,
            customer_name=customer_name,
            custom_domain=custom_domain,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

        self.jobs[job_id] = job
        self._save_job_sync(job)

        logger.info(f"Created provisioning job: {job_id} for {customer_email}")
        return job

    # =========================================
    # PERSISTENCE
    # =========================================

    def _save_job_sync(self, job: ProvisioningJob) -> None:
        """Save job to JSON file (synchronous fallback)."""
        job_file = os.path.join(self.job_store_path, f"{job.job_id}.json")
        with open(job_file, "w") as f:
            json.dump(job.to_dict(), f, indent=2)

    async def _save_job(self, job: ProvisioningJob) -> None:
        """Save job to database (or JSON fallback)."""
        if self.db_pool:
            from control_plane.database import save_job
            await save_job(self.db_pool, job.to_dict())
        else:
            await asyncio.to_thread(self._save_job_sync, job)

    async def _update_state(
        self,
        job: ProvisioningJob,
        state: ProvisioningState,
        error: Optional[str] = None,
    ) -> None:
        """Update job state and persist."""
        job.state = state
        job.updated_at = datetime.now()
        if error:
            job.error_message = error
        await self._save_job(job)
        logger.info(f"Job {job.job_id} state: {state.value}")

    # =========================================
    # MAIN ORCHESTRATION
    # =========================================

    async def run_provisioning(self, job_id: str) -> bool:
        """
        Entry point called by main.py background task.

        Looks up the job and runs the full provisioning workflow.
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return False
        return await self.execute_provisioning(job)

    async def execute_provisioning(self, job: ProvisioningJob) -> bool:
        """
        Execute the full provisioning workflow.

        This is the main orchestration method that runs through
        all steps of the one-click install.
        """
        try:
            # Step 1: Mark payment received
            await self._update_state(job, ProvisioningState.PAYMENT_RECEIVED)

            # Step 2: Provision VPS
            await self._update_state(job, ProvisioningState.PROVISIONING_VPS)
            if not await self._provision_vps(job):
                return False

            # Step 3: Wait for VPS to be ready
            await self._update_state(job, ProvisioningState.WAITING_FOR_VPS)
            if not await self._wait_for_vps(job):
                return False

            # Step 4: Configure DNS
            await self._update_state(job, ProvisioningState.CONFIGURING_DNS)
            if not await self._configure_dns(job):
                return False

            # Step 5: Deploy WOPR (via cloud-init, already in progress)
            await self._update_state(job, ProvisioningState.DEPLOYING_WOPR)
            await self._wait_for_wopr_ready(job)

            # Step 6: Generate documentation
            await self._update_state(job, ProvisioningState.GENERATING_DOCS)
            docs = await self._generate_documentation(job)

            # Step 7: Send welcome email
            await self._update_state(job, ProvisioningState.SENDING_WELCOME)
            await self._send_welcome_email(job, docs)

            # Complete!
            await self._update_state(job, ProvisioningState.COMPLETED)
            logger.info(f"Job {job.job_id} completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)
            await self._update_state(job, ProvisioningState.FAILED, str(e))
            return False

    # =========================================
    # STEP 1: PROVISION VPS
    # =========================================

    async def _provision_vps(self, job: ProvisioningJob) -> bool:
        """Provision the VPS instance."""
        provider = self.providers.get(job.provider_id)
        if not provider:
            await self._update_state(
                job, ProvisioningState.FAILED,
                f"Provider not found: {job.provider_id}"
            )
            return False

        # Generate subdomain
        short_id = job.job_id[:8]
        job.wopr_subdomain = f"{job.bundle}-{short_id}"

        # Build cloud-init user data
        user_data = self._generate_cloud_init(job)

        try:
            from control_plane.providers.base import ProvisionConfig

            provision_config = ProvisionConfig(
                name=f"wopr-{job.wopr_subdomain}",
                region=job.datacenter_id,
                plan_id=self._get_plan_for_tier(job.storage_tier, job.provider_id),
                ssh_keys=[],
                image="debian-12",
                user_data=user_data,
                wopr_bundle=job.bundle,
                wopr_customer_id=job.customer_id,
                wopr_customer_email=job.customer_email,
                wopr_customer_name=job.customer_name,
                metadata={
                    "wopr_job_id": job.job_id,
                    "wopr_instance_id": str(uuid.uuid4()),
                },
            )

            # Provider SDK calls are synchronous - run in thread
            instance = await asyncio.to_thread(
                provider.provision,
                provision_config,
            )

            job.instance_id = getattr(instance, "id", str(instance)) if instance else None
            job.instance_ip = getattr(instance, "ip_address", None)

            if hasattr(instance, "public_ips") and instance.public_ips:
                job.instance_ip = instance.public_ips[0]

            await self._save_job(job)
            logger.info(f"Provisioned instance: {job.instance_id} at {job.instance_ip}")
            return True

        except Exception as e:
            await self._update_state(
                job, ProvisioningState.FAILED,
                f"Provisioning failed: {e}"
            )
            return False

    # =========================================
    # STEP 2: WAIT FOR VPS
    # =========================================

    async def _wait_for_vps(self, job: ProvisioningJob, timeout: int = 300) -> bool:
        """Wait for VPS to be running and have an IP."""
        provider = self.providers.get(job.provider_id)
        if not provider:
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                instance = await asyncio.to_thread(
                    provider.get_instance, job.instance_id
                )
                if instance:
                    ip = getattr(instance, "ip_address", None)
                    if not ip and hasattr(instance, "public_ips") and instance.public_ips:
                        ip = instance.public_ips[0]

                    status = getattr(instance, "status", None)
                    status_str = str(status).lower() if status else ""

                    if ip and status_str in ("running", "active"):
                        job.instance_ip = ip
                        await self._save_job(job)
                        logger.info(f"VPS ready: {ip}")
                        return True

                    if status_str in ("error", "failed"):
                        await self._update_state(
                            job, ProvisioningState.FAILED,
                            "VPS entered error state"
                        )
                        return False

            except Exception as e:
                logger.warning(f"Error checking VPS status: {e}")

            await asyncio.sleep(10)

        await self._update_state(
            job, ProvisioningState.FAILED,
            "Timeout waiting for VPS"
        )
        return False

    # =========================================
    # STEP 3: CONFIGURE DNS (Cloudflare)
    # =========================================

    async def _configure_dns(self, job: ProvisioningJob) -> bool:
        """Configure DNS records via Cloudflare."""
        if not self.cloudflare_dns:
            logger.warning("No Cloudflare DNS service, skipping DNS configuration")
            return True  # Not fatal

        if not job.instance_ip:
            logger.warning("No instance IP for DNS, skipping")
            return True

        try:
            # Create A record: {subdomain}.wopr.systems -> instance IP
            record_id = await self.cloudflare_dns.create_a_record(
                name=f"{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
                ip=job.instance_ip,
                proxied=False,
            )
            job.dns_record_ids["a_record"] = record_id
            logger.info(f"Created DNS A record: {job.wopr_subdomain}.{self.WOPR_DOMAIN} -> {job.instance_ip}")

            # Create wildcard A record: *.{subdomain}.wopr.systems -> instance IP
            wildcard_id = await self.cloudflare_dns.create_a_record(
                name=f"*.{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
                ip=job.instance_ip,
                proxied=False,
            )
            job.dns_record_ids["wildcard_record"] = wildcard_id
            logger.info(f"Created DNS wildcard: *.{job.wopr_subdomain}.{self.WOPR_DOMAIN} -> {job.instance_ip}")

            await self._save_job(job)
            return True

        except Exception as e:
            logger.error(f"DNS configuration failed: {e}")
            # Not fatal - user can still use IP directly
            return True

    # =========================================
    # STEP 4: WAIT FOR WOPR READY
    # =========================================

    async def _wait_for_wopr_ready(self, job: ProvisioningJob, timeout: int = 600) -> bool:
        """Poll the beacon's health endpoint until it responds."""
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not available, using fixed wait")
            await asyncio.sleep(120)
            return True

        urls_to_check = []
        if job.wopr_subdomain:
            urls_to_check.append(f"https://{job.wopr_subdomain}.{self.WOPR_DOMAIN}/api/health")
        if job.instance_ip:
            urls_to_check.append(f"http://{job.instance_ip}:8080/api/health")

        if not urls_to_check:
            logger.warning("No URLs to check for readiness, using fixed wait")
            await asyncio.sleep(120)
            return True

        start_time = time.time()
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            while time.time() - start_time < timeout:
                for check_url in urls_to_check:
                    try:
                        resp = await client.get(check_url)
                        if resp.status_code == 200:
                            logger.info(f"WOPR ready at {check_url}")
                            return True
                    except (httpx.RequestError, httpx.TimeoutException):
                        pass

                await asyncio.sleep(15)

        logger.warning(
            f"WOPR readiness timeout after {timeout}s for {job.job_id}. "
            "Cloud-init may still be running."
        )
        # Don't fail the job - cloud-init may take longer
        return True

    # =========================================
    # STEP 5: GENERATE DOCUMENTATION
    # =========================================

    async def _generate_documentation(self, job: ProvisioningJob) -> Dict[str, Any]:
        """Generate user documentation including PDFs."""
        docs: Dict[str, Any] = {
            "welcome_url": f"https://{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
            "instance_ip": job.instance_ip,
            "subdomain": f"{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
        }

        if self.doc_generator:
            try:
                from control_plane.pdf_generator import CustomerInfo

                info = CustomerInfo(
                    customer_id=job.customer_id,
                    email=job.customer_email,
                    bundle=job.bundle,
                    instance_ip=job.instance_ip or "pending",
                    wopr_subdomain=job.wopr_subdomain or "pending",
                    wopr_domain=self.WOPR_DOMAIN,
                    custom_domain=job.custom_domain,
                )

                generated = await asyncio.to_thread(
                    self.doc_generator.generate_all_documents, info
                )
                docs.update(generated)
                logger.info(f"Generated documents: {list(generated.keys())}")

            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
                # Not fatal - continue without PDFs
        else:
            logger.warning("No document generator configured, skipping PDF generation")

        # Generate welcome PDF bytes for email attachment
        try:
            from control_plane.pdf_generator import generate_welcome_pdf_for_email

            pdf_bytes = await asyncio.to_thread(
                generate_welcome_pdf_for_email,
                name=job.customer_email.split("@")[0].title(),
                email=job.customer_email,
                beacon_name=job.wopr_subdomain or "pending",
                bundle_name=job.bundle.replace("-", " ").replace("_", " ").title(),
                tier_name=f"Tier {job.storage_tier}",
                temp_password="Set during setup wizard",
                apps=self._get_bundle_apps(job.bundle),
            )
            docs["welcome_pdf_bytes"] = pdf_bytes
        except Exception as e:
            logger.error(f"Welcome PDF generation failed: {e}")

        return docs

    # =========================================
    # STEP 6: SEND WELCOME EMAIL
    # =========================================

    async def _send_welcome_email(self, job: ProvisioningJob, docs: Dict[str, Any]) -> bool:
        """Send welcome email with setup instructions."""
        if not self.email_service:
            logger.warning("No email service configured, skipping welcome email")
            logger.info(f"Would send welcome email to {job.customer_email}")
            logger.info(f"  Beacon URL: {docs.get('welcome_url')}")
            return True

        try:
            pdf_bytes = docs.get("welcome_pdf_bytes")

            result = await asyncio.to_thread(
                self.email_service.send_welcome_email,
                to_email=job.customer_email,
                name=job.customer_email.split("@")[0].title(),
                beacon_name=job.wopr_subdomain or "pending",
                bundle_name=job.bundle.replace("-", " ").replace("_", " ").title(),
                tier_name=f"Tier {job.storage_tier}",
                billing_cycle="Monthly",
                temp_password="Set during setup wizard",
                apps=self._get_bundle_apps(job.bundle),
                pdf_attachment=pdf_bytes,
            )

            if result:
                logger.info(f"Welcome email sent to {job.customer_email}")
            else:
                logger.error(f"Welcome email failed for {job.customer_email}")

            return result

        except Exception as e:
            logger.error(f"Error sending welcome email: {e}")
            # Not fatal - user can still access their instance
            return True

    # =========================================
    # CLOUD-INIT GENERATION
    # =========================================

    def _generate_cloud_init(self, job: ProvisioningJob) -> str:
        """Generate cloud-init user data for WOPR installation."""
        return f"""#cloud-config
# WOPR Sovereign Suite Installer
# Generated: {datetime.now().isoformat()}
# Job ID: {job.job_id}

package_update: true
package_upgrade: true

packages:
  - curl
  - wget
  - git
  - jq
  - uuid-runtime
  - podman
  - iptables
  - iptables-persistent

write_files:
  - path: /etc/wopr/bootstrap.json
    permissions: '0600'
    content: |
      {{
        "job_id": "{job.job_id}",
        "customer_id": "{job.customer_id}",
        "bundle": "{job.bundle}",
        "storage_tier": {job.storage_tier},
        "domain": "{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
        "custom_domain": "{job.custom_domain or ''}",
        "provisioned_at": "{datetime.now().isoformat()}"
      }}

  - path: /opt/wopr/install.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      set -euo pipefail

      # Log output
      exec > >(tee -a /var/log/wopr/install.log) 2>&1
      echo "Starting WOPR installation at $(date)"

      # Download and run installer
      curl -fsSL https://install.wopr.systems/v1/bootstrap.sh | bash -s -- \\
        --bundle {job.bundle} \\
        --domain {job.wopr_subdomain}.{self.WOPR_DOMAIN} \\
        --non-interactive \\
        --confirm-all

      echo "WOPR installation complete at $(date)"

runcmd:
  - mkdir -p /var/log/wopr
  - mkdir -p /etc/iptables
  # Firewall rules (allow SSH, HTTP, HTTPS, Authentik)
  - iptables -F INPUT
  - iptables -A INPUT -i lo -j ACCEPT
  - iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
  - iptables -A INPUT -p icmp -j ACCEPT
  - iptables -A INPUT -p tcp --dport 22 -j ACCEPT
  - iptables -A INPUT -p tcp --dport 80 -j ACCEPT
  - iptables -A INPUT -p tcp --dport 443 -j ACCEPT
  - iptables -A INPUT -p tcp --dport 8443 -j ACCEPT
  - iptables -A INPUT -j DROP
  - iptables-save > /etc/iptables/rules.v4
  - ip6tables -F INPUT
  - ip6tables -A INPUT -i lo -j ACCEPT
  - ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
  - ip6tables -A INPUT -p icmpv6 -j ACCEPT
  - ip6tables -A INPUT -p tcp --dport 22 -j ACCEPT
  - ip6tables -A INPUT -p tcp --dport 80 -j ACCEPT
  - ip6tables -A INPUT -p tcp --dport 443 -j ACCEPT
  - ip6tables -A INPUT -p tcp --dport 8443 -j ACCEPT
  - ip6tables -A INPUT -j DROP
  - ip6tables-save > /etc/iptables/rules.v6
  # Install WOPR
  - /opt/wopr/install.sh

final_message: "WOPR Sovereign Suite installation complete after $UPTIME seconds"
"""

    # =========================================
    # HELPERS
    # =========================================

    def _get_plan_for_tier(self, storage_tier: int, provider_id: str) -> str:
        """Map storage tier to a provider plan ID."""
        # Default plans per provider per tier
        # Tier 1=MEDIUM(4GB), Tier 2=HIGH(8GB), Tier 3=VERY_HIGH(16GB)
        tier_plans = {
            "hetzner": {1: "cx22", 2: "cx32", 3: "cx42"},
            "digitalocean": {1: "s-2vcpu-4gb", 2: "s-4vcpu-8gb", 3: "s-8vcpu-16gb"},
            "linode": {1: "g6-standard-2", 2: "g6-standard-4", 3: "g6-standard-6"},
            "ovh": {1: "B2-7", 2: "B2-15", 3: "B2-30"},
            "upcloud": {1: "2xCPU-4GB", 2: "4xCPU-8GB", 3: "6xCPU-16GB"},
        }
        provider_plans = tier_plans.get(provider_id, tier_plans["hetzner"])
        return provider_plans.get(storage_tier, provider_plans.get(1, "cx22"))

    def _get_bundle_apps(self, bundle: str) -> List[Dict[str, str]]:
        """Get list of apps for a bundle (for email/PDF)."""
        try:
            from control_plane.bundles.manifests import get_modules_for_bundle
            from control_plane.modules.registry import MODULE_REGISTRY

            modules = get_modules_for_bundle(bundle)
            apps = []
            for mod_id in modules:
                mod = MODULE_REGISTRY.get(mod_id)
                if mod:
                    apps.append({
                        "name": mod.get("name", mod_id),
                        "icon": mod.get("icon", ""),
                        "subdomain": mod.get("subdomain", mod_id),
                    })
            return apps
        except Exception:
            # Fallback: return basic app list
            return [
                {"name": "Dashboard", "icon": "", "subdomain": "portal"},
                {"name": "Nextcloud", "icon": "", "subdomain": "files"},
                {"name": "Vaultwarden", "icon": "", "subdomain": "vault"},
            ]

    # =========================================
    # JOB MANAGEMENT
    # =========================================

    def get_job(self, job_id: str) -> Optional[ProvisioningJob]:
        """Get a job by ID (from cache or disk)."""
        if job_id in self.jobs:
            return self.jobs[job_id]

        # Try loading from JSON file
        job_file = os.path.join(self.job_store_path, f"{job_id}.json")
        if os.path.exists(job_file):
            try:
                with open(job_file) as f:
                    data = json.load(f)
                job = ProvisioningJob(
                    job_id=data["job_id"],
                    customer_id=data["customer_id"],
                    customer_email=data["customer_email"],
                    bundle=data["bundle"],
                    provider_id=data["provider_id"],
                    region=data.get("region", ""),
                    datacenter_id=data.get("datacenter_id", ""),
                    storage_tier=data.get("storage_tier", 1),
                    custom_domain=data.get("custom_domain"),
                    state=ProvisioningState(data.get("state", "pending")),
                    instance_id=data.get("instance_id"),
                    instance_ip=data.get("instance_ip"),
                    wopr_subdomain=data.get("wopr_subdomain"),
                    error_message=data.get("error_message"),
                    retry_count=data.get("retry_count", 0),
                    stripe_customer_id=data.get("stripe_customer_id"),
                    stripe_subscription_id=data.get("stripe_subscription_id"),
                )
                self.jobs[job_id] = job
                return job
            except Exception as e:
                logger.error(f"Error loading job {job_id}: {e}")

        return None

    def get_jobs_by_customer(self, customer_id: str) -> List[ProvisioningJob]:
        """Get all jobs for a customer."""
        return [j for j in self.jobs.values() if j.customer_id == customer_id]

    async def retry_failed_job(self, job_id: str) -> bool:
        """Retry a failed job."""
        job = self.get_job(job_id)
        if not job or job.state != ProvisioningState.FAILED:
            return False

        job.retry_count += 1
        job.error_message = None
        return await self.execute_provisioning(job)
