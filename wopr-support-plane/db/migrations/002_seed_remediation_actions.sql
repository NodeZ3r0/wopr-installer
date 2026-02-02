-- WOPR Support Plane - Seed Remediation Actions
-- Migration: 002_seed_remediation_actions.sql

BEGIN;

INSERT INTO remediation_actions (id, name, description, command_template, required_tier, risk_level) VALUES
    ('check_disk_usage',
     'Check Disk Usage',
     'Display filesystem disk space usage',
     'df -h',
     'remediate', 'low'),

    ('view_journal_errors',
     'View Recent Errors',
     'Show systemd journal error entries from the last hour',
     'journalctl -p err --since ''1 hour ago'' --no-pager -n 200',
     'remediate', 'low'),

    ('check_memory',
     'Check Memory Usage',
     'Display memory and swap usage',
     'free -h',
     'remediate', 'low'),

    ('check_services',
     'Check Service Status',
     'List all WOPR-related service statuses',
     'systemctl list-units ''wopr-*'' --no-pager',
     'remediate', 'low'),

    ('restart_caddy',
     'Restart Caddy',
     'Restart the Caddy reverse proxy service',
     'systemctl restart caddy',
     'remediate', 'medium'),

    ('restart_docker_stack',
     'Restart Docker Stack',
     'Restart a specific WOPR module docker stack',
     'docker compose -p wopr-{module} restart',
     'remediate', 'medium'),

    ('clear_redis_cache',
     'Clear Redis Cache',
     'Flush the Redis database cache',
     'redis-cli FLUSHDB',
     'remediate', 'medium'),

    ('renew_certificates',
     'Renew TLS Certificates',
     'Trust CA and reload Caddy to renew certificates',
     'caddy trust && caddy reload --config /etc/caddy/Caddyfile',
     'remediate', 'medium'),

    ('restart_authentik',
     'Restart Authentik',
     'Restart the Authentik SSO stack',
     'docker compose -p wopr-authentik restart',
     'remediate', 'high'),

    ('dns_flush',
     'Flush DNS Cache',
     'Clear the local DNS resolver cache',
     'systemd-resolve --flush-caches',
     'remediate', 'low'),

    ('restart_postgresql',
     'Restart PostgreSQL',
     'Restart the PostgreSQL database service',
     'systemctl restart postgresql',
     'remediate', 'high'),

    ('docker_prune',
     'Docker Prune',
     'Remove unused Docker images, containers, and volumes',
     'docker system prune -f --volumes',
     'breakglass', 'high')

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    command_template = EXCLUDED.command_template,
    required_tier = EXCLUDED.required_tier,
    risk_level = EXCLUDED.risk_level,
    updated_at = now();

COMMIT;
