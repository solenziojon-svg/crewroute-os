import sqlite3
import logging
import os

# ── Configuration ──
DB_PATH = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("empire.hub")

# ── Single Source of Truth Schema ──
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, date TEXT, client TEXT, status TEXT DEFAULT 'scheduled');
CREATE TABLE IF NOT EXISTS performance_metrics (id TEXT PRIMARY KEY, date TEXT, crew TEXT, planned_duration_mins INTEGER, actual_duration_mins INTEGER);
CREATE TABLE IF NOT EXISTS empire_nexus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL, 
    source_id TEXT NOT NULL, 
    target_type TEXT NOT NULL, 
    target_id TEXT NOT NULL, 
    insight_score INTEGER DEFAULT 0, 
    reviewed INTEGER DEFAULT 0, 
    created_at TEXT DEFAULT (datetime('now'))
);
"""

class EmpireHub:
    """
    The Single Data Hub for CrewRoute OS. 
    Usage: with EmpireHub() as hub: hub.write_nexus_link(...)
    """
    def __init__(self, db_file=DB_PATH):
        self.db_file = db_file
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA) # Auto-init schema
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def write_nexus_link(self, source_type, source_id, target_type, target_id, score=5):
        """Standardized link method for the Nexus flywheel."""
        self.conn.execute(
            "INSERT INTO empire_nexus (source_type, source_id, target_type, target_id, insight_score) VALUES (?, ?, ?, ?, ?)",
            (source_type, source_id, target_type, target_id, score)
        )
        logger.info(f"Nexus link recorded: {source_type} -> {target_type}")

# ── Verification Block ──
if __name__ == "__main__":
    with EmpireHub() as hub:
        print("✅ Empire OS Hub initialized successfully.")
        hub.write_nexus_link("Test", "001", "Test", "Module-01", 10)
        print("✅ Nexus link test passed.")