import json
import logging
import psycopg2
import sys
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

def sync_schema_from_db():
    """
    Connects to the PostgreSQL database and auto-generates a basic schema.json
    based on the information_schema to prevent the static file from going stale.
    This script is intended to be run during migrations or startup.
    """
    logger.info("Syncing schema.json from live database...")
    
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        cur = conn.cursor()

        # Get all relevant user tables (excluding Prisma migrations)
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            AND table_name NOT LIKE '_prisma%'
        """)
        tables = [r[0] for r in cur.fetchall()]

        schema_out = {
            "PID_LEAD_PAGE": {},
            "PID_TASK_PAGE": {}
        }
        
        for table in tables:
            cur.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = %s
            """, (table,))
            columns = cur.fetchall()
            
            table_schema = {"columns": {}}
            for col in columns:
                col_name, data_type, is_nullable = col
                
                # Simple type mapping
                schema_type = "String"
                if "int" in data_type.lower():
                    schema_type = "Int"
                elif "timestamp" in data_type.lower() or "date" in data_type.lower():
                    schema_type = "DateTime"
                elif "bool" in data_type.lower():
                    schema_type = "Boolean"
                elif "USER-DEFINED" in data_type.upper():
                    schema_type = "Enum"
                
                table_schema["columns"][col_name] = {
                    "type": schema_type,
                    "nullable": is_nullable == "YES"
                }

            # Basic heuristic routing (can be improved)
            if table in ["Task"]:
                schema_out["PID_TASK_PAGE"][table] = table_schema
            else:
                schema_out["PID_LEAD_PAGE"][table] = table_schema
                
        # Write to schema.json
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        schema_path = os.path.join(data_dir, "schema.json")
        
        with open(schema_path, "w") as f:
            json.dump(schema_out, f, indent=2)
            
        logger.info(f"Successfully generated schema.json at {schema_path}")
        
    except Exception as e:
        logger.error(f"Failed to sync schema: {e}")
        print(f"Failed to sync schema: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sync_schema_from_db()
