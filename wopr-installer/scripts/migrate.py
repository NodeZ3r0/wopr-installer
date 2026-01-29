#!/usr/bin/env python3
"""
WOPR Database Migration Runner
================================

Runs SQL migration files in order, tracking which have been applied.

Usage:
    python scripts/migrate.py                    # Run all pending
    python scripts/migrate.py --status           # Show migration status
    python scripts/migrate.py --dry-run          # Show what would run
"""

import asyncio
import os
import sys
import glob
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def get_applied_migrations(pool) -> set:
    """Get set of already-applied migration versions."""
    try:
        rows = await pool.fetch("SELECT version FROM schema_migrations")
        return {row["version"] for row in rows}
    except Exception:
        # Table might not exist yet
        return set()


async def get_pending_migrations(pool, migrations_dir: str) -> list:
    """Get list of pending migration files."""
    applied = await get_applied_migrations(pool)

    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    pending = []

    for filepath in sql_files:
        filename = os.path.basename(filepath)
        version = filename.split("_")[0]  # e.g., "000" from "000_initial_schema.sql"

        if version not in applied:
            pending.append((version, filename, filepath))

    return pending


async def run_migrations(db_url: str, migrations_dir: str, dry_run: bool = False):
    """Run all pending migrations."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

    try:
        # Ensure schema_migrations table exists
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                filename VARCHAR(255)
            )
        """)

        pending = await get_pending_migrations(pool, migrations_dir)

        if not pending:
            print("No pending migrations.")
            return

        print(f"Found {len(pending)} pending migration(s):")
        for version, filename, _ in pending:
            print(f"  [{version}] {filename}")

        if dry_run:
            print("\n(dry run — no changes applied)")
            return

        for version, filename, filepath in pending:
            print(f"\nApplying [{version}] {filename}...")
            with open(filepath, "r") as f:
                sql = f.read()

            await pool.execute(sql)
            await pool.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                version, filename,
            )
            print(f"  ✓ Applied {filename}")

        print(f"\nAll {len(pending)} migration(s) applied successfully.")

    finally:
        await pool.close()


async def show_status(db_url: str, migrations_dir: str):
    """Show migration status."""
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

    try:
        applied = await get_applied_migrations(pool)
        pending = await get_pending_migrations(pool, migrations_dir)

        print("=== Migration Status ===")
        print(f"Applied: {len(applied)}")
        print(f"Pending: {len(pending)}")

        if applied:
            print("\nApplied migrations:")
            rows = await pool.fetch(
                "SELECT version, filename, applied_at FROM schema_migrations ORDER BY version"
            )
            for row in rows:
                print(f"  [{row['version']}] {row['filename']} — {row['applied_at']}")

        if pending:
            print("\nPending migrations:")
            for version, filename, _ in pending:
                print(f"  [{version}] {filename}")

    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description="WOPR Database Migration Runner")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without applying")
    parser.add_argument("--db-url", default=None, help="Database URL (default: DATABASE_URL env)")
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get(
        "DATABASE_URL", "postgresql://wopr:changeme@localhost:5432/wopr"
    )

    migrations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "control_plane", "migrations"
    )

    if not os.path.isdir(migrations_dir):
        print(f"Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    if args.status:
        asyncio.run(show_status(db_url, migrations_dir))
    else:
        asyncio.run(run_migrations(db_url, migrations_dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
