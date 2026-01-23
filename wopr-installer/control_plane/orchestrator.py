"""
WOPR Provisioning Orchestrator
==============================

Main orchestration engine for WOPR deployments.

Ties together:
- Stripe payment completion
- VPS provisioning
- DNS configuration
- WOPR deployment
- User notifications

Flow:
1. Payment webhook received
2. Provision VPS with selected provider
3. Wait for VPS to be ready
4. Configure DNS (subdomain.wopr.systems)
5. Deploy WOPR via cloud-init
6. Send welcome email with:
   - Dashboard access details
   - Custom domain setup instructions (PDF)
   - Getting started guide

Updated: January 2026
"""

import os
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
import logging

from providers import ProviderRegistry, ProvisionConfig, Instance, InstanceStatus
from providers.plan_registry import PlanRegistry, GeoRegion, BUNDLE_TIERS
from billing import WOPRBilling, CheckoutMetadata

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

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0

    # Stripe IDs
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "customer_email": self.customer_email,
            "bundle": self.bundle,
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
            "error_message": self.error_message,
        }


class WOPROrchestrator:
    """
    Main orchestration engine for WOPR provisioning.

    Coordinates the entire flow from payment to running instance.
    """

    # WOPR subdomain base
    WOPR_DOMAIN = "wopr.systems"

    def __init__(
        self,
        providers: Dict[str, Any],
        cloudflare_token: Optional[str] = None,
        smtp_config: Optional[Dict] = None,
        job_store_path: str = "/var/lib/wopr/jobs",
    ):
        """
        Initialize the orchestrator.

        Args:
            providers: Dict of provider_id -> configured provider instance
            cloudflare_token: API token for DNS management
            smtp_config: Email configuration for notifications
            job_store_path: Path to persist job state
        """
        self.providers = providers
        self.cloudflare_token = cloudflare_token
        self.smtp_config = smtp_config
        self.job_store_path = job_store_path
        self.jobs: Dict[str, ProvisioningJob] = {}

        os.makedirs(job_store_path, exist_ok=True)

    def create_job(
        self,
        customer_id: str,
        customer_email: str,
        bundle: str,
        provider_id: str,
        region: str,
        datacenter_id: str,
        custom_domain: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> ProvisioningJob:
        """
        Create a new provisioning job.

        Args:
            customer_id: WOPR customer ID
            customer_email: Customer email for notifications
            bundle: WOPR bundle name
            provider_id: VPS provider ID
            region: Geographic region
            datacenter_id: Specific datacenter
            custom_domain: Optional custom domain
            stripe_customer_id: Stripe customer ID
            stripe_subscription_id: Stripe subscription ID

        Returns:
            New ProvisioningJob
        """
        job_id = str(uuid.uuid4())

        job = ProvisioningJob(
            job_id=job_id,
            customer_id=customer_id,
            customer_email=customer_email,
            bundle=bundle,
            provider_id=provider_id,
            region=region,
            datacenter_id=datacenter_id,
            custom_domain=custom_domain,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

        self.jobs[job_id] = job
        self._save_job(job)

        logger.info(f"Created provisioning job: {job_id} for {customer_email}")
        return job

    def _save_job(self, job: ProvisioningJob) -> None:
        """Persist job state to disk."""
        job_file = os.path.join(self.job_store_path, f"{job.job_id}.json")
        with open(job_file, "w") as f:
            json.dump(job.to_dict(), f, indent=2)

    def _update_state(
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
        self._save_job(job)
        logger.info(f"Job {job.job_id} state: {state.value}")

    # =========================================
    # MAIN ORCHESTRATION FLOW
    # =========================================

    def execute_provisioning(self, job: ProvisioningJob) -> bool:
        """
        Execute the full provisioning workflow.

        This is the main orchestration method that runs through
        all steps of the one-click install.

        Args:
            job: ProvisioningJob to execute

        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Mark payment received
            self._update_state(job, ProvisioningState.PAYMENT_RECEIVED)

            # Step 2: Provision VPS
            self._update_state(job, ProvisioningState.PROVISIONING_VPS)
            if not self._provision_vps(job):
                return False

            # Step 3: Wait for VPS to be ready
            self._update_state(job, ProvisioningState.WAITING_FOR_VPS)
            if not self._wait_for_vps(job):
                return False

            # Step 4: Configure DNS
            self._update_state(job, ProvisioningState.CONFIGURING_DNS)
            if not self._configure_dns(job):
                return False

            # Step 5: Deploy WOPR (via cloud-init, already in progress)
            self._update_state(job, ProvisioningState.DEPLOYING_WOPR)
            # Cloud-init handles this, we just wait for it to complete
            self._wait_for_wopr_ready(job)

            # Step 6: Generate documentation
            self._update_state(job, ProvisioningState.GENERATING_DOCS)
            docs = self._generate_documentation(job)

            # Step 7: Send welcome email
            self._update_state(job, ProvisioningState.SENDING_WELCOME)
            self._send_welcome_email(job, docs)

            # Complete!
            self._update_state(job, ProvisioningState.COMPLETED)
            logger.info(f"Job {job.job_id} completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            self._update_state(job, ProvisioningState.FAILED, str(e))
            return False

    # =========================================
    # STEP IMPLEMENTATIONS
    # =========================================

    def _provision_vps(self, job: ProvisioningJob) -> bool:
        """Provision the VPS instance."""
        provider = self.providers.get(job.provider_id)
        if not provider:
            self._update_state(job, ProvisioningState.FAILED, f"Provider not found: {job.provider_id}")
            return False

        # Get recommended plan for bundle
        plan = PlanRegistry.get_plan_for_bundle(job.provider_id, job.bundle)
        if not plan:
            self._update_state(job, ProvisioningState.FAILED, f"No plan for bundle: {job.bundle}")
            return False

        # Generate subdomain
        short_id = job.job_id[:8]
        job.wopr_subdomain = f"{job.bundle}-{short_id}"

        # Build cloud-init user data
        user_data = self._generate_cloud_init(job)

        # Create provision config
        config = ProvisionConfig(
            name=f"wopr-{job.wopr_subdomain}",
            region=job.datacenter_id,
            plan_id=plan.plan_id,
            ssh_keys=[],  # Will use cloud-init for key injection
            image="debian-12",
            user_data=user_data,
            wopr_bundle=job.bundle,
            wopr_customer_id=job.customer_id,
            metadata={
                "wopr_job_id": job.job_id,
                "wopr_instance_id": str(uuid.uuid4()),
            }
        )

        try:
            instance = provider.provision(config)
            job.instance_id = instance.id
            job.instance_ip = instance.ip_address
            logger.info(f"Provisioned instance: {instance.id} at {instance.ip_address}")
            return True

        except Exception as e:
            self._update_state(job, ProvisioningState.FAILED, f"Provisioning failed: {e}")
            return False

    def _wait_for_vps(self, job: ProvisioningJob, timeout: int = 300) -> bool:
        """Wait for VPS to be running and have an IP."""
        provider = self.providers.get(job.provider_id)
        if not provider:
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            instance = provider.get_instance(job.instance_id)
            if instance:
                if instance.status == InstanceStatus.RUNNING and instance.ip_address:
                    job.instance_ip = instance.ip_address
                    logger.info(f"VPS ready: {instance.ip_address}")
                    return True
                elif instance.status == InstanceStatus.ERROR:
                    self._update_state(job, ProvisioningState.FAILED, "VPS entered error state")
                    return False

            time.sleep(10)

        self._update_state(job, ProvisioningState.FAILED, "Timeout waiting for VPS")
        return False

    def _configure_dns(self, job: ProvisioningJob) -> bool:
        """Configure DNS for the instance."""
        if not self.cloudflare_token:
            logger.warning("No Cloudflare token, skipping DNS configuration")
            return True  # Not fatal

        # Create A record: {subdomain}.wopr.systems -> instance IP
        try:
            # This would use Cloudflare API
            # For now, just log what we would do
            logger.info(f"Would create DNS: {job.wopr_subdomain}.{self.WOPR_DOMAIN} -> {job.instance_ip}")
            return True

        except Exception as e:
            logger.error(f"DNS configuration failed: {e}")
            # Not fatal, user can still use IP
            return True

    def _wait_for_wopr_ready(self, job: ProvisioningJob, timeout: int = 600) -> bool:
        """Wait for WOPR installation to complete."""
        # Cloud-init handles the installation
        # We could poll an endpoint on the instance to check status
        # For now, we just wait a reasonable time
        time.sleep(120)  # Give cloud-init time to run
        return True

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

write_files:
  - path: /etc/wopr/bootstrap.json
    permissions: '0600'
    content: |
      {{
        "job_id": "{job.job_id}",
        "customer_id": "{job.customer_id}",
        "bundle": "{job.bundle}",
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
  - /opt/wopr/install.sh

final_message: "WOPR Sovereign Suite installation complete after $UPTIME seconds"
"""

    def _generate_documentation(self, job: ProvisioningJob) -> Dict[str, str]:
        """Generate user documentation including custom domain setup PDF."""
        docs = {
            "welcome_url": f"https://{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
            "instance_ip": job.instance_ip,
            "subdomain": f"{job.wopr_subdomain}.{self.WOPR_DOMAIN}",
        }

        # Generate custom domain setup instructions if they provided one
        if job.custom_domain:
            docs["custom_domain_pdf"] = self._generate_custom_domain_pdf(job)

        return docs

    def _generate_custom_domain_pdf(self, job: ProvisioningJob) -> str:
        """
        Generate PDF with custom domain setup instructions.

        Returns path to generated PDF.
        """
        # This would use a PDF library like reportlab or weasyprint
        # For now, generate the content that would go in the PDF

        pdf_content = f"""
WOPR SOVEREIGN SUITE
Custom Domain Setup Guide
========================

Hello! Thank you for choosing WOPR Sovereign Suite.

Your instance is now running at:
  IP Address: {job.instance_ip}
  WOPR Domain: {job.wopr_subdomain}.{self.WOPR_DOMAIN}

You requested to use your custom domain:
  {job.custom_domain}

STEP 1: Log into your domain registrar
----------------------------------------
Go to where you purchased your domain (GoDaddy, Namecheap,
Cloudflare, etc.) and find the DNS settings.

STEP 2: Create an A Record
----------------------------------------
Add a new DNS record with these settings:

  Type: A
  Name: @ (or leave blank for root domain)
        OR enter a subdomain like "cloud"
  Value: {job.instance_ip}
  TTL: 3600 (or "1 hour")

Example for "cloud.{job.custom_domain}":
  Type: A
  Name: cloud
  Value: {job.instance_ip}
  TTL: 3600

STEP 3: Wait for DNS propagation
----------------------------------------
DNS changes can take 5 minutes to 48 hours to propagate.
You can check progress at: https://dnschecker.org

STEP 4: Verify in WOPR
----------------------------------------
Once DNS has propagated, log into your WOPR dashboard at:
  https://{job.wopr_subdomain}.{self.WOPR_DOMAIN}

Go to Settings > Custom Domain and enter:
  {job.custom_domain}

WOPR will automatically obtain an SSL certificate for your
custom domain using Let's Encrypt.

NEED HELP?
----------------------------------------
- Documentation: https://docs.wopr.systems
- Support: support@wopr.systems
- Community: https://community.wopr.systems

Your WOPR Instance Details:
  Customer ID: {job.customer_id}
  Bundle: {job.bundle.title()}
  Server Location: {job.region}

Thank you for choosing sovereignty!
- The WOPR Team
"""

        # In production, convert to PDF
        # For now, save as text
        pdf_path = os.path.join(self.job_store_path, f"{job.job_id}_domain_setup.txt")
        with open(pdf_path, "w") as f:
            f.write(pdf_content)

        return pdf_path

    def _send_welcome_email(self, job: ProvisioningJob, docs: Dict[str, str]) -> bool:
        """Send welcome email with setup instructions."""
        if not self.smtp_config:
            logger.warning("No SMTP config, skipping welcome email")
            return True

        # Email content
        subject = f"Your WOPR {job.bundle.title()} Suite is Ready!"

        body = f"""
Hello!

Great news - your WOPR Sovereign Suite is now live!

ACCESS YOUR SUITE
-----------------
URL: {docs['welcome_url']}

Your personal cloud is ready to use. Visit the URL above
to complete the initial setup and start using your apps.

INSTANCE DETAILS
----------------
Bundle: {job.bundle.title()} Sovereign Suite
Server IP: {docs['instance_ip']}
WOPR Domain: {docs['subdomain']}

"""

        if job.custom_domain:
            body += f"""
CUSTOM DOMAIN
-------------
You requested to use: {job.custom_domain}

We've attached a PDF guide showing exactly how to point
your domain to your new WOPR instance. It only takes a
few minutes!

"""

        body += """
GETTING STARTED
---------------
1. Visit your WOPR URL above
2. Complete the initial setup wizard
3. Create your admin account
4. Start using your sovereign apps!

NEED HELP?
----------
Documentation: https://docs.wopr.systems
Support: support@wopr.systems
Community: https://community.wopr.systems

Welcome to digital sovereignty!

- The WOPR Team

---
This email was sent because you subscribed to WOPR Sovereign Suite.
To manage your subscription, visit: https://wopr.systems/account
"""

        # In production, send via SMTP
        logger.info(f"Would send welcome email to {job.customer_email}")
        logger.info(f"Subject: {subject}")

        return True

    # =========================================
    # JOB MANAGEMENT
    # =========================================

    def get_job(self, job_id: str) -> Optional[ProvisioningJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def get_jobs_by_customer(self, customer_id: str) -> List[ProvisioningJob]:
        """Get all jobs for a customer."""
        return [j for j in self.jobs.values() if j.customer_id == customer_id]

    def retry_failed_job(self, job_id: str) -> bool:
        """Retry a failed job."""
        job = self.jobs.get(job_id)
        if not job or job.state != ProvisioningState.FAILED:
            return False

        job.retry_count += 1
        job.error_message = None
        return self.execute_provisioning(job)
