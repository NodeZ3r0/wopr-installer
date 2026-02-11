"""
WOPR Provisioning Job Store
============================

Shared in-memory store for provisioning job status.
Used by both dashboard_api (for SSE streaming) and beacon_provisioner (for updates).

In production, this should be replaced with Redis or PostgreSQL.
"""

from typing import Dict, Optional, Any
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


class JobStore:
    """
    Thread-safe in-memory job store.

    Jobs are stored with the following structure:
    {
        "job_id": str,
        "state": str,  # pending, payment_received, provisioning_vps, waiting_for_vps,
                       # configuring_dns, deploying_wopr, generating_docs, sending_welcome,
                       # completed, failed
        "status": str,  # in_progress, complete, failed (for UI)
        "step": int,    # 0-5 for UI progress bar
        "progress": int,  # 0-100 percentage
        "beacon_name": str,
        "bundle": str,
        "tier": str,
        "provider": str,
        "customer_email": str,
        "customer_name": str,
        "created_at": str,  # ISO timestamp
        "updated_at": str,  # ISO timestamp
        "message": str,  # Human-readable status message
        "current_module": str,  # Currently deploying module
        "modules_completed": int,
        "modules_total": int,
        "error_message": str,  # If failed
        "beacon_url": str,  # Set on completion
        "dashboard_url": str,  # Set on completion
        "instance_ip": str,  # VPS IP address
    }
    """

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        job_id: str,
        beacon_name: str,
        bundle: str,
        tier: str,
        customer_email: str,
        customer_name: str = "",
        provider: str = "hetzner",
    ) -> Dict[str, Any]:
        """Create a new provisioning job."""
        now = datetime.now().isoformat()

        job = {
            "job_id": job_id,
            "state": "payment_received",
            "status": "in_progress",
            "step": 0,
            "progress": 5,
            "beacon_name": beacon_name,
            "bundle": bundle,
            "tier": tier,
            "provider": provider,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "created_at": now,
            "updated_at": now,
            "message": "Payment received, starting provisioning...",
            "current_module": "",
            "modules_completed": 0,
            "modules_total": 0,
            "error_message": "",
            "beacon_url": "",
            "dashboard_url": "",
            "instance_ip": "",
        }

        with self._lock:
            self._jobs[job_id] = job
            logger.info(f"Created job {job_id} for beacon {beacon_name}")

        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update job fields."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for update")
                return None

            job["updated_at"] = datetime.now().isoformat()
            job.update(updates)

            logger.debug(f"Updated job {job_id}: state={job.get('state')}, progress={job.get('progress')}")
            return job

    def set_state(
        self,
        job_id: str,
        state: str,
        message: str = "",
        progress: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update job state with automatic step/progress calculation.

        States and their UI mappings:
        - payment_received: step=0, progress=5
        - provisioning_vps: step=1, progress=15
        - waiting_for_vps: step=1, progress=25
        - configuring_dns: step=2, progress=40
        - deploying_wopr: step=3, progress=50-80 (depends on module progress)
        - generating_docs: step=4, progress=85
        - sending_welcome: step=4, progress=90
        - completed: step=5, progress=100
        - failed: step=-1
        """
        STATE_MAPPING = {
            "pending": {"step": 0, "progress": 0, "status": "in_progress"},
            "payment_received": {"step": 0, "progress": 5, "status": "in_progress"},
            "provisioning_vps": {"step": 1, "progress": 15, "status": "in_progress"},
            "waiting_for_vps": {"step": 1, "progress": 25, "status": "in_progress"},
            "configuring_dns": {"step": 2, "progress": 40, "status": "in_progress"},
            "deploying_wopr": {"step": 3, "progress": 50, "status": "in_progress"},
            "generating_docs": {"step": 4, "progress": 85, "status": "in_progress"},
            "sending_welcome": {"step": 4, "progress": 90, "status": "in_progress"},
            "completed": {"step": 5, "progress": 100, "status": "complete"},
            "failed": {"step": -1, "progress": 0, "status": "failed"},
        }

        mapping = STATE_MAPPING.get(state, {"step": 0, "progress": 0, "status": "in_progress"})

        updates = {
            "state": state,
            "step": mapping["step"],
            "progress": progress if progress is not None else mapping["progress"],
            "status": mapping["status"],
        }

        if message:
            updates["message"] = message

        return self.update_job(job_id, **updates)

    def update_module_progress(
        self,
        job_id: str,
        current_module: str,
        modules_completed: int,
        modules_total: int,
    ) -> Optional[Dict[str, Any]]:
        """Update module deployment progress (during deploying_wopr state)."""
        if modules_total > 0:
            # Progress during module deployment: 50% + (completed/total * 30%)
            # So goes from 50% to 80% as modules complete
            base = 50
            module_progress = int((modules_completed / modules_total) * 30)
            progress = base + module_progress
        else:
            progress = 50

        return self.update_job(
            job_id,
            current_module=current_module,
            modules_completed=modules_completed,
            modules_total=modules_total,
            progress=progress,
            message=f"Installing {current_module}... ({modules_completed}/{modules_total})",
        )

    def complete_job(
        self,
        job_id: str,
        beacon_name: str,
        instance_ip: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Mark job as successfully completed."""
        return self.update_job(
            job_id,
            state="completed",
            status="complete",
            step=5,
            progress=100,
            message="Your beacon is ready!",
            beacon_url=f"https://{beacon_name}.wopr.systems",
            dashboard_url=f"https://{beacon_name}.wopr.systems/dashboard",
            instance_ip=instance_ip,
        )

    def fail_job(self, job_id: str, error_message: str) -> Optional[Dict[str, Any]]:
        """Mark job as failed."""
        return self.update_job(
            job_id,
            state="failed",
            status="failed",
            step=-1,
            message=f"Provisioning failed: {error_message}",
            error_message=error_message,
        )

    def list_jobs(self, limit: int = 100) -> list:
        """List recent jobs."""
        with self._lock:
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
            return jobs[:limit]


# Global singleton instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get the global job store instance."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
