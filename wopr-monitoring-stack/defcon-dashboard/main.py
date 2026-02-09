"""WOPR DEFCON ONE Dashboard - Custom Monitoring Frontend.

A CRT-styled terminal monitoring dashboard that aggregates data from
Prometheus, Loki, and Alertmanager to display real-time security and
system status information.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic_settings import BaseSettings
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    alertmanager_url: str = "http://alertmanager:9093"
    ntfy_url: str = "http://ntfy:80"

    class Config:
        env_file = ".env"


settings = Settings()
app = FastAPI(title="DEFCON ONE Dashboard", version="1.0.0")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# HTTP client for backend queries
http_client = httpx.AsyncClient(timeout=10.0)


async def query_prometheus(query: str) -> dict[str, Any]:
    """Execute a PromQL query and return results."""
    try:
        response = await http_client.get(
            f"{settings.prometheus_url}/api/v1/query",
            params={"query": query},
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Prometheus query error: {e}")
        return {"status": "error", "error": str(e)}


async def query_loki(query: str, limit: int = 100) -> dict[str, Any]:
    """Execute a LogQL query and return results."""
    try:
        end = datetime.utcnow()
        start = end - timedelta(hours=1)
        response = await http_client.get(
            f"{settings.loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": int(start.timestamp() * 1e9),
                "end": int(end.timestamp() * 1e9),
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Loki query error: {e}")
        return {"status": "error", "error": str(e)}


async def get_alerts() -> list[dict]:
    """Get active alerts from Alertmanager."""
    try:
        response = await http_client.get(
            f"{settings.alertmanager_url}/api/v2/alerts",
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Alertmanager query error: {e}")
        return []


async def get_system_metrics() -> dict[str, Any]:
    """Gather all system metrics for the dashboard."""
    # Parallel queries for efficiency
    queries = {
        "cpu": 'avg(100 - (rate(node_cpu_seconds_total{mode="idle"}[5m]) * 100))',
        "memory": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
        "disk": '(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100',
        "load": "node_load1",
        "uptime": "time() - node_boot_time_seconds",
        "network_rx": "rate(node_network_receive_bytes_total[5m])",
        "network_tx": "rate(node_network_transmit_bytes_total[5m])",
        "targets_up": "count(up == 1)",
        "targets_down": "count(up == 0)",
    }

    results = {}
    tasks = [query_prometheus(q) for q in queries.values()]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for key, response in zip(queries.keys(), responses):
        if isinstance(response, Exception):
            results[key] = None
        elif response.get("status") == "success":
            data = response.get("data", {}).get("result", [])
            if data:
                results[key] = float(data[0].get("value", [0, 0])[1])
            else:
                results[key] = None
        else:
            results[key] = None

    return results


async def get_security_metrics() -> dict[str, Any]:
    """Get security-related metrics (fail2ban, suricata, firewall)."""
    queries = {
        # Fail2ban bans (from Loki)
        "fail2ban_bans_today": '{job="fail2ban"} |= "Ban"',
        # Suricata alerts (from Loki)
        "suricata_alerts": '{job="suricata"} | json | event_type="alert"',
        # Firewall blocks (from Loki)
        "firewall_blocks": '{job="nftables"} |= "BLOCK"',
    }

    # Get fail2ban stats from Prometheus if available
    fail2ban_result = await query_prometheus("fail2ban_banned_ip_total")
    suricata_result = await query_prometheus("suricata_detect_alert_total")

    return {
        "fail2ban_bans": (
            fail2ban_result.get("data", {}).get("result", [{}])[0].get("value", [0, 0])[1]
            if fail2ban_result.get("status") == "success"
            else 0
        ),
        "suricata_alerts": (
            suricata_result.get("data", {}).get("result", [{}])[0].get("value", [0, 0])[1]
            if suricata_result.get("status") == "success"
            else 0
        ),
    }


async def get_recent_logs(job: str, limit: int = 20) -> list[dict]:
    """Get recent log entries for a specific job."""
    result = await query_loki(f'{{job="{job}"}}', limit=limit)
    if result.get("status") == "success":
        streams = result.get("data", {}).get("result", [])
        logs = []
        for stream in streams:
            for value in stream.get("values", []):
                logs.append(
                    {
                        "timestamp": datetime.fromtimestamp(int(value[0]) / 1e9).strftime(
                            "%H:%M:%S"
                        ),
                        "message": value[1][:200],  # Truncate long messages
                        "labels": stream.get("stream", {}),
                    }
                )
        return sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]
    return []


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main DEFCON dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/status")
async def api_status():
    """Get current system status for AJAX updates."""
    metrics = await get_system_metrics()
    alerts = await get_alerts()
    security = await get_security_metrics()

    # Calculate DEFCON level based on alerts
    critical_alerts = len([a for a in alerts if a.get("labels", {}).get("severity") == "critical"])
    warning_alerts = len([a for a in alerts if a.get("labels", {}).get("severity") == "warning"])

    if critical_alerts > 0:
        defcon_level = 1
    elif warning_alerts > 2:
        defcon_level = 2
    elif warning_alerts > 0:
        defcon_level = 3
    elif metrics.get("targets_down", 0) > 0:
        defcon_level = 4
    else:
        defcon_level = 5

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "defcon_level": defcon_level,
        "metrics": metrics,
        "security": security,
        "alerts": {
            "total": len(alerts),
            "critical": critical_alerts,
            "warning": warning_alerts,
            "items": alerts[:10],  # Limit to 10 most recent
        },
    }


@app.get("/api/logs/{job}")
async def api_logs(job: str, limit: int = 50):
    """Get recent logs for a specific job."""
    logs = await get_recent_logs(job, limit)
    return {"job": job, "logs": logs}


@app.get("/api/logs/security")
async def api_security_logs():
    """Get combined security logs (fail2ban, suricata, nftables)."""
    fail2ban = await get_recent_logs("fail2ban", 20)
    suricata = await get_recent_logs("suricata", 20)
    firewall = await get_recent_logs("nftables", 20)

    # Combine and sort by timestamp
    all_logs = fail2ban + suricata + firewall
    all_logs.sort(key=lambda x: x["timestamp"], reverse=True)

    return {"logs": all_logs[:50]}


@app.get("/api/stream")
async def stream_updates(request: Request):
    """Server-Sent Events stream for real-time updates."""

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            data = await api_status()
            yield {"event": "status", "data": data}

            await asyncio.sleep(5)  # Update every 5 seconds

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "defcon-dashboard"}


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    await http_client.aclose()