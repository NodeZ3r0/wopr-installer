"""
WOPR Beacon Provisioning Orchestrator

Handles the complete Beacon setup flow when a user subscribes:
1. Payment webhook triggers provisioning
2. Collect user onboarding data
3. Provision infrastructure (Authentik, Caddy, DB)
4. Deploy bundle-appropriate modules with SSO
5. Send welcome email with access details

Bundle Structure:
- BundleType: SOVEREIGN (7 suites) or MICRO (16 bundles)
- bundle_id: e.g., "starter", "developer", "meeting_room", "therapist"
- StorageTier: 1 (50GB), 2 (200GB), 3 (500GB+)
"""

import asyncio
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Callable, Awaitable
from pathlib import Path
from enum import Enum

from .tiers import (
    BundleType,
    StorageTier,
    SovereignSuiteID,
    MicroBundleID,
    get_storage_tier,
    get_sovereign_price,
    get_micro_price,
)
from ..job_store import get_job_store
from .manifests import (
    BundleManifest,
    get_bundle,
    get_modules_for_bundle,
    parse_checkout_bundle,
)
from ..services.authentik_provisioner import AuthentikConfig, UserProfile
from ..services.module_deployer import ModuleDeployer, DeploymentConfig, DeploymentResult
from ..services.onboarding import OnboardingState, OnboardingWizard


class ProvisioningStatus(Enum):
    """Beacon provisioning status"""
    PENDING = "pending"  # Waiting for payment confirmation
    PAYMENT_CONFIRMED = "payment_confirmed"  # Payment received
    ONBOARDING = "onboarding"  # Collecting user data
    PROVISIONING_INFRA = "provisioning_infra"  # Setting up core infra
    DEPLOYING_MODULES = "deploying_modules"  # Installing modules
    CONFIGURING_SSO = "configuring_sso"  # Setting up SSO
    FINALIZING = "finalizing"  # Final checks
    COMPLETE = "complete"  # Ready to use
    FAILED = "failed"  # Provisioning failed


@dataclass
class ProvisioningProgress:
    """Track provisioning progress"""
    status: ProvisioningStatus = ProvisioningStatus.PENDING
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    current_module: Optional[str] = None
    modules_total: int = 0
    modules_completed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def progress_percent(self) -> int:
        if self.total_steps == 0:
            return 0
        return int((self.completed_steps / self.total_steps) * 100)


@dataclass
class BeaconInstance:
    """A provisioned Beacon instance"""
    beacon_id: str
    bundle_type: BundleType
    bundle_id: str  # e.g., "starter", "meeting_room"
    storage_tier: StorageTier
    user_email: str
    domain: str
    status: ProvisioningStatus
    progress: ProvisioningProgress

    # Stripe integration
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    # Deployment tracking
    deployed_modules: list[str] = field(default_factory=list)
    failed_modules: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    provisioned_at: Optional[datetime] = None

    # Access URLs
    authentik_url: Optional[str] = None
    dashboard_url: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["bundle_type"] = self.bundle_type.value
        data["storage_tier"] = self.storage_tier.value
        data["status"] = self.status.value
        data["progress"]["status"] = self.progress.status.value
        return data

    @property
    def bundle_string(self) -> str:
        """Get bundle string for checkout URL format (e.g., 'sovereign-starter')"""
        return f"{self.bundle_type.value}-{self.bundle_id}"


@dataclass
class ProvisioningRequest:
    """Request to provision a new Beacon"""
    bundle_type: BundleType  # SOVEREIGN or MICRO
    bundle_id: str           # e.g., "starter", "meeting_room"
    storage_tier: StorageTier  # 1, 2, or 3
    user_email: str
    domain: str

    # User profile
    username: str
    display_name: str
    handle: Optional[str] = None

    # Payment info
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None

    # Module selection (if user customized - for future use)
    selected_modules: Optional[list[str]] = None

    # Infrastructure
    cloudflare_api_token: Optional[str] = None
    cloudflare_zone_id: Optional[str] = None
    server_ip: Optional[str] = None

    @classmethod
    def from_checkout_params(
        cls,
        checkout_bundle: str,  # e.g., "sovereign-starter" or "micro-meeting_room"
        storage_tier: int,      # 1, 2, or 3
        user_email: str,
        domain: str,
        username: str,
        display_name: str,
        **kwargs,
    ) -> "ProvisioningRequest":
        """Create request from checkout URL parameters"""
        bundle_type, bundle_id = parse_checkout_bundle(checkout_bundle)
        return cls(
            bundle_type=bundle_type,
            bundle_id=bundle_id,
            storage_tier=StorageTier(storage_tier),
            user_email=user_email,
            domain=domain,
            username=username,
            display_name=display_name,
            **kwargs,
        )


# Type alias for progress callback
ProgressCallback = Callable[[ProvisioningProgress], Awaitable[None]]


class BeaconProvisioner:
    """
    Orchestrates complete Beacon provisioning.

    Usage:
        provisioner = BeaconProvisioner()

        # Start provisioning (async)
        beacon = await provisioner.provision(
            request=ProvisioningRequest(
                bundle_type=BundleType.SOVEREIGN,
                bundle_id="starter",
                storage_tier=StorageTier.TIER_1,
                user_email="user@example.com",
                domain="example.com",
                username="user",
                display_name="John Doe",
            ),
            on_progress=my_progress_callback,
        )
    """

    def __init__(
        self,
        config_path: Path = Path("/opt/wopr/config"),
        modules_path: Path = Path("/opt/wopr/modules"),
    ):
        self.config_path = config_path
        self.modules_path = modules_path
        self.instances: dict[str, BeaconInstance] = {}

    async def provision(
        self,
        request: ProvisioningRequest,
        on_progress: Optional[ProgressCallback] = None,
        job_id: Optional[str] = None,
    ) -> BeaconInstance:
        """
        Provision a complete Beacon instance.

        This is the main entry point called after payment is confirmed.

        Args:
            request: Provisioning parameters
            on_progress: Optional callback for progress updates
            job_id: Optional job ID for updating shared job store (for SSE streaming)
        """
        import secrets

        # Generate beacon ID
        beacon_id = f"beacon-{secrets.token_hex(8)}"

        # Initialize instance
        instance = BeaconInstance(
            beacon_id=beacon_id,
            bundle_type=request.bundle_type,
            bundle_id=request.bundle_id,
            storage_tier=request.storage_tier,
            user_email=request.user_email,
            domain=request.domain,
            status=ProvisioningStatus.PAYMENT_CONFIRMED,
            progress=ProvisioningProgress(
                status=ProvisioningStatus.PAYMENT_CONFIRMED,
                started_at=datetime.utcnow(),
            ),
            stripe_customer_id=request.stripe_customer_id,
            stripe_subscription_id=request.stripe_subscription_id,
        )

        self.instances[beacon_id] = instance

        # Store job_id in instance for later reference
        if job_id:
            instance.job_id = job_id

        try:
            # Step 1: Setup onboarding data
            await self._update_progress(
                instance, ProvisioningStatus.ONBOARDING,
                "Configuring user profile", 1, 6, on_progress, job_id
            )
            onboarding_state = await self._setup_onboarding(request)

            # Step 2: Provision core infrastructure
            await self._update_progress(
                instance, ProvisioningStatus.PROVISIONING_INFRA,
                "Deploying core infrastructure (Authentik, Caddy, Database)", 2, 6, on_progress, job_id
            )
            await self._provision_infrastructure(instance, onboarding_state)

            # Step 3: Get modules to deploy
            await self._update_progress(
                instance, ProvisioningStatus.DEPLOYING_MODULES,
                "Preparing module deployment", 3, 6, on_progress, job_id
            )
            modules_to_deploy = self._get_modules_to_deploy(request)
            instance.progress.modules_total = len(modules_to_deploy)

            # Update job store with module count
            if job_id:
                job_store = get_job_store()
                job_store.update_job(job_id, modules_total=len(modules_to_deploy))

            # Step 4: Deploy each module with SSO
            await self._update_progress(
                instance, ProvisioningStatus.CONFIGURING_SSO,
                "Deploying modules with SSO integration", 4, 6, on_progress, job_id
            )
            await self._deploy_modules(instance, modules_to_deploy, onboarding_state, on_progress, job_id)

            # Step 5: Finalize
            await self._update_progress(
                instance, ProvisioningStatus.FINALIZING,
                "Running final configuration", 5, 6, on_progress, job_id
            )
            await self._finalize_deployment(instance, onboarding_state)

            # Step 6: Complete
            instance.status = ProvisioningStatus.COMPLETE
            instance.progress.status = ProvisioningStatus.COMPLETE
            instance.progress.completed_steps = 6
            instance.progress.current_step = "Beacon ready!"
            instance.provisioned_at = datetime.utcnow()
            instance.progress.completed_at = datetime.utcnow()

            if on_progress:
                await on_progress(instance.progress)

            # Update shared job store with completion
            if job_id:
                job_store = get_job_store()
                job_store.complete_job(job_id, request.domain, "")

            # Save instance state
            await self._save_instance(instance)

            return instance

        except Exception as e:
            instance.status = ProvisioningStatus.FAILED
            instance.progress.status = ProvisioningStatus.FAILED
            instance.progress.errors.append(str(e))

            if on_progress:
                await on_progress(instance.progress)

            # Update shared job store with failure
            if job_id:
                job_store = get_job_store()
                job_store.fail_job(job_id, str(e))

            raise

    async def _update_progress(
        self,
        instance: BeaconInstance,
        status: ProvisioningStatus,
        step: str,
        completed: int,
        total: int,
        callback: Optional[ProgressCallback],
        job_id: Optional[str] = None,
    ):
        """Update provisioning progress - both instance and shared job store"""
        instance.status = status
        instance.progress.status = status
        instance.progress.current_step = step
        instance.progress.completed_steps = completed
        instance.progress.total_steps = total

        if callback:
            await callback(instance.progress)

        # Update shared job store for SSE streaming
        if job_id:
            job_store = get_job_store()
            # Map ProvisioningStatus to job_store state
            STATE_MAP = {
                ProvisioningStatus.PENDING: "pending",
                ProvisioningStatus.PAYMENT_CONFIRMED: "payment_received",
                ProvisioningStatus.ONBOARDING: "payment_received",
                ProvisioningStatus.PROVISIONING_INFRA: "provisioning_vps",
                ProvisioningStatus.DEPLOYING_MODULES: "deploying_wopr",
                ProvisioningStatus.CONFIGURING_SSO: "deploying_wopr",
                ProvisioningStatus.FINALIZING: "generating_docs",
                ProvisioningStatus.COMPLETE: "completed",
                ProvisioningStatus.FAILED: "failed",
            }
            state = STATE_MAP.get(status, "pending")
            job_store.set_state(job_id, state, message=step)

    async def _setup_onboarding(self, request: ProvisioningRequest) -> OnboardingState:
        """Create onboarding state from provisioning request"""
        wizard = OnboardingWizard()

        user_data = {
            "username": request.username,
            "email": request.user_email,
            "handle": request.handle or f"@{request.username}",
            "display_name": request.display_name,
        }

        authentik_data = {
            "base_url": f"https://auth.{request.domain}",
        }

        # Get storage limits for selected tier
        storage_limits = get_storage_tier(request.storage_tier)

        infra_data = {
            "domain": request.domain,
            "cloudflare_api_token": request.cloudflare_api_token,
            "cloudflare_zone_id": request.cloudflare_zone_id,
            "server_ip": request.server_ip,
            "storage_gb": storage_limits.storage_gb,
            "ram_mb": storage_limits.ram_mb,
            "max_users": storage_limits.max_users,
        }

        state = wizard.create_state(user_data, authentik_data, infra_data)
        state.save(self.config_path / "onboarding.json")

        return state

    async def _provision_infrastructure(
        self,
        instance: BeaconInstance,
        state: OnboardingState,
    ):
        """Deploy core infrastructure (Authentik, Caddy, PostgreSQL, Redis)"""
        from ..services.module_deployer import ModuleDeployer, DeploymentConfig

        config = DeploymentConfig(
            install_base_path=str(self.modules_path),
            github_org="NodeZ3r0",
        )

        authentik_config = state.authentik.to_authentik_config()
        user_profile = state.user.to_user_profile(state.infrastructure.domain)

        deployer = ModuleDeployer(authentik_config, user_profile, config)

        # Deploy core modules in order
        core_modules = ["postgresql", "redis", "authentik", "caddy"]

        for module_id in core_modules:
            result = await deployer.deploy_module(module_id)
            if result.success:
                instance.deployed_modules.append(module_id)
            else:
                instance.failed_modules.append(module_id)
                raise RuntimeError(f"Failed to deploy core module {module_id}: {result.error}")

        # Set Authentik URL
        instance.authentik_url = f"https://auth.{state.infrastructure.domain}"

    def _get_modules_to_deploy(self, request: ProvisioningRequest) -> list[str]:
        """Get list of modules to deploy based on bundle"""
        if request.selected_modules:
            # User customized their selection (future feature)
            return request.selected_modules

        # Get modules from bundle manifest
        return get_modules_for_bundle(request.bundle_type, request.bundle_id)

    async def _deploy_modules(
        self,
        instance: BeaconInstance,
        modules: list[str],
        state: OnboardingState,
        on_progress: Optional[ProgressCallback],
        job_id: Optional[str] = None,
    ):
        """Deploy selected modules with SSO integration"""
        from ..services.module_deployer import ModuleDeployer, DeploymentConfig

        config = DeploymentConfig(
            install_base_path=str(self.modules_path),
            github_org="NodeZ3r0",
        )

        authentik_config = state.authentik.to_authentik_config()
        user_profile = state.user.to_user_profile(state.infrastructure.domain)

        deployer = ModuleDeployer(authentik_config, user_profile, config)

        # Skip core modules (already deployed)
        core = {"authentik", "caddy", "postgresql", "redis"}
        modules_to_deploy = [m for m in modules if m not in core]

        for i, module_id in enumerate(modules_to_deploy):
            instance.progress.current_module = module_id
            instance.progress.modules_completed = i

            if on_progress:
                await on_progress(instance.progress)

            # Update shared job store with module progress
            if job_id:
                job_store = get_job_store()
                job_store.update_module_progress(
                    job_id,
                    current_module=module_id,
                    modules_completed=i,
                    modules_total=len(modules_to_deploy),
                )

            result = await deployer.deploy_module(module_id)

            if result.success:
                instance.deployed_modules.append(module_id)
            else:
                instance.failed_modules.append(module_id)
                instance.progress.errors.append(f"{module_id}: {result.error}")
                # Continue with other modules, don't fail completely

        instance.progress.modules_completed = len(modules_to_deploy)

        # Final module progress update
        if job_id:
            job_store = get_job_store()
            job_store.update_module_progress(
                job_id,
                current_module="",
                modules_completed=len(modules_to_deploy),
                modules_total=len(modules_to_deploy),
            )

    async def _finalize_deployment(
        self,
        instance: BeaconInstance,
        state: OnboardingState,
    ):
        """Final configuration and cleanup"""
        # Set dashboard URL
        instance.dashboard_url = f"https://dashboard.{state.infrastructure.domain}"

        # Update onboarding state with deployed modules
        state.deployed_modules = instance.deployed_modules
        state.save(self.config_path / "onboarding.json")

        # TODO: Send welcome email
        # TODO: Create initial admin user in Authentik
        # TODO: Generate recovery codes

    async def _save_instance(self, instance: BeaconInstance):
        """Save instance state to disk"""
        instances_dir = self.config_path / "instances"
        instances_dir.mkdir(parents=True, exist_ok=True)

        instance_file = instances_dir / f"{instance.beacon_id}.json"
        instance_file.write_text(json.dumps(instance.to_dict(), indent=2, default=str))

    async def get_instance(self, beacon_id: str) -> Optional[BeaconInstance]:
        """Get instance by ID"""
        if beacon_id in self.instances:
            return self.instances[beacon_id]

        # Try loading from disk
        instance_file = self.config_path / "instances" / f"{beacon_id}.json"
        if instance_file.exists():
            data = json.loads(instance_file.read_text())
            # Reconstruct instance
            return BeaconInstance(
                beacon_id=data["beacon_id"],
                bundle_type=BundleType(data["bundle_type"]),
                bundle_id=data["bundle_id"],
                storage_tier=StorageTier(data["storage_tier"]),
                user_email=data["user_email"],
                domain=data["domain"],
                status=ProvisioningStatus(data["status"]),
                progress=ProvisioningProgress(),
                deployed_modules=data.get("deployed_modules", []),
            )

        return None


# =============================================================================
# Stripe Webhook Handler
# =============================================================================

async def handle_stripe_webhook(
    event_type: str,
    event_data: dict,
    provisioner: BeaconProvisioner,
) -> Optional[BeaconInstance]:
    """
    Handle Stripe webhook events.

    Called by the webhook endpoint when Stripe sends payment events.

    Events handled:
    - checkout.session.completed: New subscription
    - customer.subscription.updated: Plan change
    - customer.subscription.deleted: Cancellation

    Expected metadata in checkout session:
    - bundle: "sovereign-starter" or "micro-meeting_room"
    - tier: "1", "2", or "3" (storage tier)
    - domain: "example.com"
    - username: "johndoe"
    - display_name: "John Doe"
    """
    if event_type == "checkout.session.completed":
        import secrets
        session = event_data["object"]
        metadata = session.get("metadata", {})

        # Parse bundle from checkout format (e.g., "sovereign-starter")
        checkout_bundle = metadata.get("bundle", "sovereign-starter")
        storage_tier = int(metadata.get("tier", "1"))
        beacon_name = metadata.get("beacon_name", metadata.get("domain", "").split(".")[0])
        customer_email = session.get("customer_email", "")
        customer_name = metadata.get("customer_name", metadata.get("display_name", ""))

        # Generate job ID for tracking
        job_id = secrets.token_urlsafe(16)

        # Create job in shared store immediately
        job_store = get_job_store()
        job_store.create_job(
            job_id=job_id,
            beacon_name=beacon_name,
            bundle=checkout_bundle,
            tier=f"t{storage_tier}",
            customer_email=customer_email,
            customer_name=customer_name,
        )

        # Send provisioning started email with watch link
        try:
            from ..email_service import EmailService
            email_svc = EmailService()
            provisioning_url = f"https://provision.wopr.systems/{job_id}"

            # Get bundle name for email
            bundle_parts = checkout_bundle.split("-", 1)
            bundle_name = bundle_parts[1].replace("_", " ").title() if len(bundle_parts) > 1 else checkout_bundle

            email_svc.send_provisioning_started(
                to_email=customer_email,
                name=customer_name or customer_email.split("@")[0],
                beacon_name=beacon_name,
                bundle_name=bundle_name,
                job_id=job_id,
                provisioning_url=provisioning_url,
            )
        except Exception as e:
            # Log but don't fail if email fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to send provisioning email: {e}")

        # Create provisioning request from checkout params
        request = ProvisioningRequest.from_checkout_params(
            checkout_bundle=checkout_bundle,
            storage_tier=storage_tier,
            user_email=customer_email,
            domain=metadata.get("domain", ""),
            username=metadata.get("username", ""),
            display_name=metadata.get("display_name", ""),
            stripe_customer_id=session.get("customer"),
            stripe_subscription_id=session.get("subscription"),
        )

        # Start provisioning with job_id for progress tracking
        return await provisioner.provision(request, job_id=job_id)

    elif event_type == "customer.subscription.updated":
        # Handle tier upgrades/downgrades
        subscription = event_data["object"]
        # TODO: Implement tier change logic
        pass

    elif event_type == "customer.subscription.deleted":
        # Handle cancellation
        subscription = event_data["object"]
        # TODO: Implement deprovisioning logic
        pass

    return None


# =============================================================================
# API Endpoints
# =============================================================================

def create_provisioning_api(app, provisioner: BeaconProvisioner):
    """
    Create FastAPI routes for Beacon provisioning.

    Endpoints:
    - POST /api/beacon/provision - Start provisioning (internal)
    - GET /api/beacon/{id}/status - Get provisioning status
    - POST /api/webhook/stripe - Stripe webhook handler
    """
    from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
    from pydantic import BaseModel

    router = APIRouter(tags=["beacon"])

    class ProvisionRequest(BaseModel):
        bundle: str  # e.g., "sovereign-starter" or "micro-meeting_room"
        tier: int    # Storage tier: 1, 2, or 3
        user_email: str
        domain: str
        username: str
        display_name: str
        handle: Optional[str] = None
        selected_modules: Optional[list[str]] = None
        cloudflare_api_token: Optional[str] = None

    @router.post("/api/beacon/provision")
    async def start_provisioning(
        request: ProvisionRequest,
        background_tasks: BackgroundTasks,
    ):
        """Start Beacon provisioning (called after payment)"""
        prov_request = ProvisioningRequest.from_checkout_params(
            checkout_bundle=request.bundle,
            storage_tier=request.tier,
            user_email=request.user_email,
            domain=request.domain,
            username=request.username,
            display_name=request.display_name,
            handle=request.handle,
            selected_modules=request.selected_modules,
            cloudflare_api_token=request.cloudflare_api_token,
        )

        # Run provisioning in background
        async def run_provisioning():
            await provisioner.provision(prov_request)

        background_tasks.add_task(run_provisioning)

        return {"status": "provisioning_started"}

    @router.get("/api/beacon/{beacon_id}/status")
    async def get_status(beacon_id: str):
        """Get Beacon provisioning status"""
        instance = await provisioner.get_instance(beacon_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Beacon not found")

        return {
            "beacon_id": instance.beacon_id,
            "bundle": instance.bundle_string,
            "storage_tier": instance.storage_tier.value,
            "status": instance.status.value,
            "progress": {
                "percent": instance.progress.progress_percent,
                "current_step": instance.progress.current_step,
                "current_module": instance.progress.current_module,
                "modules_completed": instance.progress.modules_completed,
                "modules_total": instance.progress.modules_total,
            },
            "deployed_modules": instance.deployed_modules,
            "failed_modules": instance.failed_modules,
            "errors": instance.progress.errors,
            "authentik_url": instance.authentik_url,
            "dashboard_url": instance.dashboard_url,
        }

    @router.post("/api/webhook/stripe")
    async def stripe_webhook(request: Request):
        """Handle Stripe webhook events"""
        import stripe

        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        # Verify webhook signature (requires STRIPE_WEBHOOK_SECRET env var)
        # endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        # event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)

        # For now, parse directly (add signature verification in production)
        event = json.loads(payload)

        await handle_stripe_webhook(
            event["type"],
            event["data"],
            provisioner,
        )

        return {"received": True}

    app.include_router(router)
    return router
