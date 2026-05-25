"""
empire_status.py — The Empire Health Check
──────────────────────────────────────────
Provides a high-level heartbeat of the system.
Usage: python empire_status.py
"""

from empire_logging import get_logger
from cjs_operating_hub import EmpireHub
import os

logger = get_logger("empire.status")

def check_heartbeat():
    logger.info("heartbeat_check_started")
    db_path = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")
    
    if not os.path.exists(db_path):
        logger.error("heartbeat_failed", reason="database_not_found")
        return

    try:
        with EmpireHub(db_path) as hub:
            # Quick operational metrics
            logger.info("heartbeat_success", 
                        status="operational", 
                        database=db_path)
    except Exception as e:
        logger.error("heartbeat_failed", error=str(e))

if __name__ == "__main__":
    print("\n--- EMPIRE STATUS REPORT ---")
    check_heartbeat()
    print("--- END OF REPORT ---\n")