"""
app/scripts/run_migration.py
============================
Runs the SQL migration file using psycopg2 (no psql needed).

Usage:
    venv\\Scripts\\python -m app.scripts.run_migration
"""
import logging
import os
from pathlib import Path
import psycopg2
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

import sys

def run(migration_name: str = None):
    # Default to 003 if not specified, or use the provided one
    filename = migration_name or "003_create_step_traces.sql"
    migration_file = Path(__file__).parent.parent / "db" / "migrations" / filename
    
    if not migration_file.exists():
        logger.error(f"❌ Migration file not found: {migration_file}")
        return

    logger.info(f"Connecting to DB: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    sql = migration_file.read_text(encoding="utf-8")
    logger.info(f"Running migration: {migration_file.name}")

    try:
        cur.execute(sql)
        logger.info(f"✅ Migration {filename} completed successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else None
    run(name)
