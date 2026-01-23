"""
WOPR BYO (Bring Your Own) VPS Provider Adapter
==============================================

SSH-based adapter for user-provided VPS instances.

This enables users to:
- Use any VPS provider not directly supported
- Use existing servers
- Use on-premise hardware
- Maintain full control over provisioning

The BYO adapter doesn't provision servers - it manages
existing servers via SSH.
"""

from typing import List, Optional, Dict
from datetime import datetime
import subprocess
import json
import os

from .base import (
    WOPRProviderInterface,
    ResourceTier,
    Plan,
    Region,
    Instance,
    InstanceStatus,
    ProvisionConfig,
    ProviderError,
    ProviderAuthError,
)
from .registry import register_provider


@register_provider
class BYOProvider(WOPRProviderInterface):
    """
    Bring Your Own VPS provider adapter.

    Instead of provisioning via API, this adapter:
    - Connects to user-provided servers via SSH
    - Detects server resources
    - Manages WOPR installation on existing infrastructure

    This is the Phase 1 implementation and the fallback
    for any provider not directly supported.
    """

    PROVIDER_ID = "byo"
    PROVIDER_NAME = "Bring Your Own VPS"
    PROVIDER_WEBSITE = "https://wopr.systems/docs/byo"
    SUPPORTS_IPV6 = True
    SUPPORTS_CLOUD_INIT = False  # Server already exists
    SUPPORTS_SSH_KEYS = True

    # Registry of BYO instances (persisted to disk)
    REGISTRY_FILE = "/var/lib/wopr/byo_instances.json"

    def __init__(self, api_token: str = "", **kwargs):
        """
        Initialize BYO provider.

        Args:
            api_token: Not used for BYO, but required by interface
            ssh_key_path: Path to SSH private key (default: ~/.ssh/id_rsa)
            ssh_user: Default SSH user (default: root)
        """
        self.ssh_key_path = kwargs.get("ssh_key_path", os.path.expanduser("~/.ssh/id_rsa"))
        self.ssh_user = kwargs.get("ssh_user", "root")
        self.api_token = api_token  # Not used but required
        self._instances: Dict[str, Dict] = {}
        self._load_registry()

    def _validate_credentials(self) -> None:
        """Validate SSH key exists."""
        if not os.path.exists(self.ssh_key_path):
            raise ProviderAuthError(
                "byo",
                f"SSH key not found: {self.ssh_key_path}"
            )

    def _load_registry(self) -> None:
        """Load instance registry from disk."""
        if os.path.exists(self.REGISTRY_FILE):
            try:
                with open(self.REGISTRY_FILE, "r") as f:
                    self._instances = json.load(f)
            except Exception:
                self._instances = {}

    def _save_registry(self) -> None:
        """Save instance registry to disk."""
        os.makedirs(os.path.dirname(self.REGISTRY_FILE), exist_ok=True)
        with open(self.REGISTRY_FILE, "w") as f:
            json.dump(self._instances, f, indent=2, default=str)

    def _ssh_command(self, host: str, command: str, user: str = None) -> tuple:
        """
        Execute SSH command and return (success, output).
        """
        user = user or self.ssh_user
        ssh_cmd = [
            "ssh",
            "-i", self.ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            f"{user}@{host}",
            command
        ]

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as e:
            return False, str(e)

    def _detect_resources(self, host: str) -> Dict:
        """Detect server resources via SSH."""
        resources = {
            "cpu": 0,
            "ram_gb": 0,
            "disk_gb": 0,
            "os": "unknown",
            "arch": "unknown",
        }

        # Detect CPU
        success, output = self._ssh_command(host, "nproc")
        if success:
            resources["cpu"] = int(output)

        # Detect RAM
        success, output = self._ssh_command(host, "grep MemTotal /proc/meminfo | awk '{print $2}'")
        if success:
            resources["ram_gb"] = int(output) // 1024 // 1024

        # Detect disk
        success, output = self._ssh_command(host, "df -BG / | tail -1 | awk '{print $4}' | tr -d 'G'")
        if success:
            resources["disk_gb"] = int(output)

        # Detect OS
        success, output = self._ssh_command(host, "cat /etc/os-release | grep '^ID=' | cut -d= -f2")
        if success:
            resources["os"] = output.strip('"')

        # Detect arch
        success, output = self._ssh_command(host, "uname -m")
        if success:
            arch = output
            if arch == "x86_64":
                arch = "amd64"
            elif arch == "aarch64":
                arch = "arm64"
            resources["arch"] = arch

        return resources

    # =========================================
    # PLAN MANAGEMENT (N/A for BYO)
    # =========================================

    def list_plans(self, tier: Optional[ResourceTier] = None) -> List[Plan]:
        """BYO doesn't have plans - returns empty list."""
        return []

    def get_cheapest_plan(self, tier: ResourceTier) -> Optional[Plan]:
        """BYO doesn't have plans."""
        return None

    # =========================================
    # REGION MANAGEMENT (N/A for BYO)
    # =========================================

    def list_regions(self) -> List[Region]:
        """BYO doesn't have regions - returns user-defined."""
        return [
            Region(id="byo", name="User Provided", country="XX", available=True)
        ]

    # =========================================
    # INSTANCE REGISTRATION
    # =========================================

    def register_instance(
        self,
        name: str,
        ip_address: str,
        ssh_user: str = None,
        ssh_port: int = 22,
        wopr_instance_id: str = None,
    ) -> Instance:
        """
        Register an existing server as a BYO instance.

        Args:
            name: Friendly name for the instance
            ip_address: Server IP address
            ssh_user: SSH username (default: root)
            ssh_port: SSH port (default: 22)
            wopr_instance_id: Optional WOPR instance ID

        Returns:
            Instance object
        """
        ssh_user = ssh_user or self.ssh_user

        # Test SSH connection
        success, _ = self._ssh_command(ip_address, "echo ok", user=ssh_user)
        if not success:
            raise ProviderError(
                "byo",
                f"Cannot connect to {ip_address} via SSH. "
                f"Ensure SSH key is authorized for {ssh_user}@{ip_address}"
            )

        # Detect resources
        resources = self._detect_resources(ip_address)

        # Generate instance ID
        import uuid
        instance_id = str(uuid.uuid4())[:8]

        # Create instance record
        instance_data = {
            "id": instance_id,
            "name": name,
            "ip_address": ip_address,
            "ssh_user": ssh_user,
            "ssh_port": ssh_port,
            "resources": resources,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "wopr_instance_id": wopr_instance_id,
        }

        self._instances[instance_id] = instance_data
        self._save_registry()

        return Instance(
            id=instance_id,
            provider=self.PROVIDER_ID,
            name=name,
            status=InstanceStatus.RUNNING,
            region="byo",
            plan=f"{resources['cpu']}vCPU/{resources['ram_gb']}GB/{resources['disk_gb']}GB",
            ip_address=ip_address,
            created_at=datetime.now(),
            wopr_instance_id=wopr_instance_id,
            metadata=instance_data,
        )

    def provision(self, config: ProvisionConfig) -> Instance:
        """
        BYO 'provisioning' registers an existing server.

        The IP address should be provided in config.metadata['ip_address'].
        """
        ip_address = config.metadata.get("ip_address")
        if not ip_address:
            raise ProviderError(
                "byo",
                "BYO provisioning requires 'ip_address' in metadata"
            )

        return self.register_instance(
            name=config.name,
            ip_address=ip_address,
            ssh_user=config.metadata.get("ssh_user", self.ssh_user),
            wopr_instance_id=config.metadata.get("wopr_instance_id"),
        )

    def destroy(self, instance_id: str) -> bool:
        """
        Remove instance from registry.

        Note: This does NOT destroy the actual server - it just
        removes it from WOPR management.
        """
        if instance_id in self._instances:
            del self._instances[instance_id]
            self._save_registry()
            return True
        return False

    # =========================================
    # INSTANCE MANAGEMENT
    # =========================================

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get a registered BYO instance."""
        data = self._instances.get(instance_id)
        if not data:
            return None

        # Check if still reachable
        success, _ = self._ssh_command(data["ip_address"], "echo ok", user=data.get("ssh_user"))
        status = InstanceStatus.RUNNING if success else InstanceStatus.ERROR

        return Instance(
            id=data["id"],
            provider=self.PROVIDER_ID,
            name=data["name"],
            status=status,
            region="byo",
            plan=f"{data['resources']['cpu']}vCPU/{data['resources']['ram_gb']}GB",
            ip_address=data["ip_address"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            wopr_instance_id=data.get("wopr_instance_id"),
            metadata=data,
        )

    def list_instances(self, tags: Optional[List[str]] = None) -> List[Instance]:
        """List all registered BYO instances."""
        instances = []
        for instance_id in self._instances:
            instance = self.get_instance(instance_id)
            if instance:
                instances.append(instance)
        return instances

    def get_status(self, instance_id: str) -> InstanceStatus:
        """Get BYO instance status (via SSH check)."""
        instance = self.get_instance(instance_id)
        return instance.status if instance else InstanceStatus.UNKNOWN

    def start(self, instance_id: str) -> bool:
        """Cannot start BYO servers remotely."""
        raise ProviderError("byo", "BYO servers cannot be started remotely")

    def stop(self, instance_id: str) -> bool:
        """Cannot stop BYO servers remotely (too dangerous)."""
        raise ProviderError("byo", "BYO servers cannot be stopped remotely")

    def reboot(self, instance_id: str) -> bool:
        """Reboot a BYO server via SSH."""
        data = self._instances.get(instance_id)
        if not data:
            return False

        success, _ = self._ssh_command(
            data["ip_address"],
            "sudo reboot",
            user=data.get("ssh_user")
        )
        return success

    # =========================================
    # SSH KEY MANAGEMENT
    # =========================================

    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List local SSH keys."""
        keys = []
        ssh_dir = os.path.expanduser("~/.ssh")

        if os.path.exists(ssh_dir):
            for filename in os.listdir(ssh_dir):
                if filename.endswith(".pub"):
                    key_path = os.path.join(ssh_dir, filename)
                    with open(key_path, "r") as f:
                        content = f.read().strip()
                    keys.append({
                        "id": filename.replace(".pub", ""),
                        "name": filename,
                        "fingerprint": content.split()[1] if len(content.split()) > 1 else "",
                    })

        return keys

    def add_ssh_key(self, name: str, public_key: str) -> str:
        """Cannot add SSH keys via BYO provider."""
        raise ProviderError("byo", "Use ssh-copy-id to add keys to BYO servers")

    def remove_ssh_key(self, key_id: str) -> bool:
        """Cannot remove SSH keys via BYO provider."""
        raise ProviderError("byo", "Manually remove keys from BYO servers")

    # =========================================
    # BYO-SPECIFIC METHODS
    # =========================================

    def deploy_wopr(self, instance_id: str, bundle: str) -> bool:
        """
        Deploy WOPR to a BYO instance.

        Args:
            instance_id: BYO instance ID
            bundle: WOPR bundle to install

        Returns:
            True if deployment started successfully
        """
        data = self._instances.get(instance_id)
        if not data:
            raise ProviderError("byo", f"Instance not found: {instance_id}")

        # Copy installer script
        # This would use scp to copy the installer and then run it
        # Implementation depends on where installer scripts are located

        return True

    def check_wopr_status(self, instance_id: str) -> Dict:
        """Check WOPR installation status on a BYO instance."""
        data = self._instances.get(instance_id)
        if not data:
            return {"installed": False, "error": "Instance not found"}

        success, output = self._ssh_command(
            data["ip_address"],
            "cat /etc/wopr/settings.json 2>/dev/null || echo '{}'",
            user=data.get("ssh_user")
        )

        if success:
            try:
                settings = json.loads(output)
                return {
                    "installed": settings.get("install_complete", False),
                    "bundle": settings.get("bundle"),
                    "domain": settings.get("domain"),
                }
            except json.JSONDecodeError:
                pass

        return {"installed": False}
