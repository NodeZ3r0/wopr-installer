import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from api.database import get_db
from api.log_analyzer import collect_recent_errors, collect_journald_errors
from api.decision import analyze_with_llm
from api.executor import execute_tier1_action
from api.models import SafetyTier, AnalysisStatus
from api.config import MAX_AUTO_ACTIONS_PER_HOUR, SCAN_INTERVAL_SECONDS
from api.notifier import notify_escalation, notify_auto_fix_failure

logger = logging.getLogger("ai_engine")

_running = False
_task = None


async def _count_recent_auto_actions() -> int:
    db = await get_db()
    cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    row = await db.execute(
        "SELECT count(*) FROM auto_actions_log WHERE executed_at > ?", (cutoff,)
    )
    result = await row.fetchone()
    return result[0] if result else 0


async def run_analysis_cycle() -> str:
    """Run one full analysis cycle: collect -> analyze -> decide -> act/escalate."""
    db = await get_db()
    run_id = str(uuid4())
    now = datetime.utcnow().isoformat()

    await db.execute(
        "INSERT INTO analysis_runs (id, started_at, status) VALUES (?, ?, ?)",
        (run_id, now, AnalysisStatus.RUNNING.value),
    )
    await db.commit()

    errors_found = 0
    auto_fixed = 0
    escalated = 0

    try:
        # Collect errors from audit DBs
        audit_errors = collect_recent_errors(minutes=5)
        # Collect errors from journald
        journal_errors = collect_journald_errors(minutes=5)

        # Group by service
        by_service = {}
        for e in audit_errors:
            svc = e["service"]
            by_service.setdefault(svc, []).append(e)
        for e in journal_errors:
            svc = e.get("service", "system")
            by_service.setdefault(svc, []).append(e)

        errors_found = len(audit_errors) + len(journal_errors)

        if errors_found == 0:
            await db.execute(
                "UPDATE analysis_runs SET status=?, completed_at=?, errors_found=0, "
                "summary='No errors found' WHERE id=?",
                (AnalysisStatus.COMPLETED.value, datetime.utcnow().isoformat(), run_id),
            )
            await db.commit()
            return run_id

        # Analyze each service's errors
        for service, svc_errors in by_service.items():
            decision = await analyze_with_llm(service, svc_errors)
            if not decision:
                continue

            if decision.tier == SafetyTier.AUTO_FIX:
                # Check rate limit
                recent_actions = await _count_recent_auto_actions()
                if recent_actions >= MAX_AUTO_ACTIONS_PER_HOUR:
                    logger.warning("Rate limit reached, escalating to tier2")
                    decision.tier = SafetyTier.SUGGEST

            if decision.tier == SafetyTier.AUTO_FIX:
                # Extract the service name for systemctl (strip the unit suffix)
                target = decision.service
                success, output = execute_tier1_action(decision.action, target)
                await db.execute(
                    "INSERT INTO auto_actions_log (id, analysis_run_id, executed_at, service, action, success, output) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid4()), run_id, datetime.utcnow().isoformat(),
                     service, decision.action, int(success), output),
                )
                if success:
                    auto_fixed += 1
                else:
                    # Auto-fix failed, escalate and notify
                    esc_id, is_new = await _create_escalation(db, run_id, decision, service)
                    if is_new:
                        escalated += 1
                        # Notify about auto-fix failure (only for new escalations)
                        await notify_auto_fix_failure(service, decision.action, output)
            else:
                # Tier 2 or Tier 3 — create escalation and notify
                esc_id, is_new = await _create_escalation(db, run_id, decision, service)
                if is_new:
                    escalated += 1
                    # Send notification (only for NEW escalations, not duplicates)
                    await notify_escalation(
                        tier=decision.tier.value,
                        service=service,
                        error_summary=decision.reasoning,
                        proposed_action=decision.action,
                        confidence=decision.confidence,
                        escalation_id=esc_id,
                    )

        await db.commit()

        summary = f"Found {errors_found} errors across {len(by_service)} services. Auto-fixed: {auto_fixed}. Escalated: {escalated}."

        await db.execute(
            "UPDATE analysis_runs SET status=?, completed_at=?, errors_found=?, "
            "auto_fixed=?, escalated=?, summary=? WHERE id=?",
            (AnalysisStatus.COMPLETED.value, datetime.utcnow().isoformat(),
             errors_found, auto_fixed, escalated, summary, run_id),
        )
        await db.commit()

    except Exception as e:
        logger.exception(f"Analysis cycle failed: {e}")
        await db.execute(
            "UPDATE analysis_runs SET status=?, completed_at=?, summary=? WHERE id=?",
            (AnalysisStatus.FAILED.value, datetime.utcnow().isoformat(), str(e), run_id),
        )
        await db.commit()

    return run_id


async def _has_recent_pending_escalation(db, service: str, action: str) -> bool:
    """Check if there's already a pending escalation for this service+action in the last 24 hours."""
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    row = await db.execute(
        "SELECT id FROM escalations WHERE service = ? AND proposed_action = ? "
        "AND status = 'pending' AND created_at > ? LIMIT 1",
        (service, action, cutoff),
    )
    result = await row.fetchone()
    return result is not None


async def _create_escalation(db, run_id, decision, service) -> tuple[str, bool]:
    """Create an escalation record and return (id, is_new).

    Returns is_new=False if there's already a pending escalation for the same issue.
    """
    # Check for existing pending escalation
    if await _has_recent_pending_escalation(db, service, decision.action):
        logger.debug(f"Skipping duplicate escalation for {service}:{decision.action}")
        return "", False

    esc_id = str(uuid4())
    await db.execute(
        "INSERT INTO escalations (id, analysis_run_id, created_at, tier, service, "
        "error_summary, proposed_action, confidence, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (esc_id, run_id, datetime.utcnow().isoformat(), decision.tier.value,
         service, decision.reasoning, decision.action, decision.confidence, "pending"),
    )
    return esc_id, True


async def _scan_loop():
    global _running
    logger.info(f"AI Engine scan loop started (interval: {SCAN_INTERVAL_SECONDS}s)")
    while _running:
        try:
            run_id = await run_analysis_cycle()
            logger.info(f"Analysis cycle completed: {run_id}")
        except Exception as e:
            logger.exception(f"Scan loop error: {e}")
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


def start_engine():
    global _running, _task
    if _running:
        return
    _running = True
    _task = asyncio.create_task(_scan_loop())
    logger.info("AI Engine started")


def stop_engine():
    global _running, _task
    _running = False
    if _task:
        _task.cancel()
        _task = None
    logger.info("AI Engine stopped")


def is_running() -> bool:
    return _running
