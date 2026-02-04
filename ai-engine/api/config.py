import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")

DB_PATH = os.environ.get("AI_ENGINE_DB", "/opt/wopr/ai-engine/ai_engine.db")

# Safety limits
MAX_AUTO_ACTIONS_PER_HOUR = int(os.environ.get("MAX_AUTO_ACTIONS_PER_HOUR", "10"))
MIN_CONFIDENCE_FOR_AUTO = float(os.environ.get("MIN_CONFIDENCE", "0.7"))
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL", "300"))  # 5 minutes

# Audit DB paths to scan
AUDIT_DBS = {
    "brainjoos": "/opt/brainjoos/brainjoos-api/audit.db",
    "wopr-orchestrator": "/opt/wopr/orchestrator/audit.db",
    "wopr-deploy-webhook": "/opt/wopr-api/audit.db",
    "nodemin": "/var/www/nodemin/audit.db",
    "joshua": "/opt/joshua/audit.db",
    "joshcore": "/opt/joshcore/audit.db",
    "wopr-main": "/var/www/wopr-main/audit.db",
}

# Tier 1 allowed actions (auto-fix without human approval)
TIER1_ALLOWED_ACTIONS = {
    "restart_service",
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
    "brainjoos-api", "nodemin", "joshua", "joshcore",
    "wopr-main", "wopr-web", "wopr-deploy-webhook",
    "wopr-orchestrator", "wopr-calcom",
]
