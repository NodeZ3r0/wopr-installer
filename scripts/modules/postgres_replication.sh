#!/bin/bash
#=================================================
# WOPR MODULE: PostgreSQL Mesh Replication
# Version: 1.0
# Purpose: Configure PostgreSQL replication for distributed mesh SSO
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh and postgresql.sh to already be loaded

wopr_deploy_postgres_replication() {
    wopr_log "INFO" "Configuring PostgreSQL mesh replication..."

    # Check if mesh_replication is enabled in bootstrap
    local mesh_enabled=$(wopr_bootstrap_get "mesh_replication.enabled")
    if [ "$mesh_enabled" != "true" ]; then
        wopr_log "INFO" "Mesh replication not enabled in bootstrap.json, skipping"
        return 0
    fi

    # Get lighthouse details from bootstrap
    local lighthouse_host=$(wopr_bootstrap_get "mesh_replication.lighthouse_postgres_host")
    local lighthouse_port=$(wopr_bootstrap_get "mesh_replication.lighthouse_postgres_port")
    local replication_pass=$(wopr_bootstrap_get "mesh_replication.replication_password")

    if [ -z "$lighthouse_host" ] || [ -z "$lighthouse_port" ]; then
        wopr_log "WARN" "Lighthouse PostgreSQL details not found in bootstrap, skipping replication setup"
        return 0
    fi

    wopr_log "INFO" "Lighthouse PostgreSQL: ${lighthouse_host}:${lighthouse_port}"

    # Configure pg_hba.conf to allow replication connections from mesh peers
    wopr_log "INFO" "Configuring pg_hba.conf for mesh peers..."

    local mesh_peers=$(wopr_bootstrap_get "mesh_replication.mesh_peers")
    if [ -n "$mesh_peers" ]; then
        # Parse mesh_peers JSON array and add to pg_hba.conf
        local peer_count=$(echo "$mesh_peers" | jq 'length' 2>/dev/null || echo "0")
        wopr_log "INFO" "Found ${peer_count} mesh peers"

        for i in $(seq 0 $((peer_count - 1))); do
            local peer_ip=$(echo "$mesh_peers" | jq -r ".[$i].ip" 2>/dev/null)
            if [ -n "$peer_ip" ] && [ "$peer_ip" != "null" ]; then
                wopr_log "INFO" "Adding pg_hba.conf entry for peer: ${peer_ip}"
                podman exec wopr-postgresql sh -c "echo 'host    authentik    replicator    ${peer_ip}/32    md5' >> /var/lib/postgresql/data/pg_hba.conf"
                podman exec wopr-postgresql sh -c "echo 'host    replication  replicator    ${peer_ip}/32    md5' >> /var/lib/postgresql/data/pg_hba.conf"
            fi
        done

        # Reload PostgreSQL configuration
        podman exec wopr-postgresql psql -U wopr -c "SELECT pg_reload_conf();" >/dev/null 2>&1
    fi

    # Wait for PostgreSQL to be ready
    wopr_log "INFO" "Waiting for PostgreSQL to accept connections..."
    local count=0
    while [ "$count" -lt 30 ]; do
        if podman exec wopr-postgresql pg_isready -U wopr >/dev/null 2>&1; then
            break
        fi
        sleep 2
        count=$((count + 2))
    done

    # Create publication for user tables
    wopr_log "INFO" "Creating publication for user tables..."
    podman exec wopr-postgresql psql -U wopr -d authentik <<SQLEOF
-- Create publication (idempotent)
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'wopr_users_pub') THEN
        CREATE PUBLICATION wopr_users_pub FOR TABLE
            authentik_core_user,
            authentik_core_group,
            authentik_core_user_groups;
    END IF;
END \$\$;
SQLEOF

    if [ $? -eq 0 ]; then
        wopr_log "OK" "Publication created"
    else
        wopr_log "ERROR" "Failed to create publication"
        return 1
    fi

    # Subscribe to lighthouse publication
    wopr_log "INFO" "Creating subscription to lighthouse..."
    podman exec wopr-postgresql psql -U wopr -d authentik <<SQLEOF
-- Drop existing subscription if it exists
DROP SUBSCRIPTION IF EXISTS lighthouse_users_sub;

-- Create subscription to lighthouse
CREATE SUBSCRIPTION lighthouse_users_sub
    CONNECTION 'host=${lighthouse_host} port=${lighthouse_port} dbname=authentik user=replicator password=${replication_pass}'
    PUBLICATION wopr_users_pub
    WITH (copy_data = true, create_slot = true);
SQLEOF

    if [ $? -eq 0 ]; then
        wopr_log "OK" "Subscription to lighthouse created"
    else
        wopr_log "WARN" "Failed to create subscription (lighthouse may not be ready yet)"
    fi

    # Record installation
    wopr_setting_set "module_postgres_replication_installed" "true"
    wopr_defcon_log "MODULE_DEPLOYED" "postgres_replication"

    wopr_log "OK" "PostgreSQL mesh replication configured"
}

wopr_remove_postgres_replication() {
    wopr_log "INFO" "Removing PostgreSQL replication..."

    # Drop subscription
    podman exec wopr-postgresql psql -U wopr -d authentik -c "DROP SUBSCRIPTION IF EXISTS lighthouse_users_sub;" 2>/dev/null || true

    # Drop publication
    podman exec wopr-postgresql psql -U wopr -d authentik -c "DROP PUBLICATION IF EXISTS wopr_users_pub;" 2>/dev/null || true

    wopr_log "INFO" "PostgreSQL replication removed"
}

wopr_status_postgres_replication() {
    local sub_count=$(podman exec wopr-postgresql psql -U wopr -d authentik -t -c "SELECT COUNT(*) FROM pg_subscription;" 2>/dev/null | tr -d ' ')
    if [ "$sub_count" -gt 0 ]; then
        echo "active"
    else
        echo "inactive"
    fi
}
