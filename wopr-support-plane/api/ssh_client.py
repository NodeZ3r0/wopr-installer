"""SSH client wrapper for executing commands on beacons via Nebula mesh."""

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SSHResult:
    stdout: str
    stderr: str
    exit_code: int


async def execute_on_beacon(
    beacon_ip: str,
    certificate_pem: str,
    private_key_pem: str,
    command: str,
    username: str = "wopr-diag",
    timeout: int = 30,
) -> SSHResult:
    """SSH to a beacon using a short-lived certificate and execute a command.

    The certificate and key are written to a temp directory for the duration
    of the command, then immediately cleaned up.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "key"
        cert_path = Path(tmpdir) / "key-cert.pub"

        key_path.write_text(private_key_pem)
        key_path.chmod(0o600)
        cert_path.write_text(certificate_pem)
        cert_path.chmod(0o644)

        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", f"CertificateFile={cert_path}",
            "-i", str(key_path),
            "-l", username,
            beacon_ip,
            command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return SSHResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            logger.error("SSH command timed out after %ds: %s@%s", timeout, username, beacon_ip)
            if proc:
                proc.kill()
            return SSHResult(stdout="", stderr="Command timed out", exit_code=124)
        except Exception as e:
            logger.error("SSH command failed: %s@%s: %s", username, beacon_ip, e)
            return SSHResult(stdout="", stderr=str(e), exit_code=1)
