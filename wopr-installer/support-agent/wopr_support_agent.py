#!/usr/bin/env python3
"""
WOPR Support Agent
==================

Lightweight systemd service that runs on the HOST (not container).
Monitors journald for errors, performs local pattern matching,
and executes remediation actions or escalates to Support Brain.

3-Tier Escalation:
- Tier 1: AUTO_FIX - Execute immediately (restart, clear, reload)
- Tier 2: SUGGEST - Send to brain, needs DEFCON ONE approval
- Tier 3: ESCALATE - Create support ticket

Memory target: <50MB RAM
"""

import asyncio
import json
import hashlib
import hmac
import logging
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from logging.handlers import RotatingFileHandler

import aiohttp
import aiofiles

# Import configuration
from config import (
    BRAIN_API_URL,
    BRAIN_API_KEY,
    BEACON_ID,
    HEALTH_BEACON_INTERVAL,
    QUEUE_RETRY_INTERVAL,
    JOURNAL_POLL_TIMEOUT,
    COMMAND_POLL_INTERVAL,
    MANAGED_SERVICES,
    TIER1_PATTERNS,
    TIER2_PATTERNS,
    TIER3_PATTERNS,
    QUEUE_FILE,
    QUEUE_MAX_SIZE,
    ALLOWED_REMOTE_COMMANDS,
    BLOCKED_COMMANDS,
    LOG_LEVEL,
    LOG_FILE,
    LOG_MAX_SIZE,
    LOG_BACKUP_COUNT,
)

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging with rotation"""
    logger = logging.getLogger("wopr-support-agent")
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Ensure log directory exists
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(file_handler)

    # Console handler for systemd journal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(message)s"
    ))
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Issue:
    """Represents a detected issue"""
    id: str
    timestamp: str
    tier: int
    pattern_name: str
    log_message: str
    suggested_action: Optional[str] = None
    action_taken: Optional[str] = None
    resolved: bool = False
    escalated: bool = False
    metadata: Dict = field(default_factory=dict)

@dataclass
class QueuedItem:
    """Item queued for brain when unreachable"""
    id: str
    timestamp: str
    item_type: str  # issue, health_beacon, action_result
    data: Dict
    retry_count: int = 0
    max_retries: int = 10

@dataclass
class HealthStatus:
    """Current health status for beacon"""
    beacon_id: str
    timestamp: str
    uptime_seconds: float
    memory_mb: float
    cpu_percent: float
    issues_processed: int
    issues_resolved: int
    queue_size: int
    services_status: Dict[str, str]

# ============================================================================
# PATTERN MATCHER
# ============================================================================

class PatternMatcher:
    """Fast pattern matching for log lines"""

    def __init__(self):
        self.tier1_compiled = [
            (p, [re.compile(pat, re.IGNORECASE) for pat in p.patterns])
            for p in TIER1_PATTERNS
        ]
        self.tier2_compiled = [
            (p, [re.compile(pat, re.IGNORECASE) for pat in p.patterns])
            for p in TIER2_PATTERNS
        ]
        self.tier3_compiled = [
            (p, [re.compile(pat, re.IGNORECASE) for pat in p.patterns])
            for p in TIER3_PATTERNS
        ]

        # Track cooldowns to avoid duplicate fixes
        self.cooldowns: Dict[str, float] = {}

    def match(self, log_line: str) -> Optional[Tuple[int, Any, re.Match]]:
        """
        Match log line against all patterns.
        Returns (tier, pattern, match) or None
        """
        # Check Tier 1 first (auto-fix)
        for pattern, compiled_list in self.tier1_compiled:
            for regex in compiled_list:
                match = regex.search(log_line)
                if match:
                    # Check cooldown
                    cooldown_key = f"{pattern.name}"
                    if cooldown_key in self.cooldowns:
                        if time.time() < self.cooldowns[cooldown_key]:
                            logger.debug(f"Pattern {pattern.name} in cooldown")
                            return None
                    return (1, pattern, match)

        # Check Tier 2 (suggest)
        for pattern, compiled_list in self.tier2_compiled:
            for regex in compiled_list:
                match = regex.search(log_line)
                if match:
                    return (2, pattern, match)

        # Check Tier 3 (escalate)
        for pattern, compiled_list in self.tier3_compiled:
            for regex in compiled_list:
                match = regex.search(log_line)
                if match:
                    return (3, pattern, match)

        return None

    def set_cooldown(self, pattern_name: str, seconds: int):
        """Set cooldown for a pattern"""
        self.cooldowns[pattern_name] = time.time() + seconds

# ============================================================================
# LOCAL REMEDIATION ACTIONS
# ============================================================================

class LocalRemediation:
    """Execute local remediation actions"""

    @staticmethod
    async def restart_service(service: str) -> Tuple[bool, str]:
        """Restart a systemd service"""
        if service not in MANAGED_SERVICES:
            # Try to extract from wopr-* pattern
            if not service.startswith("wopr-"):
                return False, f"Service {service} not in managed list"

        logger.info(f"Restarting service: {service}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "restart", service,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return True, f"Service {service} restarted successfully"
            else:
                return False, f"Failed to restart {service}: {stderr.decode()}"
        except Exception as e:
            return False, f"Error restarting {service}: {str(e)}"

    @staticmethod
    async def restart_container(container: str) -> Tuple[bool, str]:
        """Restart a Docker container"""
        logger.info(f"Restarting container: {container}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "restart", container,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return True, f"Container {container} restarted"
            else:
                return False, f"Failed to restart container: {stderr.decode()}"
        except Exception as e:
            return False, f"Error restarting container: {str(e)}"

    @staticmethod
    async def clear_tmp() -> Tuple[bool, str]:
        """Clear temporary files older than 1 day"""
        logger.info("Clearing old tmp files")
        try:
            proc = await asyncio.create_subprocess_exec(
                "find", "/tmp", "-type", "f", "-mtime", "+1", "-delete",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return True, "Cleared tmp files older than 1 day"
        except Exception as e:
            return False, f"Error clearing tmp: {str(e)}"

    @staticmethod
    async def clear_logs() -> Tuple[bool, str]:
        """Clear old journal logs"""
        logger.info("Clearing old journal logs")
        try:
            proc = await asyncio.create_subprocess_exec(
                "journalctl", "--vacuum-time=3d",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return True, f"Cleared old journal logs: {stdout.decode()}"
        except Exception as e:
            return False, f"Error clearing logs: {str(e)}"

    @staticmethod
    async def reload_caddy() -> Tuple[bool, str]:
        """Reload Caddy configuration"""
        logger.info("Reloading Caddy configuration")
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "reload", "caddy",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return True, "Caddy configuration reloaded"
            else:
                return False, f"Failed to reload Caddy: {stderr.decode()}"
        except Exception as e:
            return False, f"Error reloading Caddy: {str(e)}"

    @staticmethod
    async def dns_flush() -> Tuple[bool, str]:
        """Flush DNS cache"""
        logger.info("Flushing DNS cache")
        try:
            # Try systemd-resolved first
            proc = await asyncio.create_subprocess_exec(
                "resolvectl", "flush-caches",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return True, "DNS cache flushed via resolvectl"

            # Fallback to systemd-resolve
            proc = await asyncio.create_subprocess_exec(
                "systemd-resolve", "--flush-caches",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return True, "DNS cache flushed"
        except Exception as e:
            return False, f"Error flushing DNS: {str(e)}"

    @staticmethod
    async def fix_socket_permissions() -> Tuple[bool, str]:
        """Fix common socket permission issues"""
        logger.info("Fixing socket permissions")
        try:
            # Common socket paths
            sockets = [
                "/var/run/docker.sock",
                "/var/run/redis/redis.sock",
                "/var/run/postgresql/.s.PGSQL.5432",
            ]
            fixed = []
            for sock in sockets:
                if os.path.exists(sock):
                    os.chmod(sock, 0o660)
                    fixed.append(sock)

            if fixed:
                return True, f"Fixed permissions for: {', '.join(fixed)}"
            return True, "No sockets needed fixing"
        except Exception as e:
            return False, f"Error fixing socket permissions: {str(e)}"

    @staticmethod
    async def get_logs(service: str, lines: int = 100) -> Tuple[bool, str]:
        """Get recent logs for a service"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "journalctl", "-u", service, "-n", str(lines), "--no-pager",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return True, stdout.decode()
        except Exception as e:
            return False, f"Error getting logs: {str(e)}"

    @staticmethod
    async def get_status(service: str) -> Tuple[bool, str]:
        """Get service status"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "status", service, "--no-pager",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return True, stdout.decode()
        except Exception as e:
            return False, f"Error getting status: {str(e)}"

    @staticmethod
    async def run_diagnostic() -> Tuple[bool, str]:
        """Run basic system diagnostics"""
        results = []

        # Memory
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
            results.append(f"=== Memory ===\n{meminfo[:500]}")
        except Exception as e:
            results.append(f"Memory check failed: {e}")

        # Disk
        try:
            proc = await asyncio.create_subprocess_exec(
                "df", "-h",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            results.append(f"=== Disk ===\n{stdout.decode()}")
        except Exception as e:
            results.append(f"Disk check failed: {e}")

        # Load
        try:
            with open("/proc/loadavg", "r") as f:
                load = f.read()
            results.append(f"=== Load ===\n{load}")
        except Exception as e:
            results.append(f"Load check failed: {e}")

        return True, "\n".join(results)

    async def execute(self, action: str, params: Dict = None) -> Tuple[bool, str]:
        """Execute a remediation action"""
        params = params or {}

        actions = {
            "restart_service": self.restart_service,
            "restart_container": self.restart_container,
            "clear_tmp": self.clear_tmp,
            "clear_logs": self.clear_logs,
            "reload_caddy": self.reload_caddy,
            "dns_flush": self.dns_flush,
            "fix_socket_permissions": self.fix_socket_permissions,
            "get_logs": self.get_logs,
            "get_status": self.get_status,
            "run_diagnostic": self.run_diagnostic,
        }

        if action not in actions:
            return False, f"Unknown action: {action}"

        func = actions[action]

        # Handle different parameter signatures
        if action == "restart_service":
            service = params.get("service", "")
            return await func(service)
        elif action == "restart_container":
            container = params.get("container", "")
            return await func(container)
        elif action == "get_logs":
            service = params.get("service", "")
            lines = params.get("lines", 100)
            return await func(service, lines)
        elif action == "get_status":
            service = params.get("service", "")
            return await func(service)
        else:
            return await func()

# ============================================================================
# QUEUE MANAGER
# ============================================================================

class QueueManager:
    """Manages the local queue for when brain is unreachable"""

    def __init__(self):
        self.queue: deque[QueuedItem] = deque(maxlen=QUEUE_MAX_SIZE)
        self.queue_file = Path(QUEUE_FILE)
        self._ensure_queue_dir()
        self._load_queue()

    def _ensure_queue_dir(self):
        """Ensure queue directory exists"""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_queue(self):
        """Load queue from disk"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        self.queue.append(QueuedItem(**item))
                logger.info(f"Loaded {len(self.queue)} items from queue")
            except Exception as e:
                logger.error(f"Error loading queue: {e}")

    async def save_queue(self):
        """Save queue to disk"""
        try:
            async with aiofiles.open(self.queue_file, "w") as f:
                data = [asdict(item) for item in self.queue]
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving queue: {e}")

    def add(self, item_type: str, data: Dict):
        """Add item to queue"""
        item = QueuedItem(
            id=hashlib.md5(f"{time.time()}{item_type}".encode()).hexdigest()[:12],
            timestamp=datetime.utcnow().isoformat(),
            item_type=item_type,
            data=data,
        )
        self.queue.append(item)
        logger.debug(f"Queued {item_type}: {item.id}")

    def get_all(self) -> List[QueuedItem]:
        """Get all queued items"""
        return list(self.queue)

    def remove(self, item_id: str):
        """Remove item from queue"""
        self.queue = deque(
            [i for i in self.queue if i.id != item_id],
            maxlen=QUEUE_MAX_SIZE,
        )

    def size(self) -> int:
        """Get queue size"""
        return len(self.queue)

# ============================================================================
# BRAIN CLIENT
# ============================================================================

class BrainClient:
    """Client for communicating with Support Brain"""

    def __init__(self):
        self.base_url = BRAIN_API_URL
        self.api_key = BRAIN_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected = False

    async def start(self):
        """Start the client session"""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Beacon-ID": BEACON_ID,
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=30),
        )

    async def stop(self):
        """Stop the client session"""
        if self.session:
            await self.session.close()

    def _verify_signature(self, data: bytes, signature: str) -> bool:
        """Verify HMAC signature from brain"""
        if not self.api_key:
            return True  # Skip verification if no key configured

        expected = hmac.new(
            self.api_key.encode(),
            data,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def send_health_beacon(self, status: HealthStatus) -> bool:
        """Send health beacon to brain"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/support/beacon",
                json=asdict(status),
            ) as resp:
                if resp.status == 200:
                    self.connected = True
                    return True
                else:
                    logger.warning(f"Health beacon failed: {resp.status}")
                    self.connected = False
                    return False
        except Exception as e:
            logger.warning(f"Health beacon error: {e}")
            self.connected = False
            return False

    async def send_issue(self, issue: Issue) -> bool:
        """Send issue to brain"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/support/issues",
                json=asdict(issue),
            ) as resp:
                if resp.status in (200, 201):
                    return True
                else:
                    logger.warning(f"Send issue failed: {resp.status}")
                    return False
        except Exception as e:
            logger.warning(f"Send issue error: {e}")
            return False

    async def poll_commands(self) -> List[Dict]:
        """Poll for commands from brain"""
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/support/commands/{BEACON_ID}",
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    signature = resp.headers.get("X-Signature", "")

                    # Verify signature
                    if self.api_key and not self._verify_signature(
                        json.dumps(data).encode(), signature
                    ):
                        logger.error("Invalid command signature!")
                        return []

                    return data.get("commands", [])
                return []
        except Exception as e:
            logger.debug(f"Poll commands error: {e}")
            return []

    async def send_command_result(self, command_id: str, success: bool, result: str):
        """Send command execution result to brain"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/support/commands/{command_id}/result",
                json={
                    "beacon_id": BEACON_ID,
                    "success": success,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Send result error: {e}")
            return False

# ============================================================================
# JOURNAL MONITOR
# ============================================================================

class JournalMonitor:
    """Monitor journald for errors"""

    def __init__(self, callback):
        self.callback = callback
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False

    async def start(self):
        """Start monitoring journald"""
        self.running = True

        # Start journalctl process
        self.process = await asyncio.create_subprocess_exec(
            "journalctl",
            "-f",  # Follow
            "-p", "err",  # Priority: error and above
            "-o", "json",  # JSON output
            "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        logger.info("Started journal monitor")

        # Read lines
        while self.running:
            try:
                line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=JOURNAL_POLL_TIMEOUT,
                )

                if line:
                    await self._process_line(line.decode().strip())
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Journal monitor error: {e}")
                await asyncio.sleep(1)

    async def _process_line(self, line: str):
        """Process a journal line"""
        try:
            entry = json.loads(line)
            message = entry.get("MESSAGE", "")
            unit = entry.get("_SYSTEMD_UNIT", "")

            if message:
                await self.callback(message, unit, entry)
        except json.JSONDecodeError:
            # Plain text line
            if line:
                await self.callback(line, "", {})

    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.process:
            self.process.terminate()
            await self.process.wait()

# ============================================================================
# MAIN AGENT
# ============================================================================

class WOPRSupportAgent:
    """Main support agent orchestrator"""

    def __init__(self):
        self.start_time = time.time()
        self.pattern_matcher = PatternMatcher()
        self.remediation = LocalRemediation()
        self.queue = QueueManager()
        self.brain = BrainClient()
        self.journal: Optional[JournalMonitor] = None

        # Statistics
        self.issues_processed = 0
        self.issues_resolved = 0

        # Running state
        self.running = False

    async def start(self):
        """Start the agent"""
        logger.info("=" * 60)
        logger.info("WOPR Support Agent Starting")
        logger.info(f"Beacon ID: {BEACON_ID}")
        logger.info(f"Brain URL: {BRAIN_API_URL}")
        logger.info("=" * 60)

        self.running = True

        # Start brain client
        await self.brain.start()

        # Start journal monitor
        self.journal = JournalMonitor(self._on_journal_entry)

        # Start background tasks
        await asyncio.gather(
            self.journal.start(),
            self._health_beacon_loop(),
            self._queue_processor_loop(),
            self._command_poll_loop(),
        )

    async def stop(self):
        """Stop the agent"""
        logger.info("Stopping WOPR Support Agent...")
        self.running = False

        if self.journal:
            await self.journal.stop()

        await self.queue.save_queue()
        await self.brain.stop()

        logger.info("Agent stopped")

    async def _on_journal_entry(self, message: str, unit: str, entry: Dict):
        """Handle a journal entry"""
        # Match against patterns
        result = self.pattern_matcher.match(message)

        if not result:
            return

        tier, pattern, match = result
        self.issues_processed += 1

        # Create issue
        issue = Issue(
            id=hashlib.md5(f"{time.time()}{message[:50]}".encode()).hexdigest()[:12],
            timestamp=datetime.utcnow().isoformat(),
            tier=tier,
            pattern_name=pattern.name,
            log_message=message[:500],  # Truncate long messages
            metadata={
                "unit": unit,
                "match_groups": match.groups() if match.groups() else [],
            },
        )

        logger.info(f"Detected Tier {tier} issue: {pattern.name}")

        if tier == 1:
            await self._handle_tier1(issue, pattern, match)
        elif tier == 2:
            await self._handle_tier2(issue, pattern)
        else:
            await self._handle_tier3(issue, pattern)

    async def _handle_tier1(self, issue: Issue, pattern, match):
        """Handle Tier 1: Auto-fix"""
        logger.info(f"Tier 1 AUTO-FIX: {pattern.action}")

        # Build params
        params = dict(pattern.params)

        # Extract service name from log if needed
        if params.get("extract_service"):
            # Try to extract service name from match or message
            groups = match.groups()
            if groups:
                service = groups[0]
                if service in MANAGED_SERVICES or service.startswith("wopr-"):
                    params["service"] = service

        if params.get("extract_container"):
            # Try to extract container name
            groups = match.groups()
            if groups:
                params["container"] = groups[0]

        # Execute remediation
        success, result = await self.remediation.execute(pattern.action, params)

        issue.action_taken = pattern.action
        issue.resolved = success

        if success:
            self.issues_resolved += 1
            logger.info(f"Tier 1 fix successful: {result}")
            # Set cooldown
            self.pattern_matcher.set_cooldown(pattern.name, pattern.cooldown)
        else:
            logger.warning(f"Tier 1 fix failed: {result}")
            # Escalate to Tier 2
            issue.tier = 2
            await self._send_to_brain(issue)

        # Always report to brain
        await self._send_to_brain(issue)

    async def _handle_tier2(self, issue: Issue, pattern):
        """Handle Tier 2: Suggest (needs approval)"""
        logger.info(f"Tier 2 SUGGEST: {pattern.suggested_action}")

        issue.suggested_action = pattern.suggested_action
        issue.metadata["description"] = pattern.description
        issue.metadata["risk_level"] = pattern.risk_level

        await self._send_to_brain(issue)

    async def _handle_tier3(self, issue: Issue, pattern):
        """Handle Tier 3: Escalate (create ticket)"""
        logger.warning(f"Tier 3 ESCALATE: {pattern.severity} - {pattern.description}")

        issue.escalated = True
        issue.metadata["severity"] = pattern.severity
        issue.metadata["description"] = pattern.description

        await self._send_to_brain(issue)

    async def _send_to_brain(self, issue: Issue):
        """Send issue to brain, queue if unreachable"""
        if await self.brain.send_issue(issue):
            logger.debug(f"Issue {issue.id} sent to brain")
        else:
            logger.warning(f"Brain unreachable, queuing issue {issue.id}")
            self.queue.add("issue", asdict(issue))

    async def _health_beacon_loop(self):
        """Send health beacons periodically"""
        while self.running:
            try:
                status = await self._collect_health_status()

                if await self.brain.send_health_beacon(status):
                    logger.debug("Health beacon sent")
                else:
                    logger.warning("Health beacon failed, brain may be unreachable")
                    self.queue.add("health_beacon", asdict(status))
            except Exception as e:
                logger.error(f"Health beacon error: {e}")

            await asyncio.sleep(HEALTH_BEACON_INTERVAL)

    async def _collect_health_status(self) -> HealthStatus:
        """Collect current health status"""
        # Get memory usage
        try:
            with open("/proc/self/status", "r") as f:
                status = f.read()
            vm_rss = 0
            for line in status.split("\n"):
                if line.startswith("VmRSS:"):
                    vm_rss = int(line.split()[1]) / 1024  # KB to MB
                    break
        except:
            vm_rss = 0

        # Get CPU usage (simple approximation)
        try:
            with open("/proc/loadavg", "r") as f:
                load = float(f.read().split()[0])
            cpu_percent = min(load * 100 / os.cpu_count(), 100)
        except:
            cpu_percent = 0

        # Get service statuses
        services_status = {}
        for service in MANAGED_SERVICES:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "systemctl", "is-active", service,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                services_status[service] = stdout.decode().strip()
            except:
                services_status[service] = "unknown"

        return HealthStatus(
            beacon_id=BEACON_ID,
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=time.time() - self.start_time,
            memory_mb=vm_rss,
            cpu_percent=cpu_percent,
            issues_processed=self.issues_processed,
            issues_resolved=self.issues_resolved,
            queue_size=self.queue.size(),
            services_status=services_status,
        )

    async def _queue_processor_loop(self):
        """Process queued items when brain becomes available"""
        while self.running:
            try:
                if self.queue.size() > 0 and self.brain.connected:
                    logger.info(f"Processing {self.queue.size()} queued items")

                    for item in self.queue.get_all():
                        success = False

                        if item.item_type == "issue":
                            issue = Issue(**item.data)
                            success = await self.brain.send_issue(issue)
                        elif item.item_type == "health_beacon":
                            status = HealthStatus(**item.data)
                            success = await self.brain.send_health_beacon(status)

                        if success:
                            self.queue.remove(item.id)
                            logger.debug(f"Queued item {item.id} sent")
                        else:
                            item.retry_count += 1
                            if item.retry_count >= item.max_retries:
                                self.queue.remove(item.id)
                                logger.warning(f"Queued item {item.id} exceeded max retries")

                    await self.queue.save_queue()
            except Exception as e:
                logger.error(f"Queue processor error: {e}")

            await asyncio.sleep(QUEUE_RETRY_INTERVAL)

    async def _command_poll_loop(self):
        """Poll for commands from brain"""
        while self.running:
            try:
                commands = await self.brain.poll_commands()

                for cmd in commands:
                    await self._execute_command(cmd)
            except Exception as e:
                logger.error(f"Command poll error: {e}")

            await asyncio.sleep(COMMAND_POLL_INTERVAL)

    async def _execute_command(self, cmd: Dict):
        """Execute a command from brain"""
        command_id = cmd.get("id", "unknown")
        action = cmd.get("action", "")
        params = cmd.get("params", {})

        logger.info(f"Received command from brain: {action}")

        # Security checks
        if action not in ALLOWED_REMOTE_COMMANDS:
            logger.warning(f"Blocked unauthorized command: {action}")
            await self.brain.send_command_result(
                command_id, False, f"Command not allowed: {action}"
            )
            return

        # Check for blocked patterns in params
        params_str = json.dumps(params)
        for blocked in BLOCKED_COMMANDS:
            if blocked in params_str:
                logger.error(f"Blocked dangerous command pattern: {blocked}")
                await self.brain.send_command_result(
                    command_id, False, "Dangerous command pattern blocked"
                )
                return

        # Execute
        success, result = await self.remediation.execute(action, params)

        logger.info(f"Command {action} result: {'success' if success else 'failed'}")

        await self.brain.send_command_result(command_id, success, result)

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

agent: Optional[WOPRSupportAgent] = None

def handle_signal(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    if agent:
        asyncio.create_task(agent.stop())

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main entry point"""
    global agent

    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Create and start agent
    agent = WOPRSupportAgent()

    try:
        await agent.start()
    except KeyboardInterrupt:
        pass
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
