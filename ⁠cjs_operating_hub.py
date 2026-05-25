import sqlite3
import os
from empire_logging import get_logger

logger = get_logger("empire.hub")
DB_PATH = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, date TEXT, client TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS empire_nexus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL, source_id TEXT NOT NULL, 
    target_type TEXT NOT NULL, target_id TEXT NOT NULL, 
    insight_score INTEGER DEFAULT 0
);
"""

class EmpireHub:
    def __init__(self, db_file=DB_PATH):
        self.db_file = db_file
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def write_nexus_link(self, source_type, source_id, target_type, target_id, score=5):
        self.conn.execute(
            "INSERT INTO empire_nexus (source_type, source_id, target_type, target_id, insight_score) VALUES (?, ?, ?, ?, ?)",
            (source_type, source_id, target_type, target_id, score)
        )
        logger.info("nexus_link_recorded", source=source_type, target=target_type)