"""
alerts.py — Empire OS Notification Hub
──────────────────────────────────────
Pushes critical operational events to Telegram.
"""

import os
import aiohttp
import asyncio
from empire_logging import get_logger

logger = get_logger("empire.telemetry")

class TelegramClient:
    def __init__(self):
        # This looks for the token in your Environment Variables
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    async def send(self, text: str):
        if not self.token or not self.chat_id:
            logger.warning("telegram_config_missing", action="alert_skipped")
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                }) as resp:
                    if resp.status == 200:
                        logger.info("alert_dispatched")
                    else:
                        logger.error("telegram_api_error", status=resp.status)
        except Exception as e:
            logger.error("alert_dispatch_failed", error=str(e))

async def dispatch_alert(title: str, body: str, status: str = "info"):
    icon = {"info": "ℹ️", "warning": "⚠️", "red": "🚨"}.get(status, "ℹ️")
    message = f"{icon} *{title}*\n\n{body}"
    
    client = TelegramClient()
    await client.send(message)

if __name__ == "__main__":
    # Test your connection
    asyncio.run(dispatch_alert("Test Alert", "Empire OS Telemetry is online.", "info"))