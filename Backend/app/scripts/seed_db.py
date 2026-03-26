"""
app/scripts/seed_db.py
=======================
One-time database seeder — creates tables and inserts realistic fake data for development/testing.

Usage:
    venv\\Scripts\\python -m app.scripts.seed_db

CAUTION: This script DROPS and RECREATES all tables. Never run in production.
"""
import logging
import random
import sys
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import sql

try:
    from faker import Faker
    import cuid
except ImportError:
    print("Missing dependencies. Install with: pip install faker cuid")
    sys.exit(1)

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

fake = Faker()


def get_connection():
    """Open a direct psycopg2 connection using settings for seeding."""
    return psycopg2.connect(
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )


def create_enum(cur, name: str, values: list):
    """Create a PostgreSQL ENUM type if it doesn't already exist."""
    cur.execute(f"SELECT 1 FROM pg_type WHERE typname = '{name}'")
    if not cur.fetchone():
        val_str = ", ".join([f"'{v}'" for v in values])
        cur.execute(f"CREATE TYPE {name} AS ENUM ({val_str})")
        logger.info(f"Enum '{name}' created.")


def seed():
    logger.info("Connecting to database...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # Fix search path
    cur.execute("CREATE SCHEMA IF NOT EXISTS public;")
    cur.execute("SET search_path TO public, pg_catalog;")
    logger.info("Schema path set.")

    # ── ENUMs ─────────────────────────────────────────────────────────────────
    create_enum(cur, "source_category", ["ONLINE", "OFFLINE", "REFERRAL"])
    create_enum(cur, "user_role",       ["ADMIN", "SALES", "MANAGER"])
    create_enum(cur, "task_priority",   ["LOW", "MEDIUM", "HIGH"])
    create_enum(cur, "task_status",     ["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"])

    # ── Tables ────────────────────────────────────────────────────────────────
    tables = {
        "Organization": """
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            "isActive" BOOLEAN DEFAULT TRUE,
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "Store": """
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            "organizationId" TEXT REFERENCES "Organization"(id),
            "isActive" BOOLEAN DEFAULT TRUE,
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "User": """
            id TEXT PRIMARY KEY,
            "firstName" TEXT NOT NULL,
            "lastName" TEXT,
            email TEXT UNIQUE NOT NULL,
            role user_role NOT NULL,
            "organizationId" TEXT REFERENCES "Organization"(id),
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "Customer": """
            id TEXT PRIMARY KEY,
            "firstName" TEXT NOT NULL,
            "lastName" TEXT,
            email TEXT,
            phone TEXT,
            "organizationId" TEXT REFERENCES "Organization"(id),
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "Stage": """
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            "order" INT NOT NULL,
            "organizationId" TEXT REFERENCES "Organization"(id),
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "Link": """
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            source TEXT,
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
        "Lead": """
            id TEXT PRIMARY KEY,
            "publicId" TEXT UNIQUE NOT NULL,
            source TEXT,
            "sourceCategory" source_category,
            score INT,
            "scoreLastUpdated" TIMESTAMP,
            "customerId" TEXT REFERENCES "Customer"(id),
            "isDuplicate" BOOLEAN DEFAULT FALSE,
            "organizationId" TEXT REFERENCES "Organization"(id),
            "proposalAt" TIMESTAMP,
            "isDeleted" BOOLEAN DEFAULT FALSE,
            "deletedAt" TIMESTAMP,
            "stageId" TEXT REFERENCES "Stage"(id),
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP,
            "createdById" TEXT REFERENCES "User"(id),
            "updatedById" TEXT REFERENCES "User"(id),
            "storeId" TEXT REFERENCES "Store"(id),
            "linkId" TEXT REFERENCES "Link"(id),
            "assignedToId" TEXT REFERENCES "User"(id),
            "assignedToAI" BOOLEAN DEFAULT FALSE,
            "isRepeat" BOOLEAN DEFAULT FALSE
        """,
        "Task": """
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            priority task_priority NOT NULL,
            status task_status NOT NULL,
            "dueDate" TIMESTAMP,
            "relatedLeadId" TEXT REFERENCES "Lead"(id),
            "assignedToId" TEXT REFERENCES "User"(id),
            "organizationId" TEXT REFERENCES "Organization"(id),
            "storeId" TEXT REFERENCES "Store"(id),
            "createdById" TEXT REFERENCES "User"(id),
            "updatedById" TEXT REFERENCES "User"(id),
            "createdAt" TIMESTAMP DEFAULT NOW(),
            "updatedAt" TIMESTAMP
        """,
    }

    # Drop in reverse order to respect FK constraints
    logger.warning("Dropping existing tables...")
    for table_name in reversed(list(tables.keys())):
        cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')

    for table_name, schema in tables.items():
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({schema});')
        logger.info(f"Table '{table_name}' created.")

    # ── Seed Data ─────────────────────────────────────────────────────────────
    org_id = cuid.cuid()
    cur.execute('INSERT INTO "Organization"(id, name) VALUES(%s, %s) ON CONFLICT DO NOTHING',
                (org_id, "Demo Organization"))
    logger.info("Organization seeded.")

    store_ids = []
    for _ in range(3):
        sid = cuid.cuid()
        store_ids.append(sid)
        cur.execute('INSERT INTO "Store"(id, name, "organizationId") VALUES(%s, %s, %s)',
                    (sid, fake.company(), org_id))

    user_ids = []
    for _ in range(10):
        uid = cuid.cuid()
        user_ids.append(uid)
        cur.execute('INSERT INTO "User"(id, "firstName", "lastName", email, role, "organizationId") VALUES(%s,%s,%s,%s,%s,%s)',
                    (uid, fake.first_name(), fake.last_name(), fake.unique.email(),
                     random.choice(["ADMIN", "SALES", "MANAGER"]), org_id))
    logger.info(f"Seeded {len(user_ids)} users.")

    stage_ids = []
    for i, name in enumerate(["New", "Contacted", "Qualified", "Closed"]):
        sid = cuid.cuid()
        stage_ids.append(sid)
        cur.execute('INSERT INTO "Stage"(id, name, "order", "organizationId") VALUES(%s,%s,%s,%s)',
                    (sid, name, i + 1, org_id))

    link_ids = []
    for _ in range(5):
        lid = cuid.cuid()
        link_ids.append(lid)
        cur.execute('INSERT INTO "Link"(id, url, source) VALUES(%s,%s,%s)',
                    (lid, fake.url(), random.choice(["Google", "Facebook", "Website"])))

    customer_ids = []
    for _ in range(100):
        cid = cuid.cuid()
        customer_ids.append(cid)
        cur.execute('INSERT INTO "Customer"(id,"firstName","lastName",email,phone,"organizationId") VALUES(%s,%s,%s,%s,%s,%s)',
                    (cid, fake.first_name(), fake.last_name(), fake.email(), fake.phone_number(), org_id))
    logger.info(f"Seeded {len(customer_ids)} customers.")

    leads_seeded = 0
    for _ in range(200):
        lid = cuid.cuid()
        try:
            cur.execute("""
                INSERT INTO "Lead"(
                    id, "publicId", source, "sourceCategory", score,
                    "scoreLastUpdated", "customerId", "organizationId",
                    "proposalAt", "stageId", "createdById", "storeId",
                    "linkId", "assignedToId"
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                lid,
                "PUB-" + str(random.randint(1000000, 99999999)),
                random.choice(["Google", "Meta Ads", "Walk-in", "Referral"]),
                random.choice(["ONLINE", "OFFLINE", "REFERRAL"]),
                random.randint(0, 100),
                datetime.now(),
                random.choice(customer_ids),
                org_id,
                datetime.now() + timedelta(days=random.randint(1, 30)),
                random.choice(stage_ids),
                random.choice(user_ids),
                random.choice(store_ids),
                random.choice(link_ids),
                random.choice(user_ids),
            ))
            leads_seeded += 1
        except Exception:
            continue

    logger.info(f"Seeded {leads_seeded} leads.")

    cur.close()
    conn.close()
    logger.info("✅ Database seeding completed successfully!")


if __name__ == "__main__":
    seed()
