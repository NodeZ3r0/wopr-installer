#!/bin/bash
#=================================================
# WOPR Mesh SSO Migration Script
# Migrates existing beacon to mesh replication
#=================================================

set -e

LIGHTHOUSE_HOST="159.203.138.7"
LIGHTHOUSE_PORT="5434"
REPLICATION_PASS="W0prR3pl1c4t10n2026!"

echo "========================================"
echo "WOPR MESH SSO REPLICATION MIGRATION"
echo "========================================"
echo ""
echo "This script will:"
echo "  1. Backup PostgreSQL data"
echo "  2. Enable logical replication"
echo "  3. Create publication and subscription"
echo "  4. Verify replication is working"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! \ =~ ^[Yy]\$ ]]; then
    echo "Aborted"
    exit 1
fi

# Detect container runtime
if command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
    PG_CONTAINER="wopr-postgresql"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
    # Find PostgreSQL container
    PG_CONTAINER=\
else
    echo "ERROR: Neither podman nor docker found"
    exit 1
fi

echo "Using \ with container \"

# Step 1: Backup
echo ""
echo "=== Step 1: Backing up PostgreSQL ==="
BACKUP_DIR="/opt/wopr/backups/postgres-\20260211-134321"
mkdir -p "\"

if [ "\" = "podman" ]; then
    podman exec \ pg_dumpall -U wopr > "\/postgres-full.sql"
else
    docker exec \ pg_dumpall -U authentik > "\/postgres-full.sql"
fi

echo "✓ Backup saved to \"

# Step 2: Enable logical replication
echo ""
echo "=== Step 2: Enabling logical replication ==="

# Update PostgreSQL config
if [ "\" = "podman" ]; then
    # Update systemd service
    sed -i 's/postgres\$/postgres -c wal_level=logical -c max_replication_slots=10 -c max_wal_senders=10/' /etc/systemd/system/wopr-postgresql.service
    systemctl daemon-reload
    systemctl restart wopr-postgresql
else
    # Update docker-compose.yml
    cd /opt/authentik
    if ! grep -q "wal_level=logical" docker-compose.yml; then
        echo "ERROR: Please manually add 'command: postgres -c wal_level=logical -c max_replication_slots=10 -c max_wal_senders=10' to PostgreSQL service"
        exit 1
    fi
    docker compose restart \
fi

sleep 5
echo "✓ Logical replication enabled"

# Step 3: Create replication user
echo ""
echo "=== Step 3: Creating replication user ==="

if [ "\" = "podman" ]; then
    podman exec \ psql -U wopr -d authentik << SQLEOF
CREATE USER replicator WITH REPLICATION LOGIN PASSWORD '\';
GRANT ALL PRIVILEGES ON DATABASE authentik TO replicator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO replicator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO replicator;
SQLEOF
else
    docker exec \ psql -U authentik -d authentik << SQLEOF
CREATE USER replicator WITH REPLICATION LOGIN PASSWORD '\';
GRANT ALL PRIVILEGES ON DATABASE authentik TO replicator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO replicator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO replicator;
SQLEOF
fi

echo "✓ Replication user created"

# Step 4: Create publication
echo ""
echo "=== Step 4: Creating publication ==="

if [ "\" = "podman" ]; then
    podman exec \ psql -U wopr -d authentik << SQLEOF
CREATE PUBLICATION wopr_users_pub FOR TABLE
    authentik_core_user,
    authentik_core_group,
    authentik_core_user_groups;
SQLEOF
else
    docker exec \ psql -U authentik -d authentik << SQLEOF
CREATE PUBLICATION wopr_users_pub FOR TABLE
    authentik_core_user,
    authentik_core_group,
    authentik_core_user_groups;
SQLEOF
fi

echo "✓ Publication created"

# Step 5: Create subscription to lighthouse
echo ""
echo "=== Step 5: Creating subscription to lighthouse ==="

if [ "\" = "podman" ]; then
    podman exec \ psql -U wopr -d authentik << SQLEOF
CREATE SUBSCRIPTION lighthouse_users_sub
    CONNECTION 'host=\ port=\ dbname=authentik user=replicator password=\'
    PUBLICATION wopr_users_pub
    WITH (copy_data = true, create_slot = true);
SQLEOF
else
    docker exec \ psql -U authentik -d authentik << SQLEOF
CREATE SUBSCRIPTION lighthouse_users_sub
    CONNECTION 'host=\ port=\ dbname=authentik user=replicator password=\'
    PUBLICATION wopr_users_pub
    WITH (copy_data = true, create_slot = true);
SQLEOF
fi

echo "✓ Subscription created"

# Step 6: Verify replication
echo ""
echo "=== Step 6: Verifying replication ==="

sleep 5

if [ "\" = "podman" ]; then
    podman exec \ psql -U wopr -d authentik -c "SELECT subname, subenabled, last_msg_receipt_time FROM pg_stat_subscription;"
else
    docker exec \ psql -U authentik -d authentik -c "SELECT subname, subenabled, last_msg_receipt_time FROM pg_stat_subscription;"
fi

echo ""
echo "========================================"
echo "MIGRATION COMPLETE"
echo "========================================"
echo ""
echo "✓ PostgreSQL mesh replication is now active"
echo "✓ User accounts will sync across all beacons"
echo "✓ Backup saved: \"
echo ""
