"""
WOPR Database Layer
===================

Async PostgreSQL connection pool and query helpers using asyncpg.
Handles schema migrations on startup.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Any, List, Dict

try:
    import asyncpg
except ImportError:
    asyncpg = None
    print("WARNING: asyncpg not installed. Run: pip install asyncpg")

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Global pool reference
_pool: Optional["asyncpg.Pool"] = None


async def init_database(database_url: str, min_size: int = 2, max_size: int = 10) -> "asyncpg.Pool":
    """
    Initialize the database connection pool and run migrations.

    Args:
        database_url: PostgreSQL connection string
        min_size: Minimum pool connections
        max_size: Maximum pool connections

    Returns:
        asyncpg connection pool
    """
    global _pool

    if not asyncpg:
        raise RuntimeError("asyncpg is required. Install with: pip install asyncpg")

    logger.info("Initializing database connection pool...")
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=min_size,
        max_size=max_size,
    )

    # Run migrations
    await run_migrations(_pool)

    logger.info("Database initialized successfully")
    return _pool


async def get_pool() -> "asyncpg.Pool":
    """Get the database connection pool."""
    if _pool is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _pool


async def close_database():
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


async def run_migrations(pool: "asyncpg.Pool"):
    """
    Run pending SQL migrations in order.

    Migrations are SQL files in control_plane/migrations/ named NNN_description.sql.
    Applied migrations are tracked in the schema_migrations table.
    """
    async with pool.acquire() as conn:
        # Ensure schema_migrations table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(10) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Get already-applied migrations
        applied = set()
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        for row in rows:
            applied.add(row["version"])

        # Find and apply pending migrations
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for migration_file in migration_files:
            version = migration_file.stem.split("_")[0]  # e.g., "000" from "000_initial_schema.sql"

            if version in applied:
                logger.debug(f"Migration {version} already applied, skipping")
                continue

            logger.info(f"Applying migration {version}: {migration_file.name}")
            sql = migration_file.read_text(encoding="utf-8")

            try:
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1)",
                        version,
                    )
                logger.info(f"Migration {version} applied successfully")
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}")
                raise


# =============================================================================
# Provisioning Job Queries
# =============================================================================

async def save_job(pool: "asyncpg.Pool", job_data: Dict[str, Any]) -> None:
    """Insert or update a provisioning job."""
    await pool.execute(
        """
        INSERT INTO provisioning_jobs (
            job_id, customer_id, customer_email, bundle, storage_tier,
            provider_id, region, datacenter_id, custom_domain,
            state, instance_id, instance_ip, wopr_subdomain,
            root_password, dns_record_ids, error_message, retry_count,
            stripe_customer_id, stripe_subscription_id, beacon_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
        ON CONFLICT (job_id) DO UPDATE SET
            state = EXCLUDED.state,
            instance_id = EXCLUDED.instance_id,
            instance_ip = EXCLUDED.instance_ip,
            wopr_subdomain = EXCLUDED.wopr_subdomain,
            root_password = EXCLUDED.root_password,
            dns_record_ids = EXCLUDED.dns_record_ids,
            error_message = EXCLUDED.error_message,
            retry_count = EXCLUDED.retry_count,
            beacon_id = EXCLUDED.beacon_id,
            updated_at = NOW()
        """,
        job_data.get("job_id"),
        job_data.get("customer_id"),
        job_data.get("customer_email"),
        job_data.get("bundle"),
        job_data.get("storage_tier", 1),
        job_data.get("provider_id"),
        job_data.get("region"),
        job_data.get("datacenter_id"),
        job_data.get("custom_domain"),
        job_data.get("state", "pending"),
        job_data.get("instance_id"),
        job_data.get("instance_ip"),
        job_data.get("wopr_subdomain"),
        job_data.get("root_password"),
        job_data.get("dns_record_ids", "{}"),
        job_data.get("error_message"),
        job_data.get("retry_count", 0),
        job_data.get("stripe_customer_id"),
        job_data.get("stripe_subscription_id"),
        job_data.get("beacon_id"),
    )


async def get_job(pool: "asyncpg.Pool", job_id: str) -> Optional[Dict[str, Any]]:
    """Get a provisioning job by ID."""
    row = await pool.fetchrow(
        "SELECT * FROM provisioning_jobs WHERE job_id = $1",
        job_id,
    )
    return dict(row) if row else None


async def get_jobs_by_customer(pool: "asyncpg.Pool", customer_id: str) -> List[Dict[str, Any]]:
    """Get all provisioning jobs for a customer."""
    rows = await pool.fetch(
        "SELECT * FROM provisioning_jobs WHERE customer_id = $1 ORDER BY created_at DESC",
        customer_id,
    )
    return [dict(row) for row in rows]


async def get_jobs_by_state(pool: "asyncpg.Pool", state: str) -> List[Dict[str, Any]]:
    """Get all jobs in a specific state."""
    rows = await pool.fetch(
        "SELECT * FROM provisioning_jobs WHERE state = $1 ORDER BY created_at",
        state,
    )
    return [dict(row) for row in rows]


async def update_job_state(
    pool: "asyncpg.Pool",
    job_id: str,
    state: str,
    error_message: Optional[str] = None,
    **kwargs,
) -> None:
    """Update a job's state and optional fields."""
    sets = ["state = $2", "updated_at = NOW()"]
    params: list = [job_id, state]
    idx = 3

    if error_message is not None:
        sets.append(f"error_message = ${idx}")
        params.append(error_message)
        idx += 1

    for key, value in kwargs.items():
        if value is not None:
            sets.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

    sql = f"UPDATE provisioning_jobs SET {', '.join(sets)} WHERE job_id = $1"
    await pool.execute(sql, *params)


# =============================================================================
# Beacon Queries
# =============================================================================

async def create_beacon(pool: "asyncpg.Pool", beacon_data: Dict[str, Any]) -> str:
    """Create a new beacon and return its ID."""
    row = await pool.fetchrow(
        """
        INSERT INTO beacons (
            owner_id, name, domain, custom_domain, status, provider,
            region, datacenter_id, instance_id, instance_ip,
            bundle, storage_tier, modules, stripe_subscription_id
        ) VALUES ($1, $2, $3, $4, $5, $6::beacon_provider, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id
        """,
        beacon_data["owner_id"],
        beacon_data["name"],
        beacon_data["domain"],
        beacon_data.get("custom_domain"),
        beacon_data.get("status", "provisioning"),
        beacon_data["provider"],
        beacon_data.get("region"),
        beacon_data.get("datacenter_id"),
        beacon_data.get("instance_id"),
        beacon_data.get("instance_ip"),
        beacon_data["bundle"],
        beacon_data.get("storage_tier", 1),
        beacon_data.get("modules", "[]"),
        beacon_data.get("stripe_subscription_id"),
    )
    return str(row["id"])


async def get_beacon(pool: "asyncpg.Pool", beacon_id: str) -> Optional[Dict[str, Any]]:
    """Get a beacon by ID."""
    row = await pool.fetchrow("SELECT * FROM beacons WHERE id = $1", beacon_id)
    return dict(row) if row else None


async def get_beacon_by_subscription(pool: "asyncpg.Pool", stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
    """Get a beacon by Stripe subscription ID."""
    row = await pool.fetchrow(
        "SELECT * FROM beacons WHERE stripe_subscription_id = $1",
        stripe_subscription_id,
    )
    return dict(row) if row else None


async def update_beacon_status(pool: "asyncpg.Pool", beacon_id: str, status: str, **kwargs) -> None:
    """Update beacon status and optional fields."""
    sets = ["status = $2::beacon_status", "updated_at = NOW()"]
    params: list = [beacon_id, status]
    idx = 3

    for key, value in kwargs.items():
        if value is not None:
            sets.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

    sql = f"UPDATE beacons SET {', '.join(sets)} WHERE id = $1"
    await pool.execute(sql, *params)


# =============================================================================
# User Queries
# =============================================================================

async def get_or_create_user(
    pool: "asyncpg.Pool",
    email: str,
    stripe_customer_id: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get existing user by email or create a new one."""
    row = await pool.fetchrow("SELECT * FROM users WHERE email = $1", email)
    if row:
        # Update stripe_customer_id if newly available
        if stripe_customer_id and not row["stripe_customer_id"]:
            await pool.execute(
                "UPDATE users SET stripe_customer_id = $1 WHERE id = $2",
                stripe_customer_id, row["id"],
            )
        return dict(row)

    row = await pool.fetchrow(
        """
        INSERT INTO users (email, stripe_customer_id, name)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        email, stripe_customer_id, name,
    )
    return dict(row)


# =============================================================================
# Payment Failure Queries (Dunning)
# =============================================================================

async def record_payment_failure(
    pool: "asyncpg.Pool",
    subscription_id: str,
    invoice_id: str,
    amount_cents: int,
    failure_reason: Optional[str] = None,
) -> int:
    """Record a payment failure and return total unresolved failure count."""
    await pool.execute(
        """
        INSERT INTO payment_failures (subscription_id, stripe_invoice_id, amount_cents, failure_reason)
        VALUES ($1, $2, $3, $4)
        """,
        subscription_id, invoice_id, amount_cents, failure_reason,
    )

    count = await pool.fetchval(
        "SELECT COUNT(*) FROM payment_failures WHERE subscription_id = $1 AND resolved = false",
        subscription_id,
    )
    return count


async def resolve_payment_failures(pool: "asyncpg.Pool", subscription_id: str) -> None:
    """Mark all payment failures for a subscription as resolved."""
    await pool.execute(
        "UPDATE payment_failures SET resolved = true, resolved_at = NOW() WHERE subscription_id = $1 AND resolved = false",
        subscription_id,
    )


# =============================================================================
# Health Check
# =============================================================================

async def check_health(pool: "asyncpg.Pool") -> Dict[str, Any]:
    """Check database connectivity and return stats."""
    try:
        result = await pool.fetchval("SELECT 1")
        job_count = await pool.fetchval("SELECT COUNT(*) FROM provisioning_jobs")
        beacon_count = await pool.fetchval("SELECT COUNT(*) FROM beacons")
        active_beacons = await pool.fetchval("SELECT COUNT(*) FROM beacons WHERE status = 'active'")

        return {
            "status": "healthy",
            "connected": True,
            "jobs_total": job_count,
            "beacons_total": beacon_count,
            "beacons_active": active_beacons,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }
