```python
"""
cjs_operating_hub.py (v1.4 - PRODUCTION GATED)
─────────────────────────────────────────────────────
Central database manager for CJS Landscape Solutions operational data.
Ensures schema updates to schema/sqlite_schema.sql apply automatically.
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("crewroute.hub")

class EmpireHub:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")
        self.db_url = os.getenv("DATABASE_URL", "")
        self._init_sqlite_db()

    def _init_sqlite_db(self):
        """Initializes database schema from file or inline fallback."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            
            # Locate schema path relative to project root
            schema_path = Path(__file__).parent / "schema" / "sqlite_schema.sql"
            
            if schema_path.exists():
                schema_sql = schema_path.read_text(encoding="utf-8")
                conn.executescript(schema_sql)
                logger.info("hub.schema_initialized", source="sqlite_schema.sql")
            else:
                # Safe inline fallback if directory path is missing
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS dead_letter_queue (
                        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
                        agent_name TEXT,
                        task_id TEXT,
                        input_json TEXT,
                        error TEXT,
                        retry_count INTEGER DEFAULT 0,
                        resolved INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now'))
                    );
                    CREATE TABLE IF NOT EXISTS governance_verdicts (
                        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
                        run_date TEXT,
                        run_crew TEXT,
                        status TEXT,
                        flags_json TEXT,
                        audited_at TEXT DEFAULT (datetime('now'))
                    );
                """)
                logger.info("hub.schema_initialized", source="inline_fallback")
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("hub.sqlite_init_failed", error=str(e))

    def log_dlq(self, agent: str, task_id: str, payload_dict: dict, error_msg: str):
        """Writes structural processing failures directly to the local audit ledger."""
        try:
            import json
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dead_letter_queue (agent_name, task_id, input_json, error)
                VALUES (?, ?, ?, ?)
            """, (agent, task_id, json.dumps(payload_dict), error_msg))
            conn.commit()
            conn.close()
            logger.info("hub.dlq_logged", task_id=task_id)
        except Exception as e:
            logger.error("hub.dlq_log_failed", error=str(e))

```
