"""
WOPR Provisioning Callbacks
===========================

Handles callback-based progress reporting from newly provisioned beacons.
Instead of SSH polling, beacons POST their progress back to the orchestrator.

Flow:
1. Orchestrator generates a callback_token for each job
2. Token is embedded in cloud-init bootstrap.json
3. Beacon's install script POSTs progress to /api/provision/{job_id}/callback
4. Orchestrator validates token and updates job state
"""

import asyncio
import secrets
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CallbackStage(Enum):
    """Stages reported by the beacon during installation."""
    BOOT = "boot"                    # Cloud-init started
    PACKAGES = "packages"            # Package installation complete
    WOPR_DOWNLOAD = "wopr_download"  # WOPR installer downloaded
    CORE_MODULES = "core_modules"    # Core infra (caddy, auth, db) installed
    APP_MODULES = "app_modules"      # App modules being installed
    HEALTH_READY = "health_ready"    # Health endpoint responding
    COMPLETE = "complete"            # Full installation complete
    ERROR = "error"                  # Installation failed


@dataclass
class CallbackState:
    """Tracks callback state for a provisioning job."""
    token: str
    job_id: str
    created_at: datetime
    last_update: Optional[datetime] = None
    current_stage: CallbackStage = CallbackStage.BOOT
    current_module: Optional[str] = None
    progress_pct: int = 0
    error_message: Optional[str] = None
    ready_event: asyncio.Event = None  # Set when installation completes
    
    def __post_init__(self):
        if self.ready_event is None:
            self.ready_event = asyncio.Event()


class CallbackManager:
    """
    Manages callback tokens and events for provisioning jobs.
    
    Thread-safe storage for callback state, allowing the orchestrator
    to wait for beacon callbacks instead of polling.
    """
    
    def __init__(self):
        # job_id -> CallbackState
        self._callbacks: Dict[str, CallbackState] = {}
        self._lock = asyncio.Lock()
    
    async def create_callback(self, job_id: str) -> str:
        """
        Create a new callback token for a job.
        
        Returns the token that should be embedded in cloud-init.
        """
        token = secrets.token_urlsafe(32)
        
        async with self._lock:
            self._callbacks[job_id] = CallbackState(
                token=token,
                job_id=job_id,
                created_at=datetime.now(),
            )
        
        logger.info(f"Created callback token for job {job_id}")
        return token
    
    async def validate_callback(self, job_id: str, token: str) -> bool:
        """Validate that a callback token is correct for a job."""
        async with self._lock:
            state = self._callbacks.get(job_id)
            if not state:
                logger.warning(f"No callback state for job {job_id}")
                return False
            if not secrets.compare_digest(state.token, token):
                logger.warning(f"Invalid callback token for job {job_id}")
                return False
            return True
    
    async def handle_callback(
        self,
        job_id: str,
        token: str,
        stage: str,
        progress: int = 0,
        module: Optional[str] = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Handle a callback from a provisioning beacon.
        
        Returns True if the callback was valid and processed.
        """
        if not await self.validate_callback(job_id, token):
            return False
        
        async with self._lock:
            state = self._callbacks.get(job_id)
            if not state:
                return False
            
            try:
                state.current_stage = CallbackStage(stage)
            except ValueError:
                logger.warning(f"Unknown callback stage: {stage}")
                state.current_stage = CallbackStage.BOOT
            
            state.last_update = datetime.now()
            state.progress_pct = min(100, max(0, progress))
            state.current_module = module
            
            if error:
                state.error_message = error
                state.current_stage = CallbackStage.ERROR
            
            # Signal completion
            if state.current_stage in (CallbackStage.COMPLETE, CallbackStage.HEALTH_READY):
                state.ready_event.set()
                logger.info(f"Job {job_id} installation complete via callback")
            elif state.current_stage == CallbackStage.ERROR:
                state.ready_event.set()  # Unblock waiters on error too
                logger.error(f"Job {job_id} installation failed: {error}")
            else:
                logger.info(f"Job {job_id} progress: {stage} ({progress}%) - {module or 'N/A'}")
        
        return True
    
    async def wait_for_ready(self, job_id: str, timeout: float = 600) -> bool:
        """
        Wait for a beacon to report ready via callback.
        
        Returns True if ready, False if timeout or error.
        """
        async with self._lock:
            state = self._callbacks.get(job_id)
            if not state:
                logger.warning(f"No callback state for job {job_id}, cannot wait")
                return False
            event = state.ready_event
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            
            async with self._lock:
                state = self._callbacks.get(job_id)
                if state and state.current_stage == CallbackStage.ERROR:
                    return False
                return True
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for callback from job {job_id}")
            return False
    
    async def get_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a job."""
        async with self._lock:
            state = self._callbacks.get(job_id)
            if not state:
                return None
            return {
                "stage": state.current_stage.value,
                "progress": state.progress_pct,
                "module": state.current_module,
                "error": state.error_message,
                "last_update": state.last_update.isoformat() if state.last_update else None,
            }
    
    async def cleanup(self, job_id: str) -> None:
        """Remove callback state for a completed job."""
        async with self._lock:
            self._callbacks.pop(job_id, None)


# Global singleton
callback_manager = CallbackManager()
