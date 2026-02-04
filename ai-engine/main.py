import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from api.database import get_db, close_db
from api.engine import start_engine, stop_engine, is_running, run_analysis_cycle
from api.models import EngineStatus, Escalation, AnalysisRun, EscalationStatus
from api.config import OLLAMA_URL, OLLAMA_MODEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ai_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await get_db()
    start_engine()
    logger.info("WOPR AI Remediation Engine started")
    yield
    # Shutdown
    stop_engine()
    await close_db()
    logger.info("WOPR AI Remediation Engine stopped")


app = FastAPI(
    title="WOPR AI Remediation Engine",
    description="Automated log analysis and remediation for WOPR infrastructure",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/ai/status")
async def get_status() -> EngineStatus:
    db = await get_db()

    # Check Ollama
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    # Get stats
    row = await db.execute("SELECT count(*) FROM analysis_runs")
    total_runs = (await row.fetchone())[0]

    row = await db.execute("SELECT count(*) FROM auto_actions_log WHERE success = 1")
    total_fixes = (await row.fetchone())[0]

    row = await db.execute("SELECT count(*) FROM escalations")
    total_esc = (await row.fetchone())[0]

    row = await db.execute(
        "SELECT started_at FROM analysis_runs ORDER BY started_at DESC LIMIT 1"
    )
    last = await row.fetchone()
    last_run = last[0] if last else None

    # Rate limit
    from api.engine import _count_recent_auto_actions
    from api.config import MAX_AUTO_ACTIONS_PER_HOUR
    recent = await _count_recent_auto_actions()

    return EngineStatus(
        running=is_running(),
        ollama_available=ollama_ok,
        model=OLLAMA_MODEL,
        last_run=last_run,
        total_runs=total_runs,
        total_auto_fixes=total_fixes,
        total_escalations=total_esc,
        rate_limit_remaining=MAX_AUTO_ACTIONS_PER_HOUR - recent,
    )


@app.get("/api/v1/ai/escalations")
async def list_escalations(status: str = "pending", limit: int = 50):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        (status, limit),
    )
    results = []
    async for row in rows:
        results.append(dict(row))
    return results


@app.post("/api/v1/ai/escalations/{esc_id}/approve")
async def approve_escalation(esc_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM escalations WHERE id = ?", (esc_id,))
    esc = await row.fetchone()
    if not esc:
        raise HTTPException(404, "Escalation not found")
    if esc["status"] != "pending":
        raise HTTPException(400, f"Escalation already {esc['status']}")

    # For tier2, execute the proposed action
    from api.executor import execute_tier1_action
    success, output = execute_tier1_action(esc["proposed_action"], esc["service"])

    await db.execute(
        "UPDATE escalations SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
        (EscalationStatus.APPROVED.value, datetime.utcnow().isoformat(), "human", esc_id),
    )
    await db.commit()
    return {"status": "approved", "action_success": success, "output": output}


@app.post("/api/v1/ai/escalations/{esc_id}/reject")
async def reject_escalation(esc_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM escalations WHERE id = ?", (esc_id,))
    esc = await row.fetchone()
    if not esc:
        raise HTTPException(404, "Escalation not found")

    await db.execute(
        "UPDATE escalations SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
        (EscalationStatus.REJECTED.value, datetime.utcnow().isoformat(), "human", esc_id),
    )
    await db.commit()
    return {"status": "rejected"}


@app.post("/api/v1/ai/analyze-now")
async def trigger_analysis():
    run_id = await run_analysis_cycle()
    db = await get_db()
    row = await db.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,))
    result = await row.fetchone()
    return dict(result) if result else {"id": run_id}


@app.get("/api/v1/ai/history")
async def get_history(limit: int = 20):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM analysis_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    )
    results = []
    async for row in rows:
        results.append(dict(row))
    return results


@app.get("/api/v1/ai/actions")
async def get_actions(limit: int = 50):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM auto_actions_log ORDER BY executed_at DESC LIMIT ?", (limit,)
    )
    results = []
    async for row in rows:
        results.append(dict(row))
    return results


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "wopr-ai-engine"}
