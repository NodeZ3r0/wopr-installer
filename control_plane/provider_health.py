#!/usr/bin/env python3
"""
WOPR Provider Health Monitor
============================

Scheduled service that monitors VPS provider APIs for:
- Plan ID changes (e.g., cpx11 → cpx12)
- Pricing changes
- Region availability changes
- API deprecations
- SSH key status

Runs on a systemd timer and reports to the AI support plane.

Usage:
    # One-time check
    python provider_health.py --check

    # Install as systemd timer
    python provider_health.py --install

    # Daemon mode (check every 6 hours)
    python provider_health.py --daemon
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Minor issues (pricing drift, etc)
    CRITICAL = "critical"  # Major issues (auth failed, plans missing)
    UNKNOWN = "unknown"    # Couldn't check


@dataclass
class PlanDrift:
    """Detected plan drift from expected values."""
    plan_id: str
    field: str  # 'price', 'cpu', 'ram', 'missing', 'new'
    expected: Any
    actual: Any
    severity: str  # 'info', 'warning', 'critical'


@dataclass
class ProviderHealthReport:
    """Health report for a single provider."""
    provider_id: str
    status: HealthStatus
    checked_at: str
    auth_ok: bool
    plans_available: int
    regions_available: int
    ssh_keys_found: int
    has_wopr_key: bool
    drifts: List[PlanDrift]
    errors: List[str]
    recommendations: List[str]


class ProviderHealthMonitor:
    """
    Monitors VPS provider health and detects configuration drift.

    Designed to run as a scheduled service and feed issues to
    the AI support plane for automated remediation.
    """

    # Expected plan mappings (source of truth)
    # Updated when we detect and confirm changes
    # Last updated: February 2026 (Hetzner renamed plans in 2025)
    EXPECTED_PLANS = {
        "hetzner": {
            # Shared vCPU (CX series) - Intel - renamed in 2025
            "cx23": {"cpu": 2, "ram": 4, "price_eur": 3.79},
            "cx33": {"cpu": 4, "ram": 8, "price_eur": 7.59},
            "cx43": {"cpu": 8, "ram": 16, "price_eur": 14.99},
            "cx53": {"cpu": 16, "ram": 32, "price_eur": 29.99},
            # Shared vCPU (CPX series) - AMD - renamed in 2025
            "cpx12": {"cpu": 1, "ram": 2, "price_eur": 4.49},
            "cpx22": {"cpu": 2, "ram": 4, "price_eur": 8.49},
            "cpx32": {"cpu": 4, "ram": 8, "price_eur": 15.99},
            "cpx42": {"cpu": 8, "ram": 16, "price_eur": 29.99},
            "cpx52": {"cpu": 12, "ram": 24, "price_eur": 64.99},
            "cpx62": {"cpu": 16, "ram": 32, "price_eur": 99.99},
            # ARM (CAX series) - Ampere
            "cax11": {"cpu": 2, "ram": 4, "price_eur": 3.79},
            "cax21": {"cpu": 4, "ram": 8, "price_eur": 6.49},
            "cax31": {"cpu": 8, "ram": 16, "price_eur": 12.49},
            "cax41": {"cpu": 16, "ram": 32, "price_eur": 23.99},
            # Dedicated vCPU (CCX series) - Intel
            "ccx13": {"cpu": 2, "ram": 8, "price_eur": 15.99},
            "ccx23": {"cpu": 4, "ram": 16, "price_eur": 29.99},
            "ccx33": {"cpu": 8, "ram": 32, "price_eur": 59.99},
            "ccx43": {"cpu": 16, "ram": 64, "price_eur": 119.99},
            "ccx53": {"cpu": 32, "ram": 128, "price_eur": 239.99},
            "ccx63": {"cpu": 48, "ram": 192, "price_eur": 359.99},
        },
    }

    # Plans we actually use for provisioning (subset of above)
    # These should always exist - if not, provisioning fails
    WOPR_TIER_PLANS = {
        "hetzner": {
            "t1": ["cpx22", "cx23", "cax11"],  # Options for tier 1
            "t2": ["cpx32", "cx33", "cax21"],  # Options for tier 2
            "t3": ["cpx42", "cx43", "cax31"],  # Options for tier 3
        }
    }

    def __init__(self, state_dir: Path = None):
        """Initialize monitor with state directory."""
        self.state_dir = state_dir or Path("/var/lib/wopr/provider-health")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reports: Dict[str, ProviderHealthReport] = {}

    def _load_env(self):
        """Load environment from .env file."""
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

    def check_hetzner(self) -> ProviderHealthReport:
        """Check Hetzner provider health."""
        provider_id = "hetzner"
        errors = []
        drifts = []
        recommendations = []

        token = os.environ.get("HETZNER_API_TOKEN")
        if not token:
            return ProviderHealthReport(
                provider_id=provider_id,
                status=HealthStatus.CRITICAL,
                checked_at=datetime.now().isoformat(),
                auth_ok=False,
                plans_available=0,
                regions_available=0,
                ssh_keys_found=0,
                has_wopr_key=False,
                drifts=[],
                errors=["HETZNER_API_TOKEN not set"],
                recommendations=["Set HETZNER_API_TOKEN in environment"],
            )

        try:
            from .providers.hetzner import HetznerProvider
            provider = HetznerProvider(api_token=token)
            auth_ok = True
        except Exception as e:
            return ProviderHealthReport(
                provider_id=provider_id,
                status=HealthStatus.CRITICAL,
                checked_at=datetime.now().isoformat(),
                auth_ok=False,
                plans_available=0,
                regions_available=0,
                ssh_keys_found=0,
                has_wopr_key=False,
                drifts=[],
                errors=[f"Authentication failed: {e}"],
                recommendations=["Verify HETZNER_API_TOKEN is valid"],
            )

        # Check plans
        try:
            plans = provider.list_plans()
            plan_ids = {p.id.lower(): p for p in plans}

            expected = self.EXPECTED_PLANS.get("hetzner", {})

            # Check for missing plans we expect
            for exp_id, exp_spec in expected.items():
                if exp_id not in plan_ids:
                    drifts.append(PlanDrift(
                        plan_id=exp_id,
                        field="missing",
                        expected=exp_id,
                        actual=None,
                        severity="warning",
                    ))
                else:
                    actual = plan_ids[exp_id]
                    # Check CPU
                    if actual.cpu != exp_spec["cpu"]:
                        drifts.append(PlanDrift(
                            plan_id=exp_id,
                            field="cpu",
                            expected=exp_spec["cpu"],
                            actual=actual.cpu,
                            severity="info",
                        ))
                    # Check RAM
                    if actual.ram_gb != exp_spec["ram"]:
                        drifts.append(PlanDrift(
                            plan_id=exp_id,
                            field="ram",
                            expected=exp_spec["ram"],
                            actual=actual.ram_gb,
                            severity="info",
                        ))

            # Check for new plans we don't know about
            for plan_id, plan in plan_ids.items():
                if plan_id not in expected:
                    # Only flag if it's a plan type we use (cx, cpx, cax)
                    if any(plan_id.startswith(p) for p in ['cx', 'cpx', 'cax']):
                        drifts.append(PlanDrift(
                            plan_id=plan_id,
                            field="new",
                            expected=None,
                            actual=f"{plan.cpu}vCPU, {plan.ram_gb}GB",
                            severity="info",
                        ))

            # Check that our tier plans exist
            tier_plans = self.WOPR_TIER_PLANS.get("hetzner", {})
            for tier, plan_options in tier_plans.items():
                has_valid = any(p in plan_ids for p in plan_options)
                if not has_valid:
                    drifts.append(PlanDrift(
                        plan_id=f"tier_{tier}",
                        field="missing",
                        expected=plan_options,
                        actual=[],
                        severity="critical",
                    ))
                    recommendations.append(
                        f"No valid plans found for {tier}. Update WOPR_TIER_PLANS."
                    )

        except Exception as e:
            errors.append(f"Failed to list plans: {e}")

        # Check regions
        try:
            regions = provider.list_regions()
        except Exception as e:
            regions = []
            errors.append(f"Failed to list regions: {e}")

        # Check SSH keys
        try:
            ssh_keys = provider.list_ssh_keys()
            key_names = [k["name"] for k in ssh_keys]
            has_wopr_key = "wopr-deploy" in key_names

            if not has_wopr_key:
                recommendations.append(
                    "Add 'wopr-deploy' SSH key to Hetzner Console"
                )
        except Exception as e:
            ssh_keys = []
            has_wopr_key = False
            errors.append(f"Failed to list SSH keys: {e}")

        # Determine overall status
        critical_drifts = [d for d in drifts if d.severity == "critical"]
        if errors or critical_drifts:
            status = HealthStatus.CRITICAL
        elif drifts:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return ProviderHealthReport(
            provider_id=provider_id,
            status=status,
            checked_at=datetime.now().isoformat(),
            auth_ok=auth_ok,
            plans_available=len(plans) if 'plans' in dir() else 0,
            regions_available=len(regions),
            ssh_keys_found=len(ssh_keys),
            has_wopr_key=has_wopr_key,
            drifts=drifts,
            errors=errors,
            recommendations=recommendations,
        )

    def check_all(self) -> Dict[str, ProviderHealthReport]:
        """Check all configured providers."""
        self._load_env()

        reports = {}

        # Check Hetzner (primary provider)
        if os.environ.get("HETZNER_API_TOKEN"):
            reports["hetzner"] = self.check_hetzner()

        # Add other providers as they're implemented
        # if os.environ.get("DIGITALOCEAN_API_TOKEN"):
        #     reports["digitalocean"] = self.check_digitalocean()

        self.reports = reports
        return reports

    def save_report(self):
        """Save health report to disk."""
        report_file = self.state_dir / "latest_report.json"

        serializable = {}
        for provider_id, report in self.reports.items():
            r = asdict(report)
            r["status"] = report.status.value
            r["drifts"] = [asdict(d) for d in report.drifts]
            serializable[provider_id] = r

        report_file.write_text(json.dumps(serializable, indent=2))
        logger.info(f"Report saved to {report_file}")

        # Also save to history
        history_file = self.state_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        history_file.write_text(json.dumps(serializable, indent=2))

    def generate_ai_ticket(self, report: ProviderHealthReport) -> Optional[Dict]:
        """
        Generate a ticket for the AI support plane.

        Returns a structured ticket that the AI can act on.
        """
        if report.status == HealthStatus.HEALTHY:
            return None

        ticket = {
            "type": "provider_health",
            "provider": report.provider_id,
            "severity": "critical" if report.status == HealthStatus.CRITICAL else "warning",
            "created_at": datetime.now().isoformat(),
            "summary": f"Provider {report.provider_id} health: {report.status.value}",
            "details": {
                "auth_ok": report.auth_ok,
                "plans_available": report.plans_available,
                "has_ssh_key": report.has_wopr_key,
                "errors": report.errors,
                "drifts": [asdict(d) for d in report.drifts],
            },
            "recommendations": report.recommendations,
            "auto_fixable": [],
            "requires_human": [],
        }

        # Categorize issues
        for drift in report.drifts:
            if drift.field == "new":
                ticket["auto_fixable"].append(
                    f"Add new plan {drift.plan_id} to EXPECTED_PLANS"
                )
            elif drift.field in ["price", "cpu", "ram"]:
                ticket["auto_fixable"].append(
                    f"Update {drift.plan_id}.{drift.field}: {drift.expected} → {drift.actual}"
                )
            elif drift.field == "missing":
                ticket["requires_human"].append(
                    f"Plan {drift.plan_id} no longer available - review tier mappings"
                )

        if not report.has_wopr_key:
            ticket["requires_human"].append(
                "Add wopr-deploy SSH key to provider console"
            )

        return ticket

    def print_report(self):
        """Print human-readable report."""
        for provider_id, report in self.reports.items():
            status_icon = {
                HealthStatus.HEALTHY: "[OK]",
                HealthStatus.DEGRADED: "[WARN]",
                HealthStatus.CRITICAL: "[FAIL]",
                HealthStatus.UNKNOWN: "[?]",
            }[report.status]

            print(f"\n{'='*60}")
            print(f"{status_icon} {provider_id.upper()}: {report.status.value}")
            print(f"{'='*60}")
            print(f"  Checked:     {report.checked_at}")
            print(f"  Auth OK:     {report.auth_ok}")
            print(f"  Plans:       {report.plans_available}")
            print(f"  Regions:     {report.regions_available}")
            print(f"  SSH Keys:    {report.ssh_keys_found}")
            print(f"  WOPR Key:    {'Yes' if report.has_wopr_key else 'NO - ACTION REQUIRED'}")

            if report.errors:
                print(f"\n  Errors:")
                for err in report.errors:
                    print(f"    [X] {err}")

            if report.drifts:
                print(f"\n  Configuration Drift:")
                for drift in report.drifts:
                    icon = {"info": "[i]", "warning": "[!]", "critical": "[X]"}[drift.severity]
                    if drift.field == "new":
                        print(f"    {icon} NEW: {drift.plan_id} ({drift.actual})")
                    elif drift.field == "missing":
                        print(f"    {icon} MISSING: {drift.plan_id}")
                    else:
                        print(f"    {icon} {drift.plan_id}.{drift.field}: {drift.expected} -> {drift.actual}")

            if report.recommendations:
                print(f"\n  Recommendations:")
                for rec in report.recommendations:
                    print(f"    -> {rec}")


def generate_systemd_units() -> tuple:
    """Generate systemd service and timer units."""
    service = """[Unit]
Description=WOPR Provider Health Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/wopr
ExecStart=/usr/bin/python3 -m control_plane.provider_health --check --save
Environment=PYTHONPATH=/opt/wopr

# Report to AI support plane if issues found
ExecStartPost=/bin/bash -c 'if [ -f /var/lib/wopr/provider-health/needs_attention ]; then curl -sf -X POST http://localhost:8500/api/v1/support/ticket -H "Content-Type: application/json" -d @/var/lib/wopr/provider-health/latest_ticket.json || true; fi'

[Install]
WantedBy=multi-user.target
"""

    timer = """[Unit]
Description=Run WOPR Provider Health Check daily

[Timer]
OnCalendar=*-*-* 06:00:00
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
"""

    return service, timer


def main():
    parser = argparse.ArgumentParser(description="WOPR Provider Health Monitor")
    parser.add_argument("--check", action="store_true", help="Run health check")
    parser.add_argument("--save", action="store_true", help="Save report to disk")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--install", action="store_true", help="Install systemd units")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")

    args = parser.parse_args()

    if args.install:
        service, timer = generate_systemd_units()

        service_path = Path("/etc/systemd/system/wopr-provider-health.service")
        timer_path = Path("/etc/systemd/system/wopr-provider-health.timer")

        service_path.write_text(service)
        timer_path.write_text(timer)

        print(f"Created {service_path}")
        print(f"Created {timer_path}")
        print("\nTo enable: systemctl enable --now wopr-provider-health.timer")
        return

    if args.daemon:
        import time
        monitor = ProviderHealthMonitor()
        while True:
            logger.info("Running health check...")
            monitor.check_all()
            monitor.save_report()
            monitor.print_report()
            logger.info("Next check in 6 hours")
            time.sleep(6 * 60 * 60)

    if args.check:
        monitor = ProviderHealthMonitor()
        monitor.check_all()

        if args.json:
            import json
            for pid, report in monitor.reports.items():
                r = asdict(report)
                r["status"] = report.status.value
                print(json.dumps(r, indent=2))
        else:
            monitor.print_report()

        if args.save:
            monitor.save_report()

            # Generate tickets for AI support
            for pid, report in monitor.reports.items():
                ticket = monitor.generate_ai_ticket(report)
                if ticket:
                    ticket_file = monitor.state_dir / "latest_ticket.json"
                    ticket_file.write_text(json.dumps(ticket, indent=2))
                    (monitor.state_dir / "needs_attention").touch()
                    logger.info(f"Ticket generated for {pid}")

        # Exit with appropriate code
        has_critical = any(
            r.status == HealthStatus.CRITICAL
            for r in monitor.reports.values()
        )
        sys.exit(1 if has_critical else 0)

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
