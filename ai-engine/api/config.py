import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")

DB_PATH = os.environ.get("AI_ENGINE_DB", "/opt/wopr/ai-engine/ai_engine.db")

# Safety limits
MAX_AUTO_ACTIONS_PER_HOUR = int(os.environ.get("MAX_AUTO_ACTIONS_PER_HOUR", "10"))
MIN_CONFIDENCE_FOR_AUTO = float(os.environ.get("MIN_CONFIDENCE", "0.7"))
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL", "300"))  # 5 minutes

# Audit DB paths to scan (for lighthouse deployments with audit DBs)
# Beacons use journald as the primary error source, not audit DBs
AUDIT_DBS = {}
if os.environ.get("AUDIT_DBS"):
    import json
    try:
        AUDIT_DBS = json.loads(os.environ.get("AUDIT_DBS", "{}"))
    except json.JSONDecodeError:
        pass

# Tier 1 allowed actions (auto-fix without human approval)
TIER1_ALLOWED_ACTIONS = {
    "restart_service",
    "restart_container",
    "pull_container_image",
    "reload_caddy",
    "clear_tmp",
    "rotate_logs",
    "check_disk_usage",
    "check_memory",
    "dns_flush",
}

# Hard blocklist — always rejected regardless of tier
COMMAND_BLOCKLIST = [
    "rm -rf", "dd if=", "mkfs", "chmod 777", "DROP TABLE",
    "TRUNCATE", "DELETE FROM", "> /dev/sd", "wget -O -",
    "curl | bash", "curl | sh", "eval(", "exec(",
]

# Services that can be restarted by Tier 1
RESTARTABLE_SERVICES = [
    # Legacy WOPR services
    "brainjoos-api", "nodemin", "joshua", "joshcore",
    "wopr-main", "wopr-web", "wopr-deploy-webhook",
    "wopr-orchestrator", "wopr-calcom",
    # WOPR Beacon core services
    "wopr-postgresql", "wopr-redis", "caddy",
    "wopr-authentik-server", "wopr-authentik-worker",
    # WOPR Beacon app services
    "wopr-nextcloud", "wopr-collabora", "wopr-vaultwarden",
    "wopr-forgejo", "wopr-woodpecker", "wopr-code-server",
    "wopr-portainer", "wopr-openwebui", "wopr-nocodb", "wopr-n8n",
    # WOPR Ops/Control plane
    "wopr-ollama", "wopr-ai-engine", "wopr-reactor",
    "wopr-defcon-one", "wopr-support-plane", "wopr-deployment-queue",
    "wopr-dashboard", "wopr-dashboard-api",
    # Mesh and monitoring
    "wopr-mesh-agent", "wopr-monitor",
]

# =============================================================================
# Notification Configuration
# =============================================================================

# Mailgun configuration
# Either use MAILGUN_API_KEY for HTTP API (preferred) or SMTP credentials
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "wopr.systems")
MAILGUN_FROM = os.environ.get("MAILGUN_FROM", "WOPR AI Engine <ai@wopr.systems>")

# SMTP fallback (if no API key)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.mailgun.org")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# Beacon identification
BEACON_ID = os.environ.get("BEACON_ID", "unknown-beacon")
BEACON_DOMAIN = os.environ.get("BEACON_DOMAIN", "")

# Beacon owner email (from bootstrap.json during provisioning)
BEACON_OWNER_EMAIL = os.environ.get("BEACON_OWNER_EMAIL", "")

# WOPR support staff emails (comma-separated)
WOPR_SUPPORT_EMAILS = os.environ.get(
    "WOPR_SUPPORT_EMAILS",
    "stephen.falken@wopr.systems"
).split(",")

# Notification settings
NOTIFY_ON_TIER2 = os.environ.get("NOTIFY_ON_TIER2", "true").lower() == "true"
NOTIFY_ON_TIER3 = os.environ.get("NOTIFY_ON_TIER3", "true").lower() == "true"
NOTIFY_ON_AUTO_FIX_FAILURE = os.environ.get("NOTIFY_ON_AUTO_FIX_FAILURE", "true").lower() == "true"

# Future: ntfy for SMS/push notifications
NTFY_URL = os.environ.get("NTFY_URL", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Support Plane URL for actionable links in emails
SUPPORT_PLANE_URL = os.environ.get("SUPPORT_PLANE_URL", "https://orc.wopr.systems")
