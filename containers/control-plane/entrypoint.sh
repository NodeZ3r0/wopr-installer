#!/bin/bash
# WOPR Control Plane Entrypoint
# ==============================
# Validates environment and starts the orchestrator

set -e

echo "========================================"
echo "  WOPR Control Plane"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================"

# Required environment variables
REQUIRED_VARS=(
    "STRIPE_TEST_SECRET_KEY"
    "STRIPE_TEST_WEBHOOK_SECRET"
    "HETZNER_API_TOKEN"
    "DATABASE_URL"
)

# Check required vars
missing_vars=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "[ERROR] Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Hint: Mount your .env file or pass --env-file to podman run"
    exit 1
fi

# Optional vars with defaults
export STRIPE_DEFAULT_MODE="${STRIPE_DEFAULT_MODE:-test}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export LOG_FORMAT="${LOG_FORMAT:-json}"

# Print config summary (mask secrets)
echo ""
echo "Configuration:"
echo "  Stripe Mode:     ${STRIPE_DEFAULT_MODE}"
echo "  Stripe Key:      ${STRIPE_TEST_SECRET_KEY:0:12}..."
echo "  Hetzner Token:   ${HETZNER_API_TOKEN:0:8}..."
echo "  Database:        ${DATABASE_URL%%@*}@***"
echo "  Log Level:       ${LOG_LEVEL}"
echo ""

# Wait for database (if configured)
if [ -n "$DATABASE_URL" ]; then
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT="${DB_PORT:-5432}"

    echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
    for i in {1..30}; do
        if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "Database is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "[WARN] Database not reachable after 30s, proceeding anyway..."
        fi
        sleep 1
    done
fi

# Run database migrations if needed
if [ -f "/app/alembic.ini" ]; then
    echo "Running database migrations..."
    alembic upgrade head || echo "[WARN] Migrations failed, continuing..."
fi

echo ""
echo "Starting WOPR Control Plane..."
echo "========================================"

# Execute the main command
exec "$@"
