# WOPR Provisioning Troubleshooting Guide

This document captures common issues encountered during beacon provisioning and their solutions. Use this as a reference for the AI support tier troubleshooting system.

---

## Table of Contents
1. [VPS Provider Issues](#vps-provider-issues)
2. [Callback & API Issues](#callback--api-issues)
3. [Caddy & Reverse Proxy Issues](#caddy--reverse-proxy-issues)
4. [Cloud-Init Issues](#cloud-init-issues)
5. [Database & Migration Issues](#database--migration-issues)
6. [DNS & Cloudflare Issues](#dns--cloudflare-issues)
7. [Authentication Issues](#authentication-issues)

---

## VPS Provider Issues

### HETZ-001: Server Type Not Found (Hetzner)

**Error:**
```
Error: Server type not found: cx22
```

**Cause:** Hetzner has different server type naming conventions. The CX series (shared vCPU) vs CPX series (dedicated vCPU) have different names.

**Solution:**
```python
# Wrong
tier_plans = {"hetzner": {1: "cx22", 2: "cx32", 3: "cx42"}}

# Correct
tier_plans = {"hetzner": {1: "cpx22", 2: "cpx32", 3: "cpx42"}}
```

**File:** `control_plane/orchestrator.py` - `_get_plan_for_tier()` method

---

### HETZ-002: Invalid Label Characters

**Error:**
```
Error: invalid input in field 'labels'
```

**Cause:** Hetzner labels cannot contain `@` symbols or dots beyond 63 characters.

**Solution:**
```python
# Sanitize email for label
email_label = customer_email.replace("@", "_at_").replace(".", "_")[:63]
```

**File:** `control_plane/providers/hetzner.py` - `provision()` method

---

### HETZ-003: SSH Key Not Found

**Error:**
```
Error: SSH key not found: nodez3r0-wopr
```

**Cause:** SSH key name referenced in provisioning doesn't exist in Hetzner account.

**Solution:**
1. Upload SSH key to Hetzner Cloud Console
2. Note the key name exactly as shown
3. Update provisioning config to use correct key name

**Verification:**
```python
from hcloud import Client
client = Client(token="YOUR_TOKEN")
keys = client.ssh_keys.get_all()
print([k.name for k in keys])
```

---

### VPS-001: Timeout Waiting for VPS (InstanceStatus Enum)

**Error:**
```
Error: Timeout waiting for VPS
```

**Cause:** The `_wait_for_vps()` function checks `str(status).lower()` but Python enums return `"InstanceStatus.RUNNING"` when converted to string, not `"running"`.

**Solution:**
```python
# Wrong
status_str = str(status).lower() if status else ""

# Correct
status_str = (status.value if hasattr(status, "value") else str(status)).lower() if status else ""
```

**File:** `control_plane/orchestrator.py` - `_wait_for_vps()` method

---

## Callback & API Issues

### CALLBACK-001: Callback Returns 404

**Error:**
```
Callback URL returns 404 (Authentik error page)
```

**Cause:** The callback endpoint is being routed through Authentik forward-auth, which doesn't recognize it.

**Solution:** Add callback endpoints to public (non-auth) routes in Caddy:
```caddy
handle /api/provision/* {
    reverse_proxy localhost:8001
}
handle /api/v1/provisioning/* {
    reverse_proxy localhost:8001
}
```

**File:** `/etc/caddy/sites-enabled/orc-wopr.caddy`

---

### CALLBACK-002: Callback Token Invalid

**Error:**
```
{"detail": "Invalid callback token for this job"}
```

**Cause:** Token mismatch between what was embedded in cloud-init and what was stored in the callback manager.

**Diagnosis:**
```bash
# On the beacon
cat /etc/wopr/bootstrap.json | jq '.callback_token'

# Compare with job record
curl -s http://localhost:8001/api/provision/{job_id}/status | jq '.callback_token'
```

---

### CALLBACK-003: No Callbacks Received

**Symptom:** Job stays in `deploying_wopr` state for full timeout period.

**Causes:**
1. Cloud-init script hasn't run yet
2. Callback URL not reachable from beacon
3. Script syntax errors in callback.sh

**Diagnosis on Beacon:**
```bash
# Check cloud-init status
cloud-init status

# Check if callback script exists
cat /opt/wopr/callback.sh

# Test callback manually
source /opt/wopr/callback.sh
wopr_callback "test" 50
```

---

## Caddy & Reverse Proxy Issues

### CADDY-001: Static Assets Return 404

**Error:**
```
Failed to load resource: 404
/_app/immutable/chunks/XXXXX.js
```

**Cause:** Static file handlers not matching before authentication handlers.

**Solution:** Use file existence matcher:
```caddy
root * /opt/wopr-installer/dashboard/build

# Serve existing files directly
@exists file {path}
handle @exists {
    file_server
}

# Then auth for everything else
handle {
    import authentik-forward-auth
    rewrite * /index.html
    file_server
}
```

**File:** `/etc/caddy/sites-enabled/orc-wopr.caddy`

---

### CADDY-002: SPA Routes Return 404

**Error:**
```
/setup/job-id returns 404
```

**Cause:** Caddy not configured to serve index.html for client-side routes.

**Solution:**
```caddy
# For SPA routes, rewrite to index.html
handle /setup/* {
    rewrite * /index.html
    file_server
}
```

---

### CADDY-003: API Endpoints Return HTML Instead of JSON

**Symptom:** API calls return Authentik login page HTML.

**Cause:** API endpoint not excluded from forward-auth.

**Solution:** Add specific API path handlers BEFORE the catch-all auth handler:
```caddy
# Public APIs first
handle /api/health {
    reverse_proxy localhost:8001
}

# Protected APIs
handle /api/* {
    import authentik-forward-auth
    reverse_proxy localhost:8001
}
```

---

## Cloud-Init Issues

### CLOUDINIT-001: Script Line Continuation Broken

**Symptom:** Shell scripts in cloud-init have syntax errors, commands split across lines.

**Cause:** YAML multiline string handling corrupts backslash line continuations.

**Example of Broken Output:**
```bash
curl -sf -X POST "$URL"               -H "Content-Type: application/json"
# Should be one line with backslash continuation
```

**Solution:** Use single-line commands or proper YAML escaping:
```python
# Option 1: Single line
curl_cmd = 'curl -sf -X POST "$URL" -H "Content-Type: application/json" -d "{...}"'

# Option 2: Proper escaping in cloud-init template
content: |
    curl -sf -X POST "$URL" \\
        -H "Content-Type: application/json"
```

**File:** `control_plane/orchestrator.py` - `_generate_cloud_init()` method

---

### CLOUDINIT-002: Bootstrap Script Download Fails

**Error in /var/log/cloud-init-output.log:**
```
curl: (6) Could not resolve host: install.wopr.systems
```

**Cause:** DNS not yet configured on new VPS.

**Solution:** Ensure DNS configuration happens early in cloud-init:
```yaml
runcmd:
  - echo "nameserver 8.8.8.8" > /etc/resolv.conf
  - # ... rest of setup
```

---

### CLOUDINIT-003: Files Not Created

**Symptom:** Expected files in /etc/wopr/ or /opt/wopr/ don't exist.

**Diagnosis:**
```bash
# Check cloud-init logs
cat /var/log/cloud-init.log | grep -i error
cat /var/log/cloud-init-output.log

# Check cloud-init status
cloud-init status --long
```

---

## Database & Migration Issues

### DB-001: Trigger Already Exists

**Error:**
```
ERROR: trigger "trigger_XXX_updated_at" for relation "XXX" already exists
```

**Cause:** Migration being re-run, CREATE TRIGGER doesn't have IF NOT EXISTS.

**Solution:**
```sql
-- Drop first, then create
DROP TRIGGER IF EXISTS trigger_custom_domains_updated_at ON custom_domains;
CREATE TRIGGER trigger_custom_domains_updated_at
    BEFORE UPDATE ON custom_domains
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

**File:** `control_plane/migrations/*.sql`

---

### DB-002: Connection Pool Exhausted

**Error:**
```
asyncpg.exceptions.TooManyConnectionsError
```

**Solution:** Increase pool size or add connection timeout:
```python
pool = await asyncpg.create_pool(
    dsn=database_url,
    min_size=5,
    max_size=20,
    command_timeout=60
)
```

---

## DNS & Cloudflare Issues

### CF-001: Cached 404 Responses

**Symptom:** Files return 404 even after fixing server config.

**Cause:** Cloudflare caching the 404 response.

**Solution:**
```bash
# Purge entire cache
curl -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -d '{"purge_everything":true}'
```

---

### CF-002: DNS Record Creation Fails

**Error:**
```
Error creating DNS record: Record already exists
```

**Solution:** Check for existing record first:
```python
async def create_a_record(self, name, ip, proxied=False):
    # Check if exists
    existing = self.get_record(name)
    if existing:
        return self.update_record(existing['id'], ip)
    return self.create_record(name, ip, proxied)
```

---

## Authentication Issues

### AUTH-001: Forward Auth Blocking Public Endpoints

**Symptom:** Public endpoints (webhooks, health checks) require login.

**Cause:** Catch-all auth handler matches before specific path handlers.

**Solution:** Order handlers from most specific to least specific:
```caddy
# Specific public endpoints FIRST
handle /api/webhook/* {
    reverse_proxy localhost:8001
}

# Protected catch-all LAST
handle /api/* {
    import authentik-forward-auth
    reverse_proxy localhost:8001
}
```

---

## Quick Diagnostic Commands

```bash
# Check orchestrator status
systemctl status wopr-orchestrator

# Check orchestrator logs
journalctl -u wopr-orchestrator --since "10 minutes ago" -f

# Check Caddy logs
tail -f /var/log/caddy/orc.access.log

# Test API health
curl -s http://localhost:8001/api/health

# Check job status
curl -s http://localhost:8001/api/provision/{JOB_ID}/status | jq

# Check VPS status (Hetzner)
python3 -c "
from hcloud import Client
c = Client(token='TOKEN')
s = c.servers.get_by_id(SERVER_ID)
print(f'Status: {s.status}, IP: {s.public_net.ipv4.ip}')
"

# Test callback from beacon
curl -X POST https://orc.wopr.systems/api/provision/{JOB_ID}/callback \
  -H "Content-Type: application/json" \
  -H "X-Callback-Token: TOKEN" \
  -d '{"stage": "test", "progress": 50}'
```

---

## Support Tier Escalation

If these solutions don't resolve the issue:

1. **Tier 1 (AI):** Reference this document, attempt automated fixes
2. **Tier 2 (AI + Human Review):** Collect logs, propose solutions
3. **Tier 3 (Human):** Manual intervention required

**Log Collection for Escalation:**
```bash
# Collect all relevant logs
tar -czf /tmp/wopr-debug-$(date +%Y%m%d-%H%M%S).tar.gz \
  /var/log/caddy/orc.access.log \
  /opt/wopr-installer/jobs/*.json \
  <(journalctl -u wopr-orchestrator --since "1 hour ago")
```

---

## Installer Issues

### INSTALLER-001: Windows CRLF Line Endings in Cloud-Init

**Error:**
```
/tmp/wopr_bootstrap.sh: line 8: $'\r': command not found
/tmp/wopr_bootstrap.sh: line 9: set: pipefail: invalid option name
```

**Cause:** Cloud-init scripts generated on Windows have CRLF (`\r\n`) line endings instead of Unix LF (`\n`).

**Diagnosis:**
```bash
file /tmp/wopr_bootstrap.sh
# Output: "ASCII text, with CRLF line terminators"

cat -A /tmp/wopr_bootstrap.sh | head -5
# Shows ^M at end of lines
```

**Solution:**
```bash
# Fix existing files
sed -i 's/\r//g' /tmp/wopr_bootstrap.sh /opt/wopr/callback.sh /etc/wopr/bootstrap.json

# In Python code, normalize output:
cloud_init_content = template.replace('\r\n', '\n').replace('\r', '\n')
```

**Prevention:** Always run orchestrator on Linux, not Windows.

**File:** `control_plane/orchestrator.py` - `_generate_cloud_init()` method

---

### INSTALLER-002: Wrong Scripts Directory in Tarball

**Symptom:** Installer fails with "script not found" or has incomplete module list.

**Cause:** API tarball endpoint serving from wrong directory:
- Wrong: `/opt/wopr-installer/scripts/scripts/` (nested, incomplete)
- Correct: `/opt/wopr-installer/wopr-installer/scripts/` (complete)

**Diagnosis:**
```bash
# Check tarball contents
curl -s http://localhost:8001/api/installer/latest.tar.gz | tar -tzf - | grep '\.sh$'

# Compare to complete set
ls /opt/wopr-installer/wopr-installer/scripts/modules/
```

**Solution:**
```python
# In main.py download_installer():
# Wrong
installer_dir = Path(__file__).parent

# Correct
installer_dir = Path(__file__).parent / "wopr-installer"
```

**File:** `main.py` - `download_installer()` endpoint

---

### INSTALLER-003: Module Deployment Order

**Error:**
```
[ERROR] PostgreSQL must be running before Authentik
[ERROR] Failed to deploy infrastructure module: authentik
```

**Cause:** Core modules deployed in wrong order. Authentik depends on PostgreSQL and Redis.

**Wrong Order:** `["authentik", "caddy", "postgresql", "redis"]`
**Correct Order:** `["postgresql", "redis", "caddy", "authentik"]`

**Solution:**
```python
# In orchestrator.py _generate_cloud_init():
core_modules = ["postgresql", "redis", "caddy", "authentik"]
```

**File:** `control_plane/orchestrator.py`

---

## Podman / Container Issues

### PODMAN-001: DNS Not Enabled on Network

**Error:**
```
PostgreSQL connection failed, retrying... ([Errno -2] Name or service not known)
```

**Cause:** Podman network created without DNS support. Containers can't resolve each other by name.

**Diagnosis:**
```bash
podman network inspect wopr-network | grep dns_enabled
# Shows: "dns_enabled": false
```

**Solution:** Use host gateway IP instead of container names, or recreate network with DNS:
```bash
# Option 1: Use gateway IP in env files
sed -i 's/wopr-postgresql/172.20.0.1/g' /var/lib/wopr/authentik/authentik.env
sed -i 's/wopr-redis/172.20.0.1/g' /var/lib/wopr/authentik/authentik.env

# Option 2: Recreate network (requires stopping all containers)
podman network rm -f wopr-network
podman network create --dns-enabled wopr-network
```

---

### PODMAN-002: Services Bound to Localhost Only

**Error:**
```
Connection refused to 172.20.0.1:5432
```

**Cause:** PostgreSQL/Redis systemd services bind to `127.0.0.1` only, not accessible from container gateway.

**Diagnosis:**
```bash
netstat -tlnp | grep 5432
# Shows: 127.0.0.1:5432 (should be 0.0.0.0:5432)
```

**Solution:**
```bash
# Edit service files
sed -i 's/-p 127.0.0.1:5432:5432/-p 0.0.0.0:5432:5432/' /etc/systemd/system/wopr-postgresql.service
sed -i 's/-p 127.0.0.1:6379:6379/-p 0.0.0.0:6379:6379/' /etc/systemd/system/wopr-redis.service

# Reload and restart
systemctl daemon-reload
systemctl restart wopr-postgresql wopr-redis
```

**Security Note:** Ensure firewall blocks external access to these ports.

---

### PODMAN-003: Container Can't Reach Host Localhost

**Error:**
```
connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

**Cause:** Inside a container, `127.0.0.1` refers to the container's loopback, not the host.

**Solution:** Use the podman network gateway IP (typically `172.20.0.1`):
```bash
# Get gateway IP
podman network inspect wopr-network | jq '.[0].subnets[0].gateway'

# Update container env files to use gateway instead of localhost
```

---

## Beacon Diagnostic Commands

```bash
# Check all WOPR services
systemctl list-units --type=service | grep wopr

# Check container status
podman ps -a

# Check container logs
podman logs wopr-authentik-server 2>&1 | tail -30
podman logs wopr-postgresql 2>&1 | tail -30

# Check network connectivity
podman exec wopr-authentik-server ping -c 1 172.20.0.1

# Verify port bindings
netstat -tlnp | grep -E '(5432|6379|9000)'

# Check installer log
tail -100 /var/log/wopr/install-final.log

# Test Authentik locally
curl -s http://127.0.0.1:9000/ -o /dev/null -w "%{http_code}"

# Check Caddy config
cat /etc/caddy/Caddyfile
```

---

*Last Updated: 2026-02-09*
*Version: 1.1*
