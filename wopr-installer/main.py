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
import json
import logging
import re
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
        logger.info(f"Subscription updated: {subscription.get('id')}")
        # TODO Phase 4: handle plan changes (upgrade/downgrade)

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
                import asyncio
                await asyncio.to_thread(
                    email_service.send_trial_reminder,
                    to_email=customer_email,
                    name=customer_email.split("@")[0].title(),
                    days_remaining=3,
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

    try:
        if failure_count == 1:
            await asyncio.to_thread(
                email_service.send_payment_failed,
                to_email=customer_email,
                name=name,
                severity="notice",
                days_until_suspension=7,
            )
            logger.info(f"Dunning email (1st failure) sent to {customer_email}")
        elif failure_count == 2:
            await asyncio.to_thread(
                email_service.send_payment_failed,
                to_email=customer_email,
                name=name,
                severity="warning",
                days_until_suspension=3,
            )
            logger.info(f"Dunning email (2nd failure) sent to {customer_email}")
        elif failure_count >= 3:
            await asyncio.to_thread(
                email_service.send_payment_failed,
                to_email=customer_email,
                name=name,
                severity="urgent",
                days_until_suspension=0,
            )
            logger.warning(f"Dunning email (3rd+ failure) sent to {customer_email} — suspension pending")

            # Suspend the beacon
            if db_pool:
                from control_plane.database import get_beacon_by_subscription, update_beacon_status
                beacon = await get_beacon_by_subscription(db_pool, subscription_id)
                if beacon:
                    await update_beacon_status(db_pool, beacon["id"], "suspended")
                    logger.warning(f"Beacon {beacon['id']} suspended due to payment failures")
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
            customer_email = beacon.get("owner_email", "")
            if customer_email:
                try:
                    await asyncio.to_thread(
                        email_service.send_subscription_cancelled,
                        to_email=customer_email,
                        name=customer_email.split("@")[0].title(),
                        beacon_name=beacon.get("subdomain", ""),
                    )
                except Exception as e:
                    logger.error(f"Failed to send cancellation email: {e}")

    except Exception as e:
        logger.error(f"Subscription cleanup failed for {subscription_id}: {e}")


async def run_provisioning(job_id: str):
    """Run the full provisioning workflow."""
    orchestrator = get_orchestrator()
    try:
        await orchestrator.run_provisioning(job_id)
    except Exception as e:
        logger.error(f"Provisioning failed for {job_id}: {e}", exc_info=True)


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
async def stream_provision_status(job_id: str):
    """
    SSE stream for real-time provisioning updates.

    Used by the setup progress page.
    """
    orchestrator = get_orchestrator()

    async def event_generator():
        last_state = None
        while True:
            job = orchestrator.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            current_state = job.state.value
            if current_state != last_state:
                yield f"data: {json.dumps(job.to_dict())}\n\n"
                last_state = current_state

            if job.state in [ProvisioningState.COMPLETED, ProvisioningState.FAILED]:
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


@app.get("/api/providers")
async def list_providers():
    """List available VPS providers."""
    return {
        "providers": [
            {"id": pid, "name": getattr(p, "PROVIDER_NAME", pid)}
            for pid, p in providers.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
