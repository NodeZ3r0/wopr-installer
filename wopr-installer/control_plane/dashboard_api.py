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

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

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
from .authentik_integration import (
    AuthentikClient,
    user_can_access_feature,
    BUNDLE_GROUPS,
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
        version="1.5",
    )

    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://*.wopr.systems"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = DashboardService(billing, trial_manager, authentik)

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
