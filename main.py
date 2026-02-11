"""
WOPR Orchestrator API
=====================

Main entry point for the orchestrator service at orc.wopr.systems

Endpoints:
- POST /api/webhook/stripe - Stripe webhook (public, signature verified)
- POST /api/provision - Start provisioning (admin only)
- GET /api/provision/{job_id}/status - Get provisioning status
- GET /api/provision/{job_id}/stream - SSE progress stream
- GET /api/health - Health check
- GET /api/providers - List available providers
"""

import asyncio
import io
import json
import logging
import os
import re
import tarfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, field_validator
import stripe

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load .env file if present (dev mode)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# WOPR internal imports
from control_plane.config import WOPRConfig
from control_plane.orchestrator import WOPROrchestrator, ProvisioningState, ProvisioningJob

logger = logging.getLogger(__name__)

# Load centralized config from environment
config = WOPRConfig.from_env()

# Initialize Stripe
if config.stripe.secret_key:
    stripe.api_key = config.stripe.secret_key

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI
app = FastAPI(
    title="WOPR Orchestrator",
    description="Beacon provisioning and management API",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS from config
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
providers: Dict[str, Any] = {}
db_pool = None
email_service = None
doc_generator = None
cloudflare_dns = None
_orchestrator = None


def init_providers():
    """Initialize VPS providers from config."""
    global providers
    tokens = config.providers

    # Hetzner (native SDK)
    if tokens.hetzner:
        try:
            from control_plane.providers.hetzner import HetznerProvider
            providers["hetzner"] = HetznerProvider(tokens.hetzner)
            logger.info("Hetzner provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Hetzner: {e}")

    # DigitalOcean (libcloud)
    if tokens.digitalocean:
        try:
            from control_plane.providers.digitalocean import DigitalOceanProvider
            providers["digitalocean"] = DigitalOceanProvider(tokens.digitalocean)
            logger.info("DigitalOcean provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DigitalOcean: {e}")

    # Linode (libcloud)
    if tokens.linode:
        try:
            from control_plane.providers.linode import LinodeProvider
            providers["linode"] = LinodeProvider(tokens.linode)
            logger.info("Linode provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Linode: {e}")

    # OVH (OpenStack via libcloud)
    if tokens.ovh_application_key and tokens.ovh_project_id:
        try:
            from control_plane.providers.ovh import OVHProvider
            providers["ovh"] = OVHProvider(
                api_token=tokens.ovh_application_key,
                project_id=tokens.ovh_project_id,
            )
            logger.info("OVH provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OVH: {e}")

    # UpCloud (REST API)
    if tokens.upcloud:
        try:
            from control_plane.providers.upcloud import UpCloudProvider
            providers["upcloud"] = UpCloudProvider(tokens.upcloud)
            logger.info("UpCloud provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize UpCloud: {e}")

    logger.info(f"Initialized {len(providers)} provider(s): {list(providers.keys())}")


def init_email_service():
    """Initialize the email service."""
    global email_service
    if not config.smtp.is_configured:
        logger.warning("SMTP not configured, email service disabled")
        return

    try:
        from control_plane.email_service import EmailService, EmailConfig
        email_config = EmailConfig(
            smtp_host=config.smtp.host,
            smtp_port=config.smtp.port,
            smtp_user=config.smtp.user,
            smtp_password=config.smtp.password,
            from_email=config.smtp.from_email,
            reply_to=config.smtp.reply_to,
            use_tls=config.smtp.use_tls,
        )
        email_service = EmailService(email_config)
        logger.info("Email service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize email service: {e}")


def init_doc_generator():
    """Initialize the PDF document generator."""
    global doc_generator
    try:
        from control_plane.pdf_generator import WOPRDocumentGenerator
        doc_generator = WOPRDocumentGenerator(
            output_dir=config.document_output_dir,
        )
        logger.info("Document generator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize document generator: {e}")


async def init_cloudflare_dns():
    """Initialize Cloudflare DNS service."""
    global cloudflare_dns
    if not config.cloudflare.is_configured:
        logger.warning("Cloudflare not configured, DNS automation disabled")
        return

    try:
        from control_plane.services.cloudflare_dns import CloudflareDNS
        cloudflare_dns = CloudflareDNS(
            api_token=config.cloudflare.api_token,
            zone_id=config.cloudflare.zone_id,
        )
        logger.info("Cloudflare DNS service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Cloudflare DNS: {e}")


async def init_database():
    """Initialize the database connection pool."""
    global db_pool
    try:
        from control_plane.database import init_database as db_init
        db_pool = await db_init(config.database.url)
        logger.info("Database pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Running without database — jobs will use JSON file storage")


@app.on_event("startup")
async def startup_event():
    """Initialize all services on startup."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Initialize services (DB is async, others are sync)
    await init_database()
    await init_cloudflare_dns()
    init_providers()
    init_email_service()
    init_doc_generator()

    # Create job store directory (JSON fallback)
    import os
    os.makedirs(config.job_store_path, exist_ok=True)

    # Retry any jobs that were interrupted by a restart
    asyncio.create_task(retry_stale_jobs())

    logger.info("WOPR Orchestrator API started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")


def get_orchestrator():
    """Get or create the orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WOPROrchestrator(
            providers=providers,
            db_pool=db_pool,
            cloudflare_dns=cloudflare_dns,
            email_service=email_service,
            doc_generator=doc_generator,
            wopr_domain=config.wopr_domain,
            job_store_path=config.job_store_path,
        )
    return _orchestrator


class ProvisionRequest(BaseModel):
    bundle: str  # e.g., "sovereign-starter"
    tier: int = 1
    email: str
    domain: Optional[str] = None
    username: str
    display_name: str
    provider: str = "hetzner"
    region: str = "ash"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]{3,32}$", v):
            raise ValueError("Username must be 3-32 chars: letters, numbers, hyphens, underscores")
        return v.strip()

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v):
        if v and not re.match(r"^[a-z0-9][a-z0-9.-]{1,253}[a-z0-9]$", v.lower()):
            raise ValueError("Invalid domain format")
        return v.lower().strip() if v else None

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v):
        if v not in (1, 2, 3):
            raise ValueError("Tier must be 1, 2, or 3")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        valid = {"hetzner", "digitalocean", "vultr", "linode", "ovh"}
        if v not in valid:
            raise ValueError(f"Provider must be one of: {', '.join(valid)}")
        return v


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "providers": list(providers.keys()),
        "stripe_configured": bool(config.stripe.secret_key),
        "webhook_configured": bool(config.stripe.webhook_secret),
        "database_connected": db_pool is not None,
        "email_configured": email_service is not None,
        "dns_configured": cloudflare_dns is not None,
        "pdf_configured": doc_generator is not None,
    }

    # DB health check
    if db_pool:
        try:
            from control_plane.database import check_health
            db_health = await check_health(db_pool)
            health["database"] = db_health
        except Exception as e:
            health["database"] = {"status": "error", "error": str(e)}

    return health


@app.get("/api/installer/latest.tar.gz")
async def download_installer():
    """
    Serve the WOPR installer as a tarball.

    Beacons download this during cloud-init bootstrap.
    Public endpoint - no auth required.
    """
    # Installer lives alongside this file
    installer_dir = Path(__file__).parent / "wopr-installer"

    # Create tarball in memory
    buffer = io.BytesIO()

    # Files/dirs to include in the installer tarball
    include_paths = [
        "scripts",
        "templates",
        "systemd",
        "nginx",
        "manifest.json",
        "requirements.txt",
    ]

    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel_path in include_paths:
            full_path = installer_dir / rel_path
            if full_path.exists():
                tar.add(full_path, arcname=rel_path)

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/gzip",
        headers={
            "Content-Disposition": "attachment; filename=wopr-installer-latest.tar.gz"
        }
    )


@app.post("/api/webhook/stripe")
@limiter.limit("30/minute")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Stripe webhook events.

    This endpoint is PUBLIC but secured via Stripe signature verification.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not config.stripe.webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.stripe.webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    logger.info(f"Stripe webhook received: {event_type}")

    # ---- checkout.session.completed ----
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})

        bundle = metadata.get("wopr_bundle", metadata.get("bundle", "sovereign-starter"))
        tier = int(metadata.get("wopr_tier", metadata.get("tier", "1")))
        email = session.get("customer_email", "")
        domain = metadata.get("wopr_custom_domain", metadata.get("domain", ""))
        display_name = metadata.get("wopr_customer_name", metadata.get("display_name", ""))
        provider = metadata.get("wopr_provider", metadata.get("provider", ""))
        region = metadata.get("wopr_region", metadata.get("region", ""))

        orchestrator = get_orchestrator()

        # Auto-select provider via weighted round-robin if not specified
        if not provider or provider not in providers:
            provider = await orchestrator.select_provider(bundle=bundle)

        # Auto-select region based on provider defaults
        if not region:
            default_regions = {
                "hetzner": "ash",
                "digitalocean": "nyc1",
                "linode": "us-east",
                "ovh": "US-EAST-VA-1",
                "upcloud": "us-chi1",
            }
            region = default_regions.get(provider, "ash")

        job = orchestrator.create_job(
            customer_id=session.get("customer", ""),
            customer_email=email,
            bundle=bundle,
            provider_id=provider,
            region=region,
            datacenter_id=region,
            storage_tier=tier,
            customer_name=display_name or session.get("customer_details", {}).get("name") or None,
            custom_domain=domain or None,
            stripe_customer_id=session.get("customer"),
            stripe_subscription_id=session.get("subscription"),
        )

        background_tasks.add_task(run_provisioning, job.job_id)
        return {"received": True, "job_id": job.job_id}

    # ---- invoice.payment_failed ----
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer", "")
        subscription_id = invoice.get("subscription", "")
        logger.warning(f"Payment failed for customer={customer_id} sub={subscription_id}")

        if db_pool:
            try:
                from control_plane.database import record_payment_failure
                failure_count = await record_payment_failure(
                    db_pool,
                    subscription_id=subscription_id,
                    invoice_id=invoice.get("id", ""),
                    amount_cents=invoice.get("amount_due", 0),
                    failure_reason=invoice.get("last_finalization_error", {}).get("message", "unknown"),
                )

                # Dunning escalation based on failure count
                if email_service and customer_id:
                    try:
                        customer = stripe.Customer.retrieve(customer_id)
                        customer_email = customer.get("email", "")
                        if customer_email:
                            await _send_dunning_email(
                                customer_email, failure_count, subscription_id
                            )
                    except Exception as e:
                        logger.error(f"Failed to send dunning email: {e}")

            except Exception as e:
                logger.error(f"Failed to record payment failure: {e}")

        return {"received": True}

    # ---- customer.subscription.deleted ----
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer", "")
        subscription_id = subscription.get("id", "")
        logger.info(f"Subscription cancelled: customer={customer_id} sub={subscription_id}")
        await _handle_subscription_cleanup(customer_id, subscription_id)

        return {"received": True}

    # ---- customer.subscription.updated ----
    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        subscription_id = subscription.get("id", "")
        sub_status = subscription.get("status", "")
        logger.info(f"Subscription updated: {subscription_id} status={sub_status}")

        # If payment succeeds after failures, resolve dunning and unsuspend
        if sub_status == "active" and db_pool:
            try:
                from control_plane.database import (
                    resolve_payment_failures,
                    get_beacon_by_subscription,
                    update_beacon_status,
                )
                await resolve_payment_failures(db_pool, subscription_id)
                beacon = await get_beacon_by_subscription(db_pool, subscription_id)
                if beacon and beacon.get("status") == "suspended":
                    await update_beacon_status(db_pool, beacon["id"], "active")
                    logger.info(f"Beacon {beacon['id']} reactivated after payment recovery")
            except Exception as e:
                logger.error(f"Failed to handle subscription recovery: {e}")

        # Handle plan/tier changes from subscription metadata
        metadata = subscription.get("metadata", {})
        new_bundle = metadata.get("wopr_bundle")
        new_tier = metadata.get("wopr_tier")

        if (new_bundle or new_tier) and db_pool:
            try:
                from control_plane.database import get_beacon_by_subscription, update_beacon_status
                beacon = await get_beacon_by_subscription(db_pool, subscription_id)
                if beacon:
                    update_kwargs = {}
                    if new_bundle and new_bundle != beacon.get("bundle"):
                        update_kwargs["bundle"] = new_bundle
                    if new_tier and int(new_tier.replace("t", "")) != beacon.get("storage_tier"):
                        update_kwargs["storage_tier"] = int(new_tier.replace("t", ""))
                    if update_kwargs:
                        await update_beacon_status(
                            db_pool, beacon["id"], beacon.get("status", "active"),
                            **update_kwargs,
                        )
                        logger.info(f"Beacon {beacon['id']} updated: {update_kwargs}")
            except Exception as e:
                logger.error(f"Failed to handle plan change: {e}")

        return {"received": True}

    # ---- customer.subscription.trial_will_end ----
    elif event_type == "customer.subscription.trial_will_end":
        subscription = event["data"]["object"]
        customer_email = ""
        customer_id = subscription.get("customer", "")

        # Try to get customer email
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get("email", "")
        except Exception:
            pass

        if email_service and customer_email:
            try:
                # Look up beacon details for the reminder
                beacon_name = "your beacon"
                bundle_name = "WOPR"
                tier_name = ""
                monthly_price = ""
                sub_metadata = subscription.get("metadata", {})

                if db_pool:
                    try:
                        from control_plane.database import get_beacon_by_subscription
                        beacon = await get_beacon_by_subscription(db_pool, subscription.get("id", ""))
                        if beacon:
                            beacon_name = beacon.get("name", beacon_name)
                            bundle_name = (beacon.get("bundle", "WOPR") or "").replace("_", " ").replace("-", " ").title()
                            tier_name = f"Tier {beacon.get('storage_tier', 1)}"
                    except Exception:
                        pass

                await asyncio.to_thread(
                    email_service.send_trial_reminder,
                    to_email=customer_email,
                    name=customer_email.split("@")[0].title(),
                    beacon_name=beacon_name,
                    bundle_name=bundle_name,
                    tier_name=tier_name,
                    monthly_price=monthly_price,
                    days_remaining=3,
                    trial_days_used=0,
                )
                logger.info(f"Trial ending reminder sent to {customer_email}")
            except Exception as e:
                logger.error(f"Failed to send trial reminder: {e}")

        return {"received": True}

    return {"received": True}


async def _send_dunning_email(customer_email: str, failure_count: int, subscription_id: str):
    """Send escalating dunning emails based on failure count."""
    if not email_service:
        return

    name = customer_email.split("@")[0].title()

    # Look up beacon details for the email
    beacon_name = "your beacon"
    if db_pool:
        try:
            from control_plane.database import get_beacon_by_subscription
            beacon = await get_beacon_by_subscription(db_pool, subscription_id)
            if beacon:
                beacon_name = beacon.get("name", beacon_name)
        except Exception:
            pass

    # Map failure count to grace days
    grace_days = max(0, 7 - (failure_count * 2))

    try:
        await asyncio.to_thread(
            email_service.send_payment_failed,
            to_email=customer_email,
            name=name,
            beacon_name=beacon_name,
            amount="your subscription",
            billing_period="current period",
            card_brand="",
            card_last4="",
            failure_reason="Payment could not be processed",
            grace_days_remaining=grace_days,
        )
        logger.info(f"Dunning email (failure #{failure_count}) sent to {customer_email}")

        # Suspend the beacon after 3+ failures
        if failure_count >= 3 and db_pool:
            from control_plane.database import get_beacon_by_subscription, update_beacon_status
            beacon = await get_beacon_by_subscription(db_pool, subscription_id)
            if beacon:
                await update_beacon_status(db_pool, beacon["id"], "suspended")
                logger.warning(f"Beacon {beacon['id']} suspended due to {failure_count} payment failures")

    except Exception as e:
        logger.error(f"Dunning email failed: {e}")


async def _handle_subscription_cleanup(customer_id: str, subscription_id: str):
    """Clean up resources when a subscription is cancelled."""
    if not db_pool:
        return

    try:
        from control_plane.database import get_beacon_by_subscription, update_beacon_status
        beacon = await get_beacon_by_subscription(db_pool, subscription_id)
        if not beacon:
            logger.warning(f"No beacon found for subscription {subscription_id}")
            return

        beacon_id = beacon["id"]
        provider_id = beacon.get("provider")
        instance_id = beacon.get("instance_id")

        # Delete DNS records
        if cloudflare_dns and beacon.get("dns_record_ids"):
            import json
            try:
                record_ids = json.loads(beacon["dns_record_ids"]) if isinstance(beacon["dns_record_ids"], str) else beacon["dns_record_ids"]
                await cloudflare_dns.delete_beacon_records(record_ids)
                logger.info(f"DNS records deleted for beacon {beacon_id}")
            except Exception as e:
                logger.error(f"Failed to delete DNS records for beacon {beacon_id}: {e}")

        # Destroy VPS instance
        if provider_id and instance_id and provider_id in providers:
            try:
                provider = providers[provider_id]
                await asyncio.to_thread(provider.destroy, instance_id)
                logger.info(f"VPS instance {instance_id} destroyed for beacon {beacon_id}")
            except Exception as e:
                logger.error(f"Failed to destroy VPS for beacon {beacon_id}: {e}")

        # Mark beacon as decommissioned
        await update_beacon_status(db_pool, beacon_id, "decommissioned")
        logger.info(f"Beacon {beacon_id} decommissioned")

        # Send cancellation email
        if email_service:
            # Try multiple fields for the email (schema uses different column names)
            customer_email = (
                beacon.get("owner_email")
                or beacon.get("customer_email")
                or ""
            )
            # If no email on beacon, look up from user record
            if not customer_email and beacon.get("owner_id"):
                try:
                    async with db_pool.acquire() as conn:
                        user_row = await conn.fetchrow(
                            "SELECT email FROM users WHERE id = $1", beacon["owner_id"]
                        )
                        if user_row:
                            customer_email = user_row["email"]
                except Exception:
                    pass

            if customer_email:
                try:
                    # Calculate service end date (now, since subscription is deleted)
                    from datetime import datetime, timedelta
                    end_date = (datetime.now() + timedelta(days=7)).strftime("%B %d, %Y")

                    await asyncio.to_thread(
                        email_service.send_subscription_cancelled,
                        to_email=customer_email,
                        name=customer_email.split("@")[0].title(),
                        beacon_name=beacon.get("name", beacon.get("subdomain", "")),
                        end_date=end_date,
                    )
                except Exception as e:
                    logger.error(f"Failed to send cancellation email: {e}")

    except Exception as e:
        logger.error(f"Subscription cleanup failed for {subscription_id}: {e}")


async def run_provisioning(job_id: str):
    """Run the full provisioning workflow."""
    orchestrator = get_orchestrator()
    try:
        success = await orchestrator.run_provisioning(job_id)
        if not success:
            # Schedule automatic retry if under the limit
            job = orchestrator.get_job(job_id)
            if job and job.retry_count < 3:
                wait_seconds = 60 * (2 ** job.retry_count)  # exponential backoff: 60s, 120s, 240s
                logger.info(f"Scheduling retry #{job.retry_count + 1} for {job_id} in {wait_seconds}s")
                await asyncio.sleep(wait_seconds)
                await orchestrator.retry_failed_job(job_id)
    except Exception as e:
        logger.error(f"Provisioning failed for {job_id}: {e}", exc_info=True)


async def retry_stale_jobs():
    """On startup, retry any jobs that were left in a non-terminal state."""
    await asyncio.sleep(10)  # Wait for services to initialize
    orchestrator = get_orchestrator()

    if db_pool:
        try:
            from control_plane.database import get_jobs_by_state
            for state in ["provisioning_vps", "waiting_for_vps", "configuring_dns",
                          "deploying_wopr", "generating_docs", "sending_welcome"]:
                stale_jobs = await get_jobs_by_state(db_pool, state)
                for job_data in stale_jobs:
                    job_id = str(job_data["job_id"])
                    retry_count = job_data.get("retry_count", 0)
                    if retry_count < 3:
                        logger.info(f"Retrying stale job {job_id} (was in state: {state})")
                        asyncio.create_task(run_provisioning(job_id))
        except Exception as e:
            logger.error(f"Failed to retry stale jobs: {e}")


@app.post("/api/provision")
@limiter.limit("5/minute")
async def start_provisioning(
    request: ProvisionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually start provisioning (admin endpoint).

    This should be protected by Authentik in production.
    """
    if request.provider not in providers:
        raise HTTPException(
            status_code=400,
            detail=f"Provider not available: {request.provider}. Available: {list(providers.keys())}"
        )

    orchestrator = get_orchestrator()

    job = orchestrator.create_job(
        customer_id="manual",
        customer_email=request.email,
        bundle=request.bundle,
        provider_id=request.provider,
        region=request.region,
        datacenter_id=request.region,
        storage_tier=request.tier,
        custom_domain=request.domain,
    )

    background_tasks.add_task(run_provisioning, job.job_id)

    return {"job_id": job.job_id, "status": "provisioning_started"}


@app.get("/api/provision/{job_id}/status")
async def get_provision_status(job_id: str):
    """Get current provisioning status."""
    orchestrator = get_orchestrator()
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@app.get("/api/provision/{job_id}/stream")
@app.get("/api/v1/provisioning/{job_id}/stream")
async def stream_provision_status(job_id: str):
    """
    SSE stream for real-time provisioning updates.

    Used by the setup progress page.
    """
    orchestrator = get_orchestrator()

    # Map provisioning states to frontend step index and progress %
    STATE_TO_STEP = {
        ProvisioningState.PENDING: (0, 0),
        ProvisioningState.PAYMENT_RECEIVED: (0, 10),
        ProvisioningState.PROVISIONING_VPS: (1, 20),
        ProvisioningState.WAITING_FOR_VPS: (1, 35),
        ProvisioningState.CONFIGURING_DNS: (2, 50),
        ProvisioningState.DEPLOYING_WOPR: (3, 65),
        ProvisioningState.GENERATING_DOCS: (4, 85),
        ProvisioningState.SENDING_WELCOME: (4, 90),
        ProvisioningState.COMPLETED: (5, 100),
        ProvisioningState.FAILED: (0, 0),
    }

    async def event_generator():
        last_state = None
        while True:
            job = orchestrator.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found', 'status': 'error'})}\n\n"
                break

            current_state = job.state
            if current_state != last_state:
                step, progress = STATE_TO_STEP.get(current_state, (0, 0))

                payload = {
                    "progress": progress,
                    "step": step,
                    "state": current_state.value,
                    "job_id": job.job_id,
                }

                if current_state == ProvisioningState.COMPLETED:
                    beacon_domain = f"{job.wopr_subdomain}.{config.wopr_domain}" if job.wopr_subdomain else ""
                    payload["status"] = "complete"
                    payload["beacon_url"] = f"https://{beacon_domain}" if beacon_domain else ""
                    payload["dashboard_url"] = f"https://{beacon_domain}/dashboard" if beacon_domain else ""
                    payload["instance_ip"] = job.instance_ip
                    payload["custom_domain"] = job.custom_domain
                elif current_state == ProvisioningState.FAILED:
                    payload["status"] = "error"
                    payload["error"] = job.error_message or "Provisioning failed"
                else:
                    payload["status"] = "in_progress"

                yield f"data: {json.dumps(payload)}\n\n"
                last_state = current_state

            if current_state in [ProvisioningState.COMPLETED, ProvisioningState.FAILED]:
                break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# =============================================================================
# Beacon Installation Status Callbacks (called by installer on VPS)
# =============================================================================

@app.post("/api/v1/provision/{job_id}/status")
async def update_provision_status(job_id: str, request: Request):
    """
    Callback from beacon installer to update provisioning status.
    Called by wopr_bootstrap.sh during installation.
    """
    orchestrator = get_orchestrator()
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        data = await request.json()
        status = data.get("status", "")
        message = data.get("message", "")
        retry_count = data.get("retry_count", 0)

        logger.info(f"[{job_id}] Beacon status update: {status} - {message} (retry {retry_count})")

        # Update job metadata with retry info
        if not isinstance(job.metadata, dict):
            job.metadata = {}
        job.metadata["last_status"] = status
        job.metadata["last_message"] = message
        job.metadata["retry_count"] = retry_count
        job.metadata["last_callback"] = datetime.now().isoformat()

        # Map beacon status to orchestrator state
        if status == "complete":
            orchestrator._update_state(job, ProvisioningState.COMPLETED)
        elif status == "failed":
            orchestrator._update_state(job, ProvisioningState.FAILED, message)
        elif status == "installing":
            orchestrator._update_state(job, ProvisioningState.DEPLOYING_WOPR)

        return {"received": True, "job_id": job_id}
    except Exception as e:
        logger.error(f"[{job_id}] Status update failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/provision/{job_id}/support-ticket")
async def create_support_ticket(job_id: str, request: Request):
    """
    Create a support ticket when installation fails after max retries.
    Called by wopr_bootstrap.sh when all retry attempts are exhausted.
    """
    orchestrator = get_orchestrator()
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        data = await request.json()
        email = data.get("email", "stephen.falken@wopr.systems")
        subject = data.get("subject", f"Installation Failed: {job_id}")
        body = data.get("body", "")

        logger.error(f"[{job_id}] Support ticket created: {subject}")

        # Store ticket info in job metadata
        if not isinstance(job.metadata, dict):
            job.metadata = {}
        job.metadata["support_ticket"] = {
            "created_at": datetime.now().isoformat(),
            "email": email,
            "subject": subject,
        }

        # Try to send email via Mailgun if configured
        try:
            from control_plane.email import send_email
            await send_email(
                to=email,
                subject=subject,
                body=body,
            )
            logger.info(f"[{job_id}] Support ticket email sent to {email}")
        except Exception as email_err:
            logger.warning(f"[{job_id}] Failed to send support email: {email_err}")

        # Update job state to failed
        orchestrator._update_state(job, ProvisioningState.FAILED, "Max retries exceeded - support ticket created")

        return {"received": True, "ticket_created": True, "job_id": job_id}
    except Exception as e:
        logger.error(f"[{job_id}] Support ticket creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/providers")
async def list_providers():
    """List available VPS providers."""
    return {
        "providers": [
            {"id": pid, "name": getattr(p, "PROVIDER_NAME", pid)}
            for pid, p in providers.items()
        ]
    }


# ============================================
# ONBOARDING ENDPOINTS (public, no auth)
# ============================================

from control_plane.stripe_catalog import (
    BUNDLE_INFO,
    BUNDLE_PRICING,
    TIER_INFO,
    get_price_id,
    get_price_cents,
    is_valid_bundle,
    is_valid_tier,
)
from control_plane.billing import WOPRBilling


class OnboardCheckoutRequest(BaseModel):
    bundle: str
    tier: str
    period: str  # 'monthly' or 'yearly'
    email: str
    name: str
    beacon_name: str
    region: str = "auto"
    additional_users: List[Dict[str, str]] = []


_billing_service = None


def get_billing():
    """Get or create the billing service."""
    global _billing_service
    if _billing_service is None and config.stripe.secret_key:
        _billing_service = WOPRBilling(
            stripe_secret_key=config.stripe.secret_key,
            stripe_webhook_secret=config.stripe.webhook_secret,
            success_url=f"https://orc.{config.wopr_domain}/onboard/success",
            cancel_url=f"https://orc.{config.wopr_domain}/onboard",
        )
    return _billing_service


@app.post("/api/v1/onboard/validate-beacon")
async def validate_beacon_name(request: Request):
    """Check if a beacon name is available."""
    data = await request.json()
    name = data.get("name", "").lower().strip()

    if not re.match(r'^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$', name):
        return {
            "available": False,
            "reason": "invalid_format",
            "message": "Name must be 3-32 characters, lowercase letters, numbers, and hyphens only",
        }

    reserved = [
        "www", "api", "admin", "mail", "smtp", "ftp", "ssh",
        "test", "demo", "staging", "dev", "prod", "app",
        "dashboard", "auth", "login", "signup", "register",
        "billing", "support", "help", "status", "docs",
        "orc", "install", "vault", "git", "mstdn", "social",
        "matrix", "forum", "shop", "drive", "joshua",
    ]
    if name in reserved:
        return {
            "available": False,
            "reason": "reserved",
            "message": "This name is reserved",
        }

    # Check database for existing beacons
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM beacons WHERE subdomain = $1", name
                )
                if existing > 0:
                    return {
                        "available": False,
                        "reason": "taken",
                        "message": "This name is already in use",
                    }
        except Exception:
            pass

    return {
        "available": True,
        "name": name,
        "domain": f"{name}.{config.wopr_domain}",
    }


@app.post("/api/v1/onboard/create-checkout")
async def create_onboard_checkout(request: OnboardCheckoutRequest):
    """Create a Stripe checkout session for new customer onboarding."""
    billing = get_billing()
    if not billing:
        raise HTTPException(status_code=500, detail="Billing not configured")

    if not is_valid_bundle(request.bundle):
        raise HTTPException(status_code=400, detail=f"Invalid bundle: {request.bundle}")
    if not is_valid_tier(request.tier):
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

    price_cents = get_price_cents(request.bundle, request.tier)
    if price_cents == 0:
        raise HTTPException(status_code=400, detail="Custom pricing required for this tier")

    price_id = get_price_id(request.bundle, request.tier, request.period)
    if not price_id:
        raise HTTPException(status_code=400, detail="Price not configured for this bundle/tier")

    # Map region to provider+datacenter
    region = request.region or "auto"
    region_to_datacenter = {
        "us-east": {"hetzner": "ash", "digitalocean": "nyc1", "linode": "us-east", "ovh": "US-EAST-VA-1", "upcloud": "us-chi1"},
        "eu-west": {"hetzner": "fsn1", "digitalocean": "fra1", "linode": "eu-west", "ovh": "GRA11", "upcloud": "de-fra1"},
    }
    if region == "auto":
        region = "us-east"

    # Auto-select provider via weighted round-robin
    orchestrator = get_orchestrator()
    provider_id = "hetzner"
    try:
        if orchestrator:
            provider_id = await orchestrator.select_provider(bundle=request.bundle)
    except Exception:
        pass

    datacenter_id = region_to_datacenter.get(region, {}).get(provider_id, "ash")

    session = billing.create_checkout_session(
        email=request.email,
        name=request.name,
        bundle=request.bundle,
        tier=request.tier,
        provider_id=provider_id,
        region=region,
        datacenter_id=datacenter_id,
        beacon_name=request.beacon_name,
        additional_users=request.additional_users,
    )

    return {
        "checkout_url": session["checkout_url"],
        "session_id": session["session_id"],
    }


@app.get("/api/v1/onboard/bundles")
async def get_onboard_bundles():
    """Get all available bundles for the onboarding wizard."""
    bundles = []
    for bundle_id, info in BUNDLE_INFO.items():
        pricing = BUNDLE_PRICING.get(bundle_id, {})
        bundles.append({
            "id": bundle_id,
            "name": info.get("name", bundle_id),
            "description": info.get("description", ""),
            "type": info.get("type", "unknown"),
            "pricing": {
                "t1": pricing.get("t1", 0),
                "t2": pricing.get("t2", 0),
                "t3": pricing.get("t3", 0),
            },
        })
    return {"bundles": bundles, "tiers": TIER_INFO}


@app.get("/api/v1/onboard/success")
async def handle_onboard_success(session_id: str):
    """Handle successful checkout redirect from Stripe."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status != "paid":
            raise HTTPException(status_code=400, detail="Payment not completed")

        metadata = session.metadata or {}
        bundle = metadata.get("wopr_bundle", metadata.get("bundle", "unknown"))
        tier = metadata.get("wopr_tier", metadata.get("tier", "t1"))
        beacon_name = metadata.get("wopr_beacon_name", metadata.get("beacon_name", ""))
        provider = metadata.get("wopr_provider", metadata.get("provider", "hetzner"))
        customer_name = metadata.get("wopr_customer_name", metadata.get("customer_name", ""))

        bundle_info = BUNDLE_INFO.get(bundle, {})
        tier_info = TIER_INFO.get(tier, {})

        amount_paid = session.amount_total / 100 if session.amount_total else 0
        currency = session.currency.upper() if session.currency else "USD"

        # Look up provisioning job from the webhook (it should already exist)
        # Try by subscription ID first (most reliable), then by email
        job_id = None
        subscription_id = session.subscription

        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    if subscription_id:
                        row = await conn.fetchrow(
                            "SELECT job_id FROM provisioning_jobs WHERE stripe_subscription_id = $1 ORDER BY created_at DESC LIMIT 1",
                            subscription_id,
                        )
                        if row:
                            job_id = str(row["job_id"])

                    if not job_id and session.customer_email:
                        row = await conn.fetchrow(
                            "SELECT job_id FROM provisioning_jobs WHERE customer_email = $1 ORDER BY created_at DESC LIMIT 1",
                            session.customer_email,
                        )
                        if row:
                            job_id = str(row["job_id"])
            except Exception:
                pass

        # Also check in-memory jobs (JSON fallback)
        if not job_id:
            orchestrator = get_orchestrator()
            for jid, job in orchestrator.jobs.items():
                if (subscription_id and job.stripe_subscription_id == subscription_id) or \
                   (session.customer_email and job.customer_email == session.customer_email):
                    job_id = jid
                    break

        return {
            "order": {
                "session_id": session_id,
                "bundle": bundle,
                "bundle_name": bundle_info.get("name", bundle),
                "tier": tier,
                "tier_name": tier_info.get("name", tier),
                "beacon_name": beacon_name,
                "email": session.customer_email,
                "name": customer_name,
                "amount": f"${amount_paid:.2f} {currency}",
            },
            "job_id": job_id,
            "setup_url": f"/setup/{job_id}" if job_id else None,
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
