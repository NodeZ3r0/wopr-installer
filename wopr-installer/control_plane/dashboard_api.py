"""
WOPR Dashboard API
==================

REST API for the WOPR user dashboard.

This powers the web UI where users can:
- View their installed modules
- Start free trials
- Upgrade bundles
- Manage their instance

FastAPI-based API that integrates:
- Module registry
- Trial management
- Stripe billing
- Authentik authentication

Updated: January 2026
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .modules.registry import ModuleRegistry, BUNDLES, MODULES
from .modules.trials import TrialManager, TRIAL_OFFERINGS, TrialStatus
from .billing import WOPRBilling, PRICING_PLANS, SubscriptionTier
from .stripe_catalog import (
    BUNDLE_PRICING,
    BUNDLE_INFO,
    TIER_INFO,
    get_price_id,
    get_price_cents,
    is_valid_bundle,
    is_valid_tier,
)
from .authentik_integration import (
    AuthentikClient,
    user_can_access_feature,
    BUNDLE_GROUPS,
)
from .models.themes import (
    ThemeConfig,
    ThemeUpdateRequest,
    AppThemeUpdateRequest,
    ThemeConfigResponse,
    ThemePresetResponse,
    ThemeCSSResponse,
    THEME_PRESETS,
    NATIVE_THEMED_APPS,
    DEFAULT_PRESET,
    get_all_presets,
    validate_preset,
    is_native_app,
)


# ============================================
# PYDANTIC MODELS
# ============================================

if FASTAPI_AVAILABLE:
    class ModuleResponse(BaseModel):
        id: str
        name: str
        description: str
        category: str
        installed: bool
        status: str  # installed, available, trial, trial_expired
        url: Optional[str] = None
        trial_days_remaining: Optional[int] = None
        addon_price: Optional[float] = None

    class BundleResponse(BaseModel):
        id: str
        name: str
        description: str
        price_monthly: float
        modules: List[str]
        trial_modules: List[str]
        is_current: bool

    class TrialStartRequest(BaseModel):
        trial_id: str

    class TrialResponse(BaseModel):
        success: bool
        trial_id: str
        expires_at: str
        days_remaining: int
        modules: List[str]
        message: str

    class UpgradeRequest(BaseModel):
        new_bundle: str

    class OnboardCheckoutRequest(BaseModel):
        bundle: str
        tier: str
        period: str  # 'monthly' or 'yearly'
        email: str
        name: str
        beacon_name: str
        region: str = "auto"  # 'auto', 'us-east', 'eu-west'
        additional_users: List[Dict[str, str]] = []

    class OnboardCheckoutResponse(BaseModel):
        checkout_url: str
        session_id: str

    class OnboardSuccessResponse(BaseModel):
        order: Dict[str, Any]
        job_id: str

    class InstanceStatus(BaseModel):
        instance_id: str
        domain: str
        bundle: str
        provider: str
        region: str
        created_at: str
        modules_installed: List[str]
        modules_available: List[str]
        active_trials: List[Dict[str, Any]]


# ============================================
# DASHBOARD SERVICE
# ============================================

class DashboardService:
    """
    Core service for dashboard functionality.

    Coordinates between modules, trials, billing, and auth.
    """

    def __init__(
        self,
        billing: WOPRBilling,
        trial_manager: TrialManager,
        authentik: AuthentikClient,
    ):
        self.billing = billing
        self.trials = trial_manager
        self.authentik = authentik

    def get_instance_status(
        self,
        customer_id: str,
        instance_id: str,
    ) -> Dict[str, Any]:
        """Get full status of a WOPR instance."""
        # TODO: Fetch from database
        # This is a placeholder structure
        return {
            "instance_id": instance_id,
            "customer_id": customer_id,
            "domain": f"{instance_id}.wopr.systems",
            "bundle": "personal",
            "provider": "hetzner",
            "region": "us-east",
            "datacenter": "ash",
            "created_at": datetime.now().isoformat(),
            "status": "running",
        }

    def get_modules_for_user(
        self,
        customer_id: str,
        instance_id: str,
        user_groups: List[str],
        current_bundle: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all modules with their status for a user.

        Considers:
        - Bundle inclusion
        - Authentik group access
        - Active trials
        - Installed status
        """
        modules = []
        bundle_def = BUNDLES.get(current_bundle)

        for module_id, module in MODULES.items():
            # Check access
            access = user_can_access_feature(user_groups, module_id)

            # Determine status
            if module_id in (bundle_def.base_modules if bundle_def else []):
                status = "included"
            elif access["has_access"]:
                if access["access_type"] == "trial":
                    status = "trial"
                else:
                    status = "installed"
            elif module.trial_eligible:
                status = "trial_available"
            elif module.monthly_addon_price > 0:
                status = "addon_available"
            else:
                status = "unavailable"

            # Get trial info if applicable
            trial_days = None
            if status == "trial":
                trial_status = self.trials.check_trial_status(
                    customer_id,
                    f"{module_id}_trial"
                )
                trial_days = trial_status.get("days_remaining")

            modules.append({
                "id": module_id,
                "name": module.name,
                "description": module.description,
                "category": module.category.value,
                "tier": module.tier.value,
                "status": status,
                "subdomain": module.subdomain,
                "url": f"https://{module.subdomain}.placeholder.wopr.systems" if module.subdomain else None,
                "trial_eligible": module.trial_eligible,
                "trial_days": module.trial_days if module.trial_eligible else None,
                "trial_days_remaining": trial_days,
                "addon_price": module.monthly_addon_price if module.monthly_addon_price > 0 else None,
            })

        return modules

    def get_available_trials(
        self,
        customer_id: str,
        current_bundle: str,
    ) -> List[Dict[str, Any]]:
        """Get trials available for the user's current bundle."""
        available = self.trials.get_available_trials(current_bundle)

        return [
            {
                "trial_id": t.trial_id,
                "name": t.name,
                "description": t.description,
                "modules": t.modules,
                "duration_days": t.duration_days,
                "upgrade_bundle": t.upgrade_bundle,
            }
            for t in available
        ]

    def start_trial(
        self,
        customer_id: str,
        instance_id: str,
        customer_email: str,
        trial_id: str,
    ) -> Dict[str, Any]:
        """Start a free trial."""
        return self.trials.start_trial(
            trial_id=trial_id,
            customer_id=customer_id,
            instance_id=instance_id,
            customer_email=customer_email,
        )

    def get_upgrade_options(
        self,
        current_bundle: str,
    ) -> List[Dict[str, Any]]:
        """Get bundles user can upgrade to."""
        bundle_order = ["personal", "creator", "developer", "professional"]
        current_index = bundle_order.index(current_bundle) if current_bundle in bundle_order else 0

        options = []
        for bundle_id in bundle_order[current_index + 1:]:
            bundle = BUNDLES.get(bundle_id)
            tier = SubscriptionTier(bundle_id)
            pricing = PRICING_PLANS.get(tier)

            if bundle and pricing:
                # Calculate new features
                current_modules = set(BUNDLES[current_bundle].base_modules) if current_bundle in BUNDLES else set()
                new_modules = set(bundle.base_modules) - current_modules

                options.append({
                    "bundle_id": bundle_id,
                    "name": bundle.name,
                    "description": bundle.description,
                    "price_monthly": pricing.price_monthly_usd,
                    "new_modules": list(new_modules),
                    "features": pricing.features,
                })

        return options


# ============================================
# FASTAPI APPLICATION
# ============================================

def create_dashboard_app(
    billing: WOPRBilling,
    trial_manager: TrialManager,
    authentik: AuthentikClient,
) -> "FastAPI":
    """Create the FastAPI dashboard application."""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="WOPR Dashboard API",
        description="API for managing your Sovereign Suite",
        version="1.6",
    )

    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://*.wopr.systems",
            "https://provision.wopr.systems",
            "https://orc.wopr.systems",
            "http://localhost:3000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    from pathlib import Path
    try:
        from fastapi.staticfiles import StaticFiles
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    except ImportError:
        pass  # StaticFiles not available

    service = DashboardService(billing, trial_manager, authentik)

    # ----------------------------------------
    # INTENT RESOLVER ROUTES
    # ----------------------------------------
    # Import and include the intent resolver router
    # These handle /go/* endpoints for intent-based navigation
    from .resolvers.api import router as resolver_router
    app.include_router(resolver_router, tags=["intents"])

    # ----------------------------------------
    # AUTH DEPENDENCY
    # ----------------------------------------

    async def get_current_user(request: Request) -> Dict[str, Any]:
        """Extract user identity from Authentik headers."""
        user_id = request.headers.get("X-Authentik-UID")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        return {
            "user_id": user_id,
            "username": request.headers.get("X-Authentik-Username", ""),
            "email": request.headers.get("X-Authentik-Email", ""),
            "groups": request.headers.get("X-Authentik-Groups", "").split(","),
        }

    # ----------------------------------------
    # ENDPOINTS
    # ----------------------------------------

    @app.get("/api/v1/instance")
    async def get_instance(
        user: Dict = Depends(get_current_user),
    ):
        """Get instance status and overview."""
        # TODO: Get actual instance from user's subscription
        instance_id = "demo-instance"
        customer_id = user["user_id"]

        status = service.get_instance_status(customer_id, instance_id)
        modules = service.get_modules_for_user(
            customer_id=customer_id,
            instance_id=instance_id,
            user_groups=user["groups"],
            current_bundle=status["bundle"],
        )

        return {
            "instance": status,
            "modules": modules,
        }

    @app.get("/api/v1/modules")
    async def list_modules(
        user: Dict = Depends(get_current_user),
    ):
        """List all modules and their status."""
        instance_id = "demo-instance"
        customer_id = user["user_id"]

        # Get current bundle from subscription
        status = service.get_instance_status(customer_id, instance_id)

        modules = service.get_modules_for_user(
            customer_id=customer_id,
            instance_id=instance_id,
            user_groups=user["groups"],
            current_bundle=status["bundle"],
        )

        return {"modules": modules}

    @app.get("/api/v1/trials")
    async def list_available_trials(
        user: Dict = Depends(get_current_user),
    ):
        """List available trial offerings."""
        instance_id = "demo-instance"
        customer_id = user["user_id"]

        status = service.get_instance_status(customer_id, instance_id)
        available = service.get_available_trials(customer_id, status["bundle"])

        # Also get active trials
        active = billing.get_customer_trials(customer_id)

        return {
            "available": available,
            "active": active,
        }

    @app.post("/api/v1/trials/start")
    async def start_trial(
        request: TrialStartRequest,
        user: Dict = Depends(get_current_user),
    ):
        """Start a free trial."""
        instance_id = "demo-instance"
        customer_id = user["user_id"]

        result = service.start_trial(
            customer_id=customer_id,
            instance_id=instance_id,
            customer_email=user["email"],
            trial_id=request.trial_id,
        )

        return result

    @app.get("/api/v1/bundles")
    async def list_bundles(
        user: Dict = Depends(get_current_user),
    ):
        """List all bundles and upgrade options."""
        instance_id = "demo-instance"
        customer_id = user["user_id"]

        status = service.get_instance_status(customer_id, instance_id)
        current_bundle = status["bundle"]

        bundles = []
        for bundle_id, bundle in BUNDLES.items():
            tier = SubscriptionTier(bundle_id)
            pricing = PRICING_PLANS.get(tier)

            bundles.append({
                "id": bundle_id,
                "name": bundle.name,
                "description": bundle.description,
                "price_monthly": pricing.price_monthly_usd if pricing else 0,
                "modules": bundle.base_modules,
                "trial_modules": bundle.trial_modules,
                "is_current": bundle_id == current_bundle,
            })

        upgrade_options = service.get_upgrade_options(current_bundle)

        return {
            "bundles": bundles,
            "current_bundle": current_bundle,
            "upgrade_options": upgrade_options,
        }

    @app.post("/api/v1/upgrade")
    async def upgrade_bundle(
        request: UpgradeRequest,
        user: Dict = Depends(get_current_user),
    ):
        """Upgrade to a new bundle."""
        customer_id = user["user_id"]

        # Create Stripe checkout for upgrade
        # This would redirect user to Stripe payment
        session = billing.create_checkout_session(
            email=user["email"],
            bundle=request.new_bundle,
            provider_id="existing",  # Keep same provider
            region="existing",
            datacenter_id="existing",
        )

        return {
            "checkout_url": session["checkout_url"],
            "new_bundle": request.new_bundle,
        }

    @app.get("/api/v1/billing")
    async def get_billing_info(
        user: Dict = Depends(get_current_user),
    ):
        """Get billing information and invoices."""
        customer_id = user["user_id"]

        # Get Stripe customer info
        trials = billing.get_customer_trials(customer_id)

        return {
            "customer_id": customer_id,
            "active_trials": trials,
            # TODO: Add subscription details, invoices, etc.
        }

    # ----------------------------------------
    # ONBOARDING ENDPOINTS (PUBLIC)
    # ----------------------------------------

    @app.post("/api/v1/onboard/validate-beacon")
    async def validate_beacon_name(request: Request):
        """
        Check if a beacon name is available.
        Public endpoint - no auth required.
        """
        data = await request.json()
        name = data.get("name", "").lower().strip()

        # Validate format
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$', name):
            return {
                "available": False,
                "reason": "invalid_format",
                "message": "Name must be 3-32 characters, lowercase letters, numbers, and hyphens only",
            }

        # Reserved names
        reserved = [
            "www", "api", "admin", "mail", "smtp", "ftp", "ssh",
            "test", "demo", "staging", "dev", "prod", "app",
            "dashboard", "auth", "login", "signup", "register",
            "billing", "support", "help", "status", "docs",
        ]
        if name in reserved:
            return {
                "available": False,
                "reason": "reserved",
                "message": "This name is reserved",
            }

        # TODO: Check database for existing beacons
        # For now, assume available
        return {
            "available": True,
            "name": name,
            "domain": f"{name}.wopr.systems",
        }

    @app.post("/api/v1/onboard/create-checkout")
    async def create_onboard_checkout(request: OnboardCheckoutRequest):
        """
        Create a Stripe checkout session for new customer onboarding.
        Public endpoint - no auth required.
        """
        import json

        # Validate bundle and tier
        if not is_valid_bundle(request.bundle):
            raise HTTPException(status_code=400, detail=f"Invalid bundle: {request.bundle}")
        if not is_valid_tier(request.tier):
            raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

        # Get price
        price_cents = get_price_cents(request.bundle, request.tier)
        if price_cents == 0:
            raise HTTPException(status_code=400, detail="Custom pricing required for this tier")

        # Get Stripe price ID
        price_id = get_price_id(request.bundle, request.tier, request.period)
        if not price_id:
            # If products haven't been created in Stripe yet, we can still proceed
            # by creating a price on the fly or using a placeholder
            raise HTTPException(
                status_code=400,
                detail="Products not yet configured. Please run stripe-setup.ps1 first."
            )

        # Map region to provider+datacenter via backend round-robin
        # Customer never sees provider name — we choose it automatically
        region = request.region or "auto"
        region_to_datacenter = {
            "us-east": {"hetzner": "ash", "digitalocean": "nyc1", "linode": "us-east", "ovh": "US-EAST-VA-1", "upcloud": "us-chi1"},
            "eu-west": {"hetzner": "fsn1", "digitalocean": "fra1", "linode": "eu-west", "ovh": "GRA11", "upcloud": "de-fra1"},
        }
        if region == "auto":
            region = "us-east"  # Default; future: use X-Forwarded-For geolocation

        # Auto-select provider via weighted round-robin
        provider_id = "hetzner"  # Fallback
        try:
            from control_plane.orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if orchestrator:
                provider_id = await orchestrator.select_provider(bundle=request.bundle)
        except Exception:
            pass

        datacenter_id = region_to_datacenter.get(region, {}).get(provider_id, "ash")

        # Prepare metadata for webhook
        metadata = {
            "bundle": request.bundle,
            "tier": request.tier,
            "beacon_name": request.beacon_name,
            "provider": provider_id,
            "region": region,
            "customer_name": request.name,
            "additional_users": json.dumps(request.additional_users) if request.additional_users else "",
        }

        # Create Stripe checkout session
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

    @app.get("/api/v1/onboard/success")
    async def handle_onboard_success(session_id: str):
        """
        Handle successful checkout redirect from Stripe.
        Verifies the session and initiates provisioning.
        """
        import json

        try:
            # Verify the checkout session with Stripe
            import stripe
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status != "paid":
                raise HTTPException(status_code=400, detail="Payment not completed")

            # Extract metadata
            metadata = session.metadata or {}
            bundle = metadata.get("bundle", "unknown")
            tier = metadata.get("tier", "t1")
            beacon_name = metadata.get("beacon_name", "")
            provider = metadata.get("provider", "hetzner")
            customer_name = metadata.get("customer_name", "")
            additional_users_json = metadata.get("additional_users", "")

            additional_users = []
            if additional_users_json:
                try:
                    additional_users = json.loads(additional_users_json)
                except:
                    pass

            # Get bundle info for display
            bundle_info = BUNDLE_INFO.get(bundle, {})
            tier_info = TIER_INFO.get(tier, {})

            # Calculate amount paid
            amount_paid = session.amount_total / 100 if session.amount_total else 0
            currency = session.currency.upper() if session.currency else "USD"

            # TODO: Create provisioning job
            # For now, generate a placeholder job ID
            import uuid
            job_id = str(uuid.uuid4())

            # TODO: Store order in database
            # TODO: Queue provisioning task

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
                    "provider": provider,
                    "additional_users": additional_users,
                },
                "job_id": job_id,
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/v1/onboard/bundles")
    async def get_onboard_bundles():
        """
        Get all available bundles for the onboarding wizard.
        Public endpoint - no auth required.
        """
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

        return {
            "bundles": bundles,
            "tiers": TIER_INFO,
        }

    # ----------------------------------------
    # PROVISIONING ENDPOINTS
    # ----------------------------------------

    # Use shared job store for cross-module access
    from .job_store import get_job_store
    job_store = get_job_store()

    # Legacy alias for backwards compatibility with SSE endpoint
    _provisioning_jobs = job_store._jobs

    # Serve the provisioning watch page
    @app.get("/provision/{job_id}")
    @app.get("/setup/{job_id}")
    async def serve_provision_page(job_id: str):
        """Serve the provisioning watch page for a given job."""
        from fastapi.responses import HTMLResponse
        from pathlib import Path

        # Load the provision.html template
        static_dir = Path(__file__).parent / "static"
        html_path = static_dir / "provision.html"

        if html_path.exists():
            html_content = html_path.read_text(encoding="utf-8")
        else:
            # Fallback minimal page if template not found
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>WOPR Provisioning</title></head>
            <body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:40px;text-align:center;">
                <h1>WOPR</h1>
                <p>Provisioning Job: {job_id}</p>
                <p>Status page template not found. API endpoints available at:</p>
                <p>/api/v1/provisioning/{job_id}</p>
                <p>/api/v1/provisioning/{job_id}/stream</p>
            </body>
            </html>
            """

        return HTMLResponse(content=html_content)

    @app.get("/api/v1/provisioning/{job_id}")
    async def get_provisioning_status(job_id: str):
        """Get current status of a provisioning job."""
        job = _provisioning_jobs.get(job_id)

        if not job:
            # Return not_found status - UI will show "waiting for provisioning"
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "Job not found or not yet started",
            }

        return job

    @app.get("/api/v1/provisioning/{job_id}/stream")
    async def stream_provisioning_status(job_id: str):
        """
        Server-Sent Events endpoint for real-time provisioning updates.
        Streams progress updates as the beacon is being set up.

        Polls actual provisioning job status and maps to UI steps:
        - Step 0: Payment received
        - Step 1: Creating server (VPS provisioning)
        - Step 2: Configuring DNS
        - Step 3: Installing WOPR (modules)
        - Step 4: Final configuration (SSO, mesh)
        - Step 5: Complete
        """
        from fastapi.responses import StreamingResponse
        import asyncio
        import json

        # Map provisioning states to UI steps
        STATE_TO_STEP = {
            "pending": 0,
            "payment_received": 0,
            "provisioning_vps": 1,
            "waiting_for_vps": 1,
            "configuring_dns": 2,
            "deploying_wopr": 3,
            "generating_docs": 4,
            "sending_welcome": 4,
            "completed": 5,
            "failed": -1,
        }

        async def event_generator():
            """Generate SSE events by polling actual job status."""
            max_polls = 300  # 5 minutes max (at 1 second intervals)
            poll_count = 0
            last_progress = -1

            while poll_count < max_polls:
                poll_count += 1

                # Get job from our store
                job = _provisioning_jobs.get(job_id)

                if not job:
                    # Job not found - might still be initializing
                    yield f"data: {json.dumps({'step': 0, 'progress': 0, 'status': 'initializing', 'message': 'Waiting for job to start...'})}\n\n"
                    await asyncio.sleep(2)
                    continue

                # Extract current state
                state = job.get("state", job.get("status", "pending"))
                step = STATE_TO_STEP.get(state, 0)
                beacon_name = job.get("beacon_name", "beacon")

                # Calculate progress based on state and any progress info
                if state == "completed":
                    progress = 100
                elif state == "failed":
                    progress = job.get("progress", 0)
                else:
                    # Use module progress if available, otherwise estimate from step
                    modules_completed = job.get("modules_completed", 0)
                    modules_total = job.get("modules_total", 20)
                    if modules_total > 0 and step == 3:
                        # During module installation, use actual module progress
                        base_progress = 40  # Steps 0-2 take ~40%
                        module_progress = (modules_completed / modules_total) * 40
                        progress = int(base_progress + module_progress)
                    else:
                        # Estimate based on step
                        step_progress = {0: 5, 1: 20, 2: 40, 3: 60, 4: 90}
                        progress = step_progress.get(step, 0)

                # Build update payload
                update = {
                    "step": step,
                    "progress": progress,
                    "status": "complete" if state == "completed" else ("failed" if state == "failed" else "in_progress"),
                    "state": state,
                    "message": job.get("message", ""),
                    "current_module": job.get("current_module", ""),
                    "modules_completed": job.get("modules_completed", 0),
                    "modules_total": job.get("modules_total", 0),
                }

                # Add final URLs if complete
                if state == "completed":
                    update["beacon_url"] = f"https://{beacon_name}.wopr.systems"
                    update["dashboard_url"] = f"https://{beacon_name}.wopr.systems/dashboard"
                    update["auth_url"] = f"https://auth.{beacon_name}.wopr.systems"

                # Add error info if failed
                if state == "failed":
                    update["error"] = job.get("error_message", "Provisioning failed")

                # Only send if progress changed (reduce spam)
                if progress != last_progress or state in ("completed", "failed"):
                    yield f"data: {json.dumps(update)}\n\n"
                    last_progress = progress

                # Stop if terminal state
                if state in ("completed", "failed"):
                    break

                # Poll interval
                await asyncio.sleep(1)

            # Timeout - send final status
            if poll_count >= max_polls:
                yield f"data: {json.dumps({'step': -1, 'progress': 0, 'status': 'timeout', 'error': 'Provisioning status check timed out'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    @app.post("/api/v1/provisioning/{job_id}/start")
    async def start_provisioning(job_id: str, request: Request):
        """
        Start provisioning a new beacon.
        Called internally after successful payment or by webhook handler.
        """
        from fastapi import BackgroundTasks
        data = await request.json()

        beacon_name = data.get("beacon_name", "")
        customer_email = data.get("email", "")
        customer_name = data.get("name", "")
        bundle = data.get("bundle", "")

        # Create job record
        job = {
            "job_id": job_id,
            "state": "payment_received",
            "status": "in_progress",
            "step": 0,
            "progress": 5,
            "beacon_name": beacon_name,
            "bundle": bundle,
            "tier": data.get("tier", "t1"),
            "provider": data.get("provider", "hetzner"),
            "customer_email": customer_email,
            "customer_name": customer_name,
            "created_at": datetime.now().isoformat(),
            "message": "Payment received, starting provisioning...",
            "modules_completed": 0,
            "modules_total": 0,
        }

        _provisioning_jobs[job_id] = job

        # Send provisioning started email immediately
        try:
            from .email_service import EmailService
            email_svc = EmailService()
            provisioning_url = f"https://provision.wopr.systems/{job_id}"
            bundle_name = BUNDLE_INFO.get(bundle, {}).get("name", bundle)

            email_svc.send_provisioning_started(
                to_email=customer_email,
                name=customer_name or customer_email.split("@")[0],
                beacon_name=beacon_name,
                bundle_name=bundle_name,
                job_id=job_id,
                provisioning_url=provisioning_url,
            )
        except Exception as e:
            # Log but don't fail provisioning if email fails
            logger.warning(f"Failed to send provisioning email: {e}")

        return {
            "job_id": job_id,
            "status": "started",
            "provisioning_url": f"https://provision.wopr.systems/{job_id}",
        }

    # ----------------------------------------
    # THEME ENDPOINTS
    # ----------------------------------------

    # In-memory theme storage (TODO: Replace with PostgreSQL)
    _user_themes: Dict[str, Dict] = {}

    def _get_user_theme(user_id: str) -> Dict:
        """Get user's theme config or create default."""
        if user_id not in _user_themes:
            _user_themes[user_id] = {
                "preset": DEFAULT_PRESET,
                "custom_colors": {},
                "app_overrides": {},
                "themed_apps": NATIVE_THEMED_APPS.copy(),
            }
        return _user_themes[user_id]

    @app.get("/api/v1/themes", response_model=ThemeConfigResponse)
    async def get_theme_config(
        user: Dict = Depends(get_current_user),
    ):
        """Get user's theme configuration."""
        theme = _get_user_theme(user["user_id"])
        preset_info = THEME_PRESETS.get(theme["preset"], THEME_PRESETS[DEFAULT_PRESET])

        return {
            "preset": theme["preset"],
            "preset_name": preset_info["name"],
            "custom_colors": theme["custom_colors"],
            "app_overrides": theme["app_overrides"],
            "themed_apps": theme["themed_apps"],
            "available_presets": get_all_presets(),
        }

    @app.patch("/api/v1/themes")
    async def update_theme_config(
        request: ThemeUpdateRequest,
        user: Dict = Depends(get_current_user),
    ):
        """Update user's global theme settings."""
        theme = _get_user_theme(user["user_id"])

        # Validate and update preset
        if request.preset is not None:
            if not validate_preset(request.preset):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid preset: {request.preset}. Valid presets: {list(THEME_PRESETS.keys())}",
                )
            theme["preset"] = request.preset

        # Update custom colors
        if request.custom_colors is not None:
            theme["custom_colors"] = request.custom_colors

        # Update themed apps (ensure native apps are always included)
        if request.themed_apps is not None:
            themed = set(request.themed_apps)
            themed.update(NATIVE_THEMED_APPS)  # Always include native apps
            theme["themed_apps"] = list(themed)

        return {
            "success": True,
            "preset": theme["preset"],
            "custom_colors": theme["custom_colors"],
            "themed_apps": theme["themed_apps"],
        }

    @app.get("/api/v1/themes/presets")
    async def list_theme_presets():
        """List all available theme presets."""
        return {
            "presets": get_all_presets(),
            "default": DEFAULT_PRESET,
        }

    @app.patch("/api/v1/themes/apps/{app_id}")
    async def update_app_theme(
        app_id: str,
        request: AppThemeUpdateRequest,
        user: Dict = Depends(get_current_user),
    ):
        """Set theme override for a specific app."""
        theme = _get_user_theme(user["user_id"])

        # Validate preset if provided
        if request.preset is not None and request.preset != "inherit":
            if not validate_preset(request.preset):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid preset: {request.preset}",
                )

        # Update or remove app override
        if request.preset == "inherit" or (request.preset is None and request.custom_colors is None):
            # Remove override - app inherits global theme
            theme["app_overrides"].pop(app_id, None)
        else:
            # Set override
            theme["app_overrides"][app_id] = {
                "preset": request.preset,
                "custom_colors": request.custom_colors or {},
            }

        # Update themed_apps list if enabled flag provided
        if request.enabled is not None:
            themed = set(theme["themed_apps"])
            if request.enabled:
                themed.add(app_id)
            elif not is_native_app(app_id):
                themed.discard(app_id)
            theme["themed_apps"] = list(themed)

        return {
            "success": True,
            "app_id": app_id,
            "override": theme["app_overrides"].get(app_id),
            "themed": app_id in theme["themed_apps"],
        }

    @app.delete("/api/v1/themes/apps/{app_id}")
    async def remove_app_theme_override(
        app_id: str,
        user: Dict = Depends(get_current_user),
    ):
        """Remove theme override for an app (inherit global theme)."""
        theme = _get_user_theme(user["user_id"])

        # Remove override
        removed = theme["app_overrides"].pop(app_id, None)

        return {
            "success": True,
            "app_id": app_id,
            "removed": removed is not None,
        }

    @app.get("/api/v1/themes/css", response_model=ThemeCSSResponse)
    async def get_theme_css(
        user: Dict = Depends(get_current_user),
    ):
        """Get theme as raw CSS for injection into apps."""
        theme = _get_user_theme(user["user_id"])
        preset = THEME_PRESETS.get(theme["preset"], THEME_PRESETS[DEFAULT_PRESET])

        # Build CSS from preset colors
        css_vars = []
        preview = preset.get("preview", {})

        # Map preview colors to CSS variables
        css_vars.append(f"--theme-primary: {preview.get('primary', '#00d4aa')};")
        css_vars.append(f"--theme-accent: {preview.get('accent', '#ff9b3f')};")
        css_vars.append(f"--theme-bg: {preview.get('bg', '#0a0a0a')};")

        # Add custom color overrides
        for var, value in theme["custom_colors"].items():
            css_vars.append(f"{var}: {value};")

        css = f":root {{\n  {chr(10).join('  ' + v for v in css_vars)}\n}}"

        return {
            "css": css,
            "preset": theme["preset"],
            "custom_colors": theme["custom_colors"],
        }

    @app.get("/api/v1/themes/json")
    async def get_theme_json(
        user: Dict = Depends(get_current_user),
    ):
        """Get theme as JSON for programmatic use."""
        theme = _get_user_theme(user["user_id"])
        preset = THEME_PRESETS.get(theme["preset"], THEME_PRESETS[DEFAULT_PRESET])

        return {
            "preset": theme["preset"],
            "preview": preset.get("preview", {}),
            "custom_colors": theme["custom_colors"],
        }

    @app.get("/api/v1/themes/apps/{app_id}/css")
    async def get_app_theme_css(
        app_id: str,
        user: Dict = Depends(get_current_user),
    ):
        """
        Get complete CSS for theming a specific app.

        Returns:
        - Base theme CSS variables
        - App-specific override CSS (if available)

        This endpoint is called by the theme-loader.js injected into apps.
        """
        from pathlib import Path

        theme = _get_user_theme(user["user_id"])

        # Check if app has theming enabled
        if app_id not in theme["themed_apps"]:
            return {"css": "", "themed": False, "reason": "App theming disabled"}

        # Get the theme preset (use app override if exists, else global)
        app_override = theme["app_overrides"].get(app_id, {})
        preset_id = app_override.get("preset") or theme["preset"]
        preset = THEME_PRESETS.get(preset_id, THEME_PRESETS[DEFAULT_PRESET])

        # Build base CSS variables
        css_parts = []
        preview = preset.get("preview", {})

        base_vars = f""":root {{
  --theme-primary: {preview.get('primary', '#00d4aa')};
  --theme-primary-hover: {preview.get('primary_hover', '#00f0c0')};
  --theme-primary-subtle: {preview.get('primary', '#00d4aa')}20;
  --theme-accent: {preview.get('accent', '#ff9b3f')};
  --theme-accent-hover: {preview.get('accent_hover', '#ffb366')};
  --theme-bg: {preview.get('bg', '#0a0a0a')};
  --theme-surface: {preview.get('surface', '#1a1a1a')};
  --theme-surface-hover: {preview.get('surface_hover', '#252525')};
  --theme-elevated: {preview.get('elevated', '#2a2a2a')};
  --theme-border: {preview.get('border', '#333333')};
  --theme-border-subtle: {preview.get('border_subtle', '#2a2a2a')};
  --theme-text: {preview.get('text', '#e0e0e0')};
  --theme-text-muted: {preview.get('text_muted', '#888888')};
  --theme-text-on-primary: {preview.get('text_on_primary', '#000000')};
  --theme-success: #22c55e;
  --theme-success-subtle: #22c55e20;
  --theme-warning: #f59e0b;
  --theme-warning-subtle: #f59e0b20;
  --theme-error: #ef4444;
  --theme-error-subtle: #ef444420;
  --theme-info: #3b82f6;
  --theme-info-subtle: #3b82f620;
}}"""
        css_parts.append(base_vars)

        # Apply custom color overrides
        custom_colors = {**theme["custom_colors"], **app_override.get("custom_colors", {})}
        if custom_colors:
            custom_css = ":root {\n"
            for var, value in custom_colors.items():
                custom_css += f"  {var}: {value};\n"
            custom_css += "}"
            css_parts.append(custom_css)

        # Load app-specific override CSS if available
        # CSS files are stored in dashboard/src/lib/themes/apps/
        app_css_map = {
            # Personal bundle
            "nextcloud": "nextcloud.css",
            "vaultwarden": "vaultwarden.css",
            "freshrss": "freshrss.css",
            "authentik": "authentik.css",
            # Creator bundle
            "ghost": "ghost.css",
            "saleor": "saleor.css",
            # Developer bundle
            "forgejo": "forgejo.css",
            "uptime_kuma": "uptime-kuma.css",
            "woodpecker": "woodpecker.css",
            "code_server": "code-server.css",
            # Professional bundle
            "element": "element.css",
            # Media apps
            "immich": "immich.css",
            "jellyfin": "jellyfin.css",
        }

        if app_id in app_css_map:
            css_file = app_css_map[app_id]
            # In production, these would be served from a configured path
            # For now, we'll indicate the file that should be loaded
            css_parts.append(f"/* App override: {css_file} */")

        return {
            "css": "\n\n".join(css_parts),
            "themed": True,
            "app_id": app_id,
            "preset": preset_id,
            "override_file": app_css_map.get(app_id),
        }

    # ============================================
    # SUBSCRIPTION MANAGEMENT (CUSTOMER PORTAL)
    # ============================================

    @app.get("/api/v1/subscription")
    async def get_subscription(user: dict = Depends(get_current_user)):
        """
        Get current subscription details for the user.

        Returns subscription status, current plan, billing info, and usage.
        """
        customer_id = user.get("customer_id") or user["user_id"]

        # TODO: Fetch from database
        # For now, return mock data structure
        subscription = {
            "status": "active",  # active, trial, past_due, cancelled, pending
            "bundle": "starter",
            "bundle_name": "Starter Suite",
            "tier": "t1",
            "tier_name": "Tier 1 (50GB)",
            "billing_cycle": "monthly",
            "current_period_start": "2026-01-01T00:00:00Z",
            "current_period_end": "2026-02-01T00:00:00Z",
            "cancel_at_period_end": False,
            "trial_end": None,
            "amount": 1599,  # cents
            "currency": "usd",
            "payment_method": {
                "type": "card",
                "brand": "visa",
                "last4": "4242",
                "exp_month": 12,
                "exp_year": 2028,
            },
            "usage": {
                "storage_used_gb": 12.5,
                "storage_limit_gb": 50,
                "storage_percent": 25,
                "users_count": 1,
                "users_limit": 1,
            },
            "features": {
                "can_upgrade": True,
                "can_downgrade": True,
                "can_cancel": True,
                "can_add_users": False,
            },
        }

        return subscription

    @app.get("/api/v1/subscription/plans")
    async def get_available_plans(user: dict = Depends(get_current_user)):
        """
        Get all available plans for upgrade/downgrade.

        Returns plans with pricing, features comparison.
        """
        current_bundle = user.get("bundle", "starter")
        current_tier = user.get("tier", "t1")

        plans = []

        # Add all bundles with their tiers
        for bundle_id, bundle_info in BUNDLE_INFO.items():
            for tier_id, tier_info in TIER_INFO.items():
                price_cents = get_price_cents(bundle_id, tier_id, "monthly")
                yearly_cents = get_price_cents(bundle_id, tier_id, "yearly")

                is_current = (bundle_id == current_bundle and tier_id == current_tier)

                # Determine if this is an upgrade or downgrade
                current_price = get_price_cents(current_bundle, current_tier, "monthly")
                change_type = "current" if is_current else (
                    "upgrade" if price_cents > current_price else "downgrade"
                )

                plans.append({
                    "bundle": bundle_id,
                    "bundle_name": bundle_info.get("name", bundle_id.title()),
                    "tier": tier_id,
                    "tier_name": tier_info.get("name", tier_id.upper()),
                    "storage_gb": tier_info.get("storage_gb", 50),
                    "monthly_price": price_cents,
                    "yearly_price": yearly_cents,
                    "yearly_savings": (price_cents * 12) - yearly_cents,
                    "is_current": is_current,
                    "change_type": change_type,
                    "features": bundle_info.get("features", []),
                    "apps": bundle_info.get("apps", []),
                })

        return {"plans": plans, "current_bundle": current_bundle, "current_tier": current_tier}

    @app.post("/api/v1/subscription/upgrade")
    async def upgrade_subscription(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        """
        Upgrade or change subscription plan.

        Creates a Stripe checkout session for plan change.
        """
        data = await request.json()
        new_bundle = data.get("bundle")
        new_tier = data.get("tier")
        billing_cycle = data.get("billing_cycle", "monthly")

        if not new_bundle or not new_tier:
            raise HTTPException(status_code=400, detail="Bundle and tier required")

        if not is_valid_bundle(new_bundle) or not is_valid_tier(new_tier):
            raise HTTPException(status_code=400, detail="Invalid bundle or tier")

        customer_id = user.get("customer_id") or user["user_id"]
        email = user.get("email", "")
        beacon_name = user.get("beacon_name", "beacon")

        # Get price ID for new plan
        price_id = get_price_id(new_bundle, new_tier, billing_cycle)
        if not price_id:
            raise HTTPException(status_code=400, detail="Price not found for selected plan")

        try:
            import stripe

            # Create checkout session for subscription update
            checkout_session = stripe.checkout.Session.create(
                customer_email=email,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=f"https://{beacon_name}.wopr.systems/billing?upgrade=success",
                cancel_url=f"https://{beacon_name}.wopr.systems/billing?upgrade=cancelled",
                metadata={
                    "customer_id": customer_id,
                    "beacon_name": beacon_name,
                    "bundle": new_bundle,
                    "tier": new_tier,
                    "action": "upgrade",
                },
                subscription_data={
                    "metadata": {
                        "bundle": new_bundle,
                        "tier": new_tier,
                        "beacon_name": beacon_name,
                    }
                },
            )

            return {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create checkout: {str(e)}")

    @app.post("/api/v1/subscription/cancel")
    async def cancel_subscription(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        """
        Cancel subscription at end of current period.

        Does not immediately cancel - subscription remains active until period end.
        """
        data = await request.json()
        reason = data.get("reason", "")
        feedback = data.get("feedback", "")

        customer_id = user.get("customer_id") or user["user_id"]

        try:
            import stripe

            # TODO: Get Stripe subscription ID from database
            subscription_id = user.get("stripe_subscription_id")

            if subscription_id:
                # Cancel at period end (not immediate)
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                    metadata={
                        "cancel_reason": reason,
                        "cancel_feedback": feedback,
                    }
                )

            # TODO: Store cancellation reason in database
            # TODO: Send cancellation email

            return {
                "success": True,
                "message": "Subscription will be cancelled at the end of the current billing period",
                "cancel_at_period_end": True,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")

    @app.post("/api/v1/subscription/reactivate")
    async def reactivate_subscription(user: dict = Depends(get_current_user)):
        """
        Reactivate a subscription that was set to cancel at period end.
        """
        customer_id = user.get("customer_id") or user["user_id"]

        try:
            import stripe

            subscription_id = user.get("stripe_subscription_id")

            if subscription_id:
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=False,
                )

            return {
                "success": True,
                "message": "Subscription reactivated successfully",
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reactivate: {str(e)}")

    @app.get("/api/v1/subscription/invoices")
    async def get_invoices(
        limit: int = 10,
        user: dict = Depends(get_current_user),
    ):
        """
        Get invoice history for the customer.

        Returns list of past invoices with download links.
        """
        customer_id = user.get("customer_id") or user["user_id"]

        try:
            import stripe

            stripe_customer_id = user.get("stripe_customer_id")

            if not stripe_customer_id:
                return {"invoices": []}

            invoices = stripe.Invoice.list(
                customer=stripe_customer_id,
                limit=limit,
            )

            return {
                "invoices": [
                    {
                        "id": inv.id,
                        "number": inv.number,
                        "date": inv.created,
                        "amount": inv.amount_paid,
                        "currency": inv.currency,
                        "status": inv.status,
                        "pdf_url": inv.invoice_pdf,
                        "hosted_url": inv.hosted_invoice_url,
                        "description": f"{inv.lines.data[0].description}" if inv.lines.data else "Subscription",
                    }
                    for inv in invoices.data
                ]
            }

        except Exception as e:
            # Return empty list on error (user might not have Stripe customer yet)
            return {"invoices": []}

    @app.post("/api/v1/subscription/portal")
    async def create_portal_session(user: dict = Depends(get_current_user)):
        """
        Create a Stripe Customer Portal session.

        The portal allows customers to:
        - Update payment methods
        - View invoices
        - Manage subscription
        """
        customer_id = user.get("customer_id") or user["user_id"]
        beacon_name = user.get("beacon_name", "beacon")

        try:
            import stripe

            stripe_customer_id = user.get("stripe_customer_id")

            if not stripe_customer_id:
                raise HTTPException(status_code=400, detail="No billing account found")

            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=f"https://{beacon_name}.wopr.systems/billing",
            )

            return {
                "portal_url": portal_session.url,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create portal session: {str(e)}")

    @app.post("/api/v1/subscription/update-payment")
    async def update_payment_method(user: dict = Depends(get_current_user)):
        """
        Create a Stripe session specifically for updating payment method.
        """
        customer_id = user.get("customer_id") or user["user_id"]
        beacon_name = user.get("beacon_name", "beacon")

        try:
            import stripe

            stripe_customer_id = user.get("stripe_customer_id")

            if not stripe_customer_id:
                raise HTTPException(status_code=400, detail="No billing account found")

            # Create setup session for payment method update
            setup_session = stripe.checkout.Session.create(
                customer=stripe_customer_id,
                mode="setup",
                payment_method_types=["card"],
                success_url=f"https://{beacon_name}.wopr.systems/billing?payment_updated=success",
                cancel_url=f"https://{beacon_name}.wopr.systems/billing",
            )

            return {
                "session_url": setup_session.url,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

    @app.get("/api/v1/subscription/usage")
    async def get_usage_stats(user: dict = Depends(get_current_user)):
        """
        Get detailed usage statistics for the subscription.
        """
        customer_id = user.get("customer_id") or user["user_id"]
        beacon_name = user.get("beacon_name", "beacon")

        # TODO: Fetch actual usage from monitoring/database
        # This would integrate with the beacon's metrics
        usage = {
            "storage": {
                "used_bytes": 13421772800,  # 12.5 GB
                "limit_bytes": 53687091200,  # 50 GB
                "used_gb": 12.5,
                "limit_gb": 50,
                "percent": 25,
            },
            "bandwidth": {
                "used_bytes": 107374182400,  # 100 GB
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-02-01T00:00:00Z",
            },
            "users": {
                "count": 1,
                "limit": 1,
                "list": [
                    {
                        "email": user.get("email"),
                        "role": "admin",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
            "apps": {
                "enabled": ["nextcloud", "vaultwarden", "freshrss"],
                "available": ["wallabag", "stirling-pdf"],
            },
            "last_updated": datetime.now().isoformat(),
        }

        return usage

    # ----------------------------------------
    # STRIPE WEBHOOK ENDPOINT
    # ----------------------------------------

    @app.post("/api/v1/webhooks/stripe")
    async def stripe_webhook(request: Request):
        """
        Handle Stripe webhook events.

        This is the critical endpoint that receives payment confirmations
        and triggers VPS provisioning.

        Events handled:
        - checkout.session.completed: New subscription -> trigger provisioning
        - customer.subscription.updated: Plan changes
        - customer.subscription.deleted: Cancellations
        - invoice.payment_failed: Failed payments
        """
        import os

        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            # Verify webhook signature
            result = billing.process_webhook(payload, sig_header)

            # If checkout completed, trigger VPS provisioning
            if result.get("ready_to_provision"):
                # Import VPS provisioner
                from .vps_provisioner import VPSProvisioner, handle_stripe_checkout_completed

                # Get Hetzner token from environment
                hetzner_token = os.environ.get("HETZNER_API_TOKEN")
                orchestrator_url = os.environ.get(
                    "ORCHESTRATOR_URL",
                    "https://api.wopr.systems"
                )

                if hetzner_token:
                    provisioner = VPSProvisioner(
                        hetzner_token=hetzner_token,
                        orchestrator_url=orchestrator_url,
                    )

                    # Get the full session data for provisioning
                    import stripe
                    session = stripe.checkout.Session.retrieve(
                        result.get("session_id", ""),
                        expand=["customer_details"],
                    )

                    # Start VPS provisioning
                    import asyncio
                    provision_result = await handle_stripe_checkout_completed(
                        session_data=session,
                        provisioner=provisioner,
                    )

                    result["provision_result"] = provision_result
                else:
                    logger.warning("HETZNER_API_TOKEN not set, skipping VPS provisioning")
                    result["provision_result"] = {"error": "VPS provisioning not configured"}

            return {"status": "ok", "result": result}

        except ValueError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ----------------------------------------
    # INSTALLER CALLBACK ENDPOINT
    # ----------------------------------------

    @app.post("/api/v1/provision/{job_id}/status")
    async def update_provision_status(job_id: str, request: Request):
        """
        Receive status updates from the installer running on the VPS.

        The installer calls this endpoint to report progress as it
        deploys modules. This updates the job store which feeds the
        SSE stream to the user's browser.

        Expected JSON body:
        {
            "status": "deploying_wopr",
            "message": "Installing nextcloud...",
            "step": 3,
            "progress": 45,
            "current_module": "nextcloud",
            "modules_completed": 5,
            "modules_total": 12
        }
        """
        data = await request.json()

        status = data.get("status", "")
        message = data.get("message", "")

        # Map installer status to job store state
        status_map = {
            "provisioning_vps": "provisioning_vps",
            "waiting_for_vps": "waiting_for_vps",
            "installing": "deploying_wopr",
            "deploying": "deploying_wopr",
            "deploying_wopr": "deploying_wopr",
            "configuring_dns": "configuring_dns",
            "configuring_sso": "deploying_wopr",
            "generating_docs": "generating_docs",
            "sending_welcome": "sending_welcome",
            "complete": "completed",
            "completed": "completed",
            "failed": "failed",
            "error": "failed",
        }

        state = status_map.get(status, status)

        # Update job store
        if state == "completed":
            job_store.complete_job(
                job_id,
                beacon_name=data.get("beacon_name", ""),
                instance_ip=data.get("instance_ip", ""),
            )
        elif state == "failed":
            job_store.fail_job(job_id, message or "Provisioning failed")
        else:
            # Update progress
            updates = {"state": state}
            if message:
                updates["message"] = message
            if "step" in data:
                updates["step"] = data["step"]
            if "progress" in data:
                updates["progress"] = data["progress"]
            if "current_module" in data:
                updates["current_module"] = data["current_module"]
            if "modules_completed" in data and "modules_total" in data:
                job_store.update_module_progress(
                    job_id,
                    data["current_module"],
                    data["modules_completed"],
                    data["modules_total"],
                )
            else:
                job_store.update_job(job_id, **updates)

        logger.info(f"Job {job_id} status update: {state} - {message}")

        return {"status": "ok", "job_id": job_id, "state": state}

    # ----------------------------------------
    # PROVISION PAGE WITH SESSION LOOKUP
    # ----------------------------------------

    @app.get("/provision")
    async def provision_from_session(session_id: Optional[str] = None):
        """
        Handle Stripe success redirect.

        After Stripe checkout completes, the user is redirected here with
        the session_id. We look up the session to find the job, then
        redirect to the provisioning watch page.

        Flow:
        1. User completes Stripe checkout
        2. Stripe redirects to /provision?session_id=cs_xxx
        3. We look up the session metadata to find beacon_name
        4. Redirect to /provision/{job_id}
        """
        from fastapi.responses import RedirectResponse

        if not session_id:
            # No session, show waiting page
            return RedirectResponse(url="/provision/pending")

        try:
            import stripe

            # Get session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)

            # The job_id might be in our job store already (webhook may have fired)
            # Look it up by beacon_name from metadata
            metadata = session.metadata or {}
            beacon_name = metadata.get("wopr_beacon_name", "")

            if beacon_name:
                # Find job by beacon name
                jobs = job_store.list_jobs(limit=10)
                for job in jobs:
                    if job.get("beacon_name") == beacon_name:
                        return RedirectResponse(url=f"/provision/{job['job_id']}")

            # If job not found yet, create a placeholder
            # (webhook might still be processing)
            import secrets
            job_id = secrets.token_urlsafe(16)
            job_store.create_job(
                job_id=job_id,
                beacon_name=beacon_name or "pending",
                bundle=metadata.get("wopr_bundle", ""),
                tier=metadata.get("wopr_tier", "t1"),
                customer_email=session.customer_email or "",
                customer_name=metadata.get("wopr_customer_name", ""),
            )

            return RedirectResponse(url=f"/provision/{job_id}")

        except Exception as e:
            logger.error(f"Error looking up session {session_id}: {e}")
            return RedirectResponse(url="/provision/error")

    return app


# ============================================
# EXAMPLE USAGE
# ============================================

def create_app_from_env():
    """Create app using environment variables."""
    import os

    billing = WOPRBilling(
        stripe_secret_key=os.environ["STRIPE_SECRET_KEY"],
        stripe_webhook_secret=os.environ["STRIPE_WEBHOOK_SECRET"],
        success_url=os.environ.get("STRIPE_SUCCESS_URL", "https://wopr.systems/success"),
        cancel_url=os.environ.get("STRIPE_CANCEL_URL", "https://wopr.systems/cancel"),
    )

    trial_manager = TrialManager(
        stripe_secret_key=os.environ["STRIPE_SECRET_KEY"],
        authentik_api_url=os.environ["AUTHENTIK_API_URL"],
        authentik_api_token=os.environ["AUTHENTIK_API_TOKEN"],
    )

    authentik = AuthentikClient(
        base_url=os.environ["AUTHENTIK_API_URL"],
        api_token=os.environ["AUTHENTIK_API_TOKEN"],
    )

    return create_dashboard_app(billing, trial_manager, authentik)


# To run: uvicorn control_plane.dashboard_api:app --reload
# with: app = create_app_from_env()
