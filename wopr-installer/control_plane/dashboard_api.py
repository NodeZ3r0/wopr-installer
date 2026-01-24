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
        allow_origins=["https://*.wopr.systems"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
