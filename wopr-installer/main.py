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
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import stripe

# Import orchestrator components
from control_plane.orchestrator import WOPROrchestrator, ProvisioningState, ProvisioningJob
from control_plane.providers.registry import ProviderRegistry
from control_plane.bundles.stripe_checkout import StripeCheckout

# Configuration from environment
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
HETZNER_API_TOKEN = os.environ.get("HETZNER_API_TOKEN")
DIGITALOCEAN_API_TOKEN = os.environ.get("DIGITALOCEAN_API_TOKEN")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Initialize FastAPI
app = FastAPI(
    title="WOPR Orchestrator",
    description="Beacon provisioning and management API",
    version="1.0.0",
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wopr.systems", "https://orc.wopr.systems"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize providers
providers = {}

def init_providers():
    """Initialize VPS providers from environment"""
    global providers

    if HETZNER_API_TOKEN:
        try:
            from control_plane.providers.hetzner import HetznerProvider
            providers["hetzner"] = HetznerProvider(HETZNER_API_TOKEN)
            print("Hetzner provider initialized")
        except Exception as e:
            print(f"Failed to initialize Hetzner: {e}")

    if DIGITALOCEAN_API_TOKEN:
        try:
            from control_plane.providers.digitalocean import DigitalOceanProvider
            providers["digitalocean"] = DigitalOceanProvider(DIGITALOCEAN_API_TOKEN)
            print("DigitalOcean provider initialized")
        except Exception as e:
            print(f"Failed to initialize DigitalOcean: {e}")

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    init_providers()
    os.makedirs("/var/lib/wopr/jobs", exist_ok=True)

# Initialize orchestrator (lazy)
_orchestrator = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WOPROrchestrator(
            providers=providers,
            cloudflare_token=CLOUDFLARE_API_TOKEN,
            job_store_path="/var/lib/wopr/jobs",
        )
    return _orchestrator


class ProvisionRequest(BaseModel):
    bundle: str  # e.g., "sovereign-starter"
    tier: int
    email: str
    domain: Optional[str] = None
    username: str
    display_name: str
    provider: str = "hetzner"
    region: str = "ash"


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "providers": list(providers.keys()),
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "webhook_configured": bool(STRIPE_WEBHOOK_SECRET),
    }


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Stripe webhook events.

    This endpoint is PUBLIC but secured via Stripe signature verification.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})

        # Extract provisioning details from metadata
        bundle = metadata.get("bundle", "sovereign-starter")
        tier = int(metadata.get("tier", "1"))
        email = session.get("customer_email", "")
        domain = metadata.get("domain", "")
        username = metadata.get("username", "")
        display_name = metadata.get("display_name", "")
        provider = metadata.get("provider", "hetzner")
        region = metadata.get("region", "ash")

        orchestrator = get_orchestrator()

        # Create provisioning job
        job = orchestrator.create_job(
            customer_id=session.get("customer", ""),
            customer_email=email,
            bundle=bundle,
            provider_id=provider,
            region=region,
            datacenter_id=region,
            stripe_customer_id=session.get("customer"),
            stripe_subscription_id=session.get("subscription"),
        )

        # Run provisioning in background
        background_tasks.add_task(run_provisioning, job.job_id)

        return {"received": True, "job_id": job.job_id}

    return {"received": True}


async def run_provisioning(job_id: str):
    """Run the full provisioning workflow"""
    orchestrator = get_orchestrator()
    try:
        await orchestrator.run_provisioning(job_id)
    except Exception as e:
        print(f"Provisioning failed for {job_id}: {e}")


@app.post("/api/provision")
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
    )

    background_tasks.add_task(run_provisioning, job.job_id)

    return {"job_id": job.job_id, "status": "provisioning_started"}


@app.get("/api/provision/{job_id}/status")
async def get_provision_status(job_id: str):
    """Get current provisioning status"""
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
    """List available VPS providers"""
    return {
        "providers": [
            {"id": pid, "name": getattr(p, "PROVIDER_NAME", pid)}
            for pid, p in providers.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
