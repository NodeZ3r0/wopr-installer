#!/bin/bash
#=================================================
# WOPR MODULE: PostgreSQL
# Version: 1.0
# Purpose: Deploy PostgreSQL database for WOPR services
# License: AGPL-3.0
#=================================================

# This script is sourced by the module deployer
# It expects wopr_common.sh to already be loaded

POSTGRESQL_IMAGE="docker.io/library/postgres:15-alpine"
POSTGRESQL_PORT=5432
POSTGRESQL_DATA_DIR="${WOPR_DATA_DIR}/postgresql"
POSTGRESQL_SERVICE="wopr-postgresql"

wopr_deploy_postgresql() {
    wopr_log "INFO" "Deploying PostgreSQL..."

    # Check if already installed
    if systemctl is-active --quiet "$POSTGRESQL_SERVICE" 2>/dev/null; then
        wopr_log "INFO" "PostgreSQL is already running"
        return 0
    fi

    # Create data directories
    mkdir -p "${POSTGRESQL_DATA_DIR}/data"
    mkdir -p "${POSTGRESQL_DATA_DIR}/init"

    # Generate password if not exists
    local pg_password=$(wopr_setting_get "postgresql_password")
    if [ -z "$pg_password" ]; then
        pg_password=$(wopr_random_string 32)
        wopr_setting_set "postgresql_password" "$pg_password"
    fi

    # Pull the image
    wopr_log "INFO" "Pulling PostgreSQL image..."
    wopr_container_pull "$POSTGRESQL_IMAGE"

    # Create initialization script for databases
    cat > "${POSTGRESQL_DATA_DIR}/init/init-wopr-dbs.sh" <<'INITSCRIPT'
#!/bin/bash
set -e

# Create databases for WOPR applications
# PostgreSQL 15+ requires explicit schema grants

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Authentik database
    CREATE DATABASE authentik;
    CREATE USER authentik WITH ENCRYPTED PASSWORD '${AUTHENTIK_DB_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE authentik TO authentik;
EOSQL

# Connect to authentik DB to grant schema permissions (PG 15+)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "authentik" <<-EOSQL
    GRANT ALL ON SCHEMA public TO authentik;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO authentik;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO authentik;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Nextcloud database
    CREATE DATABASE nextcloud;
    CREATE USER nextcloud WITH ENCRYPTED PASSWORD '${NEXTCLOUD_DB_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE nextcloud TO nextcloud;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "nextcloud" <<-EOSQL
    GRANT ALL ON SCHEMA public TO nextcloud;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nextcloud;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nextcloud;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- FreshRSS database
    CREATE DATABASE freshrss;
    CREATE USER freshrss WITH ENCRYPTED PASSWORD '${FRESHRSS_DB_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE freshrss TO freshrss;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "freshrss" <<-EOSQL
    GRANT ALL ON SCHEMA public TO freshrss;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO freshrss;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO freshrss;
EOSQL

echo "All WOPR databases initialized with PG 15+ schema grants"
INITSCRIPT

    chmod +x "${POSTGRESQL_DATA_DIR}/init/init-wopr-dbs.sh"

    # Generate per-app passwords
    local authentik_db_pass=$(wopr_setting_get "authentik_db_password")
    if [ -z "$authentik_db_pass" ]; then
        authentik_db_pass=$(wopr_random_string 32)
        wopr_setting_set "authentik_db_password" "$authentik_db_pass"
    fi

    local nextcloud_db_pass=$(wopr_setting_get "nextcloud_db_password")
    if [ -z "$nextcloud_db_pass" ]; then
        nextcloud_db_pass=$(wopr_random_string 32)
        wopr_setting_set "nextcloud_db_password" "$nextcloud_db_pass"
    fi

    local freshrss_db_pass=$(wopr_setting_get "freshrss_db_password")
    if [ -z "$freshrss_db_pass" ]; then
        freshrss_db_pass=$(wopr_random_string 32)
        wopr_setting_set "freshrss_db_password" "$freshrss_db_pass"
    fi

    # Create systemd service
    cat > "/etc/systemd/system/${POSTGRESQL_SERVICE}.service" <<EOF
[Unit]
Description=WOPR PostgreSQL Database
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=10

ExecStartPre=-/usr/bin/podman stop -t 10 ${POSTGRESQL_SERVICE}
ExecStartPre=-/usr/bin/podman rm ${POSTGRESQL_SERVICE}

ExecStart=/usr/bin/podman run --rm \\
    --name ${POSTGRESQL_SERVICE} \\
    --network ${WOPR_NETWORK} \\
    -v ${POSTGRESQL_DATA_DIR}/data:/var/lib/postgresql/data:Z \\
    -v ${POSTGRESQL_DATA_DIR}/init:/docker-entrypoint-initdb.d:ro,Z \\
    -e POSTGRES_USER=wopr \\
    -e POSTGRES_PASSWORD=${pg_password} \\
    -e POSTGRES_DB=wopr \\
    -e AUTHENTIK_DB_PASSWORD=${authentik_db_pass} \\
    -e NEXTCLOUD_DB_PASSWORD=${nextcloud_db_pass} \\
    -e FRESHRSS_DB_PASSWORD=${freshrss_db_pass} \\
    -p 127.0.0.1:${POSTGRESQL_PORT}:5432 \\
    ${POSTGRESQL_IMAGE}

ExecStop=/usr/bin/podman stop -t 10 ${POSTGRESQL_SERVICE}

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start
    systemctl daemon-reload
    systemctl enable "$POSTGRESQL_SERVICE"
    systemctl start "$POSTGRESQL_SERVICE"

    # Wait for PostgreSQL to be ready
    wopr_log "INFO" "Waiting for PostgreSQL to be ready..."
    local count=0
    while [ "$count" -lt 60 ]; do
        if podman exec "$POSTGRESQL_SERVICE" pg_isready -U wopr >/dev/null 2>&1; then
            wopr_log "OK" "PostgreSQL is ready"
            break
        fi
        sleep 2
        count=$((count + 2))
    done

    if [ "$count" -ge 60 ]; then
        wopr_log "ERROR" "PostgreSQL failed to start"
        return 1
    fi

    # Record installation
    wopr_setting_set "module_postgresql_installed" "true"
    wopr_setting_set "module_postgresql_version" "15"
    wopr_defcon_log "MODULE_DEPLOYED" "postgresql"

    wopr_log "OK" "PostgreSQL deployed successfully"
}

wopr_remove_postgresql() {
    wopr_log "INFO" "Removing PostgreSQL..."

    systemctl stop "$POSTGRESQL_SERVICE" 2>/dev/null || true
    systemctl disable "$POSTGRESQL_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${POSTGRESQL_SERVICE}.service"
    systemctl daemon-reload

    # Note: Data is preserved in ${POSTGRESQL_DATA_DIR}
    wopr_log "INFO" "PostgreSQL removed (data preserved)"
}

wopr_status_postgresql() {
    if systemctl is-active --quiet "$POSTGRESQL_SERVICE" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Get connection string for an app
wopr_postgresql_connection_string() {
    local app="$1"
    local password=$(wopr_setting_get "${app}_db_password")
    echo "postgresql://${app}:${password}@127.0.0.1:${POSTGRESQL_PORT}/${app}"
}
