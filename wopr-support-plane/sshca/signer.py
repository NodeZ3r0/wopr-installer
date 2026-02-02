"""SSH certificate signing using ssh-keygen."""

import asyncio
import logging
import secrets
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def generate_keypair(tmpdir: str) -> tuple[str, str]:
    """Generate an ephemeral Ed25519 keypair for the session."""
    key_path = Path(tmpdir) / "session_key"
    proc = await asyncio.create_subprocess_exec(
        "ssh-keygen", "-t", "ed25519", "-f", str(key_path),
        "-N", "", "-q", "-C", "wopr-support-session",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("Failed to generate SSH keypair")

    private_key = key_path.read_text()
    public_key = Path(f"{key_path}.pub").read_text()
    return private_key, public_key


async def sign_user_key(
    ca_key_path: str,
    user_pubkey: str,
    identity: str,
    principals: list[str],
    validity_seconds: int,
    serial: int | None = None,
    force_command: str | None = None,
    extensions: list[str] | None = None,
) -> tuple[str, int]:
    """Sign an SSH public key with the CA and return (certificate, serial).

    Uses ssh-keygen -s for battle-tested certificate generation.
    Key material exists only in a tmpdir and is cleaned up immediately.
    """
    if serial is None:
        serial = secrets.randbelow(2**63)

    with tempfile.TemporaryDirectory() as tmpdir:
        pubkey_path = Path(tmpdir) / "user_key.pub"
        pubkey_path.write_text(user_pubkey)

        cmd = [
            "ssh-keygen",
            "-s", ca_key_path,
            "-I", identity,
            "-n", ",".join(principals),
            "-V", f"+{validity_seconds}s",
            "-z", str(serial),
        ]

        # Add certificate options
        if force_command:
            cmd.extend(["-O", f"force-command={force_command}"])

        # Default security restrictions
        cmd.extend(["-O", "no-agent-forwarding"])
        cmd.extend(["-O", "no-port-forwarding"])
        cmd.extend(["-O", "no-x11-forwarding"])

        if extensions:
            for ext in extensions:
                cmd.extend(["-O", ext])

        cmd.append(str(pubkey_path))

        logger.info(
            "Signing certificate: identity=%s principals=%s validity=%ds serial=%d",
            identity, principals, validity_seconds, serial,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("ssh-keygen signing failed: %s", stderr.decode())
            raise RuntimeError(f"Certificate signing failed: {stderr.decode()}")

        # ssh-keygen creates the cert at user_key-cert.pub
        cert_path = Path(tmpdir) / "user_key-cert.pub"
        if not cert_path.exists():
            raise RuntimeError("Certificate file not created by ssh-keygen")

        certificate = cert_path.read_text().strip()
        logger.info("Certificate signed: serial=%d", serial)
        return certificate, serial
